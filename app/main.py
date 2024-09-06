import sys
import os
from typing import Dict

from urllib3 import request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from provider.geminiProvider import geminiProvider
from provider.models import RequestModel, Message, ContentItem
from provider.openaiProvider import openaiProvider
from app.error_info import generate_error_response
from app.log import logger
from database import Database
import uuid

db = Database(os.path.join(os.path.dirname(__file__), './api.yaml'))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("服务器启动")
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # 检查exc.detail的类型，如果是字典类型，那就输出字典
    message = {}
    detail = None
    status_code = exc.status_code
    if isinstance(exc.detail, str):
        message = exc.detail
    if isinstance(exc.detail, HTTPException):
        detail = exc.detail.detail
        status_code = 500
        message = detail.get("error")

    return JSONResponse(
        status_code=status_code,
        content={
            "code": status_code,
            "message": message,
            "detail": detail,
            "error": generate_error_response(status_code)
        }
    )


security = HTTPBearer()


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    api_key = credentials.credentials
    if not await db.verify_token(api_key):
        raise HTTPException(status_code=401, detail="没有授权")
    return api_key


def getProvider(provider):
    if provider == "openai":
        return openaiProvider
    if provider == "gemini":
        return geminiProvider
    raise HTTPException(status_code=500, detail="没有适配器")


@app.post("/v1/chat/completions")
async def chat_completions(
        request: RequestModel,
        api_key: str = Depends(verify_api_key),
        req: Request = Request
):
    # 检查api_key和当前的请求的model是有可用模型
    providers, error = await db.get_user_provider(api_key, request.model)
    if not providers:
        raise HTTPException(status_code=500, detail=error)
    provider = providers[0]
    # 获取header信息
    headers = dict(req.headers)
    id = str(uuid.uuid4())
    request.id = headers.get("id", id)
    logger.name = f"main.{request.id}"
    logger.info(
        f"服务提供者:{provider['provider']} 请求模型:{request.model} 当前模型:{provider.get('mapped_model')} 名称:{provider.get('name')} \r\n 请求内容:\r\n{request.model_dump_json(indent=2)}")

    ai_provider_class = getProvider(provider["provider"])
    # 创建openai接口
    ai_provider = ai_provider_class(provider.get("api_key"), provider.get("base_url"))

    ai_provider.setDebugSave(request.id + "_" + provider.get('mapped_model'))
    ai_provider._cache = True
    ai_provider._debug = True

    request_model_name = request.model  # 保存请求时候的模型名称
    request.model = provider.get("mapped_model")  # 映射为正确的名称
    # 发送请求
    genData = ai_provider.chat2api(request, request_model_name, id)
    # 得到转发数据
    first_chunk = await genData.__anext__()

    if not request.stream:
        logger.info(f"发送到客户端\r\n{first_chunk}")
        return first_chunk

    if first_chunk:
        async def generate_stream():
            async for chunk in genData:
                logger.info(f"发送到客户端\r\n{chunk}")
                yield chunk

        return StreamingResponse(generate_stream(), media_type="text/event-stream")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "__main__:app",
        host=db.config_server.get("host", "0.0.0.0"),
        port=db.config_server.get("port", 8000),
        reload=True
    )
