# Multi-Jurisdiction Knowledge Graph — Normalization Toolkit

## Files

| File | Purpose |
|------|---------|
| `normalize_kg.py` | Normalize PIPL / GDPR / CCPA to unified schema |
| `translate_pipl.py` | Batch-translate PIPL pending fields via Anthropic API |

---

## Step 1: Normalize

```bash
# Place your three source files in the same directory, then:
python normalize_kg.py

# Or specify input directory:
python normalize_kg.py ./data
```

**Input files expected:**
- `PIPL_CN.json`
- `GDPR_EN_TXT.semantic_network.json`
- `CCPA_EN_TXT.semantic_network.json`

**Output files:**
- `PIPL_normalized.json`
- `GDPR_normalized.json`
- `CCPA_normalized.json`
- `unified_knowledge_graph.json`

---

## Step 2: Translate PIPL pending fields

```bash
# Dry run first — preview without API calls
python translate_pipl.py --dry-run

# Translate titles only (fast, low cost)
python translate_pipl.py --titles-only

# Full translation (text + statements + titles)
python translate_pipl.py

# Custom batch size (default 5)
python translate_pipl.py --batch-size 10
```

**Output:** `PIPL_normalized_translated.json`

---

## Unified Schema

### Bilingual field patterns

**Short labels** — i18n object:
```json
"title": { "zh": "个人信息处理的合法性条件", "en": "Conditions for Lawful Processing" }
```

**Long text** — parallel fields:
```json
"text":             "符合下列情形之一...",
"text_en":          "Personal information processors may...",
"text_en_source":   "llm_generated"   // pending | llm_generated | official_translation | human_reviewed
```

**Enums** — English key, translated via vocabulary table:
```json
"category": "lawful_basis"   // look up in vocabulary.categories.lawful_basis
```

### translation_source values

| Value | Meaning |
|-------|---------|
| `original` | EN source file — text IS the English |
| `pending` | PIPL — awaiting translation |
| `llm_generated` | Translated by LLM, not legally reviewed |
| `official_translation` | Authoritative official translation |
| `human_reviewed` | LLM translation reviewed by a lawyer |

### jurisdiction_specific (unified across all three laws)
```json
"jurisdiction_specific": {
  "is_specific": true,
  "features": ["consent_withdrawal"],
  "feature_notes": ["PIPL-specific note"]
}
```

### cross_jurisdiction_links (scaffold — requires legal review)
```json
{
  "link_id": "CJL_001",
  "concept": "lawful_basis_for_processing",
  "concept_label": { "zh": "合法性基础", "en": "Lawful Basis for Processing" },
  "relation_type": "equivalent",   // equivalent | similar | stricter_than | no_counterpart
  "nodes": [
    { "law_id": "PIPL", "clause_id": "...", "article_reference": "Article 13" },
    { "law_id": "GDPR", "clause_id": "...", "article_reference": "Article 6" },
    { "law_id": "CCPA", "clause_id": null,  "article_reference": "§1798.100" }
  ],
  "notes": { "zh": "...", "en": "..." },
  "status": "scaffold"
}
```

---

## Next Steps

1. **Run normalize_kg.py** with your three source files
2. **Run translate_pipl.py** to fill PIPL EN fields
3. **Review cross_jurisdiction_links** with legal counsel — the scaffold contains 3 seed links
4. **Enrich missing GDPR fields**: `category`, `importance`, `is_key_clause` (can use LLM batch)
5. **Load into graph DB**: each `clause_id` / `obligation_id` becomes a node; `relations[]` and `cross_jurisdiction_links` become edges
