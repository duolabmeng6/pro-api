import os
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse

from app.db.reqLogs import RequestLogger

router = APIRouter()
request_logger = RequestLogger()


@router.get("/statistics")
async def statistics():
    data = request_logger.statistics()
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": {
            "count": 1710,
            "rows": data
        }
    })

@router.get("/statistics_model_day")
async def statistics_model_day():
    try:
        data = request_logger.statistics_model_day()
        return JSONResponse({
            "status": 0,
            "msg": "成功获取模型每日使用统计",
            "data": data
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计数据时发生错误: {str(e)}")
