#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
"""

import base64
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger


def setup_logging(level: str = "INFO"):
    """设置日志"""
    # 移除默认处理器
    logger.remove()

    # 添加控制台处理器
    logger.add(
        sink=lambda msg: print(msg, end=''),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )

    # 添加文件处理器
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.add(
        sink=log_dir / "analyzer.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


def encode_image_to_base64(image_path: Path) -> Optional[str]:
    """将图片编码为 base64"""
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        return base64.b64encode(image_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f"图片{image_path}编码失败: {e}")
        return None


def resolve_image_files(file_patterns: List[str], img_dir: Path, supported_formats: List[str]) -> List[Path]:
    """解析图片文件模式，返回实际的文件路径列表"""
    from fnmatch import fnmatch
    import glob

    image_files = []

    for pattern in file_patterns:
        # 处理通配符模式
        if '*' in pattern or '?' in pattern:
            # 使用 glob 匹配文件
            matches = list(img_dir.glob(pattern))
            image_files.extend(matches)
        else:
            # 直接文件路径
            file_path = img_dir / pattern
            if file_path.exists():
                image_files.append(file_path)

    # 去重并过滤支持的格式
    unique_files = list(set(image_files))
    valid_files = [
        f for f in unique_files
        if f.exists() and f.suffix.lower() in supported_formats
    ]

    # 按文件名排序
    valid_files.sort()

    return valid_files


def format_timing_results(timings: Dict) -> str:
    """格式化时间结果"""
    lines = []
    lines.append("=" * 60)
    lines.append("PyCURL 详细网络时间分析")
    lines.append("=" * 60)

    timing_items = [
        ("DNS解析时间", timings['dns_time'] * 1000),
        ("TCP握手时间", timings['tcp_handshake'] * 1000),
        ("SSL握手时间", timings['ssl_handshake'] * 1000),
        ("请求发送时间", timings['request_send'] * 1000),
        ("服务器处理时间", timings['server_processing'] * 1000),
        ("响应传输时间", timings['response_transfer'] * 1000),
        ("总时间", timings['total_time'] * 1000)
    ]

    for name, value in timing_items:
        lines.append(f"{name}: {value:.1f} ms")

    # 网络统计
    lines.append("\n网络统计:")
    conn_time = (timings['dns_time'] + timings['tcp_handshake'] + timings['ssl_handshake']) * 1000
    req_time = (timings['request_send'] + timings['tcp_handshake'] + timings['ssl_handshake'] + timings[
        'dns_time']) * 1000
    network_ratio = (timings['total_time'] - timings['server_processing']) / timings['total_time'] * 100

    lines.append(f"连接建立总时间: {conn_time:.1f} ms")
    lines.append(f"请求总时间(连接+发送): {req_time:.1f} ms")
    lines.append(f"网络传输占比: {network_ratio:.1f}%")

    return "\n".join(lines)


def save_results(data: Dict, filepath: Path):
    """保存结果到文件"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"结果已保存到: {filepath}")
    except Exception as e:
        logger.error(f"保存结果失败: {e}")


def load_results(filepath: Path) -> Optional[Dict]:
    """从文件加载结果"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载结果失败: {e}")
        return None


def generate_timestamp() -> str:
    """生成时间戳"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")