import time
import ujson as json
import os


class geminiSSEHandler:
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
            "id": "chatcmpl-"+self.custom_id,
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
        if line.startswith("data:"):
            line = line[5:].strip()
        line = line.strip()
        if line == "[DONE]":
            return "[DONE]"
        if line == "":
            return None

        try:
            json_data = json.loads(line)

            candidates = json_data.get('candidates', [])
            usage_metadata = json_data.get('usageMetadata', {})

            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                finish_reason = candidates[0].get('finishReason')

                response_data = {}
                if parts:
                    part = parts[0]
                    if 'text' in part:
                        response_data['type'] = 'content'
                        response_data['content'] = part['text']
                        self.full_message_content += response_data['content']
                    elif 'functionCall' in part:
                        response_data['type'] = 'tool_calls'
                        function_call = part['functionCall']
                        tool_call = {
                            "id": f"call_{len(self.tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": function_call.get('name'),
                                "arguments": json.dumps(function_call.get('args', {}))
                            }
                        }
                        self.tool_calls.append(tool_call)
                        response_data['function'] = [tool_call]
                elif finish_reason == 'STOP':
                    response_data['type'] = 'stop'
                else:
                    response_data['type'] = 'unknown'
                    response_data['content'] = ''

                # 更新token计数
                self.prompt_tokens = usage_metadata.get('promptTokenCount', 0)
                self.completion_tokens = usage_metadata.get('candidatesTokenCount', 0)
                self.total_tokens = usage_metadata.get('totalTokenCount', 0)

                return self.generate_sse_response(response_data)

        except json.JSONDecodeError as e:
            print(f"gemini handle_SSE_data_line \r\nJSON解析失败: {e}\r\n失败内容:{line}\r\n")
            return None
        except Exception as e:
            print(f"gemini handle_SSE_data_line \r\n处理失败: {e}\r\n失败内容:{line}\r\n")
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

            # 处理candidates
            candidates = json_data.get('candidates', [])
            if candidates:
                candidate = candidates[0]
                content = candidate.get('content', {})
                parts = content.get('parts', [])

                # 处理function call
                for part in parts:
                    if 'functionCall' in part:
                        function_call = part['functionCall']
                        tool_call = {
                            "type": "function",
                            "function": {
                                "name": function_call.get('name'),
                                "arguments": json.dumps(function_call.get('args', {}))
                            }
                        }
                        self.tool_calls.append(tool_call)
                    elif 'text' in part:
                        self.full_message_content += part['text']

                # 设置role
                role = content.get('role', 'assistant')

            # 处理usage
            usage_metadata = json_data.get('usageMetadata', {})
            self.prompt_tokens = usage_metadata.get('promptTokenCount', 0)
            self.completion_tokens = usage_metadata.get('candidatesTokenCount', 0)
            self.total_tokens = usage_metadata.get('totalTokenCount', 0)

            # 生成响应
            response = self.generate_response()

            # 如果没有custom_id，使用当前时间戳
            if not self.custom_id:
                self.custom_id = f"gemini-{int(time.time())}"

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
            "/Users/ll/Desktop/2024/ll-openai/app/provider/debugdata/vertexai_gemini_gemini-1.5-pro_data.txt"
        ]
        for root, dirs, files in os.walk("../debugfile/debugdata/"):
            for file in files:
                if file.endswith(name):
                    testFIleList.append(os.path.join(root, file))
        for file_name in testFIleList:
            print("正在检查：", file_name)
            handler = geminiSSEHandler(custom_id=file_name)
            with open(file_name, "r", encoding="utf-8") as file:
                if stream:
                    for line in file:
                        sse = handler.handle_SSE_data_line(line)
                        if sse:
                            pass
                            print(sse)
                else:
                    filedata = file.read()
                    sse = handler.handle_data_line(filedata)
                    if sse:
                        pass
                    # print(handler.generate_response())


                print("文件统计信息：", json.dumps(handler.get_stats(), ensure_ascii=False, indent=4))
                print("-------------------")


    autotest("gemini_see.txt",True)
    # autotest("_data.txt", False)
