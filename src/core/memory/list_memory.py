"""
列表内存管理器
用于管理Agent的记忆存储
"""

import os
import json
import aiofiles
from typing import List, Dict, Any
from loguru import logger


class ListMemoryManager:
    """列表内存管理器"""
    def __init__(self, memory_file_path: str):
        self.memory_file_path = memory_file_path
        self.ensure_memory_file()
    def ensure_memory_file(self):
        """确保内存文件存在"""
        os.makedirs(os.path.dirname(self.memory_file_path), exist_ok=True)
        if not os.path.exists(self.memory_file_path):
            with open(self.memory_file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
    async def get_memory(self) -> List[Dict[str, Any]]:
        """获取内存数据"""
        try:
            async with aiofiles.open(self.memory_file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content.strip() else []
        except Exception as e:
            logger.error(f"读取内存文件失败: {str(e)}")
            return []
    async def add_memory(self, memory_item: Dict[str, Any]):
        """添加内存项"""
        try:
            memories = await self.get_memory()
            memories.append(memory_item)
            async with aiofiles.open(self.memory_file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(memories, ensure_ascii=False, indent=2))
            logger.info(f"添加内存项成功: {memory_item.get('type', '未知')}")
        except Exception as e:
            logger.error(f"添加内存项失败: {str(e)}")
    async def clear_memory(self):
        """清空内存"""
        try:
            async with aiofiles.open(self.memory_file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps([], ensure_ascii=False))
            logger.info("内存清空成功")
        except Exception as e:
            logger.error(f"清空内存失败: {str(e)}")
    async def search_memory(self, query: str) -> List[Dict[str, Any]]:
        """搜索内存"""
        try:
            memories = await self.get_memory()
            results = []
            for memory in memories:
                # 简单的文本搜索
                if query.lower() in str(memory).lower():
                    results.append(memory)
            return results
        except Exception as e:
            logger.error(f"搜索内存失败: {str(e)}")
            return []
