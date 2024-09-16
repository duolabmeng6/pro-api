import os
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter()

@router.get("/config")
async def show():
    # 读取 main.py 入口文件的 api.yaml 内容
    file_path = os.path.join(os.path.dirname(__file__), '..',  'api.yaml')
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="api.yaml 文件未找到")
    except IOError:
        raise HTTPException(status_code=500, detail="无法读取 api.yaml 文件")
    
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": {
            "file_path": file_path,
            "content": content
        }
    })

import yaml  # 添加此行以导入yaml模块

@router.post("/config")
async def store(request: Request):
    data = await request.json()
    content = data.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="缺少 content 字段")

    # 校验一下这个yaml是不是加载成功
    try:
        yaml.safe_load(content)
    except Exception as e:
        return JSONResponse({
            "status": 1,
            "msg": "yaml 格式错误",
        })


    file_path = os.path.join(os.path.dirname(__file__), '..',  'api.yaml')
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    return JSONResponse({
        "status": 0,
        "msg": "保存成功",
        "data": {
            "file_path": file_path,
            "content": content
        }
    })



