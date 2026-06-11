"""Resume Fill Agent 的 LangGraph 编排。

图：parse_user_info → summarize_fields → match_fields → plan_uploads → END
每一步都基于上一步结果，失败时降级。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from backend.models.llm import LLMClient
from backend.models.schemas import (
    FillPlan,
    PageField,
    UserFileMeta,
    UserProfile,
)
from backend.services.fill_planner import plan_fill
from backend.services.page_analyzer import summarize_fields
from backend.services.user_info_parser import (
    parse_user_info,
    profile_to_json,
    profile_to_summary,
)

logger = logging.getLogger(__name__)


# ------------------------- 状态 -------------------------


class AgentState(TypedDict, total=False):
    # 输入
    page_url: str
    page_title: str
    fields: List[PageField]
    user_markdown: str
    file_metas: List[Dict[str, Any]]     # 序列化为 dict
    # 中间结果
    profile: Optional[Dict[str, Any]]
    fields_text: str
    llm_raw_match: Optional[List[Dict[str, Any]]]
    # 输出
    plan: Optional[Dict[str, Any]]
    profile_summary: str
    error: Optional[str]


# ------------------------- 节点 -------------------------


def node_parse_user_info(state: AgentState) -> AgentState:
    """从 Markdown 抽 UserProfile。"""
    try:
        profile: UserProfile = parse_user_info(state["user_markdown"], llm=state.get("_llm"))  # type: ignore[arg-type]
        state["profile"] = profile.model_dump()
        state["profile_summary"] = profile_to_summary(profile)
        logger.info("解析完成，Profile 字段已填充 %d 项", sum(1 for v in state["profile"].values() if v))
    except Exception as e:  # noqa: BLE001
        logger.exception("parse_user_info 失败: %s", e)
        state["profile"] = UserProfile().model_dump()
        state["profile_summary"] = ""
        state["error"] = f"parse_user_info: {e}"
    return state


def node_summarize_fields(state: AgentState) -> AgentState:
    """把 fields 渲染成 LLM 友好的字符串。"""
    try:
        fields = [PageField(**f) for f in state["fields"]]
        state["fields_text"] = summarize_fields(fields)
    except Exception as e:  # noqa: BLE001
        logger.exception("summarize_fields 失败: %s", e)
        state["fields_text"] = ""
        state["error"] = (state.get("error") or "") + f" summarize:{e}"
    return state


def node_plan_fill(state: AgentState) -> AgentState:
    """核心：plan_fill 把 Profile + Fields 映射成 FillPlan。"""
    try:
        profile = UserProfile(**(state.get("profile") or {}))
        fields = [PageField(**f) for f in state["fields"]]
        file_metas = [UserFileMeta(**m) for m in state.get("file_metas", [])]
        plan: FillPlan = plan_fill(
            profile=profile,
            fields=fields,
            files=file_metas,
            llm=state.get("_llm"),  # type: ignore[arg-type]
        )
        state["plan"] = plan.model_dump()
        logger.info("FillPlan 生成: 动作 %d 项, 匹配 %d, 未匹配 %d",
                    len(plan.actions), plan.matched_count, len(plan.unmatched_fields))
    except Exception as e:  # noqa: BLE001
        logger.exception("plan_fill 失败: %s", e)
        state["plan"] = FillPlan(actions=[], notes=f"plan_fill 失败: {e}").model_dump()
        state["error"] = (state.get("error") or "") + f" plan:{e}"
    return state


# ------------------------- 构造图 -------------------------


def build_agent_graph() -> Any:
    workflow = StateGraph(AgentState)
    workflow.add_node("parse_user_info", node_parse_user_info)
    workflow.add_node("summarize_fields", node_summarize_fields)
    workflow.add_node("plan_fill", node_plan_fill)

    workflow.set_entry_point("parse_user_info")
    workflow.add_edge("parse_user_info", "summarize_fields")
    workflow.add_edge("summarize_fields", "plan_fill")
    workflow.add_edge("plan_fill", END)
    return workflow.compile()


# ------------------------- 包装类 -------------------------


class ResumeFillAgent:
    """对外的统一入口。"""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()
        self.graph = build_agent_graph()

    def run(
        self,
        page_url: str,
        page_title: str,
        fields: List[PageField],
        user_markdown: str,
        files: Optional[List[UserFileMeta]] = None,
    ) -> Dict[str, Any]:
        initial: AgentState = {
            "page_url": page_url,
            "page_title": page_title,
            "fields": [f.model_dump() for f in fields],
            "user_markdown": user_markdown,
            "file_metas": [f.model_dump() for f in (files or [])],
            "_llm": self.llm,  # type: ignore[typeddict-item]
        }
        result = self.graph.invoke(initial)
        # 把内部状态整理成对外结果
        return {
            "plan": result.get("plan") or FillPlan(actions=[]).model_dump(),
            "profile_summary": result.get("profile_summary", ""),
            "error": result.get("error"),
        }
