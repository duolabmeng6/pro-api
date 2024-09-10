from fastapi import APIRouter
from app.routers import amisPages
from app.routers import page
from app.routers import reqLogs
from app.routers import reqCache

api_router = APIRouter()
api_router.include_router(amisPages.router, prefix="/admin/amis-pages", tags=["amisPages"])
api_router.include_router(page.router, prefix="/page", tags=["page"])
api_router.include_router(reqLogs.router, prefix="/admin", tags=["reqLogs"])
api_router.include_router(reqCache.router, prefix="/admin", tags=["reqCache"])



