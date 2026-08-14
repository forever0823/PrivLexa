from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import src.core.multi_jurisdiction_graph as graph_module


EXPECTED_RELATION_TYPES = [
    "equivalent",
    "similar",
    "broader_narrower",
    "cross_related",
    "jurisdiction_specific",
]

EXPECTED_RELATION_TYPE_COUNTS = {
    "equivalent": 3,
    "similar": 1,
    "broader_narrower": 1,
    "cross_related": 1,
    "jurisdiction_specific": 1,
}


@pytest.fixture()
def graph(tmp_path, monkeypatch):
    monkeypatch.setattr(graph_module, "SQLITE_GRAPH_PATH", tmp_path / "kg.sqlite")
    return graph_module.RegulationKnowledgeGraph()


@pytest.fixture()
def definition_map(graph):
    return {item.relation_type: item for item in graph.get_relation_type_definitions()}


def assert_link_nodes(link, expected_clause_ids):
    assert {node.clause_id for node in link.nodes} == set(expected_clause_ids)


def test_relation_type_stats_include_five_type_table(graph):
    """关系类型统计会完整覆盖五类跨法域关联"""
    stats = graph.get_stats()

    assert stats.cross_jurisdiction_link_count == 7
    assert stats.relation_type_counts == EXPECTED_RELATION_TYPE_COUNTS
    assert stats.supported_relation_types == EXPECTED_RELATION_TYPES


def test_relation_type_definitions_follow_supported_order(graph):
    """关系类型定义列表顺序与支持表保持一致"""
    definitions = graph.get_relation_type_definitions()
    assert [item.relation_type for item in definitions] == EXPECTED_RELATION_TYPES


@pytest.mark.parametrize(
    ("relation_type", "label_zh", "direct_merge_allowed", "link_count", "basis_field", "basis_fragment"),
    [
        pytest.param(
            "equivalent",
            "\u7b49\u4ef7\u5bf9\u5e94",
            True,
            3,
            "determination_basis",
            "legal effect is materially aligned",
            id="\u7b49\u4ef7\u5bf9\u5e94",
        ),
        pytest.param(
            "similar",
            "\u529f\u80fd\u8fd1\u4f3c",
            False,
            1,
            "determination_basis",
            "trigger condition, threshold, or scope differs",
            id="\u529f\u80fd\u8fd1\u4f3c",
        ),
        pytest.param(
            "broader_narrower",
            "\u4e0a\u4f4d-\u4e0b\u4f4d",
            False,
            1,
            "determination_basis_zh",
            "\u4e00\u65b9\u89c4\u5219\u8986\u76d6\u66f4\u5bbd\u7684\u4e3b\u9898\u8303\u56f4",
            id="\u4e0a\u4f4d-\u4e0b\u4f4d",
        ),
        pytest.param(
            "cross_related",
            "\u4ea4\u53c9\u76f8\u5173",
            False,
            1,
            "determination_basis",
            "rules sit on different doctrinal axes",
            id="\u4ea4\u53c9\u76f8\u5173",
        ),
        pytest.param(
            "jurisdiction_specific",
            "\u6cd5\u57df\u7279\u6709",
            False,
            1,
            "determination_basis",
            "no stable counterpart exists in the compared regimes",
            id="\u6cd5\u57df\u7279\u6709",
        ),
    ],
)
def test_relation_type_definitions_match_table_fields(
    definition_map,
    relation_type,
    label_zh,
    direct_merge_allowed,
    link_count,
    basis_field,
    basis_fragment,
):
    """关系类型定义字段会暴露正确的中文标签和判定依据"""
    definition = definition_map[relation_type]
    assert definition.label_zh == label_zh
    assert definition.direct_merge_allowed is direct_merge_allowed
    assert definition.link_count == link_count
    assert basis_fragment in getattr(definition, basis_field)


def test_cross_related_links_expose_runtime_metadata(graph):
    """交叉相关关系会暴露运行时元数据和节点集合"""
    links = graph.get_cross_jurisdiction_links(["cross_border_transfer"])

    assert len(links) == 1
    link = links[0]
    assert link.relation_type == "cross_related"
    assert link.relation_label_zh == "\u4ea4\u53c9\u76f8\u5173"
    assert link.relation_label_en == "Cross-Related"
    assert link.direct_merge_allowed is False
    assert "rules sit on different doctrinal axes" in link.determination_basis
    assert "regulatory axis" in link.comparison_basis
    assert_link_nodes(link, {"CN_PIPL_ART_38", "GDPR_ART_44"})


def test_broader_narrower_links_keep_hierarchical_seed(graph):
    """上位下位关系会保留参考法规和层级对照信息"""
    links = graph.get_cross_jurisdiction_links(["sensitive_personal_information"])

    assert len(links) == 1
    link = links[0]
    assert link.relation_type == "broader_narrower"
    assert link.relation_label_zh == "\u4e0a\u4f4d-\u4e0b\u4f4d"
    assert link.reference_law_id == "EU_GDPR_2016_679"
    assert "thematic scope" in link.comparison_basis
    assert_link_nodes(link, {"CN_PIPL_ART_29", "GDPR_ART_9", "CCPA_SEC_1798_121"})


def test_jurisdiction_specific_links_preserve_reference_law(graph):
    """法域特有关系会在查询结果中保留参考法规和摘要标记"""
    result = graph.query_knowledge_graph(
        query="",
        concept_ids=["consumer_opt_out_controls"],
        jurisdictions=["US"],
        top_k=3,
    )

    assert result["cross_jurisdiction_links"]
    link = result["cross_jurisdiction_links"][0]
    assert link["relation_type"] == "jurisdiction_specific"
    assert link["relation_label_zh"] == "\u6cd5\u57df\u7279\u6709"
    assert link["reference_law_id"] == "US_CA_CCPA_CPRA_2018"
    assert link["direct_merge_allowed"] is False
    assert "消费者退出控制机制［法域特有］" in result["summary_markdown"]
