![2ab9b68a36219debc6ee6cb77eba00d7](https://github.com/user-attachments/assets/67bd5cae-01cb-475d-b4d2-22941fcbe356)


0、**项目背景**
    
    监控多个AI服务商并将状态定时更新到监控屏幕，当前使用了MQTT协议推送到消息服务器

1、**初始化项目**

    uv init ai_provider_monitor



2、**添加依赖**

    uv add openai paho-mqtt python-dotenv


3、**运行**

    python monitor.py


4、**TODO**

    增加ESP-32那边的代码，读取MQTT来做警告 已完成

5、**增加服务端接口**

    uv add fastapi uvicorn duckdb
    uv add asyncio httpx

6、**本地透明网关**
    启动gateway.py，然后本地8000接口会监听，配置到http://localhost:8000/v1，就行了，注意是http，不是https
    依赖都在pyproject.toml里，我用的是uv在管理项目，可以问一下AI，怎么安装py的依赖