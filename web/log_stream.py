"""实时日志流：将后端日志通过 SSE 推送到前端"""
import asyncio
import logging
from typing import Set
from queue import Empty, Queue
import threading

# 全局日志队列
_log_queue: Queue = Queue(maxsize=1000)
_subscribers: Set[Queue] = set()
_lock = threading.Lock()


class WebLogHandler(logging.Handler):
    """自定义日志处理器，将日志推送到队列"""

    def emit(self, record: logging.LogRecord):
        try:
            log_entry = {
                'time': self.format_time(record),
                'level': record.levelname,
                'name': record.name,
                'message': record.getMessage()
            }

            # 推送到所有订阅者
            with _lock:
                for queue in list(_subscribers):
                    try:
                        queue.put_nowait(log_entry)
                    except:
                        _subscribers.discard(queue)
        except Exception:
            pass

    def format_time(self, record):
        import time
        ct = time.localtime(record.created)
        return f"{ct.tm_hour:02d}:{ct.tm_min:02d}:{ct.tm_sec:02d}"


def subscribe() -> Queue:
    """订阅日志流"""
    queue = Queue(maxsize=100)
    with _lock:
        _subscribers.add(queue)
    return queue


def unsubscribe(queue: Queue):
    """取消订阅"""
    with _lock:
        _subscribers.discard(queue)


def install_handler():
    """安装日志处理器：将 aitext 与访问日志推送到 SSE 订阅队列"""
    handler = WebLogHandler()
    handler.setLevel(logging.DEBUG)

    # 添加到 aitext 命名空间（子 logger 会向上冒泡到此）
    logger = logging.getLogger("aitext")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    # 访问日志单独挂到 uvicorn.access（名称不在 aitext 下）
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.setLevel(logging.INFO)
    uvicorn_logger.addHandler(handler)
