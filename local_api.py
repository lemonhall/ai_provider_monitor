from openai import OpenAI

# 构造 client
client = OpenAI(
    api_key="XXXXXXXXXXXXXXXXX",  # 知识引擎原子能力 APIKey
    base_url="http://localhost:8000/v1",
)
# 流式
stream = False
# 请求
chat_completion = client.chat.completions.create(
    model="deepseek-r1",
    messages=[
        {
            "role": "user",
            "content": "你是谁",
        }
    ]
)

result = chat_completion.choices[0].message.content

print(result)