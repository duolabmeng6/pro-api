import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
import json
import pyefun
from app.log import logger

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/v1/chat/completions":
            # 记录请求头和请求体
            headers = dict(request.headers)
            body = await request.body()
            body_str = body.decode()
            
            logger.info(f"请求头: {json.dumps(headers, ensure_ascii=False)}")
            logger.info(f"请求体: {body_str}")

            # 调用下一个中间件或路由处理程序
            response = await call_next(request)
            
            # 如果是流式响应，我们需要特殊处理
            if isinstance(response, StreamingResponse):
                content = b""
                async def wrapped_stream():
                    nonlocal content
                    async for chunk in response.body_iterator:
                        content += chunk
                        yield chunk
                    logger.info(f"响应内容: {content.decode()}")
                
                return StreamingResponse(wrapped_stream(), headers=response.headers, status_code=response.status_code)
            else:
                # 对于非流式响应，直接记录响应内容
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                logger.info(f"响应内容: {response_body.decode()}")
                

                pyefun.文件_写出(f"./debug/{time.time()}.txt",
                             f"请求头:\r\n\r\n"
                             f"{json.dumps(headers, ensure_ascii=False)}\r\n\r\n"
                             f"请求体:\r\n\r\n"
                             f"{body_str}\r\n\r\n"
                             f"响应数据:\r\n\r\n"
                             f"{response_body.decode()}\r\n\r\n"
                             )
                return Response(content=response_body, headers=response.headers, status_code=response.status_code)
        else:
            response = await call_next(request)
            return response

# 在创建FastAPI应用后添加中间件
# app.add_middleware(LoggingMiddleware)
