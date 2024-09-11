#!/bin/bash
docker-compose down
docker rmi duolabmeng/pro-api:latest
docker-compose pull
docker-compose up --build -d
echo "更新完成并重新启动"
docker-compose logs -f
