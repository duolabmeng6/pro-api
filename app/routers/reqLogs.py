from fastapi import APIRouter, HTTPException, Query, Body, Path
from fastapi.responses import JSONResponse
from typing import List
from app.db.reqLogs import RequestLogger
from pydantic import BaseModel
import datetime

router = APIRouter()
request_logger = RequestLogger()

class LogData(BaseModel):
    req_id: str


@router.get("/req_logs")
async def index(
    keywords: str = Query(None),
    per_page: int = Query(10, gt=0),
    page: int = Query(1, gt=0),
    order_by: str = Query("id"),
    order_dir: str = Query("desc")
):
    logs, total = request_logger.index(keywords, per_page, page, order_by, order_dir)
    return JSONResponse({
        "items": logs,  
        "total": total
    })

@router.post("/req_logs")
async def store(log_data: LogData):
    log_id = request_logger.insert(log_data.dict())
    if log_id is None:
        raise HTTPException(status_code=500, detail="创建日志失败")
    new_log = request_logger.find_one(log_id)
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": new_log.__dict__
    })

@router.get("/req_logs/{log_id}")
async def show(log_id: int):
    log = request_logger.find_one(log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="日志不存在")
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": log
    })

@router.put("/req_logs/{log_id}")
async def update(log_id: int, log_data: LogData):
    update_data = log_data.dict()
    update_data["id"] = log_id
    success = request_logger.update(update_data)
    if not success:
        raise HTTPException(status_code=500, detail="更新日志失败")
    return JSONResponse({
        "status": 0,
        "msg": "更新成功"
    })

@router.delete("/req_logs/{log_id}")
async def destroy(log_id: int):
    success = request_logger.delete(log_id)
    if not success:
        raise HTTPException(status_code=404, detail="日志不存在或删除失败")
    return JSONResponse({
        "status": 0,
        "msg": "删除成功",
        "data": ""
    })


@router.delete("/req_logs/bulkDelete/{ids}")
async def bulk_delete(ids: str = Path(..., description="逗号分隔的ID列表")):
    id_list = [int(id.strip()) for id in ids.split(',') if id.strip().isdigit()]
    if not id_list:
        raise HTTPException(status_code=400, detail="无效的ID列表")
    
    success = request_logger.bulk_delete(id_list)
    if not success:
        raise HTTPException(status_code=500, detail="批量删除失败")
    return JSONResponse({
        "status": 0,
        "msg": "删除成功",
        "data": ""
    })
