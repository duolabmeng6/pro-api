import json
import sys
import os
from types import SimpleNamespace
from app.log import logger
from app.provider.test import load_providers

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.error_info import generate_error_response
from apiDB import apiDB
import uuid

db = apiDB(os.path.join(os.path.dirname(__file__), './api.yaml'))
ai_manager = load_providers(db)

# 添加一个访问计数器
request_counter = 0

from anyio.lowlevel import RunVar
from anyio import CapacityLimiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("服务器启动")
    RunVar("_default_thread_limiter").set(CapacityLimiter(200))
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

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    api_key = credentials.credentials
    if not db.verify_token(api_key):
        raise HTTPException(status_code=401, detail="没有授权")
    return api_key

def getProvider(providerConfig):
    name = f"{providerConfig.get('provider', '')}_{providerConfig.get('name', '')}"
    chat = ai_manager.chat(name)
    if not chat:
        raise HTTPException(status_code=500, detail="没有适配器")
    return chat

import pyefun

import asyncio

# 创建一个锁对象
request_counter_lock = asyncio.Lock()

async def increment_request_counter():
    global request_counter
    async with request_counter_lock:
        request_counter += 1
        return request_counter

@app.post("/v1/chat/completions")
async def chat_completions(
        api_key: str = Depends(verify_api_key),
        req: Request = Request
):
    
    try:
        body = json.loads(await req.body())
    except:
        raise HTTPException(status_code=500, detail="body解析失败")

    request = SimpleNamespace(**body)
    # 检查api_key和当前的请求的model是有可用模型
    providers, error = db.get_user_provider(api_key, request.model)
    if not providers:
        raise HTTPException(status_code=500, detail=error)
    provider = providers[0]
    headers = dict(req.headers)
    id = str(uuid.uuid4())
    request.id = headers.get("id", id)
    logger.name = f"main.{request.id}"

    logger.info(f"请求计数: {request_counter}, 服务提供者:{provider['provider']}, 请求模型:{request.model}, 当前模型:{provider.get('mapped_model')}, 名称:{provider.get('name')}")

    # logger.info(
    #     f"服务提供者:{provider['provider']} 请求模型:{request.model} 当前模型:{provider.get('mapped_model')} 名称:{provider.get('name')}")

    # 创建openai接口
    ai_chat = getProvider(provider)

    debug = db.config_server.get("debug", False)
    if debug:
        ai_chat.setDebugSave(f"{provider.get('mapped_model')}_{provider.get('provider')}_{request.id}")
        ai_chat._cache = True
        ai_chat._debug = True
        body2json = json.dumps(body, indent=4, ensure_ascii=False)
        pyefun.文件_保存(f"./provider/sendbody/{provider.get('provider')}_{request.id}_{request.model}.txt", body2json)
    else:
        ai_chat._cache = False
        ai_chat._debug = False

    request_model_name = request.model  # 用户请求的模型名称
    body["model"] = provider.get("mapped_model")  # 请求对应的api的模型名称

    genData = ai_chat.chat2api(body, request_model_name, id)
    first_chunk = await genData.__anext__()
    if not request.stream:
        if debug:
            logger.info(f"发送到客户端\r\n{first_chunk}")
        return first_chunk
    if first_chunk:
        async def generate_stream():
            async for chunk in genData:
                if debug:
                    logger.info(f"发送到客户端\r\n{chunk}")
                yield chunk + "\r\n\r\n"
            stats_data = ai_chat.DataHeadler.get_stats()
            yield f"data: {json.dumps(stats_data)}\n\n"
            logger.info(f"SSE 数据迭代完成，统计信息：{stats_data}")
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
        host=db.config_server.get("host", "127.0.0.1"),
        port=db.config_server.get("port", 8000),
    )
