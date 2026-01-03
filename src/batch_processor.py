#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量处理器模块
"""

import time
from pathlib import Path
from typing import Dict, Any, List
from tqdm import tqdm
from loguru import logger

from .config import get_config
from .utils import resolve_image_files, save_results, generate_timestamp
from .analyzer import GeminiAnalyzer


class BatchProcessor:
    """批量处理器"""

    def __init__(self, timing_mode='standard'):
        self.config = get_config()
        self.analyzer = GeminiAnalyzer(timing_mode=timing_mode)
        self.results = {}

    def get_images_to_process(self) -> List[Path]:
        """获取要处理的图片列表"""
        image_files = resolve_image_files(
            self.config.image_files,
            self.config.image_directory,
            self.config.supported_formats
        )

        logger.info(f"找到 {len(image_files)} 个图片文件需要处理")
        for img in image_files:
            logger.debug(f"  - {img.name}")

        return image_files

    def process_batch(self, prompt_name: str = None, save_individual: bool = None) -> Dict[str, Any]:
        """批量处理图片"""

        if prompt_name is None:
            prompt_name = self.config.default_prompt

        if save_individual is None:
            save_individual = self.config.save_individual_results

        # 获取图片列表
        image_files = self.get_images_to_process()
        if not image_files:
            logger.warning("没有找到要处理的图片")
            return {}

        # 批量处理
        batch_results = {
            'metadata': {
                'start_time': generate_timestamp(),
                'total_images': len(image_files),
                'prompt_used': prompt_name,
                'config_file': str(self.config.config_path),
                'timing_mode': self.analyzer.timing_mode
            },
            'results': {},
            'summary': {}
        }

        successful = 0
        failed = 0
        total_processing_time = 0.0

        # 使用进度条
        for image_path in tqdm(image_files, desc="处理图片"):
            image_name = image_path.name

            logger.info(f"处理图片: {image_name}")

            # 记录开始时间
            start_time = time.time()

            # 分析图片
            result = self.analyzer.analyze_image(image_name, prompt_name)

            # 记录处理时间
            processing_time = time.time() - start_time
            result['processing_time'] = processing_time
            total_processing_time += processing_time

            # 保存单个结果（如果需要）
            if save_individual:
                individual_filename = f"individual_{image_path.stem}_{generate_timestamp()}.json"
                individual_path = self.config.results_directory / individual_filename
                save_results(result, individual_path)

            # 统计成功/失败
            if result.get('success'):
                successful += 1
            else:
                failed += 1
                logger.error(f"图片处理失败: {image_name} - {result.get('error', '未知错误')}")

            # 添加到批量结果
            batch_results['results'][image_name] = result

            # 打印时间分析
            if 'timings' in result:
                self.analyzer.print_timing_analysis(result)

            # 添加延迟，避免请求过于频繁
            time.sleep(0.5)

        # 生成摘要
        batch_results['metadata']['end_time'] = generate_timestamp()
        batch_results['metadata']['successful'] = successful
        batch_results['metadata']['failed'] = failed

        batch_results['summary'] = {
            'total_images': len(image_files),
            'successful': successful,
            'failed': failed,
            'success_rate': successful / len(image_files) * 100 if image_files else 0,
            'average_processing_time': total_processing_time / len(image_files) if image_files else 0,
            'total_processing_time': total_processing_time
        }

        self.results = batch_results
        return batch_results

    def save_batch_results(self, filename: str = None) -> Path:
        """保存批量结果"""
        if not self.results:
            logger.warning("没有结果可保存，请先运行批量处理")
            return None

        if filename is None:
            filename = self.config.get_results_filename()

        filepath = self.config.results_directory / filename
        save_results(self.results, filepath)

        return filepath

    def generate_report(self) -> str:
        """生成处理报告"""
        if not self.results:
            return "没有可用的处理结果"

        summary = self.results['summary']

        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("批量处理报告")
        report_lines.append("=" * 60)
        report_lines.append(f"总图片数: {summary['total_images']}")
        report_lines.append(f"成功处理: {summary['successful']}")
        report_lines.append(f"处理失败: {summary['failed']}")
        report_lines.append(f"成功率: {summary['success_rate']:.1f}%")
        report_lines.append(f"平均处理时间: {summary['average_processing_time']:.2f}秒")
        report_lines.append(f"总处理时间: {summary['total_processing_time']:.2f}秒")
        report_lines.append(f"时间模式: {self.results['metadata'].get('timing_mode', 'unknown')}")

        # 显示每个图片的结果摘要
        report_lines.append("\n各图片处理结果:")
        for image_name, result in self.results['results'].items():
            status = "✓" if result.get('success') else "✗✗"
            response = result.get('response_text', 'N/A')
            report_lines.append(f"  {status} {image_name}: {response}")

        return "\n".join(report_lines)

    def process_with_multiple_prompts(self, prompt_names: List[str] = None) -> Dict[str, Any]:
        """使用多个 prompt 处理图片"""
        if prompt_names is None:
            # 使用所有可用的 prompt
            available_prompts = self.config.get_available_prompts()
            prompt_names = list(available_prompts.keys())

        all_results = {}

        for prompt_name in prompt_names:
            logger.info(f"使用 prompt '{prompt_name}' 处理图片...")

            # 处理当前 prompt
            results = self.process_batch(prompt_name=prompt_name)
            all_results[prompt_name] = results

            # 保存当前 prompt 的结果
            prompt_filename = f"results_prompt_{prompt_name}_{generate_timestamp()}.json"
            self.save_batch_results(prompt_filename)

            # 打印报告
            print(f"\nPrompt '{prompt_name}' 处理报告:")
            print(self.generate_report())
            print("\n" + "=" * 60 + "\n")

        return all_results

    def get_processing_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        if not self.results:
            return {}

        summary = self.results['summary']

        # 计算时间统计
        timing_stats = {}
        successful_results = [r for r in self.results['results'].values() if r.get('success')]

        if successful_results:
            # 网络时间统计
            if 'timings' in successful_results[0]:
                timing_keys = ['total_time', 'dns_time', 'tcp_handshake', 'ssl_handshake',
                               'server_processing', 'response_transfer']

                for key in timing_keys:
                    times = [r['timings']['standard'][key] for r in successful_results if 'timings' in r and 'standard' in r['timings']]
                    if times:
                        timing_stats[key] = {
                            'min': min(times),
                            'max': max(times),
                            'avg': sum(times) / len(times)
                        }

        return {
            'summary': summary,
            'timing_statistics': timing_stats,
            'total_images_processed': len(self.results['results'])
        }