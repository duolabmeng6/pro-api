import os
import json
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse

from app.routers.web_config import jwt_handler, admin_password, admin_username

router = APIRouter()

@router.post("/login")
async def login(request: Request):
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")

        token = jwt_handler.create_token(1)

        if username == admin_username and password == admin_password:
            response = JSONResponse(content={"status": 0, "msg": "登录成功", "data": {"token": token}})
            response.set_cookie(key="token", value=token, httponly=True)
            return response
        else:
            return JSONResponse(content={"status": 1, "msg": "用户名或密码错误"}, status_code=401)
    except Exception as e:
        return JSONResponse(content={"status": 1, "msg": f"登录失败: {str(e)}"}, status_code=500)


@router.get("")
async def admin(request: Request):
    # 获取cookie中的token
    token = request.cookies.get("token")
    
    if not token:
        # 未登录，跳转到登录页面
        return HTMLResponse(content='<script>window.location.href="/login.html";</script>')
    
    try:
        # 验证token
        jwt_handler.decode_token(token)
        # 已登录，跳转到管理页面
        return HTMLResponse(content='<script>window.location.href="/admin.html";</script>')
    except:
        # token无效，跳转到登录页面
        return HTMLResponse(content='<script>window.location.href="/login.html";</script>')

    
@router.get("/logout")
async def logout():
    response = JSONResponse(content={"status": 0, "msg": "退出登录成功"})
    response.delete_cookie(key="token")
    response.headers["Location"] = "/login.html"
    response.status_code = 302
    return response
