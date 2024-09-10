import os
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter()

@router.get("")
async def index():
    # 查找目录 ./public/pages/*.json 文件返回文件列表
    files = [f for f in os.listdir("./public/pages") if f.endswith(".json")]
    
    # 构建 JSON 列表
    json_list = []
    for file in files:
        with open(os.path.join("./public/pages", file), "r") as f:
            json_list.append({
                "name": os.path.splitext(file)[0],
                "config": f.read()
            })
    
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": {
            "items": json_list,
            "total": len(json_list)
        }
    })

@router.post("")
async def store(request: Request):
    data = await request.json()
    name = data.get("name")
    config = data.get("config")
    
    if not name:
        return JSONResponse({
            "status": 1,
            "msg": "name不能为空",
            "data": ""
        })
    
    # 保存文件
    with open(f"./public/pages/{name}.json", "w") as f:
        f.write(config)
    
    return JSONResponse({
        "status": 0,
        "msg": "",
        "data": ""
    })

@router.get("/{page_name}")
async def show(page_name: str):
    if not page_name:
        return JSONResponse({
            "status": 1,
            "msg": "id不能为空",
            "data": ""
        })
    
    # 这里假设您有一个HTML模板引擎，实际使用时可能需要调整
    return HTMLResponse(content=f"""
    <html>
        <body>
            <h1>{page_name}</h1>
            <div id="root"></div>
            <script>
                var pageSchemaApi = "GET:/pages/{page_name}.json";
                var getConfigAddr = "/pages/{page_name}.json";
            </script>
        </body>
    </html>
    """)

@router.delete("/{page_name}")
async def destroy(page_name: str):
    if not page_name:
        return JSONResponse({
            "status": 1,
            "msg": "name不能为空",
            "data": ""
        })
    
    try:
        os.remove(f"./public/pages/{page_name}.json")
    except FileNotFoundError:
        return JSONResponse({
            "status": 1,
            "msg": "文件不存在",
            "data": ""
        })
    
    return JSONResponse({
        "status": 0,
        "msg": "删除成功",
        "data": ""
    })

# 其他方法如 create, edit, update 可以根据需要添加