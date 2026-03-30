"""Chroma 向量记忆库（本地持久化），使用 onnxruntime + bge-small-zh-v1.5。

落盘位置：每本书目目录下 `vecdb/`（与项目文件同生命周期）。
支持GPU加速，完全离线运行。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# 尝试使用 pysqlite3 替代内置 sqlite3（解决 Chroma 对 sqlite3 版本要求）
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except (ImportError, KeyError):
    pass

from ..config import Config

logger = logging.getLogger("aitext.web.vector_memory")

_SQLITE_MIN = (3, 35, 0)


def _ensure_sqlite() -> None:
    """Chroma 依赖 sqlite3>=3.35。"""
    import sqlite3

    ver = getattr(sqlite3, "sqlite_version_info", (0, 0, 0))
    if tuple(ver) >= _SQLITE_MIN:
        return
    raise RuntimeError(
        "sqlite3 版本过低，Chroma 无法使用。"
        f"当前 sqlite3={getattr(sqlite3, 'sqlite_version', ver)}，需 >= 3.35.0。\n"
        "解决方式（二选一）：\n"
        "1) 更换/升级 Python 环境（推荐 Python 3.11+，通常自带更高 sqlite3）。\n"
        "2) 改用不依赖 sqlite3 的向量库（如 LanceDB / Qdrant）。"
    )


def _persist_dir(root: Path) -> Path:
    return Path(root) / "vecdb"


_embedder = None


class ONNXEmbedder:
    """使用ONNX Runtime的离线embedding模型"""

    def __init__(self, model_path, tokenizer_path, device='cuda'):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        import numpy as np

        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.np = np

        # 配置ONNX Runtime
        providers = []
        if device == 'cuda':
            providers.append('CUDAExecutionProvider')
        providers.append('CPUExecutionProvider')

        self.session = ort.InferenceSession(str(model_path), providers=providers)
        self.device = device
        logger.info(f"ONNX模型加载成功，使用设备: {self.session.get_providers()}")

    def encode(self, texts):
        """编码文本为向量"""
        if isinstance(texts, str):
            texts = [texts]

        # Tokenize
        encodings = self.tokenizer.encode_batch(texts)

        # 找到最大长度并padding
        max_len = max(len(e.ids) for e in encodings)

        input_ids = []
        attention_mask = []
        for e in encodings:
            ids = e.ids + [0] * (max_len - len(e.ids))  # padding with 0
            mask = e.attention_mask + [0] * (max_len - len(e.attention_mask))
            input_ids.append(ids)
            attention_mask.append(mask)

        input_ids = self.np.array(input_ids, dtype=self.np.int64)
        attention_mask = self.np.array(attention_mask, dtype=self.np.int64)
        token_type_ids = self.np.zeros_like(input_ids, dtype=self.np.int64)

        # 运行推理
        outputs = self.session.run(
            None,
            {
                'input_ids': input_ids,
                'attention_mask': attention_mask,
                'token_type_ids': token_type_ids
            }
        )

        # 提取[CLS] token的embedding (第一个token)
        embeddings = outputs[0][:, 0, :]

        # 归一化
        norms = self.np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms

        return embeddings


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder

    from pathlib import Path
    import torch

    # 检测GPU
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"使用设备: {device}")

    # 本地模型路径
    model_dir = Path.home() / ".cache" / "fastembed" / "Qdrant_bge-small-zh-v1.5"
    model_path = model_dir / "model_optimized.onnx"
    tokenizer_path = model_dir / "tokenizer.json"

    if not model_path.exists():
        raise RuntimeError(f"模型文件不存在: {model_path}\n请先下载模型文件")

    if not tokenizer_path.exists():
        raise RuntimeError(f"Tokenizer文件不存在: {tokenizer_path}\n请先下载tokenizer文件")

    try:
        _embedder = ONNXEmbedder(model_path, tokenizer_path, device=device)
        logger.info("模型加载成功（完全离线）")
    except Exception as e:
        logger.error(f"加载模型失败: {e}")
        raise

    return _embedder


def _passage_embed(texts: List[str]) -> List[List[float]]:
    emb = _get_embedder()
    vecs = emb.encode(texts)
    return vecs.tolist()


def _query_embed(text: str) -> List[float]:
    emb = _get_embedder()
    vec = emb.encode([text])[0]
    return vec.tolist()


def _get_collection(root: Path):
    _ensure_sqlite()
    try:
        import chromadb  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("缺少 chromadb 依赖，请 pip install chromadb") from e
    pdir = _persist_dir(root)
    pdir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(pdir))
    return client.get_or_create_collection(name="mem")


def upsert_docs(
    root: Path,
    ids: List[str],
    documents: List[str],
    metadatas: Optional[List[Dict[str, Any]]] = None,
) -> None:
    if not ids or not documents:
        return
    if len(ids) != len(documents):
        raise ValueError("ids/documents 长度不一致")
    if metadatas is not None and len(metadatas) != len(documents):
        raise ValueError("metadatas 长度不一致")
    col = _get_collection(root)
    vecs = _passage_embed(documents)
    col.upsert(ids=ids, embeddings=vecs, documents=documents, metadatas=metadatas)


def query(
    root: Path,
    text: str,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    q = (text or "").strip()
    if not q:
        return []
    col = _get_collection(root)
    vec = _query_embed(q)
    n = int(top_k if top_k is not None else Config.VECTOR_TOP_K)
    res = col.query(query_embeddings=[vec], n_results=max(1, n), include=["documents", "metadatas", "distances"])
    out: List[Dict[str, Any]] = []
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for i in range(min(len(docs), n)):
        doc = str(docs[i] or "")
        if len(doc) > Config.VECTOR_MAX_SNIPPET_CHARS:
            doc = doc[: Config.VECTOR_MAX_SNIPPET_CHARS] + "…"
        out.append(
            {
                "id": ids[i] if i < len(ids) else None,
                "text": doc,
                "meta": metas[i] if i < len(metas) else None,
                "distance": dists[i] if i < len(dists) else None,
            }
        )
    return out

