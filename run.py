#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

def check_environment():
    """检查运行环境"""
    print("🔍 检查运行环境...")

    # 检查 Python 版本
    python_version = sys.version_info
    if python_version < (3, 7):
        print(f"❌ Python 版本过低: {sys.version}")
        print("请使用 Python 3.7 或更高版本")
        return False

    print(f"✅ Python 版本: {sys.version}")

    # 检查必要的目录
    necessary_dirs = ['src/img', 'results', 'logs']
    for dir_name in necessary_dirs:
        dir_path = Path(__file__).parent / dir_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 创建目录: {dir_name}")

    # 检查配置文件
    config_file = Path(__file__).parent / 'config.yaml'
    if not config_file.exists():
        print("❌ 未找到 config.yaml 文件")
        print("请确保配置文件存在")
        return False

    # 检查 .env 文件
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        print("❌ 未找到 .env 文件")
        print("请复制 .env.example 为 .env 并设置你的 API 密钥")
        return False

    print("✅ 环境检查通过")
    return True


def install_dependencies():
    """安装依赖"""
    print("\n📦 检查依赖...")

    try:
        # 检查主要依赖
        import pycurl
        import yaml
        import dotenv
        import loguru
        import tqdm
        print("✅ 所有依赖已安装")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

    return True


def main():
    """主启动函数"""
    print("=" * 50)
    print("Gemini 图片颜色分析器")
    print("=" * 50)

    # 检查环境
    if not check_environment():
        return

    # 检查依赖
    if not install_dependencies():
        return

    # 导入主程序
    try:
        from src.main import main as app_main
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return

    # 运行主程序
    print("\n🚀 启动分析器...")
    try:
        app_main()
    except KeyboardInterrupt:
        print("\n👋 程序已被用户中断")
    except Exception as e:
        print(f"❌ 程序运行出错: {e}")


if __name__ == "__main__":
    main()