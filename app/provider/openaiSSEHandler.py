import time

import pyefun
import ujson as json
import os


class openaiSSEHandler:
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
        if line.strip() == "data: [DONE]":
            return "[DONE]"

        if not line or line.isspace():
            return ""

        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()

        if line == "[DONE]":
            return "[DONE]"

        try:
            json_data = json.loads(line)

            # id = json_data.get('id', '')
            # self.model = json_data.get('model', '')
            choices = json_data.get('choices', [{}])

            if choices:
                delta = choices[0].get('delta', {})
                finish_reason = choices[0].get('finish_reason')
            else:
                delta = {}
                finish_reason = None

            response_data = {}
            if 'content' in delta:
                response_data['type'] = 'content'
                response_data['content'] = delta['content']
                self.full_message_content += delta['content']
            elif 'tool_calls' in delta:
                response_data['type'] = 'tool_calls'
                response_data['function'] = delta['tool_calls']
                self._update_tool_calls(delta['tool_calls'])
            elif finish_reason == 'tool_calls':
                response_data['type'] = 'tool_calls'
                response_data['function'] = self.tool_calls
            elif finish_reason == 'stop':
                response_data['type'] = 'stop'
            else:
                response_data['type'] = 'unknown'
                response_data['content'] = ''

            # 检查有没有 usage 如果有就读取 然后更新到 self.prompt_tokens 和 self.completion_tokens 和 self.total_tokens
            usage = json_data.get('usage', {})
            if usage:
                self.prompt_tokens = usage.get('prompt_tokens', 0)
                self.completion_tokens = usage.get('completion_tokens', 0)
                self.total_tokens = usage.get('total_tokens', 0)


            return self.generate_sse_response( response_data)

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}\r\n{line}\r\n")
            return None
        except Exception as e:
            print(f"处理失败: {e}\r\n{line}\r\n")
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
            
            self.custom_id = json_data.get('id', self.custom_id)
            self.model = json_data.get('model', self.model)
            
            choices = json_data.get('choices', [{}])
            if choices:
                message = choices[0].get('message', {})
                self.full_message_content = message.get('content', '')
                self.tool_calls = message.get('tool_calls', [])
            
            usage = json_data.get('usage', {})
            self.prompt_tokens = usage.get('prompt_tokens', 0)
            self.completion_tokens = usage.get('completion_tokens', 0)
            self.total_tokens = usage.get('total_tokens', 0)
            
            return self.generate_response()
        
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}\n{line}\n")
            return None
        except Exception as e:
            print(f"处理失败: {e}\n{line}\n")
            return None


if __name__ == "__main__":
    # testFIleList = [
    #     "./debugdata/1.txt",
    # ]
    # for file_name in testFIleList:
    #     print("正在检查：", file_name)
    #     handler = openaiSSEHandler(custom_id=file_name)
    #     with open(file_name, "r", encoding="utf-8") as file:
    #         filedata = file.read()
    #         out = handler.handle_data_line(filedata)
    #         print(out)
    #         print("文件统计信息：", json.dumps(handler.get_stats(), ensure_ascii=False, indent=4))
    #
    # exit()
    def autotest(name,stream=False):
        testFIleList = [
            "/Users/ll/Desktop/2024/ll-openai/app/provider/自留测试数据/sse.txt",
        ]
        for root, dirs, files in os.walk("debugfile/debugdata/"):
            for file in files:
                if file.endswith(name):
                    testFIleList.append(os.path.join(root, file))
        for file_name in testFIleList:
            print("正在检查：", file_name)
            handler = openaiSSEHandler(custom_id=file_name)
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

                print("文件统计信息：", json.dumps(handler.get_stats(), ensure_ascii=False, indent=4))
                # print("文件统计信息：",json.dumps(handler.get_stats(), ensure_ascii=False))
                # ic(handler.get_stats())
                d =handler.get_stats()
                pyefun.写到文件("1.html",d['full_message_content'])
                print("-------------------")

    autotest("xopenai_sse.txt",True)
    # autotest("openai_data.txt",False)
