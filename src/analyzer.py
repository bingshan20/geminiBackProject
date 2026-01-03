#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析器核心模块 - 修正版本
提供两种清晰的回调模式选择
"""

import pycurl
from io import BytesIO
import json
import time
from typing import Dict, Any
from pathlib import Path
from loguru import logger
from .config import get_config
from .utils import encode_image_to_base64, save_results, generate_timestamp


class StandardTimingAnalyzer:
    """标准时间分析器 - 只使用pycurl标准API，无回调开销"""

    def __init__(self):
        self.buffer = BytesIO()

    def write_callback(self, data):
        """必要的写入回调 - 用于接收响应数据"""
        self.buffer.write(data)
        return len(data)

    def get_response_data(self):
        """获取响应数据"""
        return self.buffer.getvalue()

    def reset(self):
        """重置分析器状态"""
        self.buffer = BytesIO()

    def calculate_timings(self, curl_obj, request_body_size: int = 0):
        """基于pycurl标准API计算时间，包含上传时间估算"""
        # 直接从curl对象获取时间信息
        timings = {
            'dns_time': curl_obj.getinfo(pycurl.NAMELOOKUP_TIME) * 1000,
            'tcp_handshake': (curl_obj.getinfo(pycurl.CONNECT_TIME) -
                              curl_obj.getinfo(pycurl.NAMELOOKUP_TIME)) * 1000,
            'ssl_handshake': (curl_obj.getinfo(pycurl.APPCONNECT_TIME) -
                              curl_obj.getinfo(pycurl.CONNECT_TIME)) * 1000,
            'request_send': (curl_obj.getinfo(pycurl.PRETRANSFER_TIME) -
                             curl_obj.getinfo(pycurl.APPCONNECT_TIME)) * 1000,
            'server_processing': (curl_obj.getinfo(pycurl.STARTTRANSFER_TIME) -
                                  curl_obj.getinfo(pycurl.PRETRANSFER_TIME)) * 1000,
            'response_transfer': (curl_obj.getinfo(pycurl.TOTAL_TIME) -
                                  curl_obj.getinfo(pycurl.STARTTRANSFER_TIME)) * 1000,
            'total_time': curl_obj.getinfo(pycurl.TOTAL_TIME) * 1000
        }

        # 如果提供了请求体大小，添加上传时间估算
        if request_body_size > 0:
            # 尝试获取实际上传速度
            try:
                upload_speed = curl_obj.getinfo(pycurl.SPEED_UPLOAD)  # 字节/秒
            except:
                upload_speed = 0

            # 估算上传时间
            estimated_upload_time = 0
            if upload_speed > 0:
                estimated_upload_time = request_body_size / upload_speed * 1000  # 转换为毫秒
            else:
                # 基于经验估算
                if request_body_size < 1024:  # 小于1KB
                    estimated_upload_time = 10  # 10ms
                elif request_body_size < 10240:  # 小于10KB
                    estimated_upload_time = 50  # 50ms
                else:
                    estimated_upload_time = 100  # 100ms

            # 添加上传估算信息（不调整服务器处理时间）
            timings.update({
                'upload_size': request_body_size,
                'upload_speed': upload_speed,
                'estimated_upload_time': estimated_upload_time,
                'upload_estimation_quality': 'measured' if upload_speed > 0 else 'estimated'
            })

        return timings


class PreciseTimingAnalyzer:
    """精确时间分析器 - 使用回调获取精确的关键事件时间"""

    def __init__(self):
        self.key_events = {
            'request_body_sent': None,  # 请求体发送完成时间
            'first_byte_received': None,  # 收到第一个字节时间
        }

        self.buffer = BytesIO()
        self.request_body_sent = False
        self.first_byte_received = False

        # 回调统计
        self.callback_stats = {
            'progress_calls': 0,
            'write_calls': 0
        }

    def progress_callback(self, dltotal, dlnow, ultotal, ulnow):
        """进度回调 - 记录请求体发送完成时间"""
        self.callback_stats['progress_calls'] += 1

        # 只在上传完成且尚未记录时记录一次
        if not self.request_body_sent and ultotal > 0 and ulnow >= ultotal:
            self.key_events['request_body_sent'] = time.perf_counter()
            self.request_body_sent = True

        return 0

    def write_callback(self, data):
        """写入回调 - 记录第一个字节到达时间"""
        self.callback_stats['write_calls'] += 1

        # 只在第一次收到数据时记录
        if not self.first_byte_received:
            self.key_events['first_byte_received'] = time.perf_counter()
            self.first_byte_received = True

        # 处理数据
        self.buffer.write(data)
        return len(data)

    def get_response_data(self):
        """获取响应数据"""
        return self.buffer.getvalue()

    def reset(self):
        """重置分析器状态"""
        self.buffer = BytesIO()
        for key in self.key_events:
            self.key_events[key] = None
        self.request_body_sent = False
        self.first_byte_received = False
        self.callback_stats = {'progress_calls': 0, 'write_calls': 0}

    def calculate_precise_timings(self, start_time, standard_timings):
        """计算精确的时间信息"""
        if not start_time:
            return None

        precise_timings = {}

        # 计算请求体发送时间（从开始到请求体发送完成）
        if self.key_events['request_body_sent']:
            precise_timings['request_body_send_time'] = (self.key_events['request_body_sent'] - start_time) * 1000

        # 计算服务器处理时间（从请求体发送完成到收到第一个字节）
        if self.key_events['request_body_sent'] and self.key_events['first_byte_received']:
            precise_timings['server_processing_time'] = (self.key_events['first_byte_received'] - self.key_events[
                'request_body_sent']) * 1000

        # 添加回调统计
        precise_timings['callback_stats'] = self.callback_stats.copy()

        # 与标准时间对比
        if standard_timings:
            precise_timings['standard_comparison'] = {
                'standard_server_processing': standard_timings.get('server_processing', 0)
            }

            # 计算差异
            if 'server_processing_time' in precise_timings:
                diff = (precise_timings['server_processing_time'] -
                        precise_timings['standard_comparison']['standard_server_processing'])
                precise_timings['standard_comparison']['server_processing_diff'] = diff

        return precise_timings


class GeminiAnalyzer:
    """Gemini 分析器 - 修正版本"""

    def __init__(self, timing_mode='standard'):
        """
        timing_mode:
        - 'standard': 使用标准时间（无进度回调，性能最佳）
        - 'precise': 使用精确时间（有进度回调，获取关键事件时间）
        """
        self.config = get_config()
        self.timing_mode = timing_mode

        if timing_mode == 'standard':
            self.analyzer = StandardTimingAnalyzer()
        else:  # precise
            self.analyzer = PreciseTimingAnalyzer()

    def analyze_image(self, image_path: str, prompt_name: str = None, save_result: bool = False) -> Dict[str, Any]:
        """分析单张图片"""

        # 重置分析器状态
        self.analyzer.reset()

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

        # 构建请求 URL
        url = f"{self.config.api_url}?key={self.config.api_key}"

        # 构建请求载荷
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
                            "text": prompt_text
                        }
                    ]
                }
            ]
        }

        data = json.dumps(payload)
        request_body_size = len(data)  # 获取请求体大小

        # 创建 curl 对象
        c = pycurl.Curl()

        try:
            # 设置基本选项
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.POST, 1)
            c.setopt(pycurl.POSTFIELDS, data)
            c.setopt(pycurl.HTTPHEADER, [
                "Content-Type: application/json",
                f"Content-Length: {len(data)}"
            ])

            # 设置写入回调（两种模式都需要）
            c.setopt(pycurl.WRITEFUNCTION, self.analyzer.write_callback)

            # 根据模式设置进度回调
            if self.timing_mode == 'precise':
                # 精确模式：启用进度回调
                try:
                    c.setopt(pycurl.XFERINFOFUNCTION, self.analyzer.progress_callback)
                    c.setopt(pycurl.NOPROGRESS, 0)
                except AttributeError:
                    c.setopt(pycurl.PROGRESSFUNCTION, self.analyzer.progress_callback)
                    c.setopt(pycurl.NOPROGRESS, 0)
            else:
                # 标准模式：禁用进度回调
                c.setopt(pycurl.NOPROGRESS, 1)

            # 其他优化选项
            c.setopt(pycurl.VERBOSE, 0)
            c.setopt(pycurl.TIMEOUT, self.config.api_timeout)

            # 记录开始时间（精确模式需要）
            start_time = time.perf_counter() if self.timing_mode == 'precise' else None

            # 执行请求
            c.perform()

            # 获取 HTTP 状态码
            http_code = c.getinfo(pycurl.RESPONSE_CODE)

            # 获取响应
            response_bytes = self.analyzer.get_response_data()

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
                'success': result.get('success', False),
                'timing_mode': self.timing_mode
            })

            # 添加时间信息
            timing_data = {}

            if self.timing_mode == 'standard':
                # 标准模式：使用pycurl标准API计算时间，包含上传估算
                standard_timings = self.analyzer.calculate_timings(c, request_body_size)
                if standard_timings:
                    timing_data['standard'] = standard_timings

            else:  # precise模式
                # 精确模式：使用回调记录的关键事件计算时间
                # 首先获取标准时间作为参考
                standard_timings = self._extract_standard_timings(c, request_body_size)
                if standard_timings:
                    timing_data['standard'] = standard_timings

                # 然后获取精确时间
                precise_timings = self.analyzer.calculate_precise_timings(start_time, standard_timings)
                if precise_timings:
                    timing_data['precise'] = precise_timings

            # 关闭 curl 对象
            c.close()
            if timing_data:
                result['timings'] = timing_data

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

    def _extract_standard_timings(self, curl_obj, request_body_size: int = 0) -> Dict[str, float]:
        """提取标准时间信息（用于精确模式对比）"""
        timings = {
            'namelookup_time': curl_obj.getinfo(pycurl.NAMELOOKUP_TIME),
            'connect_time': curl_obj.getinfo(pycurl.CONNECT_TIME),
            'appconnect_time': curl_obj.getinfo(pycurl.APPCONNECT_TIME),
            'pretransfer_time': curl_obj.getinfo(pycurl.PRETRANSFER_TIME),
            'starttransfer_time': curl_obj.getinfo(pycurl.STARTTRANSFER_TIME),
            'total_time': curl_obj.getinfo(pycurl.TOTAL_TIME),
        }

        # 计算各个阶段时间
        timings['dns_time'] = timings['namelookup_time']
        timings['tcp_handshake'] = timings['connect_time'] - timings['namelookup_time']
        timings['ssl_handshake'] = timings['appconnect_time'] - timings['connect_time']
        timings['request_send'] = timings['pretransfer_time'] - timings['appconnect_time']
        timings['server_processing'] = timings['starttransfer_time'] - timings['pretransfer_time']
        timings['response_transfer'] = timings['total_time'] - timings['starttransfer_time']

        # 转换为毫秒
        for key in list(timings.keys()):
            timings[key] = timings[key] * 1000

        # 添加上传估算信息
        if request_body_size > 0:
            try:
                upload_speed = curl_obj.getinfo(pycurl.SPEED_UPLOAD)  # 字节/秒
            except:
                upload_speed = 0

            estimated_upload_time = 0
            if upload_speed > 0:
                estimated_upload_time = request_body_size / upload_speed * 1000  # 转换为毫秒
            else:
                if request_body_size < 1024:
                    estimated_upload_time = 10
                elif request_body_size < 10240:
                    estimated_upload_time = 50
                else:
                    estimated_upload_time = 100

            timings.update({
                'upload_size': request_body_size,
                'upload_speed': upload_speed,
                'estimated_upload_time': estimated_upload_time,
                'upload_estimation_quality': 'measured' if upload_speed > 0 else 'estimated'
            })

        return timings

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
        if 'timings' not in result:
            print("无时间分析数据")
            return

        timing_mode = result.get('timing_mode', 'unknown')
        print("=" * 60)
        print(f"时间分析结果 - 模式: {timing_mode}")
        print("=" * 60)

        # 显示标准时间信息（两种模式都有）
        if 'standard' in result['timings']:
            standard = result['timings']['standard']
            print("标准时间信息:")
            print(f"  DNS解析时间: {standard.get('dns_time', 0):.1f} ms")
            print(f"  TCP握手时间: {standard.get('tcp_handshake', 0):.1f} ms")
            print(f"  SSL握手时间: {standard.get('ssl_handshake', 0):.1f} ms")
            print(f"  请求头发送时间: {standard.get('request_send', 0):.1f} ms")
            print(f"  服务器处理时间: {standard.get('server_processing', 0):.1f} ms")
            print(f"  响应传输时间: {standard.get('response_transfer', 0):.1f} ms")
            print(f"  总时间: {standard.get('total_time', 0):.1f} ms")

            # 显示上传估算信息
            if 'estimated_upload_time' in standard:
                quality = standard.get('upload_estimation_quality', 'estimated')
                quality_text = '基于实际速度' if quality == 'measured' else '基于经验估算'
                print(f"  请求体上传估算: {standard.get('estimated_upload_time', 0):.1f} ms ({quality_text})")
                print(f"  请求体大小: {standard.get('upload_size', 0)} 字节")
                if standard.get('upload_speed', 0) > 0:
                    print(f"  实际上传速度: {standard.get('upload_speed', 0) / 1024:.1f} KB/s")

        # 显示精确模式的结果
        if timing_mode == 'precise' and 'precise' in result['timings']:
            precise = result['timings']['precise']
            print("\n精确时间信息（基于回调）:")

            if 'request_body_send_time' in precise:
                print(f"  请求体发送完成时间: {precise['request_body_send_time']:.1f} ms")

            if 'server_processing_time' in precise:
                print(f"  服务器处理时间: {precise['server_processing_time']:.1f} ms")

                # 与标准时间对比
                if 'standard_comparison' in precise:
                    comparison = precise['standard_comparison']
                    if 'server_processing_diff' in comparison:
                        diff = comparison['server_processing_diff']
                        print(f"  与标准时间差异: {diff:+.1f} ms")

            # 回调统计
            if 'callback_stats' in precise:
                stats = precise['callback_stats']
                print(f"  进度回调调用次数: {stats.get('progress_calls', 0)}")
                print(f"  写入回调调用次数: {stats.get('write_calls', 0)}")

        print()