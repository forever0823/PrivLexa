"""
API routes for generation, compliance review, conflict detection, and knowledge graph access.
"""

from __future__ import annotations

from datetime import datetime
import json
import time
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from .models import (
    AgentListResponse,
    ChatRequest,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ConflictDetectionRequest,
    ConflictDetectionResponse,
    DocumentRetrievalRequest,
    DocumentRetrievalResponse,
    GeneratePolicyRequest,
    GeneratePolicyResponse,
    HealthResponse,
    KnowledgeGraphConceptListResponse,
    KnowledgeGraphQueryRequest,
    KnowledgeGraphQueryResponse,
    KnowledgeGraphRelationTypeListResponse,
    KnowledgeGraphStatsResponse,
    ListJurisdictionsResponse,
    MultiJurisdictionOrchestrationRequest,
    MultiJurisdictionOrchestrationResponse,
)

try:
    from src.agents.agent_factory import AgentFactory
except ImportError:
    from ..agents.agent_factory import AgentFactory

try:
    from src.core.compliance_runtime import get_compliance_runtime
except ImportError:
    from ..core.compliance_runtime import get_compliance_runtime

try:
    from src.core.exceptions import (
        AgentBuildError,
        AgentExecutionError,
        PPGLLMException,
        UnsupportedAgentTypeError,
    )
except ImportError:
    from ..core.exceptions import (
        AgentBuildError,
        AgentExecutionError,
        PPGLLMException,
        UnsupportedAgentTypeError,
    )

try:
    from src.core.factory_manager import get_agent_factory as get_agent_factory_safe
except ImportError:
    from ..core.factory_manager import get_agent_factory as get_agent_factory_safe

try:
    from src.core.health import HealthCheckService
except ImportError:
    from ..core.health import HealthCheckService

try:
    from src.core.text_normalizer import normalize_policy_text
except ImportError:
    from ..core.text_normalizer import normalize_policy_text


router = APIRouter()


def get_agent_factory() -> AgentFactory:
    return get_agent_factory_safe()


def _stream_chunks(payload: Dict[str, Any], text: str, chunk_size: int = 120):
    text = text or ""
    for index in range(0, len(text), chunk_size):
        data = dict(payload)
        data["content"] = text[index : index + chunk_size]
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def _build_text_quality_section(notes: List[str]) -> str:
    if not notes:
        return ""
    lines = ["## 文本质量说明"]
    lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)


def _build_model_note_section(message: Optional[str], llm_report: Optional[str]) -> str:
    notes: List[str] = []
    if message:
        notes.append(message)
    if not notes:
        return ""
    lines = ["## 生成说明"]
    lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)


def _build_deterministic_baseline_section(baseline_report: Dict[str, Any]) -> str:
    """将确定性基线格式化为补充参考章节。"""
    if not baseline_report:
        return ""
    lines = ["## 确定性基线参考数据", ""]
    lines.append(f"- 整体得分: {baseline_report.get('overall_score', 0)}/100")
    lines.append(f"- 整体状态: {baseline_report.get('overall_status', 'unknown')}")
    for jr in baseline_report.get("jurisdiction_results", []):
        code = jr.get("jurisdiction", "?")
        lines.append(f"- {code}: {jr.get('compliance_score', 0)}/100, "
                      f"覆盖 {jr.get('violations_count', 0)} 项风险")
    critical = baseline_report.get("critical_violations", [])
    if critical:
        lines.append("")
        lines.append("### 关键风险项")
        for v in critical[:5]:
            lines.append(f"- [{v.get('severity', '?')}] {v.get('clause', '?')}: {v.get('description', '')}")
    return "\n".join(lines)


def _collapse_blank_lines(text: str) -> str:
    """Collapse every run of 2+ blank lines into exactly 1, and strip trailing whitespace per line."""
    lines = text.split("\n")
    out: List[str] = []
    prev_blank = False
    for line in lines:
        stripped = line.rstrip()
        is_blank = stripped == ""
        if is_blank:
            if not prev_blank:
                out.append("")
            prev_blank = True
        else:
            out.append(stripped)
            prev_blank = False
    return "\n".join(out).strip()


