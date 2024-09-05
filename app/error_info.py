def generate_error_response(error_code):
    # 401 - 无效的身份验证，确保API密钥和组织正确。
    # 403 - 国家、地区或领土不受支持。请查看文档以获取更多信息。
    # 404 - 提供的API密钥不正确，或您必须是组织的成员才能使用API。
    # 429 - 达到速率限制或超出配额。请检查您的计划和账单详情。
    # 500 - 服务器在处理您的请求时发生错误。
    # 503 - 引擎当前超载。请稍后再试。
    error_messages = {
        401: {
            "message": "Invalid authentication. Ensure the correct API key and requesting organization are being used.",
            "type": "authentication_error"
        },
        403: {
            "message": "Country, region, or territory not supported. Please see the documentation for more information.",
            "type": "access_forbidden"
        },
        404: {
            "message": "Incorrect API key provided or you must be a member of an organization to use the API.",
            "type": "not_found"
        },
        429: {
            "message": "Rate limit reached or quota exceeded. Please check your plan and billing details.",
            "type": "rate_limit_error"
        },
        500: {
            "message": "The server had an error while processing your request.",
            "type": "server_error"
        },
        503: {
            "message": "The engine is currently overloaded. Please try again later.",
            "type": "server_overload"
        }
    }

    # 默认的未知错误处理
    default_error = {
        "message": "An unknown error occurred.",
        "type": "unknown_error"
    }

    # 返回对应的错误消息，如果没有匹配则返回默认值
    error_response = error_messages.get(error_code, default_error)

    # 按指定格式返回错误响应
    return {
        # "error": {
            "message": error_response["message"],
            "type": error_response["type"],
            "param": None,
            "code": None
        # }
    }