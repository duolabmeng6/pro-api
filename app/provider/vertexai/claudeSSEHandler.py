import time
import ujson as json
import os


class claudeSSEHandler:
    def __init__(self, custom_id=None, model=""):
        self.custom_id = custom_id
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.full_message_content = ""
        self.model = model
        self.tool_calls = []  # 新增: 用于存储完整的工具调用信息

    def generate_response(self):
        chunk = {
            "id": "chatcmpl-" + self.custom_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.full_message_content,
                        "tool_calls": self.tool_calls if self.tool_calls else None
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens
            }
        }

        # json_data = json.dumps(chunk)
        return chunk

    def generate_sse_response(self, content=None):
        current_timestamp = int(time.time())
        chunk = {
            "id": f"chatcmpl-{self.custom_id}",
            "object": "chat.completion.chunk",
            "created": current_timestamp,
            "model": self.model,
            "system_fingerprint": None,
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
        elif content['type'] == 'tool_calls':
            chunk["choices"][0]["delta"] = {"tool_calls": content['function']}
        elif content['type'] == 'stop':
            chunk["choices"][0]["delta"] = {}
            chunk["choices"][0]["finish_reason"] = "stop"
            chunk["usage"] = {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            }
        elif content['type'] == 'end':
            return "[DONE]"
        else:
            return None

        json_data = json.dumps(chunk)
        return f"{json_data}"

    def handle_SSE_data_line(self, line: str):
        if line.startswith("event:"):
            return None
        if line.startswith("data:"):
            line = line[5:].strip()
        line = line.strip()
        if line == "[DONE]":
            return "[DONE]"
        if line == "":
            return None

        try:
            json_data = json.loads(line)
            event_type = json_data.get('type')

            if event_type == 'message_start':
                message = json_data.get('message', {})
                self.custom_id = message.get('id')
                self.model = message.get('model')
                self.prompt_tokens = message.get('usage', {}).get('input_tokens', 0)
                return self.generate_sse_response()

            elif event_type == 'content_block_delta':
                delta = json_data.get('delta', {})
                if delta.get('type') == 'text_delta':
                    content = delta.get('text', '')
                    self.full_message_content += content
                    return self.generate_sse_response({'type': 'content', 'content': content})
                elif delta.get('type') == 'input_json_delta':
                    partial_json = delta.get('partial_json', '')
                    if self.tool_calls:
                        self.tool_calls[-1]['function']['arguments'] += partial_json
                    else:
                        self.tool_calls.append({
                            "id": f"call_{len(self.tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": "search",  # 假设工具名称为 search
                                "arguments": partial_json
                            }
                        })
                    return self.generate_sse_response({'type': 'tool_calls', 'function': self.tool_calls})

            elif event_type == 'message_delta':
                delta = json_data.get('delta', {})
                self.completion_tokens = json_data.get('usage', {}).get('output_tokens', 0)
                self.total_tokens = self.prompt_tokens + self.completion_tokens
                if delta.get('stop_reason'):
                    return self.generate_sse_response({'type': 'stop'})

            elif event_type == 'message_stop':
                return self.generate_sse_response({'type': 'end'})

        except json.JSONDecodeError as e:
            print(f"claude handle_SSE_data_line \r\nJSON解析失败: {e}\r\n失败内容:{line}\r\n")
        except Exception as e:
            print(f"claude handle_SSE_data_line \r\n处理失败: {e}\r\n失败内容:{line}\r\n")

        return None

    def _update_tool_calls(self, new_tool_calls):
        for new_call in new_tool_calls:
            call_id = new_call.get('id')
            if call_id:
                existing_call = next((call for call in self.tool_calls if call.get('id') == call_id), None)
                if existing_call:
                    self._merge_tool_call(existing_call, new_call)
                else:
                    self.tool_calls.append(new_call)
            else:
                # 如果新的 tool call 没有 id，我们更新最后一个 tool call
                if self.tool_calls:
                    self._merge_tool_call(self.tool_calls[-1], new_call)
                else:
                    self.tool_calls.append(new_call)

    def _merge_tool_call(self, existing_call, new_call):
        for key, value in new_call.items():
            if key == 'function':
                if 'function' not in existing_call:
                    existing_call['function'] = {}
                for func_key, func_value in value.items():
                    if func_key == 'arguments':
                        existing_call['function']['arguments'] = existing_call['function'].get('arguments',
                                                                                               '') + func_value
                    else:
                        existing_call['function'][func_key] = func_value
            else:
                existing_call[key] = value

    def get_stats(self):
        return {
            "full_message_content": self.full_message_content,
            "custom_id": self.custom_id,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "tool_calls": self.tool_calls
        }

    def handle_data_line(self, line: str):
        try:
            json_data = json.loads(line)

            # 处理content
            content = json_data.get('content', [])
            for part in content:
                if part.get('type') == 'text':
                    self.full_message_content += part.get('text', '')
                elif part.get('type') == 'tool_use':
                    tool_call = {
                        "id": part.get('id'),
                        "type": "function",
                        "function": {
                            "name": part.get('name'),
                            "arguments": json.dumps(part.get('input', {}))
                        }
                    }
                    self.tool_calls.append(tool_call)

            # 处理usage
            usage = json_data.get('usage', {})
            self.prompt_tokens = usage.get('input_tokens', 0)
            self.completion_tokens = usage.get('output_tokens', 0)
            self.total_tokens = self.prompt_tokens + self.completion_tokens

            # 生成响应
            response = self.generate_response()

            return response

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}\n{line}\n")
            return None
        except Exception as e:
            print(f"处理失败: {e}\n{line}\n")
            return None


if __name__ == "__main__":
    def autotest(name, stream=False):
        testFIleList = [
            # "/Users/ll/Desktop/2024/ll-openai/app/provider/savebody/claude-3-5-sonnet@20240620_1a251e84e84ad6a2871c1faad6277946_sse.json"
            "/Users/ll/Desktop/2024/ll-openai/app/provider/savebody/claude-3-5-sonnet@20240620_4fb2fa075e8aa72291ea9da548e13d3e_data.json"
        ]
        for root, dirs, files in os.walk("../debugfile/debugdata/"):
            for file in files:
                if file.endswith(name):
                    testFIleList.append(os.path.join(root, file))
        for file_name in testFIleList:
            print("正在检查：", file_name)
            handler = claudeSSEHandler(custom_id=file_name)
            with open(file_name, "r", encoding="utf-8") as file:
                if stream:
                    for line in file:
                        sse = handler.handle_SSE_data_line(line)
                        if sse:
                            pass
                else:
                    filedata = file.read()
                    sse = handler.handle_data_line(filedata)
                    if sse:
                        pass
                    # print(handler.generate_response())

                print("文件统计信息：", json.dumps(handler.get_stats(), ensure_ascii=False, indent=4))
                print("-------------------")


    # autotest("claude_see.txt",True)
    autotest("claude_data.txt", False)
