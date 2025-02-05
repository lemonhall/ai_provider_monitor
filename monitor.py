import os
import time
import json
from typing import Dict, Optional
import paho.mqtt.client as mqtt
from openai import OpenAI
from openai import APIConnectionError, APIError, APIStatusError

# 配置信息
MQTT_BROKER = "192.168.50.233"
MQTT_PORT = 1883
STATUS_TOPIC = "api_status"  # 状态上报主题
CHECK_INTERVAL = 300  # 检查间隔（秒）

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
    }
]

class APIMonitor:
    def __init__(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        self.mqtt_client.loop_start()
    
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
    
    def publish_status(self, status: Dict):
        """发布状态到MQTT"""
        payload = json.dumps(status, ensure_ascii=False)
        self.mqtt_client.publish(
            f"{STATUS_TOPIC}/{status['provider']}",
            payload
        )
        print(f"Published status: {payload}")

if __name__ == "__main__":
    monitor = APIMonitor()
    try:
        while True:
            monitor.check_all_providers()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        monitor.mqtt_client.loop_stop()
        print("Monitoring stopped")