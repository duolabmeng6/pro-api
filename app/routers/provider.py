from fastapi import APIRouter, HTTPException, Query, Body, Path
from fastapi.responses import JSONResponse
from typing import List
from app.db.reqLogs import RequestLogger
from pydantic import BaseModel
import datetime

router = APIRouter()


from app.api_data import db, get_db


@router.get("/provider")
async def index(
):
    pass
    db = get_db()
    data = db.get_all_provider()
    return JSONResponse({
        "items": data,  
        "total": 0
    })

@router.post("/provider")
async def store():
    pass

@router.get("/provider/{log_id}")
async def show():
   pass

@router.put("/provider/{log_id}")
async def update():
    pass

@router.delete("/provider/{log_id}")
async def destroy():
    pass
