"""将用户提供的 Markdown 自由文本解析为结构化 UserProfile。

策略：
  1. 先用关键字 + 正则做"轻量抽取"（姓名、手机、邮箱、性别、出生日期）。
  2. 再用 Qwen 把剩余块（教育、实习、项目、技能、语言、获奖、自我评价）抽成结构化 JSON。
  3. 合并为 UserProfile。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.models.llm import LLMClient
from backend.models.schemas import (
    EducationItem,
    InternshipItem,
    LanguageItem,
    ProjectItem,
    UserProfile,
)

logger = logging.getLogger(__name__)


# ------------------------- 轻量正则抽取 -------------------------

RE_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
RE_BIRTH = re.compile(r"(?:出生|生年|出生日期|birth)\s*[:：]?\s*(\d{4}[-/年.]?\d{1,2}[-/月.]?\d{0,2}\d?)", re.IGNORECASE)


def _quick_extract(md: str) -> Dict[str, Any]:
    """正则抽取姓名、手机、邮箱、性别、出生日期。"""
    out: Dict[str, Any] = {}

    # 邮箱
    m = RE_EMAIL.search(md)
    if m:
        out["email"] = m.group(0)

    # 手机
    m = RE_PHONE.search(md)
    if m:
        out["phone"] = m.group(1)

    # 性别
    if re.search(r"性别\s*[:：]\s*男", md):
        out["gender"] = "男"
    elif re.search(r"性别\s*[:：]\s*女", md):
        out["gender"] = "女"

    # 出生日期
    m = RE_BIRTH.search(md)
    if m:
        out["birth_date"] = m.group(1).replace("年", "-").replace("月", "-").rstrip("-")

    # 姓名：寻找 "姓名: 张三" 或首行第一个非空"词"
    m = re.search(r"姓\s*名\s*[:：]\s*([^\s\n#*|]+)", md)
    if m:
        out["name"] = m.group(1).strip()

    return out


# ------------------------- LLM 抽取块 -------------------------

EXTRACT_PROMPT = """你是简历结构化助手。把下面"用户简历原始 Markdown"解析为严格 JSON。

要求：
- 严格输出 JSON，**不要任何解释**。
- 字段缺失时填空字符串 `""` 或空数组 `[]`，不要编造。
- 字段说明：
  - name: 完整姓名
  - phone: 手机号
  - email: 邮箱
  - gender: "男" 或 "女"
  - birth_date: 出生日期 YYYY-MM
  - nationality: 民族
  - political_status: 政治面貌
  - address: 现居地址
  - current_city: 当前所在城市
  - expected_city: 期望工作城市
  - expected_salary: 期望薪资
  - earliest_start_date: 可到岗日期
  - educations: 数组，每项 {school, major, degree, start, end, description}
  - internships: 数组，每项 {company, role, start, end, description}
  - projects: 数组，每项 {name, role, start, end, description}
  - skills: 字符串数组
  - languages: 数组，每项 {name, level}
  - awards: 字符串数组
  - self_evaluation: 自我评价完整文本
  - custom: 对象，存放其它非标准字段

