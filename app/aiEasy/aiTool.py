from functools import wraps
from typing import Callable


class _aiTool:
    def __init__(self, func: Callable, **kwargs):
        self.func = func
        self.options = {}
        # 如果传入的纯文本参数name就设置为description
        for name, value in kwargs.items():
            if isinstance(value, str):
                self.options[name] = {"description": value}
            else:
                self.options[name] = value

        pass

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def aiTool(**kwargs):
    def decorator(func: Callable) -> _aiTool:
        @wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        return _aiTool(wrapper, **kwargs)

    return decorator