"""Novel API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel, Field

from application.services.novel_service import NovelService
from application.dtos.novel_dto import NovelDTO
from interfaces.api.dependencies import get_novel_service
from domain.shared.exceptions import EntityNotFoundError


router = APIRouter(prefix="/novels", tags=["novels"])


# Request Models
class CreateNovelRequest(BaseModel):
    """创建小说请求"""
    novel_id: str = Field(..., description="小说 ID")
    title: str = Field(..., description="小说标题")
    author: str = Field(..., description="作者")
    target_chapters: int = Field(..., gt=0, description="目标章节数")


class UpdateStageRequest(BaseModel):
    """更新阶段请求"""
    stage: str = Field(..., description="小说阶段")


# Routes
@router.post("/", response_model=NovelDTO, status_code=201)
async def create_novel(
    request: CreateNovelRequest,
    service: NovelService = Depends(get_novel_service)
):
    """创建新小说

    Args:
        request: 创建小说请求
        service: Novel 服务

    Returns:
        创建的小说 DTO
    """
    return service.create_novel(
        novel_id=request.novel_id,
        title=request.title,
        author=request.author,
        target_chapters=request.target_chapters
    )


@router.get("/{novel_id}", response_model=NovelDTO)
async def get_novel(
    novel_id: str,
    service: NovelService = Depends(get_novel_service)
):
    """获取小说详情

    Args:
        novel_id: 小说 ID
        service: Novel 服务

    Returns:
        小说 DTO

    Raises:
        HTTPException: 如果小说不存在
    """
    novel = service.get_novel(novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail=f"Novel not found: {novel_id}")
    return novel


@router.get("/", response_model=List[NovelDTO])
async def list_novels(service: NovelService = Depends(get_novel_service)):
    """列出所有小说

    Args:
        service: Novel 服务

    Returns:
        小说 DTO 列表
    """
    return service.list_novels()


@router.put("/{novel_id}/stage", response_model=NovelDTO)
async def update_novel_stage(
    novel_id: str,
    request: UpdateStageRequest,
    service: NovelService = Depends(get_novel_service)
):
    """更新小说阶段

    Args:
        novel_id: 小说 ID
        request: 更新阶段请求
        service: Novel 服务

    Returns:
        更新后的小说 DTO

    Raises:
        HTTPException: 如果小说不存在
    """
    try:
        return service.update_novel_stage(novel_id, request.stage)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    service: NovelService = Depends(get_novel_service)
):
    """删除小说

    Args:
        novel_id: 小说 ID
        service: Novel 服务
    """
    service.delete_novel(novel_id)


@router.get("/{novel_id}/statistics")
async def get_novel_statistics(
    novel_id: str,
    service: NovelService = Depends(get_novel_service)
):
    """获取小说统计信息

    Args:
        novel_id: 小说 ID
        service: Novel 服务

    Returns:
        统计信息字典

    Raises:
        HTTPException: 如果小说不存在
    """
    try:
        return service.get_novel_statistics(novel_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
