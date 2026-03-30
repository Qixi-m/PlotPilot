# aitext 架构设计

> 自动长篇小说：多阶段 LLM 流水线（圣经 + 大纲 → 章纲 → 正文 → 滚动摘要 → 合并），分层对齐 [aivideo](../aivideo/docs/ARCHITECTURE.md)。

## 系统概览

- **输入**：书名、梗概、类型、章数、每章目标字数、风格提示。
- **输出**：项目目录下 `manifest.json`、`bible.json`、`outline.json`、`beats/chapter_NNN.json`、`chapters/chapter_NNN_标题.md`、`running_summary.json`、`novel.md`。

## 分层

| 层 | 路径 | 职责 |
|----|------|------|
| CLI | `cli/run.py` | `init` / `plan` / `write` / `run` / `export`；加载包根 `.env` |
| Pipeline | `pipeline/runner.py`, `pipeline/confirm.py` | 阶段编排、断点续写、长任务确认 |
| Story | `story/models.py`, `prompts.py`, `engine.py`, `jsonutil.py` | Pydantic 模型、提示词、生成与落盘辅助 |
| Clients | `clients/llm.py` | 方舟 SDK，`quiet` 默认减少刷屏 |
| Config | `config/settings.py` | `PROJECTS_DIR`、`ARK_*`、`AITEXT_*` 默认篇幅 |

## 数据流

1. **init**：在 `output/novels/<slug>/` 创建目录与 `manifest.json`。
2. **plan (S1)**：`generate_bible_and_outline` → `bible.json` + `outline.json`，`current_stage=planned`。
3. **write (S2–S3)**：对每章 `generate_chapter_beats` → `generate_chapter_draft` → 可选 `continuity_light_revision` → `update_running_summary`；更新 `completed_chapters`。
4. **export (S5)**：`assemble_novel` 按 `outline` 章节顺序合并 `chapters/*.md` → `novel.md`。

## 环境变量

与 aivideo 共用：`ARK_API_KEY`、`ARK_BASE_URL`、`ARK_MODEL`、`ARK_TIMEOUT`、`ARK_REASONING_EFFORT`、`ARK_NO_PROXY`。

可选：`AITEXT_DEFAULT_CHAPTERS`、`AITEXT_DEFAULT_WORDS_PER_CHAPTER`、`AITEXT_SUMMARY_MAX_CHAPTERS`。

## Web 前端（Vue）

- 前端目录：`web-app/`（Vue 3 + Vite + Naive UI）。入口页：`/`；工作台：`/book/:slug/workbench`。
- 开发启动：在一个终端运行 `python -m aitext serve --port 8005`，另一个终端在 `web-app/` 运行 `npm run dev -- --port 3001`（Vite 通过 `/api` 代理到后端）。也可直接运行 `python aitext/run_server.py` 一键启动。
- 功能：书目建档、结构规划与撰稿任务、对话流上下文管理、设定库/人物关系/叙事知识维护、章节校阅与审定；审定数据写入各项目根目录 `editorial.json`。

## 入口

```bash
python -m aitext init --title "..." --premise "..."
python -m aitext plan <slug>
python -m aitext write <slug> --from 1 --to 3
python -m aitext run <slug> -y
python -m aitext export <slug>
python -m aitext serve --port 8005
# 前端（另开终端）
cd web-app
npm run dev -- --port 3001
```

## 测试

```bash
cd d:\CODE\aitext
python -m pytest tests -v
```
