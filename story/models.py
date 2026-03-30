"""小说项目 Pydantic 模型：manifest、bible、outline、章纲、滚动摘要。"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Stage = Literal["init", "planned", "writing", "completed"]


class NovelManifest(BaseModel):
    novel_id: str
    slug: str
    title: str
    premise: str
    genre: str = ""
    target_chapter_count: int = Field(ge=1, default=5)
    target_words_per_chapter: int = Field(ge=500, default=2500)
    current_stage: Stage = "init"
    completed_chapters: List[int] = Field(default_factory=list)
    style_hint: str = ""

    def mark_planned(self) -> None:
        self.current_stage = "planned"

    def mark_writing(self) -> None:
        self.current_stage = "writing"

    def mark_completed(self) -> None:
        self.current_stage = "completed"

    def is_chapter_done(self, chapter_id: int) -> bool:
        return chapter_id in self.completed_chapters

    def register_chapter_done(self, chapter_id: int) -> None:
        if chapter_id not in self.completed_chapters:
            self.completed_chapters.append(chapter_id)
            self.completed_chapters.sort()


class OutlineChapter(BaseModel):
    id: int = Field(ge=1)
    title: str
    one_liner: str


class Outline(BaseModel):
    chapters: List[OutlineChapter] = Field(default_factory=list)


class BibleCharacter(BaseModel):
    name: str
    role: str = ""
    traits: str = ""
    arc_note: str = ""


class BibleLocation(BaseModel):
    name: str
    description: str = ""


class Bible(BaseModel):
    characters: List[BibleCharacter] = Field(default_factory=list)
    locations: List[BibleLocation] = Field(default_factory=list)
    timeline_notes: List[str] = Field(default_factory=list)
    style_notes: str = ""


class CastStoryEvent(BaseModel):
    """人物或人物关系上的具体剧情事件（里程碑、共同经历等），供检索与 ReAct 工具展示。"""

    id: str = Field(..., min_length=1, max_length=80)
    summary: str = Field(default="", max_length=4000)
    chapter_id: Optional[int] = Field(default=None, ge=1)
    # normal | key —— 关键事件在摘要注入时优先列出
    importance: str = Field(default="normal", max_length=16)


class CastCharacter(BaseModel):
    """人物表节点（与 bible 人物可并行维护，关系网专用 id）。"""

    id: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=120)
    aliases: List[str] = Field(default_factory=list)
    role: str = ""
    traits: str = ""
    note: str = ""
    story_events: List[CastStoryEvent] = Field(default_factory=list)


class CastRelationship(BaseModel):
    """人物关系边。"""

    id: str = Field(..., min_length=1, max_length=80)
    source_id: str = Field(..., min_length=1, max_length=80)
    target_id: str = Field(..., min_length=1, max_length=80)
    label: str = ""
    note: str = ""
    directed: bool = True
    story_events: List[CastStoryEvent] = Field(default_factory=list)


class CastGraph(BaseModel):
    """人物落表 + 关系网（独立文件 cast_graph.json）。"""

    version: int = 2
    characters: List[CastCharacter] = Field(default_factory=list)
    relationships: List[CastRelationship] = Field(default_factory=list)


class ChapterNarrativeEntry(BaseModel):
    """单章叙事摘要（防跑篇、对齐大纲）；可由工具 story_upsert_chapter_summary 写入。"""

    chapter_id: int = Field(ge=1)
    summary: str = ""
    key_events: str = ""
    open_threads: str = ""
    consistency_note: str = ""
    # 大纲下的子段落 / 节拍（每元素一条，便于按章拆分上下文）
    beat_sections: List[str] = Field(default_factory=list)
    # 与全书上下文的同步状态：draft 草稿 | synced 已对齐 | stale 待重扫
    sync_status: str = Field(default="draft", max_length=32)


class KnowledgeTriple(BaseModel):
    """知识图谱三元组（可与人物 id 或纯文本实体混用）。"""

    id: str = Field(..., min_length=1, max_length=80)
    subject: str = ""
    predicate: str = ""
    object: str = ""
    chapter_id: Optional[int] = Field(default=None, ge=1)
    note: str = ""


class StoryKnowledge(BaseModel):
    """全书知识图谱 + 章级摘要（novel_knowledge.json）。"""

    version: int = 1
    premise_lock: str = ""
    chapters: List[ChapterNarrativeEntry] = Field(default_factory=list)
    facts: List[KnowledgeTriple] = Field(default_factory=list)


class BibleOutlineBundle(BaseModel):
    """单次 LLM 返回：圣经 + 大纲。"""

    bible: Bible
    outline: Outline


class ChapterBeatScene(BaseModel):
    summary: str
    setting: Optional[str] = None


class ChapterBeats(BaseModel):
    chapter_id: int = Field(ge=1)
    chapter_title: str = ""
    pov: str = ""
    scenes: List[ChapterBeatScene] = Field(default_factory=list)
    must_resolve: str = ""
    foreshadow_refs: List[str] = Field(default_factory=list)


class SummaryEntry(BaseModel):
    chapter_id: int
    summary: str


class RunningSummary(BaseModel):
    entries: List[SummaryEntry] = Field(default_factory=list)


class ChapterFolderRelations(BaseModel):
    """章节目录内：与前后章、并行线的编务关系（章号仍全书连续）。"""

    follows: Optional[int] = Field(default=None, description="叙事上紧接的章号，默认可空")
    parallels: List[int] = Field(default_factory=list, description="并行剧情线涉及的章号")
    notes: str = Field(default="", description="结构说明，供编务/模型理解")


class ChapterFolderMeta(BaseModel):
    """chapters/{nnn}/chapter.json — 与正文文件并列，描述分场景片段与关系。"""

    version: int = 1
    chapter_id: int = Field(ge=1)
    title: str = ""
    use_parts: bool = Field(
        default=False,
        description="为 true 时只拼接 parts_order 下列文件；为 false 时以 body.md 为准",
    )
    parts_order: List[str] = Field(
        default_factory=list,
        description="相对章节目录的路径，如 parts/01.md",
    )
    relations: ChapterFolderRelations = Field(default_factory=ChapterFolderRelations)
