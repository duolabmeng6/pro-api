from fastapi import APIRouter, Depends
from app.routers import amisPages
from app.routers import page
from app.routers import reqLogs
from app.routers import reqCache
from app.routers import admin
from app.routers import statistics
from app.routers import systemConfig
from app.routers import provider
from app.routers.web_config import jwt_bearer

api_router = APIRouter()
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(statistics.router, prefix="/admin", tags=["statistics"])

api_router.include_router(amisPages.router, prefix="/admin/amis-pages", tags=["amisPages"], dependencies=[Depends(jwt_bearer)])
api_router.include_router(page.router, prefix="/page", tags=["page"])
api_router.include_router(reqLogs.router, prefix="/admin", tags=["reqLogs"], dependencies=[Depends(jwt_bearer)])
api_router.include_router(reqCache.router, prefix="/admin", tags=["reqCache"], dependencies=[Depends(jwt_bearer)])
api_router.include_router(provider.router, prefix="/admin", tags=["provider"], dependencies=[Depends(jwt_bearer)])


api_router.include_router(systemConfig.router, prefix="/admin", tags=["SystemConfig"], dependencies=[Depends(jwt_bearer)])


