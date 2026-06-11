"""把 PageField + UserProfile 映射为 FillPlan。

实现：
  1. 规则阶段：常见字段（name / email / phone）按关键字精确匹配。
  2. LLM 阶段：未匹配字段交给 Qwen 决定。
  3. 特殊处理：文件字段（按 name/id/label 推断用途）。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.models.llm import LLMClient
from backend.models.schemas import (
    FillAction,
    FillPlan,
    PageField,
    UserFileMeta,
    UserProfile,
)
from backend.services.page_analyzer import field_text_signals, summarize_fields

logger = logging.getLogger(__name__)


# ------------------------- 规则匹配 -------------------------


# 把"Profile 字段名"映射到"页面关键字列表"
PROFILE_FIELD_KEYWORDS: Dict[str, List[str]] = {
    "name": ["姓名", "名字", "name", "fullname", "user_name", "username", "realname", "真实姓名"],
    "phone": ["手机", "联系电话", "电话", "phone", "tel", "mobile", "联系电话"],
    "email": ["邮箱", "邮件", "email", "e-mail", "mail", "电子邮箱"],
    "gender": ["性别", "gender", "sex"],
    "birth_date": ["出生", "生日", "birth", "dob", "出生日期", "生年月日"],
    "nationality": ["民族", "nationality", "ethnic"],
    "political_status": ["政治面貌", "政治", "political"],
    "address": ["现居地址", "居住地", "家庭住址", "地址", "address", "residence"],
    "current_city": ["所在城市", "当前城市", "现居城市", "城市", "city", "location", "现居地"],
    "expected_city": ["期望城市", "期望工作地", "期望工作城市", "意向城市", "工作地点", "工作城市", "expected city", "preferred city", "城市意向"],
    "expected_salary": ["期望薪资", "薪资要求", "salary", "期望月薪", "薪酬"],
    "earliest_start_date": ["到岗时间", "可到岗", "入职时间", "start date", "到岗日期"],
    "self_evaluation": ["自我评价", "自我介绍", "个人评价", "评价", "self", "evaluation", "introduction", "自我描述", "个人介绍"],
    "skills": ["专业技能", "技能", "skills", "ability", "技术栈", "掌握技能"],
}


# Profile 中可"压平为单值字符串"的字段
SINGLE_VALUE_FIELDS = set(PROFILE_FIELD_KEYWORDS.keys())


def _get_profile_value(profile: UserProfile, key: str) -> str:
    val = getattr(profile, key, "")
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val) if val else ""


def _match_field_by_rule(field: PageField, profile: UserProfile) -> Optional[str]:
    """如果命中规则，返回 Profile 中的对应值；否则 None。"""
    sigs = field_text_signals(field)
    if not sigs:
        return None

    # 把所有信号拼接成大字符串，便于多关键字子串匹配
    haystack = " ".join(sigs)

    for profile_key, keywords in PROFILE_FIELD_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in haystack:
                value = _get_profile_value(profile, profile_key)
                if value:
                    return value
    return None


# ------------------------- 文件字段推断 -------------------------


# 推断文件字段用途的关键字
FILE_PURPOSE_KEYWORDS: Dict[str, List[str]] = {
    "resume": ["简历", "resume", "cv", "附件"],
    "avatar": ["头像", "证件照", "照片", "个人照片", "avatar", "photo", "头像上传"],
    "cover_letter": ["求职信", "cover", "letter"],
    "portfolio": ["作品集", "作品", "portfolio", "作品附件"],
    "transcript": ["成绩单", "transcript"],
    "certificate": ["证书", "certificate", "资质"],
}


def _classify_file_field(field: PageField, file_names: List[str]) -> Optional[Tuple[int, str]]:
    """根据字段标签和文件名猜测用第几个文件。

    返回 (file_index, purpose) 或 None。
    """
    sigs = " ".join(field_text_signals(field)).lower()
    purpose: Optional[str] = None
    for p, kws in FILE_PURPOSE_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in sigs:
                purpose = p
                break
        if purpose:
            break

    if not purpose:
        # 没有明确的字段标签，按用户选择的顺序默认用第一个文件
        if file_names:
            return 0, "default"
        return None

    # 在用户选中的文件中，找名称符合 purpose 的
    for i, name in enumerate(file_names):
        ln = name.lower()
        for kw in FILE_PURPOSE_KEYWORDS[purpose]:
            if kw.lower() in ln:
                return i, purpose

    # 没找到对应文件，但有文件可用，返回第一个（兜底）
    if file_names:
        return 0, purpose
    return None


# ------------------------- LLM 兜底匹配 -------------------------


MATCH_PROMPT = """你是网页表单字段匹配专家。请把"用户 Profile"中的字段映射到"网页表单字段"。

【网页字段】（每行格式：#序号 [tag:type] name=... id=... label="..." placeholder="..." options=[...]）
{fields_text}

【用户 Profile JSON】
{profile_json}

要求：
1. 仔细看每个网页字段的 label / placeholder / name / id，决定它要填 Profile 哪一项。
2. 一个网页字段最多匹配 Profile 中的一项；可写"-"表示不填。
3. 对 `type=file` 的字段（tag 为 file），输出 file_purpose 字段（resume / avatar / cover_letter / portfolio / transcript / certificate / other）。
4. 严格输出 JSON 数组，元素格式：
   {{"selector": "<从下方 #N 抄过来>", "profile_key": "<profile 字段名或 - >", "value": "<若 profile_key 为 -，这里直接给出值，否则用占位 '__FROM_PROFILE__'>", "file_purpose": "<当是 file 字段时填写>"}}
