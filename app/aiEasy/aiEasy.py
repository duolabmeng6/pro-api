import inspect
import json
from openai import OpenAI

from app.aiEasy.aiTool import _aiTool


class aiEasy:
    def __init__(self, client: OpenAI, model, prompt=""):
        self.client = client
        self.model = model
        self.tools = []
        self.available_functions = {}
        if prompt == "":
            prompt = """你是一个智能助手,擅长利用各种工具来帮助用户解决问题。请仔细分析用户的需求,并合理地使用可用的工具函数来获取信息或执行任务。在回答时,要综合考虑用户的原始问题和通过工具获得的信息,给出全面、准确、有帮助的回答。如果需要多个步骤,请清晰地解释你的思路。始终以用户的需求为中心,努力提供最佳的解决方案。"""
        self.prompt = prompt

    def _register_tool(self, func):
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        sig = inspect.signature(func.func)

        for name, param in sig.parameters.items():
            param_info = {
                "type": "string",  # 默认类型为字符串
                "description": f"parameters {name}"
            }

            # 如果在options中定义了该参数的信息，则使用定义的信息
            if name in func.options:
                for option, value in func.options[name].items():
                    param_info[option] = value

            # 如果参数没有默认值，则将其添加到required列表中
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(name)

            # 将参数信息添加到properties中
            parameters["properties"][name] = param_info

        # 添加函数到tools列表
        self.tools.append({
            "type": "function",
            "function": {
                "name": func.func.__name__,
                "description": func.func.__doc__ or "",
                "parameters": parameters
            }
        })

        # 打印tools列表（用于调试）
        # print(json.dumps(self.tools, indent=4, ensure_ascii=False))

        # 将函数添加到可用函数字典中
        self.available_functions[func.func.__name__] = func.func

    def register_function(self, func):
        # 检查是不是tool封装的
        if isinstance(func, _aiTool):
            self._register_tool(func)
            return

        sig = inspect.signature(func)

        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        for name, param in sig.parameters.items():
            parameters["properties"][name] = {
                "type": "string",
                "description": ""
            }
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(name)

        self.tools.append({
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": func.__doc__,
                "parameters": parameters
            }
        })
        self.available_functions[func.__name__] = func

    def setSystemPrompt(self, prompt):
        self.prompt = prompt

    def chat(self, user_input, output=None, id=""):
        output = "using this JSON schema Output JSON Format: \r\n" + json.dumps(output, indent=4, ensure_ascii=False)
        input = f"question: {user_input}"
        # if output:
        #     input = f"{input}\r\n{output}"

        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": input}
        ]
        print(f"send 1: 第一次")
        print(f"{input}")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
            extra_headers={
                "id": id + "a"
            }
            # response_format={
            #     'type': 'json_object'
            # }
        )
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            print(f"检测到 {len(tool_calls)} 个工具调用")
            messages.append(response_message)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                print(f"调用函数: {function_name}, 参数: {function_args}")
                # 这里需要做一些容错处理 检查函数是否存在
                if function_name not in self.available_functions:
                    print(f"函数 {function_name} 不存在")
                    continue
                else:
                    try:
                        function_response = self.available_functions[function_name](**function_args)
                    except Exception as e:
                        print(f"函数 {function_name} 调用失败: {e}")
                        function_response = f"函数 {function_name} 调用失败"

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": function_response
                })
                print(f"函数 {function_name} 的响应: {function_response}")

            messages.append({"role": "user", "content": output})

            # 第二次请求：汇总结果
            print("send 2: 汇总结果")
            second_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={
                    'type': 'json_object'
                },
                extra_headers={
                    "id": id + "b"
                }
            )
            output_data = second_response.choices[0].message.content
        else:
            output_data = response_message.content

        print(f"最终结果: {output_data}")
        if output:
            ok = False
            # 使用正则表达式截取代码块内容
            import re
            pattern = r'```(?:\w+)?\s*\n?(.*?)(?:\n?```|$)'
            matches = re.findall(pattern, output_data, re.DOTALL)
            if matches:
                output_data = '\n'.join(matches)

            # 尝试解析JSON
            try:
                output_data = json.loads(output_data)
                ok = True
            except json.JSONDecodeError:
                # 如果解析失败，尝试清理字符串并再次解析
                cleaned_data = re.sub(r'[\n\r\t]', '', output_data)
                try:
                    output_data = json.loads(cleaned_data)
                    ok = True
                except json.JSONDecodeError:
                    print("JSON 解析失败")
                    # 如果仍然失败，保留原始字符串

            if not ok:
                print("无法解析为JSON，保留原始输出")

            print(f"json最终结果: {output_data}")

        return output_data
