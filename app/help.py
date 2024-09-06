import json
import time



async def build_openai_response(id: str, response_data: dict, model: str, prompt_tokens: int, completion_tokens: int,
                          total_tokens=int):
    current_timestamp = int(time.time())
    response = {
        "id": id,
        "object": "chat.completion",
        "created": current_timestamp,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                },
                "logprobs": None,
                "finish_reason": None
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0
        },
        "system_fingerprint": ""
    }

    if response_data['type'] == 'content':
        response["choices"][0]["message"]["content"] = response_data['content']
        response["choices"][0]["finish_reason"] = "stop"
    elif response_data['type'] == 'function_call':
        response["choices"][0]["message"]["tool_calls"] = response_data['function']
        response["choices"][0]["finish_reason"] = "tool_calls"
    if response_data['type'] == 'stop':
        response["choices"][0]["message"]["content"] = response_data['content']
        response["choices"][0]["finish_reason"] = "stop"

    return response


async def generate_sse_response(id, model, content=None):
    current_timestamp = int(time.time())
    chunk = {
        "id": f"chatcmpl-{id}",
        "object": "chat.completion.chunk",
        "created": current_timestamp,
        "model": model,
        "system_fingerprint": "",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "logprobs": None,
                "finish_reason": None
            }
        ]
    }

    if content is None:
        chunk["choices"][0]["delta"] = {"role": "assistant", "content": ""}
    elif content['type'] == 'content':
        chunk["choices"][0]["delta"] = {"content": content['content']}
    elif content['type'] == 'stop':
        chunk["choices"][0]["delta"] = {}
        chunk["choices"][0]["finish_reason"] = "stop"
        chunk["usage"] = {
            "prompt_tokens": content.get('prompt_tokens', 0),
            "completion_tokens": content.get('completion_tokens', 0),
            "total_tokens": content.get('total_tokens', 0)
        }
    elif content['type'] == 'end':
        return "data: [DONE]"
    else:
        return None

    json_data = json.dumps(chunk, ensure_ascii=False)
    return f"data: {json_data}\n\n"

