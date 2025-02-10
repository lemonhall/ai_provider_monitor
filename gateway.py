from datetime import datetime
import os
import time
import json
import asyncio
from typing import AsyncIterator, Dict, List, Optional, Set
from fastapi.concurrency import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from openai import APIConnectionError, APIError, AsyncOpenAI
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import uvicorn


# 服务商配置列表
PROVIDERS = [
    {
        "name": "deepseek",
        "env_var": "OPENAI_API_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat"
    },
    {
        "name": "siliconflow",
        "env_var": "SILICONFLOW_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3"
    },
    {
        "name": "huoshan",
        "env_var": "HUOSHAN_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "ep-20250204220334-l2q5g"
    },
    {
        "name": "tencent",
        "env_var": "TENCENT_API_KEY",
        "base_url": "https://api.lkeap.cloud.tencent.com/v1",
        "model": "deepseek-v3"
    },
    {
        "name": "bailian",
        "env_var": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "deepseek-v3"
    }
]

class ProviderStatus(BaseModel):
    online: bool = False
    last_check: datetime = datetime.min
    response_time: float = 0.0
    success_rate: float = 0.0
    total_requests: int = 0
    failed_requests: int = 0
    last_error: Optional[str] = None  # 新增错误信息字段
    retry_count: int = 0

class RoutingManager:
    def __init__(self):
        self.provider_stats = {p["name"]: ProviderStatus() for p in PROVIDERS}
        self.history = []
        
    def update_stats(self, provider: str, success: bool, response_time: float):
        # 其他统计逻辑保持不变...
        stats = self.provider_stats[provider]
        stats.online = success
        stats.total_requests += 1
        stats.failed_requests += 0 if success else 1
        stats.success_rate = 1 - (stats.failed_requests / stats.total_requests)
        stats.response_time = (stats.response_time + response_time) / stats.total_requests
        stats.last_check = datetime.now()
        print(provider,":",stats)

    def get_best_provider(self) -> Optional[Dict]:
        available = []
        for provider in PROVIDERS:
            stats = self.provider_stats[provider["name"]]
            if stats.online and stats.success_rate > 0.7:
                available.append((provider, stats))
        
        if not available:
            return None
        
        my_choice = min(
            available,
            key=lambda x: (x[1].response_time * 0.6 + (1 - x[1].success_rate) * 0.4)
        )[0]

        print("get_best_provider:",my_choice)
        # 根据响应时间和成功率综合评分
        return my_choice

class APIMonitor:
    def __init__(self, routing: RoutingManager):
        #这里相当于是依赖注入了对应的路由管理器
        self.routing = routing
        
    async def check_provider(self, provider: Dict):
        """使用OpenAI SDK进行健康检查"""
        status = self.routing.provider_stats[provider["name"]]
        """异步检查单个服务商可用性"""
        api_key = os.getenv(provider["env_var"])
        if not api_key:
            return
            
        try:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=provider["base_url"],
                timeout=10.0
            )
            start_time = time.time()
            # 发送真实的API请求测试
            response = await client.chat.completions.create(
                messages=[{"role": "user", "content": "ping"}],
                model=provider["model"],
                max_tokens=5,
                temperature=0.1
            )
            # 验证响应有效性
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("Invalid API response")
            
            latency = (time.time() - start_time) * 1000  # 毫秒

            #对RoutingManager上报最新的情况
            self.routing.update_stats(
                provider["name"],
                success=True,
                response_time=latency
            )
            status.online = True
            status.retry_count = 0
            status.last_error = None

        except Exception as e:
            status.online = False
            status.last_error = self._format_error(e)
            status.retry_count += 1
            self.routing.update_stats(
                provider["name"],
                success=False,
                response_time=30000  #失败一次我就给你加30秒的惩罚
            )
        
        finally:
            status.last_check = datetime.now()
    
    def _format_error(self, e: Exception) -> str:
        """格式化错误信息"""
        if isinstance(e, APIConnectionError):
            return f"Connection error: {e.__cause__}"
        elif isinstance(e, APIError):
            return f"API error: {e.code} {e.message}"
        return f"{type(e).__name__}: {str(e)}"

    async def run_continuous_check(self):  # 修复2：正确的方法名称
        """持续运行健康检查"""
        while True:
            try:
                await self.run_health_check_cycle()  # 修复3：调用实际检查方法
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Monitor error: {str(e)}")
                await asyncio.sleep(60)
    
    async def run_health_check_cycle(self):
        """执行完整健康检查周期"""
        tasks = []
        for provider in PROVIDERS:
            tasks.append(self.check_provider(provider))
        await asyncio.gather(*tasks)
        #都跑完了打印一个你当前的最佳选择给我们看看呗
        self.routing.get_best_provider()

