from app.apiDB import apiDB
db = apiDB("./api.yaml")


from app.routers.JWTHandler import JWTHandler, JWTBearer

jwt_handler = JWTHandler(secret_key="secret_key")
jwt_bearer = JWTBearer(jwt_handler)

admin_username = db.config_server.get("username","admin")
admin_password = db.config_server.get("password","666666")