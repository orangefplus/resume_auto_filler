"""User Info Parser 单元测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.user_info_parser import _quick_extract, parse_user_info
from backend.models.schemas import UserProfile


SAMPLE_MD = """
# 张三的简历

## 基本信息
- 姓名：张三
- 性别：男
- 出生：1999-01
- 手机：13800001234
- 邮箱：zhangsan@example.com
- 居住地：北京

## 教育经历
### 清华大学 - 计算机 - 本科
- 2020-09 至 2024-06

## 自我评价
热爱 AI 技术。
"""


def test_quick_extract_phone_email_gender_birth():
    quick = _quick_extract(SAMPLE_MD)
    assert quick.get("phone") == "13800001234"
    assert quick.get("email") == "zhangsan@example.com"
    assert quick.get("gender") == "男"
    assert "1999" in quick.get("birth_date", "")
    assert quick.get("name") == "张三"
    print("✓ test_quick_extract_phone_email_gender_birth")


def test_parse_user_info_returns_profile():
    profile = parse_user_info(SAMPLE_MD, llm=None)  # 纯规则 fallback
    assert isinstance(profile, UserProfile)
    assert profile.name == "张三"
    assert profile.phone == "13800001234"
    assert profile.email == "zhangsan@example.com"
    assert profile.gender == "男"
    print("✓ test_parse_user_info_returns_profile")


def test_parse_user_info_empty():
    profile = parse_user_info("", llm=None)
    assert profile.name == ""
    assert profile.phone == ""
    print("✓ test_parse_user_info_empty")


def test_parse_user_info_skills():
    md = """
## 技能
- Python, PyTorch, SQL
"""
    profile = parse_user_info(md, llm=None)
    # 规则版不含技能，由 LLM 处理
    assert isinstance(profile.skills, list)
    print("✓ test_parse_user_info_skills")


if __name__ == "__main__":
    test_quick_extract_phone_email_gender_birth()
    test_parse_user_info_returns_profile()
    test_parse_user_info_empty()
    test_parse_user_info_skills()
    print("\nAll tests passed.")