class OpenAIGateway:
    def __init__(self):
        self.app = FastAPI(title="AI Gateway")
        self.routing = RoutingManager()
        self.monitor = APIMonitor(self.routing)
        self.background_tasks: Set[asyncio.Task] = set()

        
        # 使用新的 lifespan 处理机制
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            """生命周期管理"""
            # 启动阶段
            monitor_task = asyncio.create_task(self.monitor.run_continuous_check())
            self.background_tasks.add(monitor_task)
            monitor_task.add_done_callback(self.background_tasks.discard)
            
            yield  # 应用运行阶段
            
            # 关闭阶段
            for task in self.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.app = FastAPI(
            title="AI Gateway",
            lifespan=lifespan
        )
        
        # 注册路由保持不变
        self.app.add_api_route(
            "/v1/chat/completions",
            self.chat_completion,
            methods=["POST"]
        )

    async def forward_request(self, provider: Dict, request: Request):
        print("进入了forward_request")
        """转发请求到指定服务商"""
        api_key = os.getenv(provider["env_var"])
        if not api_key:
            raise ValueError(f"Missing API key for {provider['name']}")
            
        try:
            original_body = await request.json()
            modified_body = original_body.copy()
            modified_body["model"] = provider["model"]
            stream_mode = modified_body.get("stream", False)  # 获取流式模式标志

            async with httpx.AsyncClient(base_url=provider["base_url"]) as client:
                # 添加流式传输支持
                stream = modified_body.get("stream", False)
                
                start = time.time()
                response = await client.post(
                    "/chat/completions",
                    json=modified_body,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    timeout=30,
                    # 关键修改：根据stream参数启用流式响应
                    follow_redirects=stream_mode
                )
                response.raise_for_status()

                # 更新统计信息
                self.routing.update_stats(
                    provider["name"],
                    True,
                    (time.time() - start) * 1000
                )

                # 返回原始响应内容和 headers，并携带流式模式标志
                return {
                    "content": response,
                    "headers": dict(response.headers),
                    "status_code": response.status_code,
                    "stream": stream_mode  # 新增流式模式标志
                }
                
        except httpx.HTTPStatusError as e:
            self.routing.update_stats(provider["name"], False, 30000)
            # 改为抛出HTTPException而不是返回JSONResponse
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Upstream error: {e.response.text}"
            )
        except Exception as e:
            self.routing.update_stats(provider["name"], False, 30000)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    async def chat_completion(self, request: Request):
        """处理聊天补全请求"""
        # 智能路由选择
        provider = self.routing.get_best_provider()
        print("本次请求由：",provider," 执行；")
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No available AI providers"
            )
            
        # 请求转发
        try:
            result = await self.forward_request(provider, request)
            
            if result["stream"]:
                # 创建异步生成器逐块转发流式数据
                async def generate_stream():
                    async for chunk in result["content"].aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    content=generate_stream(),
                    headers=result["headers"],
                    status_code=result["status_code"],
                    media_type="text/event-stream"  # 强制指定流式类型
                )
            else:
                return JSONResponse(
                    content=json.loads(await result["content"].aread()),
                    headers=result["headers"],
                    status_code=result["status_code"]
                )
        except HTTPException as e:
            print("============================================")
            print("触发了chat_completion的失败重试逻辑，错误如下：")
            print(e)
            # 获取原始请求体
            original_body = await request.json()
            print("触发了错误的请求体为：")
            print(original_body)
            print("============================================")
            # 失败重试逻辑
            backup_providers = [p for p in PROVIDERS if p["name"] != provider["name"]]
            for backup in backup_providers:
                try:
                    result = await self.forward_request(backup, request)
                    return JSONResponse(content=result)
                except:
                    continue
            raise e

# 运行服务
if __name__ == "__main__":
    gateway = OpenAIGateway()
    uvicorn.run(gateway.app, host="0.0.0.0", port=8000)