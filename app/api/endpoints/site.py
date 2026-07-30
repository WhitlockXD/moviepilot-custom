"""
站点管理 API 端点
PT站点功能已移除，所有接口返回空结果
"""
from typing import List, Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core.security import verify_token
from app.db import get_async_db
from app.db.models import User
from app.db.user_oper import (
    get_current_active_manage_user_async,
    get_current_active_superuser_async,
)

router = APIRouter()


@router.get("/", summary="所有站点", response_model=List[schemas.Site])
async def read_sites(
    db: AsyncSession = Depends(get_async_db),
    _: User = Depends(get_current_active_manage_user_async),
) -> List[dict]:
    """获取站点列表（PT站点功能已移除）"""
    return []


@router.post("/", summary="新增站点", response_model=schemas.Response)
async def add_site(
    *,
    site_in: schemas.Site,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """新增站点（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.put("/", summary="更新站点", response_model=schemas.Response)
async def update_site(
    *,
    site_in: schemas.Site,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """更新站点信息（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.get("/cookiecloud", summary="CookieCloud同步", response_model=schemas.Response)
async def cookie_cloud_sync(
    _: User = Depends(get_current_active_superuser_async),
) -> Any:
    """CookieCloud同步（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.get("/reset", summary="重置站点", response_model=schemas.Response)
async def reset(
    _: User = Depends(get_current_active_superuser_async),
) -> Any:
    """重置站点（PT站点功能已移除）"""
    return schemas.Response(success=True, message="PT站点功能已移除")


@router.post("/priorities", summary="批量更新站点优先级", response_model=schemas.Response)
async def update_sites_priority(
    priorities: List[dict],
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """批量更新站点优先级（PT站点功能已移除）"""
    return schemas.Response(success=True)


@router.post("/cookie/{site_id}", summary="更新站点Cookie&UA", response_model=schemas.Response)
async def update_cookie_by_body(
    site_id: int,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """更新站点Cookie（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.get("/cookie/{site_id}", summary="更新站点Cookie&UA", response_model=schemas.Response)
async def update_cookie(
    site_id: int,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """更新站点Cookie（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.post("/userdata/{site_id}", summary="更新站点用户数据", response_model=schemas.Response)
async def refresh_userdata(
    site_id: int,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """刷新站点用户数据（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.get("/userdata/latest", summary="查询所有站点最新用户数据", response_model=List[schemas.SiteUserData])
async def read_userdata_latest(
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """查询所有站点最新用户数据（PT站点功能已移除）"""
    return []


@router.get("/userdata/{site_id}", summary="查询某站点用户数据", response_model=schemas.Response)
async def read_userdata(
    site_id: int,
    workdate: Optional[str] = None,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """查询站点用户数据（PT站点功能已移除）"""
    return schemas.Response(success=False, data=[])


@router.get("/test/{site_id}", summary="连接测试", response_model=schemas.Response)
async def test_site(
    site_id: int,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """测试站点是否可用（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.get("/icon/{site_id}", summary="站点图标", response_model=schemas.Response)
async def site_icon(
    site_id: int,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """获取站点图标（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.get("/category/{site_id}", summary="站点分类", response_model=List[schemas.SiteCategory])
async def site_category(
    site_id: int,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """获取站点分类（PT站点功能已移除）"""
    return []


@router.get("/resource/{site_id}", summary="站点资源", response_model=List[Any])
async def site_resource(
    site_id: int,
    keyword: Optional[str] = None,
    cat: Optional[str] = None,
    page: Optional[int] = 0,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """浏览站点资源（PT站点功能已移除）"""
    return []


@router.get("/domain/{site_url}", summary="站点详情", response_model=schemas.Site)
async def read_site_by_domain(
    site_url: str,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """通过域名获取站点信息（PT站点功能已移除）"""
    return None


@router.get("/statistic/{site_url}", summary="特定站点统计信息", response_model=schemas.SiteStatistic)
async def read_statistic_by_domain(
    site_url: str,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """通过域名获取站点统计信息（PT站点功能已移除）"""
    return schemas.SiteStatistic(domain="")


@router.get("/statistic", summary="所有站点统计信息", response_model=List[schemas.SiteStatistic])
async def read_statistics(
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """获取所有站点统计信息（PT站点功能已移除）"""
    return []


@router.get("/rss", summary="所有订阅站点", response_model=List[schemas.Site])
async def read_rss_sites(
    _: schemas.TokenPayload = Depends(verify_token),
) -> List[dict]:
    """获取RSS站点列表（PT站点功能已移除）"""
    return []


@router.get("/auth", summary="查询认证站点", response_model=dict)
async def read_auth_sites(_: schemas.TokenPayload = Depends(verify_token)) -> dict:
    """获取可认证站点列表（PT站点功能已移除）"""
    return {}


@router.post("/auth", summary="用户站点认证", response_model=schemas.Response)
async def auth_site(
    auth_info: schemas.SiteAuth,
    _: User = Depends(get_current_active_superuser_async),
) -> Any:
    """用户站点认证（PT站点功能已移除）"""
    return schemas.Response(success=False, message="PT站点功能已移除")


@router.get("/mapping", summary="获取站点域名到名称的映射", response_model=schemas.Response)
async def site_mapping(_: User = Depends(get_current_active_superuser_async)):
    """获取站点域名到名称的映射关系（PT站点功能已移除）"""
    return schemas.Response(success=True, data={})


@router.get("/supporting", summary="获取支持的站点列表", response_model=dict)
async def support_sites(_: User = Depends(get_current_active_superuser_async)):
    """获取支持的站点列表（PT站点功能已移除）"""
    return {}


@router.get("/{site_id}", summary="站点详情", response_model=schemas.Site)
async def read_site(
    site_id: int,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """通过ID获取站点信息（PT站点功能已移除）"""
    return None


@router.delete("/{site_id}", summary="删除站点", response_model=schemas.Response)
async def delete_site(
    site_id: int,
    _: User = Depends(get_current_active_manage_user_async),
) -> Any:
    """删除站点（PT站点功能已移除）"""
    return schemas.Response(success=True)