输出 JSON：
"""


def _llm_extract(md: str, llm: LLMClient) -> Dict[str, Any]:
    """调用 Qwen 抽 JSON。失败时返回空 dict。"""
    try:
        result = llm.chat_json(
            [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": md},
            ],
        )
        if isinstance(result, dict):
            return result
        logger.warning("LLM 返回非 dict: %s", type(result))
        return {}
    except Exception as e:  # noqa: BLE001
        logger.exception("LLM 抽取失败: %s", e)
        return {"_error": str(e)}


# ------------------------- 合并 -------------------------


def _to_education_list(raw: Any) -> List[EducationItem]:
    items: List[EducationItem] = []
    if not isinstance(raw, list):
        return items
    for r in raw:
        if not isinstance(r, dict):
            continue
        items.append(
            EducationItem(
                school=str(r.get("school", "") or ""),
                major=str(r.get("major", "") or ""),
                degree=str(r.get("degree", "") or ""),
                start=str(r.get("start", "") or ""),
                end=str(r.get("end", "") or ""),
                description=str(r.get("description", "") or ""),
            )
        )
    return items


def _to_internship_list(raw: Any) -> List[InternshipItem]:
    items: List[InternshipItem] = []
    if not isinstance(raw, list):
        return items
    for r in raw:
        if not isinstance(r, dict):
            continue
        items.append(
            InternshipItem(
                company=str(r.get("company", "") or ""),
                role=str(r.get("role", "") or ""),
                start=str(r.get("start", "") or ""),
                end=str(r.get("end", "") or ""),
                description=str(r.get("description", "") or ""),
            )
        )
    return items


def _to_project_list(raw: Any) -> List[ProjectItem]:
    items: List[ProjectItem] = []
    if not isinstance(raw, list):
        return items
    for r in raw:
        if not isinstance(r, dict):
            continue
        items.append(
            ProjectItem(
                name=str(r.get("name", "") or ""),
                role=str(r.get("role", "") or ""),
                start=str(r.get("start", "") or ""),
                end=str(r.get("end", "") or ""),
                description=str(r.get("description", "") or ""),
            )
        )
    return items


def _to_language_list(raw: Any) -> List[LanguageItem]:
    items: List[LanguageItem] = []
    if not isinstance(raw, list):
        return items
    for r in raw:
        if not isinstance(r, dict):
            continue
        items.append(
            LanguageItem(
                name=str(r.get("name", "") or ""),
                level=str(r.get("level", "") or ""),
            )
        )
    return items


def parse_user_info(md: str, llm: Optional[LLMClient] = None) -> UserProfile:
    """主入口：把 Markdown 解析为 UserProfile。"""
    if not md or not md.strip():
        return UserProfile()

    quick = _quick_extract(md)
    llm_result: Dict[str, Any] = {}
    if llm is not None:
        llm_result = _llm_extract(md, llm)

    # LLM 优先，quick 兜底（轻量抽取不覆盖 LLM 已经填好的）
    def pick(key: str, default: str = "") -> str:
        v = llm_result.get(key)
        if v is None or v == "":
            v = quick.get(key, default)
        return str(v) if v is not None else default

    profile = UserProfile(
        name=pick("name"),
        phone=pick("phone"),
        email=pick("email"),
        gender=pick("gender"),
        birth_date=pick("birth_date"),
        nationality=pick("nationality"),
        political_status=pick("political_status"),
        address=pick("address"),
        current_city=pick("current_city"),
        expected_city=pick("expected_city"),
        expected_salary=pick("expected_salary"),
        earliest_start_date=pick("earliest_start_date"),
        educations=_to_education_list(llm_result.get("educations")),
        internships=_to_internship_list(llm_result.get("internships")),
        projects=_to_project_list(llm_result.get("projects")),
        skills=[str(s) for s in llm_result.get("skills", []) or [] if s],
        languages=_to_language_list(llm_result.get("languages")),
        awards=[str(s) for s in llm_result.get("awards", []) or [] if s],
        self_evaluation=str(llm_result.get("self_evaluation", "") or ""),
        custom={k: str(v) for k, v in (llm_result.get("custom", {}) or {}).items()},
    )
    return profile


def profile_to_summary(profile: UserProfile) -> str:
    """把 Profile 渲染成对人友好的多行摘要（供侧栏展示）。"""
    lines = []
    if profile.name:
        lines.append(f"**{profile.name}**")
    if profile.gender or profile.birth_date:
        bits = [b for b in (profile.gender, profile.birth_date) if b]
        lines.append(" · ".join(bits))
    if profile.phone:
        lines.append(f"📱 {profile.phone}")
    if profile.email:
        lines.append(f"📧 {profile.email}")
    if profile.educations:
        e = profile.educations[0]
        lines.append(f"🎓 {e.school} · {e.major} · {e.degree}")
    if profile.internships:
        i = profile.internships[0]
        lines.append(f"💼 {i.company} · {i.role}")
    if profile.self_evaluation:
        lines.append("\n> " + profile.self_evaluation[:200] + ("..." if len(profile.self_evaluation) > 200 else ""))
    return "\n".join(lines)


def profile_to_json(profile: UserProfile) -> str:
    """把 Profile 序列化为紧凑 JSON 字符串，供 LLM Prompt 使用。"""
    return profile.model_dump_json(ensure_ascii=False)
