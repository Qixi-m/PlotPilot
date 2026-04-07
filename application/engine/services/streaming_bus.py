"""流式消息总线 - 用于自动驾驶守护进程与 SSE 接口之间的实时通信

守护进程在独立进程中运行，SSE 接口在主进程中运行。
使用内存队列 + 轮询方式实现跨进程通信（简化方案）。

注意：这是一个简化实现，使用文件系统作为消息传递媒介。
在生产环境中，应该使用 Redis pub/sub 或消息队列。
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)

# 使用内存队列存储流式内容（进程内）
# 由于守护进程在独立进程中运行，这里使用共享文件作为后备
_stream_queues: Dict[str, List[str]] = defaultdict(list)
_stream_positions: Dict[str, int] = defaultdict(int)
_lock = threading.Lock()

# 共享文件路径（用于跨进程通信）
_STREAM_DIR = Path(__file__).parent.parent.parent.parent / "data" / "streaming"


def _ensure_stream_dir():
    """确保流式目录存在"""
    _STREAM_DIR.mkdir(parents=True, exist_ok=True)


class StreamingBus:
    """流式消息总线 - 发布/订阅模式"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        # 跨进程读取位置追踪（每个 novel_id 的文件读取位置）
        self._file_positions: Dict[str, int] = defaultdict(int)
    
    def publish(self, novel_id: str, chunk: str):
        """发布增量文字"""
        # 内存队列
        with _lock:
            _stream_queues[novel_id].append(chunk)
            # 限制队列长度，避免内存溢出
            if len(_stream_queues[novel_id]) > 10000:
                _stream_queues[novel_id] = _stream_queues[novel_id][-5000:]
        
        # 写入共享文件（跨进程）- 使用行式 JSON 格式，便于增量读取
        try:
            _ensure_stream_dir()
            file_path = _STREAM_DIR / f"{novel_id}.stream"
            with open(file_path, "a", encoding="utf-8") as f:
                # 每行一个 JSON 对象，包含时间戳和内容
                record = json.dumps({"c": chunk, "t": time.time()}, ensure_ascii=False)
                f.write(record + "\n")
        except Exception as e:
            logger.warning(f"Failed to write streaming file: {e}")
        
        # 通知订阅者
        for queue in self._subscribers.get(novel_id, []):
            try:
                queue.put_nowait(chunk)
            except asyncio.QueueFull:
                pass
    
    def subscribe(self, novel_id: str) -> asyncio.Queue:
        """订阅增量文字"""
        queue = asyncio.Queue(maxsize=1000)
        self._subscribers[novel_id].append(queue)
        return queue
    
    def unsubscribe(self, novel_id: str, queue: asyncio.Queue):
        """取消订阅"""
        if novel_id in self._subscribers:
            try:
                self._subscribers[novel_id].remove(queue)
            except ValueError:
                pass
    
    def get_content_from_file(self, novel_id: str, position: int = 0) -> tuple:
        """从共享文件读取内容（用于跨进程）

        读取增量内容（从上次位置开始的新内容）。
        
        支持两种文件格式：
        - 新格式：每行一个 JSON 对象 {"c": "chunk", "t": timestamp}
        - 旧格式：纯文本追加
        
        Returns:
            (content, new_position) 新内容和新的读取位置
            content 可能是空字符串（无新内容）
        """
        try:
            file_path = _STREAM_DIR / f"{novel_id}.stream"
            if not file_path.exists():
                return "", position
            
            new_position = position
            
            # 直接读取从位置到文件末尾的所有内容
            with open(file_path, "r", encoding="utf-8") as f:
                f.seek(position)
                content = f.read()
                new_position = f.tell()
            
            # 如果内容为空，直接返回
            if not content:
                return "", position
            
            # 尝试按行解析 JSON（新格式）
            # 如果解析失败，说明是旧格式，直接返回原始内容
            chunks = []
            has_json_format = True
            
            lines = content.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    chunk = record.get("c", "")
                    if chunk:
                        chunks.append(chunk)
                except json.JSONDecodeError:
                    # 如果有任何一行不是 JSON，说明是旧格式
                    has_json_format = False
                    break
            
            if has_json_format and chunks:
                return "".join(chunks), new_position
            else:
                # 旧格式：直接返回原始内容
                return content, new_position
            
        except Exception as e:
            logger.warning(f"Failed to read streaming file: {e}")
            return "", position
    
    def clear(self, novel_id: str):
        """清空流式内容"""
        with _lock:
            _stream_queues[novel_id] = []
        
        try:
            file_path = _STREAM_DIR / f"{novel_id}.stream"
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
        
        # 重置文件读取位置
        if novel_id in self._file_positions:
            del self._file_positions[novel_id]


# 全局单例
streaming_bus = StreamingBus()
