import os
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter()

@router.get("/{page_name}")
async def show(page_name: str):
    if not page_name:
        return JSONResponse({
            "status": 1,
            "msg": "id不能为空",
            "data": ""
        })
    
    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="zh-hans">

<head>
    <meta charset="UTF-8"/>
    <title>goAmis</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"/>
    <meta http-equiv="X-UA-Compatible" content="IE=Edge"/>
    <link rel="stylesheet" href="/sdk/sdk.css"/>
    <link rel="stylesheet" href="/sdk/helper.css"/>
    <link rel="stylesheet" href="/sdk/iconfont.css"/>
    <script src="/sdk/sdk.js"></script>
    <style>
        html,
        body,
        .app-wrapper {{
            position: relative;
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
        }}
    </style>
</head>

<body>
<div id="root" class="app-wrapper"></div>
<script type="text/javascript">
    (function () {{
        const amis = amisRequire('amis/embed');
        const amisJSON = {{
            type: 'page',
            title: '{page_name}',
            body: {{
                type: "service",
                schemaApi: "GET:/pages/{page_name}.json"
            }},
            regions: [
                "body",
                "header",
                "toolbar"
            ],
            toolbar: [
                {{
                    "type": "button",
                    "label": "获取当前页面配置",
                    "url": "/pages/{page_name}.json",
                    "actionType": "url"
                }}
            ],
            className: "p",
        }};
        amis.embed('#root', amisJSON, {{}}, {{}});
    }})();
</script>
</body>

</html>
    """)
