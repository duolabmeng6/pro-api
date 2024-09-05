# 配置文件编写

api.yaml
```
providers:
  - provider: openai
    name: 智谱清言
    base_url: https://open.bigmodel.cn/api/paas/v4
    api_key: sk-xxx
    model:
      - glm-4-flash
      - glm-4-flash: gpt-4o
      - glm-4-flash: gpt-3.5-turbo

  - provider: openai
    name: 硅基流动
    base_url: https://api.siliconflow.cn/v1
    api_key: sk-xxx
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

tokens:
  - api_key: sk-111111
    model:
      - glm*
      - all

  - api_key: sk-222222
    model:
      - gpt-3.5-turbo

server:
    port: 8000
    host: 0.0.0.0
    default_model: glm-4-flash
```
