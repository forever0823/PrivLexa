"""
PIPL Translation Enricher
Batch-translates PIPL text_en and statement_en fields marked as "pending"
using the Anthropic API.

Usage:
    python translate_pipl.py                         # translates PIPL_normalized.json
    python translate_pipl.py --input path/to/file    # custom input
    python translate_pipl.py --dry-run               # preview only, no API calls
    python translate_pipl.py --batch-size 5          # items per API call (default 5)
"""

import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE  = PROJECT_ROOT / "output" / "normalized" / "PIPL_normalized.json"
OUTPUT_FILE = PROJECT_ROOT / "output" / "normalized" / "PIPL_normalized_translated.json"
MODEL       = "claude-sonnet-4-20250514"
MAX_TOKENS  = 4096
BATCH_SIZE  = 5   # clauses or obligations per API call
RETRY_WAIT  = 2   # seconds between retries

SYSTEM_PROMPT = """You are a professional legal translator specializing in Chinese data protection law.
Translate the provided Chinese legal text into formal English suitable for legal documentation.
Requirements:
- Use standard legal English terminology
- Map Chinese legal terms to their recognized English equivalents:
  * 个人信息处理者 → personal information processor / controller
  * 个人 → individual / data subject
  * 国家网信部门 → the national cyberspace administration authority
  * 受托人 → entrusted party / processor
- Preserve the structure and numbering (e.g. (一)(二)(三) → (1)(2)(3))
- Output ONLY the JSON requested, no preamble or explanation
- Keep translations concise and precise"""


def call_api(messages: list[dict]) -> str:
    """Call Anthropic API via urllib (no SDK dependency)."""
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]


def translate_batch(items: list[dict], field: str, dry_run: bool) -> list[dict]:
    """
    Translate a batch of items.
    Each item: {"id": ..., "text_zh": ...}
    Returns list of {"id": ..., "text_en": ...}
    """
    if dry_run:
        return [{"id": item["id"], "text_en": f"[DRY RUN] {item['text_zh'][:60]}..."}
                for item in items]

    prompt = f"""Translate each Chinese legal text to English.
Return ONLY a JSON array with this exact structure:
[
  {{"id": "<id>", "text_en": "<english translation>"}},
  ...
]

Items to translate:
{json.dumps(items, ensure_ascii=False, indent=2)}"""

    for attempt in range(3):
        try:
            raw = call_api([{"role": "user", "content": prompt}])
            # Strip markdown fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            return json.loads(raw.strip())
        except Exception as e:
            print(f"    Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(RETRY_WAIT * (attempt + 1))
    print("    ⚠ All retries failed — skipping batch")
    return []


def enrich_clauses(clauses: list[dict], batch_size: int, dry_run: bool) -> list[dict]:
    """Translate clause text fields."""
    pending = [c for c in clauses if c.get("text_en_source") == "pending" and c.get("text")]
    print(f"\n  Clauses pending translation: {len(pending)}")

    translated_map = {}
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i+batch_size]
        items = [{"id": c["clause_id"], "text_zh": c["text"]} for c in batch]
        print(f"    Translating clauses {i+1}–{min(i+batch_size, len(pending))} / {len(pending)} ...")
        results = translate_batch(items, "text", dry_run)
        for r in results:
            translated_map[r["id"]] = r["text_en"]
        if not dry_run:
            time.sleep(0.5)

    enriched = []
    for c in clauses:
        c = dict(c)
        if c["clause_id"] in translated_map:
            c["text_en"] = translated_map[c["clause_id"]]
            c["text_en_source"] = "llm_generated"
        enriched.append(c)

    return enriched


def enrich_obligations(obligations: list[dict], batch_size: int, dry_run: bool) -> list[dict]:
    """Translate obligation statement fields."""
    pending = [o for o in obligations
               if o.get("statement_en_source") == "pending" and o.get("statement")]
    print(f"\n  Obligations pending translation: {len(pending)}")

    translated_map = {}
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i+batch_size]
        items = [{"id": o["obligation_id"], "text_zh": o["statement"]} for o in batch]
        print(f"    Translating obligations {i+1}–{min(i+batch_size, len(pending))} / {len(pending)} ...")
        results = translate_batch(items, "statement", dry_run)
        for r in results:
            translated_map[r["id"]] = r["text_en"]
        if not dry_run:
            time.sleep(0.5)

    enriched = []
    for o in obligations:
        o = dict(o)
        if o["obligation_id"] in translated_map:
            o["statement_en"] = translated_map[o["obligation_id"]]
            o["statement_en_source"] = "llm_generated"
        enriched.append(o)

    return enriched


def enrich_titles(clauses: list[dict], dry_run: bool) -> list[dict]:
    """Translate clause title i18n objects where en is None."""
    pending = [c for c in clauses
               if isinstance(c.get("title"), dict) and not c["title"].get("en")]
    print(f"\n  Clause titles pending translation: {len(pending)}")

    # Titles are short — translate all in one shot
    if not pending:
        return clauses

    items = [{"id": c["clause_id"], "text_zh": c["title"].get("zh", "")} for c in pending]
    print(f"    Translating {len(items)} clause titles ...")
    results = translate_batch(items, "title", dry_run)
    title_map = {r["id"]: r["text_en"] for r in results}

    enriched = []
    for c in clauses:
        c = dict(c)
        if c["clause_id"] in title_map and isinstance(c.get("title"), dict):
            c["title"] = dict(c["title"])
            c["title"]["en"] = title_map[c["clause_id"]]
        enriched.append(c)
    return enriched


def main():
    parser = argparse.ArgumentParser(description="Translate PIPL pending fields to English")
    parser.add_argument("--input",      default=str(INPUT_FILE), help="Input JSON path")
    parser.add_argument("--output",     default=str(OUTPUT_FILE), help="Output JSON path")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Items per API call")
    parser.add_argument("--dry-run",    action="store_true", help="Preview without API calls")
    parser.add_argument("--titles-only", action="store_true", help="Only translate titles")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"❌ Input file not found: {in_path}")
        return

    print(f"Loading {in_path.name} ...")
    with open(in_path, encoding="utf-8") as f:
        data = json.load(f)

    if args.dry_run:
        print("  [DRY RUN mode — no API calls will be made]\n")

    clauses     = data.get("clauses", [])
    obligations = data.get("obligations", [])

    clauses = enrich_titles(clauses, args.dry_run)

    if not args.titles_only:
        clauses     = enrich_clauses(clauses, args.batch_size, args.dry_run)
        obligations = enrich_obligations(obligations, args.batch_size, args.dry_run)

    data["clauses"]     = clauses
    data["obligations"] = obligations

    # Update meta if present
    if "meta" in data:
        data["meta"]["pending_translations"] = (
            "none" if not args.dry_run
            else "dry-run — no translations applied"
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    still_pending = sum(1 for c in clauses if c.get("text_en_source") == "pending")
    still_pending += sum(1 for o in obligations if o.get("statement_en_source") == "pending")

    print(f"\n  ✓ Wrote {out_path.name}")
    print(f"  Remaining pending translations: {still_pending}")
    if still_pending and not args.dry_run:
        print("  (Re-run to retry failed batches)")


if __name__ == "__main__":
    main()
