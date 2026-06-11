"""把扩展传来的 PageField 列表归一化为 LLM 友好的字符串表格。

这一步纯字符串处理，不消耗 LLM 配额。
"""
from __future__ import annotations

from typing import List

from backend.models.schemas import PageField


def summarize_fields(fields: List[PageField]) -> str:
    """生成形如下面的表格，便于 LLM 一次性理解所有字段：

    #1 [text-input] name=username  id=#name  label="姓名"  placeholder="请输入姓名"  required=true
    #2 [file-input] name=resume  label="简历附件"  required=true
    #3 [select]  name=gender  options=["男","女"]
    """
    lines: List[str] = []
    for i, f in enumerate(fields, 1):
        parts = [f"#{i}", f"[{f.tag}{':' + f.input_type if f.input_type else ''}]"]
        if f.name:
            parts.append(f"name={f.name}")
        if f.id:
            parts.append(f"id={f.id}")
        if f.label_text:
            parts.append(f'label="{f.label_text}"')
        if f.aria_label:
            parts.append(f'aria="{f.aria_label}"')
        if f.placeholder:
            parts.append(f'placeholder="{f.placeholder}"')
        if f.required:
            parts.append("required")
        if f.options:
            opts = ",".join(f.options[:10]) + ("..." if len(f.options) > 10 else "")
            parts.append(f"options=[{opts}]")
        if f.in_repeatable_section:
            parts.append(f"section={f.section_hint or '?'}*")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def field_text_signals(field: PageField) -> List[str]:
    """提取一个字段所有可能的"文本信号"，用于规则匹配。

    包括 label / placeholder / aria / name / id。
    """
    sigs: List[str] = []
    for s in (field.label_text, field.placeholder, field.aria_label, field.name, field.id):
        if s:
            sigs.append(s.lower())
    return sigs
