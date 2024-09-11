import time

from app.api_data import db


from app.routers.JWTHandler import JWTHandler, JWTBearer

jwt_secret_key = db.config_server.get("jwt_secret_key",str(time.time()))

jwt_handler = JWTHandler(secret_key=jwt_secret_key)
jwt_bearer = JWTBearer(jwt_handler)

admin_username = db.config_server.get("username","admin")
admin_password = db.config_server.get("password","666666")
