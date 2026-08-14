#!/usr/bin/env python
"""
日志文件清理脚本
清理或删除旧的日志文件，解决Windows文件锁定问题
"""

import os
import shutil
from pathlib import Path


def clean_logs(log_dir="logs"):
    """清理日志目录

    Args:
        log_dir: 日志目录路径
    """
    if not os.path.exists(log_dir):
        print(f"日志目录不存在: {log_dir}")
        return

    log_path = Path(log_dir)

    # 列出所有日志文件
    log_files = list(log_path.glob("*.log*"))

    if not log_files:
        print(f"没有找到日志文件在 {log_dir}")
        return

    print(f"找到 {len(log_files)} 个日志文件:")
    for log_file in log_files:
        print(f"  - {log_file.name}")

    # 清理日志文件
    removed_count = 0
    for log_file in log_files:
        try:
            if log_file.is_file():
                os.remove(log_file)
                print(f"已删除: {log_file.name}")
                removed_count += 1
        except Exception as e:
            print(f"无法删除 {log_file.name}: {str(e)}")

    print(f"\n共删除了 {removed_count} 个日志文件")


if __name__ == "__main__":
    clean_logs()
