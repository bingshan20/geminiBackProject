#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析器核心模块 - 修复版本
"""

import pycurl
from io import BytesIO
import json
import time
from typing import Dict, Any
from pathlib import Path
from loguru import logger
from .config import get_config
from .utils import encode_image_to_base64, format_timing_results, save_results, generate_timestamp


class CurlCallbackAnalyzer:
    """CURL 回调分析器 - 修复版本"""

    def __init__(self):
        self.timestamps = {
            'start': None,
            'dns_complete': None,
            'tcp_connect_complete': None,
            'ssl_complete': None,
            'upload_start': None,
            'upload_complete': None,
            'first_byte_received': None,
            'response_complete': None,
        }

        # 回调统计
        self.callback_stats = {
            'progress_callbacks': 0,
            'write_callbacks': 0,
            'header_callbacks': 0,
            'debug_callbacks': 0,
            'callback_methods_used': []
        }

        self.upload_started = False
        self.first_byte_received = False
        self.bytes_uploaded = 0
        self.bytes_downloaded = 0
        self.buffer = BytesIO()  # 添加缓冲区

    def progress_callback(self, dltotal, dlnow, ultotal, ulnow):
        """进度回调函数 - 修复版本"""
        current_time = time.perf_counter()
        self.callback_stats['progress_callbacks'] += 1

        if 'progress' not in self.callback_stats['callback_methods_used']:
            self.callback_stats['callback_methods_used'].append('progress')

        # 记录上传开始时间
        if ultotal > 0 and not self.upload_started:
            self.timestamps['upload_start'] = current_time
            self.upload_started = True

        # 记录上传完成时间
        if ultotal > 0 and ulnow == ultotal and self.timestamps['upload_complete'] is None:
            self.timestamps['upload_complete'] = current_time
            self.bytes_uploaded = ultotal

        # 记录下载完成时间
        if dltotal > 0 and dlnow == dltotal and self.timestamps['response_complete'] is None:
            self.timestamps['response_complete'] = current_time
            self.bytes_downloaded = dlnow

        return 0

    def write_callback(self, data):
        """写入回调函数 - 修复版本"""
        current_time = time.perf_counter()
        self.callback_stats['write_callbacks'] += 1

        if 'write' not in self.callback_stats['callback_methods_used']:
            self.callback_stats['callback_methods_used'].append('write')

        # 记录第一个字节到达时间
        if not self.first_byte_received:
            self.timestamps['first_byte_received'] = current_time
            self.first_byte_received = True

        data_len = len(data)
        self.bytes_downloaded += data_len

        # 写入到缓冲区
        self.buffer.write(data)
        return data_len

    def get_response_data(self):
        """获取响应数据"""
        return self.buffer.getvalue()

    def reset(self):
        """重置分析器状态"""
        self.buffer = BytesIO()
        for key in self.timestamps:
            self.timestamps[key] = None
        self.upload_started = False
        self.first_byte_received = False
        self.bytes_uploaded = 0
        self.bytes_downloaded = 0
        self.callback_stats = {
            'progress_callbacks': 0,
            'write_callbacks': 0,
            'callback_methods_used': []
        }

    def calculate_precise_timings(self, curl_timings):
        """计算精确的时间分解"""
        if not self.timestamps['start']:
            return None, None

        start = self.timestamps['start']
        precise_timings = {}
        callback_timings = {}

        # 计算各阶段耗时（单位：毫秒）
        if self.timestamps['dns_complete']:
            precise_timings['dns_resolution'] = (self.timestamps['dns_complete'] - start) * 1000

        if self.timestamps['dns_complete'] and self.timestamps['tcp_connect_complete']:
            precise_timings['tcp_handshake'] = (self.timestamps['tcp_connect_complete'] -
                                                self.timestamps['dns_complete']) * 1000

        if self.timestamps['tcp_connect_complete'] and self.timestamps['ssl_complete']:
            precise_timings['ssl_handshake'] = (self.timestamps['ssl_complete'] -
                                                self.timestamps['tcp_connect_complete']) * 1000

        if self.timestamps['ssl_complete'] and self.timestamps['upload_start']:
            precise_timings['request_header_send'] = (self.timestamps['upload_start'] -
                                                      self.timestamps['ssl_complete']) * 1000

        if self.timestamps['upload_start'] and self.timestamps['upload_complete']:
            precise_timings['request_body_upload'] = (self.timestamps['upload_complete'] -
                                                      self.timestamps['upload_start']) * 1000

        # 关键：精确的服务器处理时间
        if self.timestamps['upload_complete'] and self.timestamps['first_byte_received']:
            precise_timings['server_processing'] = (self.timestamps['first_byte_received'] -
                                                    self.timestamps['upload_complete']) * 1000

        if self.timestamps['first_byte_received'] and self.timestamps['response_complete']:
            precise_timings['response_receive'] = (self.timestamps['response_complete'] -
                                                   self.timestamps['first_byte_received']) * 1000

        if 'total' in curl_timings:
            precise_timings['total'] = curl_timings['total'] * 1000

        # 回调时间统计
        callback_timings = {
            'total_callbacks': sum(v for v in self.callback_stats.values() if isinstance(v, (int, float))),
            'callback_stats': self.callback_stats,
            'callback_methods_count': len(self.callback_stats.get('callback_methods_used', [])),
            'callback_analysis_available': True
        }

        return precise_timings, callback_timings

class GeminiAnalyzer:
    """Gemini 分析器 - 修复版本"""

    def __init__(self):
        self.config = get_config()
        self.callback_analyzer = CurlCallbackAnalyzer()

    def analyze_image(self, image_path: str, prompt_name: str = None, save_result: bool = False) -> Dict[str, Any]:
        """分析单张图片 - 修复版本"""

        # 重置分析器状态
        self.callback_analyzer.reset()

        # 获取 prompt 文本
        prompt_text = self.config.get_prompt(prompt_name)

        # 读取并编码图片
        full_image_path = self.config.image_directory / image_path
        image_b64 = encode_image_to_base64(full_image_path)
        if not image_b64:
            error_result = {'error': '图片编码失败', 'success': False}
            if save_result:
                self._save_single_result(error_result, image_path, prompt_name)
            return error_result

        # 构建请求 URL - 使用测试代码的成功格式
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.config.api_key}"

        # 构建请求载荷 - 使用测试代码的成功格式
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64
                            }
                        },
                        {
                            "text": prompt_text or "请快速说出字的颜色，可以容忍不确定性，只返回一个字，其他不要返回"
                        }
                    ]
                }
            ]
        }

        data = json.dumps(payload)

        # 创建 curl 对象
        c = pycurl.Curl()

        try:
            # 设置基本选项 - 使用测试代码的成功配置
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.POST, 1)
            c.setopt(pycurl.POSTFIELDS, data)
            c.setopt(pycurl.HTTPHEADER, [
                "Content-Type: application/json",
                f"Content-Length: {len(data)}"
            ])

            # 使用 WRITEFUNCTION 而不是 WRITEDATA
            c.setopt(pycurl.WRITEFUNCTION, self.callback_analyzer.write_callback)

            # 设置进度回调 - 使用兼容性处理
            try:
                # 优先使用 XFERINFOFUNCTION（新API）
                c.setopt(pycurl.FERINFOFUNCTION, self.callback_analyzer.progress_callback)
            except AttributeError:
                # 回退到 PROGRESSFUNCTION（旧API）
                c.setopt(pycurl.PROGRESSFUNCTION, self.callback_analyzer.progress_callback)

            c.setopt(pycurl.NOPROGRESS, 0)  # 启用进度回调
            c.setopt(pycurl.VERBOSE, 0)  # 关闭详细输出（避免干扰）
            c.setopt(pycurl.TIMEOUT, self.config.api_timeout)

            # 记录开始时间
            self.callback_analyzer.timestamps['start'] = time.perf_counter()

            # 执行请求
            c.perform()

            # 获取 HTTP 状态码
            http_code = c.getinfo(pycurl.RESPONSE_CODE)

            # 获取标准时间信息
            standard_timings = self._extract_timing_info(c) if self.config.enable_timing else {}

            # 获取精确时间信息（通过回调）
            precise_timings = {}
            callback_timings = {}

            # 记录DNS、TCP、SSL完成时间
            self.callback_analyzer.timestamps['dns_complete'] = (
                    self.callback_analyzer.timestamps['start'] + c.getinfo(pycurl.NAMELOOKUP_TIME)
            )
            self.callback_analyzer.timestamps['tcp_connect_complete'] = (
                    self.callback_analyzer.timestamps['start'] + c.getinfo(pycurl.CONNECT_TIME)
            )
            self.callback_analyzer.timestamps['ssl_complete'] = (
                    self.callback_analyzer.timestamps['start'] + c.getinfo(pycurl.APPCONNECT_TIME)
            )

            precise_timings, callback_timings = self.callback_analyzer.calculate_precise_timings(standard_timings)

            # 获取响应
            response_bytes = self.callback_analyzer.get_response_data()
            c.close()

            if not response_bytes:
                error_msg = "响应体为空"
                logger.error(error_msg)
                error_result = {'error': error_msg, 'success': False}
                if save_result:
                    self._save_single_result(error_result, image_path, prompt_name)
                return error_result

            response_body = response_bytes.decode('utf-8')

            # 解析响应
            result = self._parse_response(response_body, http_code)

            # 添加元数据
            result.update({
                'image_file': image_path,
                'prompt_used': prompt_name or self.config.default_prompt,
                'http_status': http_code,
                'success': result.get('success', False)
            })

            # 添加时间信息
            timing_data = {}
            if standard_timings:
                timing_data['standard'] = standard_timings
            if precise_timings:
                timing_data['precise'] = precise_timings
            if timing_data:
                result['timings'] = timing_data

            # 添加回调信息
            if callback_timings:
                result['callback'] = callback_timings

            # 保存结果（如果需要）
            if save_result:
                self._save_single_result(result, image_path, prompt_name)

            return result

        except pycurl.error as e:
            error_msg = f"PyCURL 请求失败: {e}"
            c.close()
            logger.error(error_msg)
            error_result = {'error': error_msg, 'success': False}
            if save_result:
                self._save_single_result(error_result, image_path, prompt_name)
            return error_result
        except Exception as e:
            error_msg = f"处理请求时发生错误: {e}"
            logger.error(error_msg)
            error_result = {'error': error_msg, 'success': False}
            if save_result:
                self._save_single_result(error_result, image_path, prompt_name)
            return error_result

    def _save_single_result(self, result: Dict[str, Any], image_path: str, prompt_name: str = None):
        """保存单个分析结果到 JSON 文件"""
        try:
            # 确保结果目录存在
            self.config.results_directory.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            image_stem = Path(image_path).stem
            prompt_suffix = f"_{prompt_name}" if prompt_name else ""
            timestamp = generate_timestamp()
            filename = f"individual_{image_stem}{prompt_suffix}_{timestamp}.json"

            filepath = self.config.results_directory / filename

            # 保存结果
            save_results(result, filepath)
            logger.info(f"单个分析结果已保存到: {filepath}")

        except Exception as e:
            logger.error(f"保存单个分析结果失败: {e}")

    def _extract_timing_info(self, curl_obj) -> Dict[str, float]:
        """提取标准时间信息"""
        timings = {
            'namelookup_time': curl_obj.getinfo(pycurl.NAMELOOKUP_TIME),
            'connect_time': curl_obj.getinfo(pycurl.CONNECT_TIME),
            'appconnect_time': curl_obj.getinfo(pycurl.APPCONNECT_TIME),
            'pretransfer_time': curl_obj.getinfo(pycurl.PRETRANSFER_TIME),
            'starttransfer_time': curl_obj.getinfo(pycurl.STARTTRANSFER_TIME),
            'total_time': curl_obj.getinfo(pycurl.TOTAL_TIME),
            'redirect_time': curl_obj.getinfo(pycurl.REDIRECT_TIME),
        }

        # 计算衍生时间指标
        timings['dns_time'] = timings['namelookup_time']
        timings['tcp_handshake'] = timings['connect_time'] - timings['namelookup_time']
        timings['ssl_handshake'] = timings['appconnect_time'] - timings['connect_time']
        timings['request_send'] = timings['pretransfer_time'] - timings['appconnect_time']
        timings['server_processing'] = timings['starttransfer_time'] - timings['pretransfer_time']
        timings['response_transfer'] = timings['total_time'] - timings['starttransfer_time']

        return timings

    def _parse_response(self, response_body: str, http_code: int) -> Dict[str, Any]:
        """解析 API 响应"""
        result = {
            'success': http_code == 200,
            'http_code': http_code,
            'response_text': None,
            'raw_response': response_body
        }

        if http_code != 200:
            logger.error(f"API 请求失败，HTTP 状态码: {http_code}")
            return result

        try:
            response_data = json.loads(response_body)
            result['raw_data'] = response_data

            # 提取响应文本
            if 'candidates' in response_data and response_data['candidates']:
                response_text = response_data['candidates'][0]['content']['parts'][0]['text']
                result['response_text'] = response_text.strip()
                logger.info(f"识别结果: {result['response_text']}")
            else:
                logger.warning("响应中未找到有效结果")

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"解析响应失败: {e}")
            result['error'] = f"解析错误: {e}"

        return result

    def print_timing_analysis(self, result: Dict):
        """打印时间分析结果"""
        if 'timings' in result:
            print("标准时间分析:")
            print(format_timing_results(result['timings'].get('standard', {})))

            if 'precise' in result['timings']:
                print("\n精确时间分析 (基于回调):")
                self._print_precise_timing_analysis(result['timings']['precise'])

            if 'callback' in result:
                self._print_callback_analysis(result['callback'])
            print()

    def _print_precise_timing_analysis(self, timings: Dict):
        """打印精确时间分析"""
        timing_items = [
            ("DNS解析时间", timings.get('dns_resolution', 0)),
            ("TCP握手时间", timings.get('tcp_handshake', 0)),
            ("SSL握手时间", timings.get('ssl_handshake', 0)),
            ("请求头发送时间", timings.get('request_header_send', 0)),
            ("请求体上传时间", timings.get('request_body_upload', 0)),
            ("服务器处理时间", timings.get('server_processing', 0)),
            ("响应接收时间", timings.get('response_receive', 0)),
            ("总时间", timings.get('total', 0))
        ]

        for name, value in timing_items:
            if value > 0:
                print(f"{name}: {value:.1f} ms")

    def _print_callback_analysis(self, callback_data: Dict):
        """打印回调分析"""
        print("\n回调机制分析:")
        stats = callback_data.get('callback_stats', {})
        print(f"总回调次数: {callback_data.get('total_callbacks', 0)}")
        print(f"进度回调: {stats.get('progress_callbacks', 0)} 次")
        print(f"写入回调: {stats.get('write_callbacks', 0)} 次")
        print(f"头部回调: {stats.get('header_callbacks', 0)} 次")
        print(f"调试回调: {stats.get('debug_callbacks', 0)} 次")
        print(f"使用的回调方法: {', '.join(stats.get('callback_methods_used', []))}")
