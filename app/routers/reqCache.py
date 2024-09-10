from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse
from typing import List
from app.db.reqCache import RequestCacheManager
from pydantic import BaseModel
import datetime

router = APIRouter()
cache_manager = RequestCacheManager()

class CacheData(BaseModel):
    md5: str
    req: str
    resp: str

@router.get("/req_cache")
async def index(
    keywords: str = Query(None),
    per_page: int = Query(10, gt=0),
    page: int = Query(1, gt=0),
    order_by: str = Query("id"),
    order_dir: str = Query("desc")
):
    caches, total = cache_manager.index(keywords, per_page, page, order_by, order_dir)
    return JSONResponse({
        "items": caches,  
        "total": total
    })

@router.post("/req_cache")
async def store(cache_data: CacheData):
    cache_id = cache_manager.insert(cache_data.dict())
    if cache_id is None:
        raise HTTPException(status_code=500, detail="创建缓存失败")
    new_cache = cache_manager.find_one(cache_id)
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": new_cache
    })

@router.get("/req_cache/{cache_id}")
async def show(cache_id: int):
    cache = cache_manager.find_one(cache_id)
    if cache is None:
        raise HTTPException(status_code=404, detail="缓存不存在")
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": cache
    })

@router.put("/req_cache/{cache_id}")
async def update(cache_id: int, cache_data: CacheData):
    update_data = cache_data.dict()
    update_data["id"] = cache_id
    success = cache_manager.update(update_data)
    if not success:
        raise HTTPException(status_code=500, detail="更新缓存失败")
    return JSONResponse({
        "status": 0,
        "msg": "更新成功"
    })

@router.delete("/req_cache/{cache_id}")
async def destroy(cache_id: int):
    success = cache_manager.delete(cache_id)
    if not success:
        raise HTTPException(status_code=404, detail="缓存不存在或删除失败")
    return JSONResponse({
        "status": 0,
        "msg": "删除成功",
        "data": ""
    })

@router.delete("/req_cache/bulkDelete/{ids}")
async def bulk_delete(ids: str = Path(..., description="逗号分隔的ID列表")):
    id_list = [int(id.strip()) for id in ids.split(',') if id.strip().isdigit()]
    if not id_list:
        raise HTTPException(status_code=400, detail="无效的ID列表")
    
    success = cache_manager.bulk_delete(id_list)
    if not success:
        raise HTTPException(status_code=500, detail="批量删除失败")
    return JSONResponse({
        "status": 0,
        "msg": "删除成功",
        "data": ""
    })

@router.get("/req_cache/md5/{md5}")
async def get_by_md5(md5: str):
    cache = cache_manager.get_by_md5(md5)
    if cache is None:
        raise HTTPException(status_code=404, detail="缓存不存在")
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": cache
    })
