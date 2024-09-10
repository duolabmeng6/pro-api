from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Security, Depends,Request
from fastapi.logger import logger
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.status import HTTP_401_UNAUTHORIZED


class JWTHandler:
    secret_key: str
    algorithm: str
    expire_minutes: int

    def __init__(self, secret_key: str, algorithm: str = "HS256", expire_minutes: int = 60 * 24 * 7):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expire_minutes = expire_minutes

    def create_token(self, user_id: int) -> str:
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if datetime.fromtimestamp(payload['exp']) < datetime.utcnow():
                raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token expired")
            return payload
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token")


class JWTBearer(HTTPBearer):
    def __init__(self, jwt_handler: JWTHandler):
        super(JWTBearer, self).__init__(auto_error=False)
        self.jwt_handler = jwt_handler

    async def __call__(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)), request: Request = None):
        token = None
        if credentials:
            if credentials.scheme.lower() == "bearer":
                token = credentials.credentials
        elif request:
            token = request.cookies.get("token")

        if not token:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="未登录")

        try:
            payload = self.jwt_handler.decode_token(token)
            return payload
        except HTTPException as e:
            raise e
        except Exception:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="无效的令牌")


# 使用示例
# jwt_handler = JWTHandler("your-secret-key")
# jwt_bearer = JWTBearer(jwt_handler)
#
# # 在路由中使用
# from fastapi import Depends
#
# @router.get("/protected")
# async def protected_route(payload: dict = Depends(jwt_bearer)):
#     return {"user_id": payload["user_id"]}
#
# # 创建token
# @router.post("/login")
# async def login(user_id: int):
#     token = jwt_handler.create_token(user_id)
#     return {"access_token": token, "token_type": "bearer"}

if __name__ == '__main__':
    jwt_handler = JWTHandler("your-secret-key");
    print(jwt_handler.create_token(1))
    a = jwt_handler.create_token(1)
    print(jwt_handler.decode_token(a))
