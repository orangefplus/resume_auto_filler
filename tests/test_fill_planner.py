"""Fill Planner 单元测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models.schemas import (
    EducationItem,
    PageField,
    UserFileMeta,
    UserProfile,
)
from backend.services.fill_planner import (
    _classify_file_field,
    _match_field_by_rule,
    plan_fill,
)


def test_rule_match_name():
    f = PageField(
        selector="input#name",
        tag="input",
        input_type="text",
        name="username",
        id="name",
        label_text="姓名",
    )
    profile = UserProfile(name="张三")
    val = _match_field_by_rule(f, profile)
    assert val == "张三"
    print("✓ test_rule_match_name")


def test_rule_match_email():
    f = PageField(
        selector="input#email",
        tag="input",
        input_type="email",
        name="email",
        label_text="邮箱",
    )
    profile = UserProfile(email="a@b.com")
    assert _match_field_by_rule(f, profile) == "a@b.com"
    print("✓ test_rule_match_email")


def test_rule_no_match():
    f = PageField(
        selector="input#xx",
        tag="input",
        input_type="text",
        name="xxx",
        label_text="完全无关的字段",
    )
    profile = UserProfile()
    assert _match_field_by_rule(f, profile) is None
    print("✓ test_rule_no_match")


def test_classify_file_field_resume():
    f = PageField(
        selector="input[type=file]",
        tag="file",
        input_type="file",
        name="resume",
        label_text="简历附件",
    )
    files = [UserFileMeta(name="张三_简历.pdf")]
    res = _classify_file_field(f, [f.name for f in files])
    assert res is not None
    idx, purpose = res
    assert idx == 0
    assert purpose == "resume"
    print("✓ test_classify_file_field_resume")


def test_classify_file_field_avatar():
    f = PageField(
        selector="input[type=file]",
        tag="file",
        input_type="file",
        name="avatar",
        label_text="个人照片",
    )
    files = [UserFileMeta(name="简历.pdf"), UserFileMeta(name="photo.jpg")]
    res = _classify_file_field(f, [f.name for f in files])
    assert res is not None
    idx, purpose = res
    assert idx == 1
    assert purpose == "avatar"
    print("✓ test_classify_file_field_avatar")


def test_plan_fill_full():
    fields = [
        PageField(selector="#name", tag="input", input_type="text", name="name", id="name", label_text="姓名"),
        PageField(selector="#email", tag="input", input_type="email", name="email", id="email", label_text="邮箱"),
        PageField(selector="#phone", tag="input", input_type="tel", name="phone", id="phone", label_text="手机"),
        PageField(selector="#resume", tag="file", input_type="file", name="resume", label_text="简历附件"),
    ]
    profile = UserProfile(
        name="李四",
        email="li@si.com",
        phone="13900000000",
    )
    files = [UserFileMeta(name="简历.pdf")]
    plan = plan_fill(profile, fields, files, llm=None)

    # 4 个动作：3 type + 1 set_file
    assert len(plan.actions) == 4, plan.actions
    types = [a.action for a in plan.actions]
    assert types.count("type") == 3
    assert types.count("set_file") == 1
    assert plan.matched_count == 4
    assert plan.unmatched_fields == []
    print("✓ test_plan_fill_full")


def test_plan_fill_partial_match():
    fields = [
        PageField(selector="#x", tag="input", input_type="text", name="x", label_text="完全不存在的字段名"),
    ]
    profile = UserProfile(name="无名")
    plan = plan_fill(profile, fields, [], llm=None)
    # 没匹配上
    assert len(plan.actions) == 0
    assert len(plan.unmatched_fields) == 1
    print("✓ test_plan_fill_partial_match")


if __name__ == "__main__":
    test_rule_match_name()
    test_rule_match_email()
    test_rule_no_match()
    test_classify_file_field_resume()
    test_classify_file_field_avatar()
    test_plan_fill_full()
    test_plan_fill_partial_match()
    print("\nAll tests passed.")
