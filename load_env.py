"""加载包根目录 `.env` 到 `os.environ`（与 CLI 行为一致，供 `serve` 使用）。"""
from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
_ENV_PATH = _PACKAGE_ROOT / ".env"


def load_env(path: Path | None = None) -> Path | None:
    """
    读取 KEY=VALUE 行并写入环境变量（覆盖已有键）。
    返回已加载的文件路径；未找到文件则返回 None。
    """
    env_file = path or _ENV_PATH
    if not env_file.is_file():
        return None
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ[k.strip()] = v.strip()
    return env_file
