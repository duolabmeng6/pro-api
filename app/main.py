import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import ujson
def monkey_patch_json():
    json.__name__ = 'ujson'
    json.dumps = ujson.dumps
    json.loads = ujson.loads
monkey_patch_json()


from types import SimpleNamespace

from fastapi.routing import APIRoute

from app.log import logger
from app.db.logDB import RequestLogger
from app.provider.load_providers import load_providers
from app.routers.router import api_router

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.error_info import generate_error_response
from apiDB import apiDB
import uuid
import pyefun

db = apiDB(os.path.join(os.path.dirname(__file__), './api.yaml'))
ai_manager = load_providers(db)
request_logger = RequestLogger()

def print_routes():
    print("FastAPI 定义的路由:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"路径: {route.path}, 方法: {route.methods}, 名称: {route.name}")


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    providers, error = db.get_user_provider(api_key, request.model)
    if not providers:
        raise HTTPException(status_code=500, detail=error)
    provider = providers[0]
    headers = dict(req.headers)
    id = str(uuid.uuid4())
    request.id = headers.get("id", id)
    logger.name = f"main.{request.id}"

    logger.info(
        f"服务提供者:{provider['provider']}, 请求模型:{request.model}, 当前模型:{provider.get('mapped_model')}, 名称:{provider.get('name')}")

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
    ai_chat._db_cache = db.config_server.get("debug", False)

    request_model_name = request.model
    body["model"] = provider.get("mapped_model")

    # 先插入日志记录
    service_provider = f"{provider.get('provider', '')}_{provider.get('name', '')}"
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
        if debug:
            logger.info(f"发送到客户端\r\n{first_chunk}")

        stats_data = ai_chat.DataHeadler.get_stats()
        logger.info(f"SSE 数据迭代完成，统计信息：{stats_data}")

        # 更新日志记录
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
                if debug:
                    logger.info(f"发送到客户端\r\n{chunk}")
                yield chunk + "\r\n\r\n"

            stats_data = ai_chat.DataHeadler.get_stats()
            logger.info(f"SSE 数据迭代完成，统计信息：{stats_data}")

            # 更新日志记录
            request_logger.update_req_log(
                req_id=id,
                prompt=stats_data["prompt_tokens"],
                completion=stats_data["completion_tokens"],
                quota=0,  # 假设每1000个token花费0.002美元
                response_data=json.dumps(stats_data),
                api_status="200",
                api_error=""
            )

        return StreamingResponse(generate_stream(), media_type="text/event-stream")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix="")

from fastapi.staticfiles import StaticFiles

# 设置./web为静态目录
app.mount("/", StaticFiles(directory="./public", html=True), name="static")



if __name__ == "__main__":
    print_routes()

    import uvicorn

    uvicorn.run(
        "__main__:app",
        host=db.config_server.get("host", "127.0.0.1"),
        port=db.config_server.get("port", 8000),
        reload=True
    )

