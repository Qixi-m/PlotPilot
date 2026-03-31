"""AI Generation API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from application.services.ai_generation_service import AIGenerationService
from interfaces.api.dependencies import get_ai_generation_service
from domain.shared.exceptions import EntityNotFoundError


router = APIRouter(prefix="/ai", tags=["ai"])


# Request Models
class GenerateChapterRequest(BaseModel):
    """生成章节请求"""
    novel_id: str = Field(..., description="小说 ID")
    chapter_number: int = Field(..., gt=0, description="章节编号")
    outline: str = Field(..., description="章节大纲")


# Response Models
class GenerateChapterResponse(BaseModel):
    """生成章节响应"""
    content: str = Field(..., description="生成的章节内容")


# Routes
@router.post("/generate-chapter", response_model=GenerateChapterResponse)
async def generate_chapter(
    request: GenerateChapterRequest,
    service: AIGenerationService = Depends(get_ai_generation_service)
):
    """生成章节内容

    Args:
        request: 生成章节请求
        service: AI 生成服务

    Returns:
        生成的章节内容

    Raises:
        HTTPException: 如果小说不存在或生成失败
    """
    try:
        content = await service.generate_chapter(
            novel_id=request.novel_id,
            chapter_number=request.chapter_number,
            outline=request.outline
        )
        return GenerateChapterResponse(content=content)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
