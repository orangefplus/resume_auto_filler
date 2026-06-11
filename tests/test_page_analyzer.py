"""Page Analyzer 单元测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models.schemas import PageField
from backend.services.page_analyzer import field_text_signals, summarize_fields


def test_summarize_fields_includes_required_signals():
    fields = [
        PageField(
            selector="#name", tag="input", input_type="text",
            name="username", id="name", label_text="姓名",
            placeholder="请输入姓名", required=True,
        ),
        PageField(
            selector="#file_resume", tag="file", input_type="file",
            name="resume", label_text="简历附件", required=True,
        ),
    ]
    text = summarize_fields(fields)
    assert "#1" in text
    assert "姓名" in text
    assert "required" in text
    assert "#2" in text
    assert "简历附件" in text
    assert "file" in text
    print("✓ test_summarize_fields_includes_required_signals")


def test_field_text_signals_lowercases():
    f = PageField(
        selector="#x", tag="input", input_type="text",
        name="Email", id="X", label_text="邮 箱", placeholder="Please enter",
        aria_label="email-input",
    )
    sigs = field_text_signals(f)
    joined = " ".join(sigs)
    # 大小写被压平
    assert "email" in joined
    assert "邮箱" not in joined  # 中文保留原文
    assert "email-input" in joined
    print("✓ test_field_text_signals_lowercases")


if __name__ == "__main__":
    test_summarize_fields_includes_required_signals()
    test_field_text_signals_lowercases()
    print("\nAll tests passed.")
