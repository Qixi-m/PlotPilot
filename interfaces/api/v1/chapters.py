"""Chapter API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel, Field

from application.services.chapter_service import ChapterService
from application.dtos.chapter_dto import ChapterDTO
from interfaces.api.dependencies import get_chapter_service
from domain.shared.exceptions import EntityNotFoundError


router = APIRouter(prefix="/chapters", tags=["chapters"])


# Request Models
class UpdateChapterContentRequest(BaseModel):
    """更新章节内容请求"""
    content: str = Field(..., description="章节内容")


# Routes
@router.get("/{chapter_id}", response_model=ChapterDTO)
async def get_chapter(
    chapter_id: str,
    service: ChapterService = Depends(get_chapter_service)
):
    """获取章节详情

    Args:
        chapter_id: 章节 ID
        service: Chapter 服务

    Returns:
        章节 DTO

    Raises:
        HTTPException: 如果章节不存在
    """
    chapter = service.get_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"Chapter not found: {chapter_id}")
    return chapter


@router.put("/{chapter_id}/content", response_model=ChapterDTO)
async def update_chapter_content(
    chapter_id: str,
    request: UpdateChapterContentRequest,
    service: ChapterService = Depends(get_chapter_service)
):
    """更新章节内容

    Args:
        chapter_id: 章节 ID
        request: 更新内容请求
        service: Chapter 服务

    Returns:
        更新后的章节 DTO

    Raises:
        HTTPException: 如果章节不存在
    """
    try:
        return service.update_chapter_content(chapter_id, request.content)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{chapter_id}", status_code=204)
async def delete_chapter(
    chapter_id: str,
    service: ChapterService = Depends(get_chapter_service)
):
    """删除章节

    Args:
        chapter_id: 章节 ID
        service: Chapter 服务
    """
    service.delete_chapter(chapter_id)


@router.get("/novels/{novel_id}/chapters", response_model=List[ChapterDTO])
async def list_chapters_by_novel(
    novel_id: str,
    service: ChapterService = Depends(get_chapter_service)
):
    """列出小说的所有章节

    Args:
        novel_id: 小说 ID
        service: Chapter 服务

    Returns:
        章节 DTO 列表
    """
    return service.list_chapters_by_novel(novel_id)
