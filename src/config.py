#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / '.env')

class Config:
    """配置管理类"""

    def __init__(self, config_path: Path = None):
        # 默认配置路径
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config_path = config_path
        self._config = self._load_config()
        self._validate_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config or {}

    def _validate_config(self):
        """验证配置"""
        # 必须的配置项
        required_sections = ['api', 'images', 'prompts', 'output']
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"配置文件中缺少必要的段: {section}")

        # 验证 API 密钥
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("未设置 GOOGLE_API_KEY 环境变量")

    @property
    def api_key(self) -> str:
        """获取 API 密钥"""
        return os.getenv("GOOGLE_API_KEY")

    @property
    def api_url(self) -> str:
        """获取 API URL"""
        return self._config['api']['base_url']

    @property
    def api_timeout(self) -> int:
        """获取 API 超时时间"""
        return self._config['api']['timeout']

    @property
    def max_retries(self) -> int:
        """获取最大重试次数"""
        return self._config['api']['max_retries']

    @property
    def image_files(self) -> List[str]:
        """获取要处理的图片文件列表"""
        return self._config['images']['files']

    @property
    def image_directory(self) -> Path:
        """获取图片目录"""
        return Path(__file__).parent / self._config['images']['directory']

    @property
    def supported_formats(self) -> List[str]:
        """获取支持的图片格式"""
        return self._config['images']['supported_formats']

    @property
    def default_prompt(self) -> str:
        """获取默认 prompt 名称"""
        return self._config['prompts']['default']

    def get_prompt(self, prompt_name: str = None) -> str:
        """获取指定 prompt 的文本"""
        if prompt_name is None:
            prompt_name = self.default_prompt

        prompts = self._config['prompts']['available']
        if prompt_name not in prompts:
            raise ValueError(f"未知的 prompt: {prompt_name}")

        return prompts[prompt_name]['text']

    def get_available_prompts(self) -> Dict[str, Any]:
        """获取所有可用的 prompt"""
        return self._config['prompts']['available']

    @property
    def results_directory(self) -> Path:
        """获取结果目录"""
        dir_path = Path(__file__).parent.parent / self._config['output']['results']['directory']
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    def get_results_filename(self, timestamp: str = None) -> str:
        """获取结果文件名"""
        if timestamp is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename_template = self._config['output']['results']['filename']
        return filename_template.format(timestamp=timestamp)

    @property
    def enable_timing(self) -> bool:
        """是否启用时间分析"""
        return self._config['performance']['enable_timing']

    @property
    def save_individual_results(self) -> bool:
        """是否保存单个结果"""
        return self._config['performance']['save_individual_results']

    @property
    def log_level(self) -> str:
        """获取日志级别"""
        return self._config['performance']['log_level']

    @property
    def enable_callback_timing(self) -> bool:
        """是否启用回调时间分析"""
        return self._config.get('performance', {}).get('enable_callback_timing', True)

    @property
    def callback_interval_ms(self) -> int:
        """获取回调间隔时间（毫秒）"""
        return self._config.get('performance', {}).get('callback_interval_ms', 100)


# 全局配置实例
_config = None

def get_config() -> Config:
    """获取配置实例（单例模式）"""
    global _config
    if _config is None:
        _config = Config()
    return _config