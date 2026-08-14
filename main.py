"""
主入口文件
启动 PrivLexa 隐律智策平台
"""

import sys
import io

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
elif getattr(sys.stdout, "buffer", None) is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import uvicorn
from loguru import logger

# 导入应用和配置
from src.app import app
from src.core.config import get_config_manager

# 获取配置管理器并验证配置
config_manager = get_config_manager()
api_config = config_manager.get_api_config()

if __name__ == "__main__":
    try:
        print("🚀 启动 PrivLexa 隐律智策平台...")
        logger.info("应用启动中...")
        print(f"📖 API文档地址: http://localhost:{api_config.port}/docs")
        print(f"🔗 系统地址: http://localhost:{api_config.port}")

        uvicorn.run(
            "src.app:app",
            host=api_config.host,
            port=api_config.port,
            reload=api_config.reload,
            log_level=api_config.log_level
        )
    except Exception as e:
        logger.error(f"应用启动失败: {str(e)}")
        print(f"❌ 应用启动失败: {str(e)}")
        sys.exit(1)
