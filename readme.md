# pro-api

<p align="center">
   <a href="https://hub.docker.com/repository/docker/duolabmeng/pro-api">
    <img src="https://img.shields.io/docker/pulls/duolabmeng/pro-api?color=blue" alt="docker pull">
  </a>
</p>

[English](./README.md)
[简体中文](./README_CN.md)


## Introduction

This is a project that centrally manages a large model API and can call multiple backend services through OpenAI's API interface format. The project aims to simplify interactions with different AI models and support the calling of multiple backend services.

## Supported backend services

Currently supported backend services include: OpenAI, Anthropic, Gemini, Vertex, Cloudflare, DeepBricks, OpenRouter, etc.

## Background functions

The background provides query of request logs and query of usage statistics. If the background is not started, only request forwarding is performed and no information is recorded.


![image-20240912122715188](./assets/image-20240912122715188.png)

![image-20240912122804912](./assets/image-20240912122804912.png)

![image-20240912122347488](./assets/image-20240912122347488.png)

## Configuration

Using the `api.yaml` configuration file, multiple models can be configured, and each model can be configured with multiple backend services to support load balancing. The following is an example of the `api.yaml` configuration file:


api.yaml
```
providers:
  - provider: openai # Service provider
    name: ZhiPuQingYan # Service name
    base_url: https://open.bigmodel.cn/api/paas/v4 # Service address
    api_key: Please enter your api_key
    model:
      - glm-4-flash # Model name
      

  - provider: gemini
    name: Gemini
    base_url: https://generativelanguage.googleapis.com/v1beta
    api_key: Please enter your API key
    model:
      - gemini-1.5-pro
      - gemini-1.5-flash
      - gemini-1.5-flash: gpt-4o
    balance: # Configure load balancing. No configuration is default to 1
      - gemini-1.5-pro: 1 #Indicates that the model weight under this name is 1
      - gemini-1.5-flash: 1 #Indicates that the model weight under this name is 2
      - gemini-flash: 1 #Indicates that the model weight under this name is 2


  - provider: openai
    name: doubao
    base_url: https://ark.cn-beijing.volces.com/api/v3
    api_key: Please enter your api_key
    model:
      - ep-20240906033439-zrc2x: doubao-pro-128k # You can simplify the model name to doubao-pro-128k
      - ep-20240613130011-c2zgx: doubao-pro-32k
      - ep-20240729175503-5bbf7: moonshot-v1-128k

  - provider: openai
    name: SiliconFlow
    base_url: https://api.siliconflow.cn/v1
    api_key: Please enter your api_key
    model:
      - Qwen/Qwen2-72B-Instruct: qwen2-72b
      - Qwen/Qwen1.5-110B-Chat: qwen1.5-110b
      - deepseek-ai/DeepSeek-V2-Chat: deepseek-chat
      - deepseek-ai/DeepSeek-Coder-V2-Instruct: deepseek-coder
      - Qwen/Qwen2-7B-Instruct: qwen2-7b
      - Qwen/Qwen2-7B-Instruct: gpt-3.5-turbo
      - Qwen/Qwen2-1.5B-Instruct: qwen2-1.5b
      - Qwen/Qwen1.5-7B-Chat: qwen1.5-7b-chat
      - THUDM/glm-4-9b-chat: glm-4-9b-chat
      - THUDM/chatglm3-6b: chatglm3-6b
      - 01-ai/Yi-1.5-9B-Chat-16K: yi-1.5-9b-chat-16k
      - 01-ai/Yi-1.5-6B-Chat: yi-1.5-6b-chat
      - google/gemma-2-9b-it: gemma-2-9b
      - internlm/internlm2_5-7b-chat: internlm-7b-chat
      - meta-llama/Meta-Llama-3-8B-Instruct: meta-llama-3-8b
      - meta-llama/Meta-Llama-3.1-8B-Instruct: meta-llama-3.1-8b
      - mistralai/Mistral-7B-Instruct-v0.2: mistral-7b


  - provider: openai
    name: deepseek
    base_url: https://api.deepseek.com/v1
    api_key: Please enter your api_key
    model:
      - deepseek-chat
      - deepseek-coder


  - provider: vertexai_claude
    name: vertexai_claude
    PROJECT_ID: Please enter
    CLIENT_ID: Please enter
    CLIENT_SECRET: Please fill in
REFRESH_TOKEN: Please fill in
model:
- claude-3-5-sonnet@20240620
- claude-3-5-sonnet@20240620: claude-3-5-sonnet

  - provider: vertexai_gemini
    name: vertexai_gemini
    PROJECT_ID: Please fill in
    CLIENT_ID: Please fill in
    CLIENT_SECRET: Please fill in
    REFRESH_TOKEN: Please fill in
    model:
      - gemini-1.5-flash-001


  - provider: cohere
    name: cohere
    base_url: https://api.cohere.com/v1
    api_key: Please enter
    model:
      - command-r-plus-08-2024
      - command-r-plus-04-2024: gpt-4
      - command-r-plus
      - command-nightly
      - command-light
      - command-light-nightly

  provider: cloudflare
    name: cloudflare
    api_key: Please enter
    account_id: Please enter
    model:
      - ‘@cf/qwen/qwen1.5-14b-chat-awq’: qwen1.5-14b
      - ‘@hf/thebloke/deepseek-coder-6.7b-instruct-awq’


  - provider: openai
    name: openrouter
    base_url: https://openrouter.ai/api/v1
    api_key: s Please fill in
    model:
      - mattshumer/reflection-70b:free: reflection-70b
      - nousresearch/hermes-3-llama-3.1-405b:free: llama-3.1-405b



tokens:
  - api_key: sk-111111
    model:
      - glm* # wildcard *
      - all # all means all

  - api_key: sk-222222
    model:
      - gpt-3.5-turbo

server:
    default_model: glm-4-flash # If no match is found, this default model is used
    debug: false
    admin_server: false # Whether to enable the background function. If not enabled, only forwarding is performed without any logging
    db_cache: false # Return the last successful response if the content is the same
    save_log_file: false
    db_path: sqlite:///./data/request_log.db
    username: admin # Background user name
    password: admin # Background password
    jwt_secret_key: admin # Fill in whatever you like, it's random
```

