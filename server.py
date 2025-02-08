from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
import duckdb
import json

from fastapi.staticfiles import StaticFiles

# 定义监控数据的数据模型
class Status(BaseModel):
    provider: str
    online: bool
    response_time: float | None = None
    error: str | None = None
    timestamp: int

app = FastAPI()

# 挂载静态文件路径 (将其他静态文件放在 static 文件夹中)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 数据库连接池
db = duckdb.connect("mqtt_status.duckdb", read_only=False)

# 初始化数据库表
def init_database():
    # 检查表是否存在，不存在时创建
    try:
        # 尝试查询表
        db.sql("SELECT * FROM api_monitor LIMIT 0")
    except duckdb.CatalogException:
        # 如果表不存在，创建表
        db.sql("""
        CREATE TABLE api_monitor (
            provider VARCHAR,
            online BOOLEAN,
            response_time FLOAT,
            error VARCHAR,
            timestamp INT
        )
        """)

init_database()  # 初始化数据库表

# 定义依赖，管理数据库连接
async def get_db_conn():
    try:
        yield db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# 定义接收监控数据的接口
@app.post("/api_status", tags=["monitor"])
async def post_status(status: Status, db_conn=Depends(get_db_conn)):
    try:
        # 构造 SQL 查询和参数
        query = """
        INSERT INTO api_monitor (provider, online, response_time, error, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (
            status.provider,
            status.online,
            status.response_time,
            status.error,
            status.timestamp
        )

        # 插入数据到 DuckDB，使用 params 参数
        db_conn.sql(query, params=params)
        
        return {"message": "Status received and stored successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to store status: {str(e)}")

# 定义查询历史监控数据的接口
@app.get("/api_status/history", tags=["monitor"])
async def get_status_history(limit: int = Query(100, description="Maximum number of records to return")):
    try:
        # 查询历史数据
        result = db.sql("SELECT * FROM api_monitor ORDER BY timestamp DESC LIMIT ?", params=(limit,))
        # 将结果转换为 JSON 格式的列表
        return [dict(zip(["provider", "online", "response_time", "error", "timestamp"], row)) for row in result.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve status history: {str(e)}")


# 处理根路径请求，返回 index.html
@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# 启动 FastAPI 服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)