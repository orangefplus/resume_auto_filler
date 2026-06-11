"""FastAPI 入口。"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# 把项目根加入 sys.path，方便 `uvicorn backend.main:app` 直接启动
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agent.resume_agent import ResumeFillAgent
from backend.config import get_config
from backend.models.schemas import (
    FillPlan,
    FillRequest,
    FillResponse,
    PageField,
    UserFileMeta,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backend")

app = FastAPI(
    title="简历自动填写助手 API",
    description="接收 Chrome 扩展传来的页面字段 + 用户 Markdown 简历，返回 FillPlan。",
    version="1.0.0",
)

# CORS：Chrome 扩展 + 本地调试
ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8765",
    "http://127.0.0.1",
    "http://127.0.0.1:8765",
    "chrome-extension://*",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 简化：允许所有（本地后端风险可控）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 单例 Agent
_agent: ResumeFillAgent | None = None


def get_agent() -> ResumeFillAgent:
    global _agent
    if _agent is None:
        _agent = ResumeFillAgent()
    return _agent


@app.get("/api/health")
async def health():
    cfg = get_config()
    has_key = bool(cfg.dashscope_api_key and cfg.dashscope_api_key.strip())
    return {
        "status": "ok",
        "model": cfg.text_model,
        "api_key_configured": has_key,
        "host": cfg.host,
        "port": cfg.port,
    }


@app.post("/api/fill", response_model=FillResponse)
async def fill(req: FillRequest):
    """主接口：接收页面 fields + 用户 Markdown + 文件元信息，返回 FillPlan。"""
    if not req.user_markdown.strip():
        return FillResponse(
            success=False,
            plan=FillPlan(actions=[], notes="用户未提供简历文本"),
            error="user_markdown is empty",
        )

    try:
        agent = get_agent()
        file_metas = [
            UserFileMeta(name=n, size=0, mime="")
            for n in (req.file_names or [])
        ]
        result = agent.run(
            page_url=req.page_url,
            page_title=req.page_title,
            fields=[PageField(**f.model_dump()) for f in req.fields],
            user_markdown=req.user_markdown,
            files=file_metas,
        )
        return FillResponse(
            success=True,
            plan=FillPlan(**result.get("plan") or {"actions": []}),
            profile_summary=result.get("profile_summary", ""),
            error=result.get("error"),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("fill 失败: %s", e)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "plan": {"actions": [], "notes": str(e)},
                "error": str(e),
            },
        )


def run():
    """`python -m backend.main` 入口。"""
    import uvicorn

    cfg = get_config()
    uvicorn.run(
        "backend.main:app",
        host=cfg.host,
        port=cfg.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
