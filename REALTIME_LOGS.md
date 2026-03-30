# 实时日志功能说明

## 功能概述

前端现在可以实时显示所有后端操作日志，包括：
- API 请求/响应
- LLM 调用过程
- 对话消息处理
- 任务执行状态
- 错误和警告信息

## 技术实现

### 后端

1. **日志流模块** (`web/log_stream.py`)
   - 自定义日志处理器 `WebLogHandler`
   - 将日志推送到订阅队列
   - 支持多个客户端同时订阅

2. **SSE 端点** (`/api/logs/stream`)
   - 使用 Server-Sent Events 推送日志
   - 自动心跳保持连接
   - 客户端断开自动清理

3. **日志增强**
   - 所有关键操作都添加了 `print(flush=True)` 和 `logger` 双重输出
   - 包含时间戳、日志级别、模块名称、详细消息

### 前端

1. **日志面板组件** (`components/LogPanel.vue`)
   - VS Code 风格的终端界面
   - 颜色区分日志级别（INFO/DEBUG/ERROR/WARNING）
   - 自动滚动到最新日志
   - 清空和暂停滚动功能
   - 限制最多 500 条日志

2. **工作台集成** (`views/Workbench.vue`)
   - 右侧面板可切换"设定库"和"实时日志"
   - 自动连接日志流
   - 断线自动重连（5秒后）
   - 流式对话输出
   - 停止生成按钮

## 使用方法

### 启动服务

```bash
cd D:/CODE
python -m aitext serve --host 127.0.0.1 --port 8005
```

### 前端访问

1. 打开浏览器访问 `http://localhost:3001`
2. 进入任意书目的工作台
3. 点击"显示日志"按钮
4. 实时查看所有后端操作

## 日志示例

```
00:18:37 INFO    [aitext.web.app] >>> GET /api/books
00:18:37 INFO    [aitext.web.app] GET /api/books - 获取书籍列表
00:18:37 DEBUG   [aitext.web.app] 返回 4 本书籍
00:18:37 INFO    [aitext.web.app] <<< GET /api/books - 200

00:19:15 INFO    [aitext.web.app] >>> POST /api/book/test/chat/stream
00:19:15 INFO    [aitext.clients.llm_stream] [LLM Stream] 开始流式请求，消息数: 5
00:19:15 DEBUG   [aitext.clients.llm_stream] [LLM Stream] Model: claude-sonnet-4-6
00:19:15 INFO    [aitext.clients.llm_stream] [LLM Stream] 发送请求到 API...
00:19:16 INFO    [aitext.clients.llm_stream] [LLM Stream] 收到响应，状态码: 200
00:19:18 INFO    [aitext.clients.llm_stream] [LLM Stream] 流式响应完成，共 45 个文本块
00:19:18 INFO    [aitext.web.app] <<< POST /api/book/test/chat/stream - 200
```

## 已实现的功能

✅ 实时日志流（SSE）
✅ 日志面板组件
✅ 流式对话输出
✅ 停止生成按钮
✅ 自动重连机制
✅ 日志级别颜色区分
✅ 自动滚动
✅ 清空日志
✅ 暂停/恢复滚动

## 下一步优化

- [ ] 日志过滤（按级别、模块）
- [ ] 日志搜索
- [ ] 日志导出
- [ ] 性能监控面板
- [ ] 请求耗时统计
