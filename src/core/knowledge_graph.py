"""
Compatibility wrapper for the data-backed multi-jurisdiction knowledge graph.
"""

from __future__ import annotations

from .multi_jurisdiction_graph import (  # noqa: F401
    CrossJurisdictionLink,
    CrossJurisdictionNode,
    GraphConcept,
    KnowledgeGraphStats,
    RegulationClause,
    RegulationKnowledgeGraph,
    RegulationLaw,
    RegulationObligation,
    get_regulation_knowledge_graph,
)

