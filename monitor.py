from datetime import datetime
import os
import time
import json
import warnings
from typing import Dict, Optional
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from openai import OpenAI
from openai import APIConnectionError, APIError, APIStatusError
# 使用 asyncio 运行异步代码
import asyncio
import httpx


# -----------------------------------------------------------------------------
# 使用 PowerShell
# 打开 PowerShell（在 “开始” 菜单中搜索 “PowerShell” 并打开）。
# 要为当前用户设置环境变量，可以使用
# $env:OPENAI_API_KEY = "your_api_key"
# 命令。
# 同样，将"your_api_key"替换为实际的 API 密钥。不过，这种方式设置的环境变量只在当前 PowerShell 会话中有效。

# 要永久设置环境变量（对于当前用户），可以使用
# [Environment]::SetEnvironmentVariable("HUOSHAN_API_KEY","your_api_key","User")。
# 如果要设置系统级别的环境变量（需要管理员权限），可以将最后一个参数改为"Machine"，
# 例如
# [Environment]::SetEnvironmentVariable("TENCENT_API_KEY","your_api_key","Machine")。
# Set up OpenAI API key
# 记得使用以上方法后，需要关闭vscode后重启vscode，之后点击F5运行python脚本的时候才能生效

# 配置信息
MQTT_BROKER = "192.168.50.233"
MQTT_PORT = 1883
STATUS_TOPIC = "api_status"  # 状态上报主题
CHECK_INTERVAL = 60  # 检查间隔（秒）

# 日志文件路径
LOG_FILE = "mqtt_status.log"

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

class APIMonitor:
    def __init__(self):
        self.mqtt_client = mqtt.Client(client_id="api_monitor", callback_api_version=CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_log = self.on_log  # 可选：用于调试日志
        self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
    
    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        """连接回调"""
        # Check if connection succeeded (0: Connection accepted)
        if reason_code.value == 0:
            print("Connected to MQTT broker successfully.")
        else:
            print(f"Connection failed with reason code: {reason_code.value}")
    
    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        """断开连接回调"""
        print(f"Disconnected from MQTT broker with reason code: {reason_code}")
    
    def on_log(self, client, userdata, level, buf):
        """调试日志回调"""
        print(f"MQTT Log: {buf}")
    
    def check_provider_status(self, provider: Dict) -> Dict:
        """检查单个服务商状态"""
        status = {
            "provider": provider["name"],
            "online": False,
            "response_time": None,
            "error": None,
            "timestamp": int(time.time())
        }
        
        api_key = os.getenv(provider["env_var"])
        if not api_key:
            status["error"] = "API key not found"
            return status
        
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=provider["base_url"],
                timeout=10
            )
            
            start_time = time.time()
            # 发送测试请求
            client.chat.completions.create(
                messages=[{"role": "user", "content": "ping"}],
                model=provider["model"],
                max_tokens=5
            )
            status["response_time"] = round((time.time() - start_time) * 1000, 2)
            status["online"] = True
        except APIConnectionError as e:
            status["error"] = f"Connection error: {e}"
        except APIStatusError as e:
            status["error"] = f"API error: {e.status_code} {e.message}"
        except APIError as e:
            status["error"] = f"API error: {e}"
        except Exception as e:
            status["error"] = f"Unexpected error: {str(e)}"
        
        return status
    
    def check_all_providers(self):
        """检查所有服务商"""
        for provider in PROVIDERS:
            status = self.check_provider_status(provider)
            self.publish_status(status)
            
    def log_payload(self, payload: str):
        """将 payload 写入日志文件"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] Published status: {payload}\n"

        # 确保以 UTF-8 格式写入文件
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_entry)
    
    def publish_status(self, status: Dict):
        """发布状态到MQTT"""
        payload = json.dumps(status, ensure_ascii=False)
        self.mqtt_client.publish(
            f"{STATUS_TOPIC}",
            payload,
            retain=True  # 设置 retain 标志为 True
        )
        print(f"Published status: {payload}")

        """发布状态到 FastAPI 服务器"""
        async def send_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api_status",  # 替换为 FastAPI 服务器的实际 IP 和端口
                    json=status
                )
                return response

        try:
            # 使用 asyncio.run 运行异步函数
            response = asyncio.run(send_request())
            
            if response.status_code == 200:
                print(f"Status published successfully: {payload}")
            else:
                print(f"Failed to publish status: {response.text}")
                print(response)
        except Exception as e:
            print(f"Error publishing status: {str(e)}")
        # 写入日志文件
        self.log_payload(payload)

if __name__ == "__main__":
    monitor = APIMonitor()
    try:
        while True:
            monitor.check_all_providers()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        monitor.mqtt_client.loop_stop()
        print("Monitoring stopped")