5. 只输出 JSON 数组，不要任何解释。
"""


def _llm_match(
    fields: List[PageField],
    profile: UserProfile,
    llm: LLMClient,
) -> List[Dict[str, Any]]:
    """调用 LLM 兜底匹配剩余字段。"""
    fields_text = summarize_fields(fields)
    profile_json = profile.model_dump_json(ensure_ascii=False)
    prompt = MATCH_PROMPT.format(fields_text=fields_text, profile_json=profile_json)

    try:
        result = llm.chat_json(
            [
                {"role": "system", "content": "严格 JSON 输出。"},
                {"role": "user", "content": prompt},
            ],
        )
        if isinstance(result, list):
            return [r for r in result if isinstance(r, dict)]
        logger.warning("LLM match 返回非 list: %s", type(result))
        return []
    except Exception as e:  # noqa: BLE001
        logger.exception("LLM match 失败: %s", e)
        return []


# ------------------------- 主入口 -------------------------


def plan_fill(
    profile: UserProfile,
    fields: List[PageField],
    files: List[UserFileMeta],
    llm: Optional[LLMClient] = None,
) -> FillPlan:
    """把 Profile + 页面 fields + 用户文件映射为 FillPlan。"""
    actions: List[FillAction] = []
    matched: List[str] = []
    unmatched: List[str] = []
    file_names = [f.name for f in files]

    # 找出规则未命中的字段，留给 LLM
    need_llm: List[PageField] = []

    for f in fields:
        if f.tag == "file":
            # 文件字段直接走文件推断
            cls = _classify_file_field(f, file_names)
            if cls is not None:
                idx, purpose = cls
                actions.append(
                    FillAction(
                        selector=f.selector,
                        action="set_file",
                        file_index=idx,
                        delay_ms=200,
                    )
                )
                matched.append(f.label_text or f.name or f.selector)
            else:
                unmatched.append(f.label_text or f.name or f.selector)
            continue

        # 普通字段先尝试规则
        value = _match_field_by_rule(f, profile)
        if value:
            if f.tag == "select":
                actions.append(
                    FillAction(selector=f.selector, action="set_select", value=value, delay_ms=150)
                )
            elif f.input_type == "checkbox":
                lower = value.lower()
                action = "check" if lower in ("是", "yes", "true", "1", "y") else "uncheck"
                actions.append(FillAction(selector=f.selector, action=action, delay_ms=100))
            else:
                actions.append(
                    FillAction(selector=f.selector, action="type", value=value, delay_ms=150)
                )
            matched.append(f.label_text or f.name or f.selector)
        else:
            need_llm.append(f)

    # LLM 兜底未匹配字段
    if need_llm and llm is not None:
        llm_results = _llm_match(need_llm, profile, llm)
        selector_to_field = {f.selector: f for f in need_llm}
        for r in llm_results:
            sel = r.get("selector", "")
            field = selector_to_field.get(sel)
            if field is None:
                # 尝试按 #N 编号匹配
                m = re.match(r"#(\d+)", str(sel))
                if m:
                    idx = int(m.group(1)) - 1
                    if 0 <= idx < len(need_llm):
                        field = need_llm[idx]
            if field is None:
                continue

            profile_key = r.get("profile_key", "-")
            value = r.get("value", "")
            if profile_key and profile_key != "-":
                # 从 profile 取值
                if profile_key in SINGLE_VALUE_FIELDS:
                    actual = _get_profile_value(profile, profile_key)
                elif profile_key == "educations" and profile.educations:
                    # 简化：动态列表字段（学校/专业等）取第一项
                    e = profile.educations[0]
                    mapping = {
                        "school": e.school,
                        "major": e.major,
                        "degree": e.degree,
                        "start": e.start,
                        "end": e.end,
                    }
                    actual = mapping.get(value, "")  # value 在这里是子字段
                else:
                    actual = _get_profile_value(profile, profile_key)
            else:
                actual = value

            if not actual:
                unmatched.append(field.label_text or field.name or field.selector)
                continue

            if field.tag == "select":
                actions.append(
                    FillAction(selector=field.selector, action="set_select", value=str(actual), delay_ms=150)
                )
            elif field.input_type == "checkbox":
                lv = str(actual).lower()
                action = "check" if lv in ("是", "yes", "true", "1", "y") else "uncheck"
                actions.append(FillAction(selector=field.selector, action=action, delay_ms=100))
            else:
                actions.append(
                    FillAction(selector=field.selector, action="type", value=str(actual), delay_ms=150)
                )
            matched.append(field.label_text or field.name or field.selector)
            # 标记已处理
            selector_to_field.pop(field.selector, None)

        # LLM 没返回的字段加入 unmatched
        for f in need_llm:
            if f.selector in selector_to_field:
                unmatched.append(f.label_text or f.name or f.selector)
    else:
        for f in need_llm:
            unmatched.append(f.label_text or f.name or f.selector)

    notes_parts: List[str] = []
    notes_parts.append(f"匹配成功 {len(matched)} 项")
    if unmatched:
        notes_parts.append(f"未匹配 {len(unmatched)} 项: " + ", ".join(unmatched[:8]))

    return FillPlan(
        actions=actions,
        notes="; ".join(notes_parts),
        matched_count=len(matched),
        unmatched_fields=unmatched,
    )