def _merge_markdown_sections(*sections: Optional[str]) -> str:
    raw = "\n\n".join(s.strip() for s in sections if s and s.strip())
    return _collapse_blank_lines(raw)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    try:
        health_status = await HealthCheckService.check_health()
        return HealthResponse(
            status=health_status["status"],
            timestamp=datetime.now().isoformat(),
            version=health_status["version"],
            details=health_status.get("checks"),
        )
    except Exception as exc:
        logger.error(f"Health check failed: {exc}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/agents", response_model=AgentListResponse)
async def get_agents(factory: AgentFactory = Depends(get_agent_factory)) -> AgentListResponse:
    try:
        agents = await factory.get_available_agents()
        return AgentListResponse(agents=agents)
    except Exception as exc:
        logger.error(f"Agent listing failed: {exc}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.post("/chat")
async def chat_with_agent(
    request: ChatRequest,
    factory: AgentFactory = Depends(get_agent_factory),
):
    request_id = f"chat_{datetime.now().timestamp()}"

    async def generate():
        try:
            generation_options = request.context.get("generation_options", {}) if request.context else {}
            selected_jurisdiction = request.jurisdiction or (request.jurisdictions[0] if request.jurisdictions else None)
            result = await factory.chat_with_agent(
                agent_type=request.agent_type,
                message=request.message,
                tools=request.context.get("tools") if request.context else None,
                memory_files=request.context.get("memory_files") if request.context else None,
                jurisdiction=selected_jurisdiction,
                jurisdictions=request.jurisdictions,
                parallel_execution=request.parallel_execution,
                return_markdown=request.return_markdown,
                detection_mode=request.detection_mode,
                enable_conflict_detection=request.enable_conflict_detection,
                use_rag=generation_options.get("use_rag", generation_options.get("useRag")),
            )
            for chunk in _stream_chunks({}, result.get("response", ""), chunk_size=100):
                yield chunk
        except UnsupportedAgentTypeError as exc:
            logger.warning(f"[{request_id}] Unsupported agent type: {exc.message}")
            yield f"data: {json.dumps({'error': exc.message}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except (AgentBuildError, AgentExecutionError, PPGLLMException) as exc:
            logger.error(f"[{request_id}] Agent execution failed: {exc}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'error': exc.message}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error(f"[{request_id}] Unexpected chat failure: {exc}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'error': 'Internal server error'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/api/v2/generate-policy", response_model=GeneratePolicyResponse)
async def generate_policy(
    request: GeneratePolicyRequest,
    factory: AgentFactory = Depends(get_agent_factory),
) -> GeneratePolicyResponse:
    request_id = f"policy_{datetime.now().timestamp()}"

    try:
        runtime = get_compliance_runtime()
        rag_context = None
        generation_message = (
            "请为以下应用生成隐私政策。除非用户明确指定其他语言，全文使用简体中文。\n"
            f"- 目标法域：{request.jurisdiction}\n"
            f"- 应用名称：{request.app_name}\n"
            f"- 应用类型：{request.app_type}\n"
            f"- 数据类型：{', '.join(request.data_types)}\n"
        )
        if request.regions:
            generation_message += f"- 目标地区：{', '.join(request.regions)}\n"
        if request.additional_context:
            generation_message += f"- 补充背景：{request.additional_context}\n"
        if request.use_rag:
            rag_context = runtime.build_generation_context(
                jurisdiction=request.jurisdiction,
                topic=request.app_type or request.app_name,
                context=request.additional_context or request.app_name,
            )
            generation_message += (
                "\n法规知识图谱参考资料：\n"
                f"{rag_context['prompt_context']}\n"
            )

        result = await factory.chat_with_agent(
            agent_type="privacy_policy_generator",
            message=generation_message,
            jurisdiction=request.jurisdiction,
            use_rag=request.use_rag,
        )

        logger.info(f"[{request_id}] Policy generated")
        return GeneratePolicyResponse(
            success=True,
            jurisdiction=request.jurisdiction,
            policy=result["response"],
            policy_content=result["response"],
            rag_enabled=request.use_rag,
            retrieved_documents=rag_context["relevant_documents"] if rag_context else [],
            metadata={
                "jurisdiction": request.jurisdiction,
                "app_name": request.app_name,
                "use_rag": request.use_rag,
                "use_fine_tuned_glm": request.use_fine_tuned_glm,
                "knowledge_graph_stats": rag_context["knowledge_graph_stats"] if rag_context else None,
                "jurisdiction_embedding": rag_context["jurisdiction_embedding"] if rag_context else None,
                "retrieval_strategy": rag_context["retrieval_strategy"] if rag_context else None,
                "rerank_metadata": rag_context["rerank_metadata"] if rag_context else None,
            },
        )
    except Exception as exc:
        logger.error(f"[{request_id}] Policy generation failed: {exc}\n{traceback.format_exc()}")
        return GeneratePolicyResponse(
            success=False,
            error_message=f"Policy generation failed: {exc}",
        )


@router.post("/api/v2/detect-conflicts", response_model=ConflictDetectionResponse)
async def detect_conflicts(
    request: ConflictDetectionRequest,
    factory: AgentFactory = Depends(get_agent_factory),
) -> ConflictDetectionResponse:
    request_id = f"conflict_{datetime.now().timestamp()}"

    try:
        runtime = get_compliance_runtime()
        normalized_text = normalize_policy_text(request.policy_text)
        detection_mode = request.detection_mode
        if not detection_mode:
            requested = set(request.detection_types)
            if requested == {"hard"}:
                detection_mode = "hard"
            elif requested == {"soft"}:
                detection_mode = "soft"
            else:
                detection_mode = "both"

        baseline = runtime.detect_conflicts(
            normalized_text.text,
            detection_mode=detection_mode or "both",
        )

        llm_report = None
        fallback_message = None
        try:
            result = await factory.chat_with_agent(
                agent_type="conflict_detector",
                message=(
                    "请检查以下隐私政策中的条款冲突，并使用简体中文输出。\n\n"
                    f"{normalized_text.text}\n\n"
                    "混合检测基线：\n"
                    f"{baseline['prompt_context']}"
                ),
                detection_mode=detection_mode,
            )
            llm_report = result["response"]
        except Exception as model_error:
            fallback_message = (
                "Model-generated conflict commentary failed; using rule and similarity baseline only: "
                f"{model_error}"
            )
            logger.error(
                f"[{request_id}] Conflict explanation generation failed: {model_error}\n"
                f"{traceback.format_exc()}"
            )

        detection_results = _merge_markdown_sections(
            _build_text_quality_section(
                normalized_text.applied_fixes + normalized_text.warnings
            ),
            baseline["summary_markdown"],
            _build_model_note_section(fallback_message, llm_report),
        )

        return ConflictDetectionResponse(
            success=True,
            hard_conflicts=baseline["hard_conflicts"],
            soft_conflicts=baseline["soft_conflicts"],
            total_conflicts=baseline["total_conflicts"],
            critical_count=baseline["critical_count"],
            major_count=baseline["major_count"],
            minor_count=baseline["minor_count"],
            detection_results=detection_results,
            detection_mode=detection_mode,
            message=fallback_message,
        )
    except Exception as exc:
        logger.error(f"[{request_id}] Conflict detection failed: {exc}\n{traceback.format_exc()}")
        return ConflictDetectionResponse(
            success=False,
            error_message=f"Conflict detection failed: {exc}",
        )


@router.post("/api/v2/compliance-check", response_model=ComplianceCheckResponse)
async def compliance_check(
    request: ComplianceCheckRequest,
    factory: AgentFactory = Depends(get_agent_factory),
) -> ComplianceCheckResponse:
    request_id = f"comply_{datetime.now().timestamp()}"

    try:
        normalized_text = normalize_policy_text(request.policy_text or request.privacy_policy or "")
        policy_text = normalized_text.text
        runtime = get_compliance_runtime()

        baseline_report = await runtime.analyze_compliance(
            policy_text=policy_text,
            jurisdictions=request.jurisdictions,
            policy_title=request.policy_title or "未命名隐私政策",
            parallel_execution=request.parallel_execution,
        )

        llm_report = None
        report_message = None
        try:
            result = await factory.chat_with_agent(
                agent_type="compliance_checker_multi",
                message=(
                    "请对以下隐私政策进行多法域合规审查。全文必须使用中文输出。\n\n"
                    f"{policy_text}\n\n"
                    f"政策标题：{request.policy_title or '未命名隐私政策'}\n\n"
                    "以下为确定性基线分析的参考数据（关键词匹配 + 知识图谱检索），"
                    "请将其作为辅助参考，以你的深度法律分析为主。"
                    "基线数据中的英文标签（如 Transparency and Notice）请转换为中文后使用：\n\n"
                    f"{baseline_report['prompt_context']}"
                ),
                jurisdictions=request.jurisdictions,
                parallel_execution=request.parallel_execution,
                return_markdown=request.return_markdown,
            )
            llm_report = result["response"]
        except Exception as model_error:
            report_message = (
                "LLM 深度分析生成失败，使用确定性基线报告作为备选："
                f"{model_error}"
            )
            logger.error(
                f"[{request_id}] Compliance explanation generation failed: {model_error}\n"
                f"{traceback.format_exc()}"
            )

        conflict_detection_report = None
        if request.enable_conflict_detection:
            conflict_baseline = runtime.detect_conflicts(
                policy_text,
                detection_mode=request.detection_mode or "both",
            )
            conflict_detection_report = conflict_baseline["summary_markdown"]

        # Build the final report: LLM deep analysis is PRIMARY, baseline is supplementary
        if llm_report:
            compliance_report = _merge_markdown_sections(
                _build_text_quality_section(
                    normalized_text.applied_fixes + normalized_text.warnings
                ),
                llm_report,
                conflict_detection_report,
                _build_deterministic_baseline_section(baseline_report),
                _build_model_note_section(report_message, None),
            )
        else:
            compliance_report = _merge_markdown_sections(
                _build_text_quality_section(
                    normalized_text.applied_fixes + normalized_text.warnings
                ),
                baseline_report["markdown_report"],
                conflict_detection_report,
                _build_model_note_section(report_message, None),
            )

        return ComplianceCheckResponse(
            success=True,
            policy_title=request.policy_title,
            jurisdictions=request.jurisdictions,
            overall_status=baseline_report["overall_status"],
            overall_score=baseline_report["overall_score"],
            jurisdiction_results=baseline_report["jurisdiction_results"],
            critical_violations=baseline_report["critical_violations"],
            recommendations=baseline_report["recommendations"],
            compliance_report=compliance_report,
            markdown_report=compliance_report if request.return_markdown else None,
            report_format="markdown" if request.return_markdown else "json",
            conflict_detection_enabled=request.enable_conflict_detection,
            conflict_detection_report=conflict_detection_report,
            conflict_detection_error=None,
            detection_mode=request.detection_mode,
            message=report_message,
        )
    except Exception as exc:
        logger.error(f"[{request_id}] Compliance analysis failed: {exc}\n{traceback.format_exc()}")
        return ComplianceCheckResponse(
            success=False,
            error_message=f"Compliance analysis failed: {exc}",
        )


@router.post(
    "/api/v2/multi-jurisdiction-orchestration",
    response_model=MultiJurisdictionOrchestrationResponse,
)
async def multi_jurisdiction_orchestration(
    request: MultiJurisdictionOrchestrationRequest,
    factory: AgentFactory = Depends(get_agent_factory),
) -> MultiJurisdictionOrchestrationResponse:
    request_id = f"orch_{datetime.now().timestamp()}"

    try:
        runtime = get_compliance_runtime()
        orchestration_context = ""
        summary: Dict[str, Any] = {}

        if request.operation in {"generate", "full"} and request.app_name and request.app_type and request.include_rag:
            generation_summary = runtime.build_generation_context(
                jurisdiction=request.jurisdiction,
                topic=request.app_type,
                context="; ".join(
                    item for item in [request.app_name, ", ".join(request.data_types or [])] if item
                ),
            )
            orchestration_context += (
                f"\n确定性生成参考：\n{generation_summary['prompt_context']}\n"
            )
            summary["generation"] = {
                "retrieved_documents": generation_summary["document_count"],
                "retrieval_strategy": generation_summary["retrieval_strategy"],
                "jurisdiction_embedding": generation_summary["jurisdiction_embedding"],
            }

        if request.operation in {"comply", "full"} and request.policy_text:
            compliance_summary = await runtime.analyze_compliance(
                policy_text=request.policy_text,
                jurisdictions=[request.jurisdiction] + (request.additional_jurisdictions or []),
                policy_title=request.app_name or "未命名隐私政策",
                parallel_execution=request.parallel_processing,
            )
            orchestration_context += (
                f"\n确定性合规基线：\n{compliance_summary['prompt_context']}\n"
            )
            summary["compliance"] = {
                "overall_status": compliance_summary["overall_status"],
                "overall_score": compliance_summary["overall_score"],
            }

        if request.operation in {"detect", "full"} and request.policy_text:
            conflict_summary = runtime.detect_conflicts(request.policy_text, detection_mode="both")
            orchestration_context += (
                f"\n确定性冲突检测基线：\n{conflict_summary['prompt_context']}\n"
            )
            summary["conflicts"] = {
                "total_conflicts": conflict_summary["total_conflicts"],
                "critical_count": conflict_summary["critical_count"],
            }

        result = await factory.chat_with_agent(
            agent_type="multi_jurisdiction_coordinator",
            message=(
                "请执行以下多法域隐私政策任务，并使用简体中文输出：\n"
                f"- 操作：{request.operation}\n"
                f"- 主要法域：{request.jurisdiction}\n"
                f"- 其他法域：{request.additional_jurisdictions}\n"
                f"- 应用名称：{request.app_name}\n"
                f"- 应用类型：{request.app_type}\n"
                f"- 数据类型：{', '.join(request.data_types or [])}\n"
                f"- 并行处理：{'启用' if request.parallel_processing else '关闭'}\n"
                f"- 法规检索增强：{'启用' if request.include_rag else '关闭'}\n"
                f"{orchestration_context}"
            ),
            operation=request.operation,
            parallel_processing=request.parallel_processing,
        )

        logger.info(f"[{request_id}] Multi-jurisdiction orchestration completed")
        return MultiJurisdictionOrchestrationResponse(
            success=True,
            operation=request.operation,
            orchestration_result=result["response"],
            jurisdictions=[request.jurisdiction] + (request.additional_jurisdictions or []),
            summary=summary or None,
        )
    except Exception as exc:
        logger.error(f"[{request_id}] Orchestration failed: {exc}\n{traceback.format_exc()}")
        return MultiJurisdictionOrchestrationResponse(
            success=False,
            error_message=f"Multi-jurisdiction orchestration failed: {exc}",
        )


@router.get("/api/v2/jurisdictions", response_model=ListJurisdictionsResponse)
async def list_jurisdictions() -> ListJurisdictionsResponse:
    try:
        try:
            from src.core.jurisdiction import get_jurisdiction_manager
        except ImportError:
            from ..core.jurisdiction import get_jurisdiction_manager

        manager = get_jurisdiction_manager()
        jurisdictions_list = manager.list_jurisdictions()
        return ListJurisdictionsResponse(
            success=True,
            jurisdictions=jurisdictions_list,
            total_count=len(jurisdictions_list),
        )
    except Exception as exc:
        logger.error(f"Jurisdiction listing failed: {exc}\n{traceback.format_exc()}")
        return ListJurisdictionsResponse(
            success=False,
            error_message=f"Failed to list jurisdictions: {exc}",
        )


@router.get("/api/v2/knowledge-graph/stats", response_model=KnowledgeGraphStatsResponse)
async def knowledge_graph_stats() -> KnowledgeGraphStatsResponse:
    try:
        try:
            from src.core.knowledge_graph import get_regulation_knowledge_graph
        except ImportError:
            from ..core.knowledge_graph import get_regulation_knowledge_graph

        graph = get_regulation_knowledge_graph()
        return KnowledgeGraphStatsResponse(
            success=True,
            stats=graph.get_stats().model_dump(),
            sqlite_path=str(graph.get_sqlite_path()),
        )
    except Exception as exc:
        logger.error(f"Knowledge graph stats failed: {exc}\n{traceback.format_exc()}")
        return KnowledgeGraphStatsResponse(success=False, error_message=str(exc))


@router.get("/api/v2/knowledge-graph/concepts", response_model=KnowledgeGraphConceptListResponse)
async def knowledge_graph_concepts(jurisdiction: Optional[str] = None) -> KnowledgeGraphConceptListResponse:
    try:
        try:
            from src.core.knowledge_graph import get_regulation_knowledge_graph
        except ImportError:
            from ..core.knowledge_graph import get_regulation_knowledge_graph

        graph = get_regulation_knowledge_graph()
        if jurisdiction:
            concepts = graph.get_concepts_for_jurisdiction(jurisdiction)
        else:
            concepts = [graph.concepts[key] for key in sorted(graph.concepts)]

        payload = [concept.model_dump(mode="json") for concept in concepts if concept.is_core]
        return KnowledgeGraphConceptListResponse(
            success=True,
            concepts=payload,
            total_count=len(payload),
        )
    except Exception as exc:
        logger.error(f"Knowledge graph concept listing failed: {exc}\n{traceback.format_exc()}")
        return KnowledgeGraphConceptListResponse(success=False, error_message=str(exc))


@router.get("/api/v2/knowledge-graph/relation-types", response_model=KnowledgeGraphRelationTypeListResponse)
async def knowledge_graph_relation_types() -> KnowledgeGraphRelationTypeListResponse:
    try:
        try:
            from src.core.knowledge_graph import get_regulation_knowledge_graph
        except ImportError:
            from ..core.knowledge_graph import get_regulation_knowledge_graph

        graph = get_regulation_knowledge_graph()
        payload = [item.model_dump(mode="json") for item in graph.get_relation_type_definitions()]
        return KnowledgeGraphRelationTypeListResponse(
            success=True,
            relation_types=payload,
            total_count=len(payload),
        )
    except Exception as exc:
        logger.error(f"Knowledge graph relation-type listing failed: {exc}\n{traceback.format_exc()}")
        return KnowledgeGraphRelationTypeListResponse(success=False, error_message=str(exc))


@router.post("/api/v2/knowledge-graph/query", response_model=KnowledgeGraphQueryResponse)
async def knowledge_graph_query(
    request: KnowledgeGraphQueryRequest,
) -> KnowledgeGraphQueryResponse:
    start = time.perf_counter()
    try:
        try:
            from src.core.knowledge_graph import get_regulation_knowledge_graph
        except ImportError:
            from ..core.knowledge_graph import get_regulation_knowledge_graph

        graph = get_regulation_knowledge_graph()
        result = graph.query_knowledge_graph(
            query=request.query or "",
            jurisdictions=request.jurisdictions,
            concept_ids=request.concept_ids,
            top_k=request.top_k,
        )
        return KnowledgeGraphQueryResponse(
            success=True,
            query=result["query"],
            matched_concepts=result["matched_concepts"],
            cross_jurisdiction_links=result["cross_jurisdiction_links"],
            jurisdiction_results=result["jurisdiction_results"],
            summary_markdown=result["summary_markdown"],
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
        )
    except Exception as exc:
        logger.error(f"Knowledge graph query failed: {exc}\n{traceback.format_exc()}")
        return KnowledgeGraphQueryResponse(
            success=False,
            query=request.query,
            error_message=str(exc),
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
        )


@router.post("/api/v2/retrieve-documents", response_model=DocumentRetrievalResponse)
async def retrieve_documents(
    request: DocumentRetrievalRequest,
) -> DocumentRetrievalResponse:
    request_id = f"retrieve_{datetime.now().timestamp()}"
    start = time.perf_counter()

    try:
        try:
            from src.core.rag import get_rag_pipeline
        except ImportError:
            from ..core.rag import get_rag_pipeline

        jurisdiction = request.jurisdiction or "CN"
        rag = get_rag_pipeline()
        result = rag.retrieve_for_generation(
            jurisdiction=jurisdiction,
            topic=request.query,
            context="",
        )

        logger.info(f"[{request_id}] Retrieved {result['document_count']} documents")
        return DocumentRetrievalResponse(
            success=True,
            query=request.query,
            jurisdiction=jurisdiction,
            documents=result["relevant_documents"][: request.top_k],
            total_found=result["document_count"],
            total_count=result["document_count"],
            context_summary=result.get("context_summary", ""),
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
        )
    except Exception as exc:
        logger.error(f"[{request_id}] Document retrieval failed: {exc}\n{traceback.format_exc()}")
        return DocumentRetrievalResponse(
            success=False,
            error_message=f"Document retrieval failed: {exc}",
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
        )
