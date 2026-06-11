"""Pydantic 数据模型：UserProfile、PageField、FillPlan 等。"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ------------------------- User Profile -------------------------


class EducationItem(BaseModel):
    school: str = ""
    major: str = ""
    degree: str = ""          # 学历: 本科 / 硕士 / 博士
    start: str = ""           # 2020-09
    end: str = ""             # 2024-06
    description: str = ""


class InternshipItem(BaseModel):
    company: str = ""
    role: str = ""
    start: str = ""
    end: str = ""
    description: str = ""


class ProjectItem(BaseModel):
    name: str = ""
    role: str = ""
    start: str = ""
    end: str = ""
    description: str = ""


class LanguageItem(BaseModel):
    name: str = ""            # 英语 / 日语
    level: str = ""           # CET-6 / 流利


class UserProfile(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    gender: str = ""          # 男 / 女
    birth_date: str = ""      # 1999-01
    nationality: str = ""     # 汉族
    political_status: str = ""  # 群众 / 共青团员 / 党员
    address: str = ""
    current_city: str = ""
    expected_city: str = ""
    expected_salary: str = ""
    earliest_start_date: str = ""
    educations: List[EducationItem] = Field(default_factory=list)
    internships: List[InternshipItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    languages: List[LanguageItem] = Field(default_factory=list)
    awards: List[str] = Field(default_factory=list)
    self_evaluation: str = ""
    # 兜底：把额外字段以 key->value 形式保存
    custom: Dict[str, str] = Field(default_factory=dict)


class UserFileMeta(BaseModel):
    name: str                            # 文件名（含扩展名）
    size: int = 0
    mime: str = ""


# ------------------------- Page Field -------------------------


class PageField(BaseModel):
    selector: str                                  # 唯一 CSS selector
    tag: Literal["input", "textarea", "select", "file", "button"]
    input_type: Optional[str] = None               # text / email / tel / number / date / radio / checkbox ...
    name: Optional[str] = None
    id: Optional[str] = None
    placeholder: Optional[str] = None
    label_text: Optional[str] = None
    aria_label: Optional[str] = None
    required: bool = False
    options: List[str] = Field(default_factory=list)  # select 的可选值
    in_repeatable_section: bool = False
    section_hint: str = ""                         # "education" / "internship" / ...


# ------------------------- Fill Plan -------------------------


FillActionType = Literal["type", "set_select", "set_file", "click", "check", "uncheck", "clear"]


class FillAction(BaseModel):
    selector: str
    action: FillActionType
    value: Optional[str] = None
    file_index: Optional[int] = None
    section_action: Optional[str] = None     # e.g. "add_education"
    delay_ms: int = 200


class FillPlan(BaseModel):
    actions: List[FillAction] = Field(default_factory=list)
    notes: str = ""
    matched_count: int = 0
    unmatched_fields: List[str] = Field(default_factory=list)


# ------------------------- Request / Response -------------------------


class FillRequest(BaseModel):
    page_url: str
    page_title: str = ""
    fields: List[PageField]
    user_markdown: str
    file_names: List[str] = Field(default_factory=list)


class FillResponse(BaseModel):
    success: bool
    plan: FillPlan
    profile_summary: str = ""
    debug: Optional[Dict] = None
    error: Optional[str] = None
