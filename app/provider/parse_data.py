import json

from box import Box  # pip install python-box


def parse_data(json_str):
    if json_str.startswith("data:"):
        json_str = json_str[5:]
    else:
        return None
    try:
        return Box(json.loads(json_str),
                   default_box=True,
                   default_box_none=True,
                   conversion_box=True,
                   box_dots=True,

                   )
    except:
        return None


if __name__ == '__main__':
    pass
    with open("debugfile/debugdata/ep-20240729175503-5bbf7_openai_sse.txt", "r", encoding="utf-8") as f:
        data = f.read()
    # 换行符分割文本然后 去掉 前面的 data:
    datas = data.split("\n")
    addstr = ""
    for v in datas:
        parsed_data = parse_data(v)
        if parsed_data ==  None:
            continue
        print(parsed_data.choices[0].delta.content)

        print(parsed_data, v)
        print(parsed_data.a)
        print(parsed_data.a == "")

    print(addstr)
