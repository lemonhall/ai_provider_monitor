import httpx

payload = {
    "model": "deepseek-ai/DeepSeek-V3",
    "messages": [
        {
            "role": "user",
            "content": "你好啊"
        }
    ]
}
headers = {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
}

async def main():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions",
            json=payload,
            headers=headers
        )
        print(response.text)

# 运行异步函数
import asyncio
asyncio.run(main())