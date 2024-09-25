import asyncio
import sys
import os
import time

from starlette.types import Scope, Send, Receive

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pydantic import BaseModel
import ujson as json
from fastapi.routing import APIRoute
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from app.error_info import generate_error_response
import uuid
import pyefun
from app.log import logger

from app.api_data import db, get_db, reload_db, 监视配置
from app.provider.load_providers import load_providers
from app.Balance import Balance

G_balance = {}
ai_manager = {}
def reload_config():
    global ai_manager, db, G_balance
    G_balance = {}
    db = reload_db()
    ai_manager = load_providers(db)

config_url = os.environ.get('config_url', False)
if not config_url:
    api_file_path = os.path.join(os.path.dirname(__file__), 'api.yaml')
    监视配置(api_file_path, reload_config)

reload_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    def print_routes():
        logger.info("FastAPI 定义的路由:")
        for route in app.routes:
            if isinstance(route, APIRoute):
                logger.info(f"路径: {route.path}, 方法: {route.methods}, 名称: {route.name}")

    logger.info("服务器启动")
    print_routes()
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
    else:
        detail = exc.detail

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


@app.get("/")
async def index():
    return {
        "name": "pro-api",
        "version": "1.0.0",
        "author": "duolabmeng6",
        "url": "https://github.com/duolabmeng6/pro-api",
    }


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


class ChatCompletionRequest(BaseModel):
    stream: bool = False
    model: str
    id: str = None


def get_provider(api_key, model):
    balance_key = f"{api_key}_{model}"
    if balance_key in G_balance:
        balance = G_balance[balance_key]
    else:
        providers, error = db.get_user_provider(api_key, model)
        if not providers:
            raise HTTPException(status_code=500, detail=error)
        balance = Balance(api_key, providers)
        G_balance[balance_key] = balance
    provider = balance.next().data
    print(f"provider: {provider}")
    return provider


if db.config_server.get("debug", False):
    from app.LoggingMiddleware import LoggingMiddleware

    app.add_middleware(LoggingMiddleware)


@app.post("/chat/completions")
@app.post("/v1/chat/completions")
async def chat_completions(
        api_key: str = Depends(verify_api_key),
        req: Request = Request,
        request: ChatCompletionRequest = Body(...),
):
    try:
        body = json.loads(await req.body())
    except:
        raise HTTPException(status_code=500, detail="body解析失败")

    provider = get_provider(api_key, request.model)

    headers = dict(req.headers)
    id = str(uuid.uuid4().hex)[:16]
    request.id = headers.get("id", id)
    logger.name = f"main.{request.id}"

    logger.info(
        f"服务提供者:{provider['provider']}_{provider['name']}, 请求模型:{request.model}, 当前模型:{provider.get('mapped_model')}, 名称:{provider.get('name')}")

    # return provider['name']

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
    ai_chat._db_cache = db.config_server.get("db_cache", False)

    request_model_name = request.model
    body["model"] = provider.get("mapped_model")

    # 先插入日志记录
    service_provider = f"{provider.get('provider', '')}_{provider.get('name', '')}"

    if db.config_server.get("admin_server", False):
        request_logger.insert_req_log(
            req_id=id,
            service_provider=service_provider,
            token=api_key,
            model=request.model,
            prompt=0,
            completion=0,
            quota=0,
            uri=req.url.path,
            request_data=json.dumps(body),
            response_data=""
        )

    genData = ai_chat.chat2api(body, request_model_name, id)
    first_chunk = await genData.__anext__()

    if not request.stream:
        stats_data = ai_chat.DataHeadler.get_stats()

        if debug:
            logger.info(f"发送到客户端\r\n{first_chunk}")
            logger.info(f"SSE数据迭代完成，统计信息：{json.dumps(stats_data, indent=4)}")

        if db.config_server.get("admin_server", False):
            request_logger.update_req_log(
                req_id=id,
                prompt=stats_data["prompt_tokens"],
                completion=stats_data["completion_tokens"],
                quota=0,  # 假设每1000个token花费0.002美元
                response_data=json.dumps(stats_data),
                api_status="200",
                api_error=""
            )
        return first_chunk

    if first_chunk:
        async def generate_stream():
            async for chunk in genData:
                yield chunk + "\n\n"
                if debug:
                    await asyncio.sleep(0.1)
                    logger.info(f"发送到客户端\r\n{chunk}")
            stats_data = ai_chat.DataHeadler.get_stats()
            if db.config_server.get("admin_server", False):
                request_logger.update_req_log(
                    req_id=id,
                    prompt=stats_data["prompt_tokens"],
                    completion=stats_data["completion_tokens"],
                    quota=0,  # 假设每1000个token花费0.002美元
                    response_data=json.dumps(stats_data),
                    api_status="200",
                    api_error=""
                )
            if debug:
                logger.info(f"数据迭代完成，统计信息：{json.dumps(stats_data, indent=4, ensure_ascii=False)}")

        return StreamingResponse(generate_stream(), media_type="text/event-stream")


@app.get("/v1/models")
async def models(
        api_key: str = Depends(verify_api_key),
        req: Request = Request
):
    return {
        "data": db.get_all_models(api_key)
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/reload_config")
def reloadconfig():
    reload_config()
    return JSONResponse({
        "status": 0,
        "msg": f"已经执行刷新配置"
    })

class GzipStaticFiles(StaticFiles):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            gzip_middleware = GZipMiddleware(super().__call__, compresslevel=9)
            await gzip_middleware(scope, receive, send)
        else:
            await super().__call__(scope, receive, send)


if db.config_server.get("admin_server", False):
    from app.db.logDB import RequestLogger

    request_logger = RequestLogger()
    from app.routers.router import api_router

    app.include_router(api_router, prefix="")
    # app.mount("/", StaticFiles(directory="./public", html=True), name="static")
    # app.add_middleware(GZipMiddleware, minimum_size=100 * 1024)
    app.mount("/", GzipStaticFiles(directory="./public", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # workers=1,
    )
