"""Agent 可调用的工具（LangChain Tool 风格）。

目前实现以"内部函数"形式为主，LangGraph 直接调用函数节点。
保留该文件以方便后续扩展为真正的 ReAct Tool（如加入搜索/记忆）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from backend.models.llm import LLMClient
from backend.models.schemas import PageField, UserFileMeta, UserProfile
from backend.services.fill_planner import plan_fill
from backend.services.page_analyzer import summarize_fields
from backend.services.user_info_parser import parse_user_info


def tool_parse_user_info(md: str, llm: LLMClient) -> UserProfile:
    """Tool: Markdown -> UserProfile。"""
    return parse_user_info(md, llm=llm)


def tool_summarize_fields(fields: List[PageField]) -> str:
    """Tool: PageField[] -> 字符串。"""
    return summarize_fields(fields)


def tool_plan_fill(
    profile: UserProfile,
    fields: List[PageField],
    files: List[UserFileMeta],
    llm: LLMClient,
) -> Dict[str, Any]:
    """Tool: Profile+Fields+Files -> FillPlan (dict)。"""
    return plan_fill(profile, fields, files, llm=llm).model_dump()
