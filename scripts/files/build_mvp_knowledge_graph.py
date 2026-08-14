"""
Build and validate the minimum viable multi-jurisdiction knowledge graph.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.knowledge_graph import get_regulation_knowledge_graph


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output" / "normalized"
REPORT_PATH = OUTPUT_DIR / "multi_jurisdiction_kg_build_report.json"


def main() -> None:
    graph = get_regulation_knowledge_graph()
    stats = graph.get_stats().model_dump(mode="json")
    sample_access = graph.query_knowledge_graph(
        query="access deletion cross-border transfer",
        jurisdictions=["CN", "EU", "US"],
        top_k=4,
    )

    report = {
        "stats": stats,
        "sqlite_path": str(graph.get_sqlite_path()),
        "core_concept_count": len([concept for concept in graph.concepts.values() if concept.is_core]),
        "jurisdiction_profiles": {
            code: graph.get_jurisdiction_profile(code) for code in graph.list_supported_jurisdictions()
        },
        "sample_query": {
            "query": sample_access["query"],
            "matched_concepts": sample_access["matched_concepts"],
            "jurisdiction_result_sizes": [
                {
                    "jurisdiction": item["jurisdiction"],
                    "clauses": len(item["clauses"]),
                    "aggregated_obligations": len(item["aggregated_obligations"]),
                    "raw_obligations": len(item["raw_obligations"]),
                }
                for item in sample_access["jurisdiction_results"]
            ],
        },
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
