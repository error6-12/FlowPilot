"""
FastAPI应用程序

主应用程序入口，配置中间件、路由和异常处理
自动初始化企业知识库；旧预约模式需显式开启
"""
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from services.knowledge_service import KnowledgeService
from typing import List, Optional
import logging
import asyncio

# 导入路由
from api import LEGACY_APPOINTMENT_ENABLED, api_routers
from api.core.exceptions import api_exception_handler, general_exception_handler, BusinessException
from web import router as web_router

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic模型
from pydantic import BaseModel

class KnowledgeRequest(BaseModel):
    content: str
    category: str
    keywords: List[str] = []

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    category: Optional[str] = None

async def initialize_system():
    """系统启动时自动初始化"""
    try:
        logger.info("🚀 正在初始化 FlowPilot 企业员工服务平台...")
        
        # 初始化知识库服务
        logger.info("📚 初始化知识库服务...")
        knowledge_service = KnowledgeService()
        await knowledge_service.initialize()
        
        if LEGACY_APPOINTMENT_ENABLED:
            from services.recommendation_service import RecommendationService
            from services.technician_service import TechnicianService

            logger.info("旧预约兼容模式已开启，初始化技师与推荐服务")
            TechnicianService().initialize_default_technicians()
            RecommendationService().start_scheduler()
        
        logger.info("✅ 系统初始化完成！")
        
    except Exception as e:
        logger.error(f"❌ 系统初始化失败: {e}")
        raise

def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    
    app = FastAPI(
        title="FlowPilot 企业员工服务与流程协同平台",
        description="Multi-Agent 驱动的企业知识咨询、流程执行与运营治理平台",
        version="2.0.0",
        docs_url=None,
        redoc_url="/redoc"
    )

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境中应该设置具体的域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册异常处理器
    app.add_exception_handler(BusinessException, api_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # 注册API路由
    for router in api_routers:
        app.include_router(router)

    # 注册Web界面路由
    app.include_router(web_router)

    @app.get("/docs", include_in_schema=False)
    async def flowpilot_swagger_ui():
        """Render Swagger UI with a stable link back to FlowPilot."""
        swagger = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - 流程 API",
        )
        html = swagger.body.decode("utf-8")
        back_button = """
        <a href="/" aria-label="返回 FlowPilot 首页" style="
          position:fixed;top:14px;right:18px;z-index:9999;
          padding:10px 16px;border-radius:999px;text-decoration:none;
          color:#fff;background:linear-gradient(120deg,#38bdf8,#06b6d4);
          box-shadow:0 6px 18px rgba(14,116,144,.28);
          font:600 14px 'Microsoft YaHei',system-ui,sans-serif;
        ">← 返回 FlowPilot</a>
        """
        return HTMLResponse(html.replace("<body>", f"<body>{back_button}", 1))

    # 静态文件
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    # 添加启动事件
    @app.on_event("startup")
    async def startup_event():
        """应用启动时自动初始化系统"""
        await initialize_system()

    return app

# 创建应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
