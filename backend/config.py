"""配置文件加载。从同级目录的 config.yml 读取 DashScope Key。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Config:
    dashscope_api_key: str
    base_url: str
    text_model: str
    vision_model: str
    host: str
    port: int
    config_path: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1] / "config.yml")


def load_config(config_path: Optional[str | Path] = None) -> Config:
    """加载 YAML 配置。如果文件不存在则使用环境变量或空 Key。"""
    if config_path is None:
        config_path = Path(__file__).resolve().parents[1] / "config.yml"
    else:
        config_path = Path(config_path)

    defaults = {
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY", ""),
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "text_model": "qwen-plus",
        "vision_model": "qwen-vl-plus",
        "host": "127.0.0.1",
        "port": 8765,
    }

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        defaults.update({k: v for k, v in data.items() if v is not None})

    return Config(**defaults)


_cached_config: Optional[Config] = None


def get_config() -> Config:
    """获取单例配置。"""
    global _cached_config
    if _cached_config is None:
        _cached_config = load_config()
    return _cached_config


def reset_config() -> None:
    """测试用：清空缓存。"""
    global _cached_config
    _cached_config = None