[VertexAI parameter acquisition tutorial](./docs/vertexai的参数获取教程.md)

# Configure load balancing

Models with the same model name can be load balanced

The default weight is 1 

```
  - provider: gemini
    name: Gemini1
    base_url: https://generativelanguage.googleapis.com/v1beta
    api_key: Please fill in
    model:
      - gemini-1.5-pro
      - gemini-1.5-flash
      - gemini-1.5-flash : gemini-flash
    balance: # Load balancing
      - gemini-1.5-pro: 1 #indicates that the model weight under this name is 1
      - gemini-1.5-flash: 1 #indicates that the model weight under this name is 2
      - gemini-flash: 1 #indicates that the model weight under this name is 2

  - provider: gemini
    name: Gemini2
    base_url: https://generativelanguage.googleapis.com/v1beta
    api_key: Please fill in
    model:
      - gemini-1.5-pro
      - gemini-1.5-flash
      - gemini-1.5-flash : gemini-flash
    balance: # Load balancing
      - gemini-1.5-pro: 2 # Indicates that the model weight under this name is 1
      - gemini-1.5-flash: 2 # indicates that the model weight under this name is 2
      - gemini-flash: 3 # indicates that the model weight under this name is 2
```
Explanation of the above configuration:

For example:

Current weight information

* Gemini1‘s gemini-1.5-flash weight 1
* Gemini2’s gemini-1.5-flash weight 2

When requesting gemini-1.5-flash

- 1st time gemini-1.5-flash for Gemini1
- 2nd time gemini-1.5-flash for Gemini2
- 3rd time gemini-1.5-flash for Gemini2
- 4th time gemini-1.5-flash for Gemini1
- 5th time gemini-1.5-flash for Gemini2


## vercel deployment


Click the button below to deploy to Vercel with one click:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fduolabmeng6%2Fpro-api&env=config_url,secret_key&project-name=pro-api&repository-name=pro-api)

The following environment variables need to be set during deployment:

- `config_url`: URL of the remote configuration file
- `secret_key`: key used for encryption (can be left blank if encryption is not required) If encryption is required, use aes-128-ecb encryption. If not encrypted, give the plaintext configuration content

After deployment, access the domain name assigned by Vercel to use the API.

Note: Please ensure that your remote configuration file (`config_url`) can be accessed publicly, otherwise Vercel will not be able to retrieve the configuration information.

Here I give the simplest configuration content

config_url=https://The address where you can access the download configuration/api.yaml

```
providers:
  - provider: openai
    name: deepseek
    base_url: https://api.deepseek.com/v1
    api_key: sk-xxxxxxxxxxxxx
    model:
      - deepseek-chat
      - deepseek-coder

tokens:
  - api_key: sk-123456
    model:
      - all

server:
    default_model: deepseek-chat

```


## Docker local deployment

Start the container

1. Start using the local api.yaml configuration file
```bash
docker run -d \
  --name pro-api \
  -p 8001:8000 \
  -v $(pwd)/api.yaml:/app/api.yaml \
  -v $(pwd)/data:/app/data:rw \
  duolabmeng/pro-api:latest
```

2. Start with the remote api.yaml configuration file
```bash
docker run -d \
  --name pro-api \
  -e config_url=http://你的服务器/api.yaml \
  -e secret_key=123456789 \
  -p 8001:8000 \
  -v $(pwd)/api.yaml:/app/api.yaml
-v $(pwd)/data:/app/data:rw
duolabmeng/pro-api:latest
```
config_url automatically downloads the remote configuration file 
secret_key encrypted with aes, ECB, 128 bits, if you want to be safe remember to enable the aes password, if you don't fill it in, you will get the plaintext configuration


3. If you want to use Docker Compose
```yaml
services:
  pro-api:
    container_name: pro-api
    image: duolabmeng/pro-api:latest
    environment:
      - config_url=http://file_url/api.yaml
      - secret_key=123456789
    ports:
      - 8001:8000
    volumes:
      - ./api.yaml:/app/api.yaml
      - ./data/:/app/data:rw
```

For example, if you are not in a position to modify the configuration file on a certain platform, you can upload the configuration file to a hosting service, which can provide a direct link for pro-api to download. config_url is this direct link.
If you don't want to restart the container to update the configuration, you can just refresh the configuration by accessing /reload_config.


Restart the Docker image with one click

```bash
set -eu
docker pull duolabmeng/pro-api:latest
docker rm -f pro-api
docker run --user root -p 8001:8000 -dit --name pro-api
-v ./api.yaml:/app/api.yaml
duolabmeng/pro-api:latest
docker logs -f pro-api
```

RESTful curl test

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
-H ‘Content-Type: application/json’ \
-H ‘Authorization: Bearer ${API}’ \
-d ‘{’model‘: “gpt-4o”,’messages‘: [{’role‘: “user”, “content”: “Hello”}],’stream‘: true}’
```

# Help

1. If you cannot install dependencies on some cloud platforms, you can directly install the dependencies in the running directory and then start

```shell
pip install -r requirements.txt --no-user -t ./app 

```

## Star History

<a href="https://github.com/duolabmeng6/pro-api/stargazers">
        <img width="500" alt="Star History Chart" src="https://api.star-history.com/svg?repos=duolabmeng6/pro-api&type=Date">
</a>