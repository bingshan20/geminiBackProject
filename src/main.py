#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序入口
"""

import sys
import argparse
from pathlib import Path
from loguru import logger
from typing import List

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from .utils import setup_logging
from .config import get_config
from .batch_processor import BatchProcessor
from .analyzer import GeminiAnalyzer


def main():
    """主函数"""
    # 设置日志
    config = get_config()
    setup_logging(config.log_level)

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Gemini 图片颜色分析器')
    parser.add_argument('--image', '-i', type=str, help='要分析的单个图片文件名')
    parser.add_argument('--all', '-a', action='store_true', help='分析所有配置的图片')
    parser.add_argument('--prompt', '-p', type=str, help='指定使用的 prompt 名称')
    parser.add_argument('--list-prompts', action='store_true', help='列出所有可用的 prompt')
    parser.add_argument('--multi-prompt', action='store_true', help='使用所有 prompt 处理图片')
    parser.add_argument('--output', '-o', type=str, help='输出结果文件名')
    parser.add_argument('--timing-mode', type=str, choices=['standard', 'precise'],
                       default='standard', help='时间分析模式: standard(标准) 或 precise(精确)')

    args = parser.parse_args()

    logger.info("启动 Gemini 图片分析器")

    # 列出可用的 prompt
    if args.list_prompts:
        list_available_prompts()
        return

    # 单个图片分析
    if args.image:
        if args.multi_prompt:
            # 使用所有可用的 prompt
            available_prompts = config.get_available_prompts()
            prompt_names = list(available_prompts.keys())
            analyze_single_image_multiple_prompts(args.image, prompt_names, args.timing_mode)
        else:
            # 单 prompt 处理
            analyze_single_image(args.image, args.prompt, True, args.timing_mode)
        return

    # 批量处理
    if args.all or not args.image:
        if args.multi_prompt:
            # 多 prompt 处理
            process_with_multiple_prompts(args.output, args.timing_mode)
        else:
            # 单 prompt 批量处理
            process_batch_images(args.prompt, args.output, args.timing_mode)


def list_available_prompts():
    """列出所有可用的 prompt"""
    config = get_config()
    prompts = config.get_available_prompts()

    print("\n可用的 Prompt:")
    print("=" * 50)
    for prompt_name, prompt_info in prompts.items():
        print(f"名称: {prompt_name}")
        print(f"描述: {prompt_info['description']}")
        print(f"内容: {prompt_info['text']}")
        print("-" * 30)


def analyze_single_image(image_name: str, prompt_name: str = None, save_result: bool = False, timing_mode: str = 'standard'):
    """分析单个图片"""
    analyzer = GeminiAnalyzer(timing_mode=timing_mode)

    logger.info(f"开始分析单个图片: {image_name}")

    result = analyzer.analyze_image(image_name, prompt_name, save_result)

    # 打印结果
    if result.get('success'):
        print(f"\n分析结果: {result.get('response_text')}")
    else:
        print(f"\n分析失败: {result.get('error', '未知错误')}")

    # 打印时间分析
    if 'timings' in result:
        analyzer.print_timing_analysis(result)

def analyze_single_image_multiple_prompts(image_name: str, prompt_names: List[str] = None, timing_mode: str = 'standard'):
    """分析单个图片"""
    analyzer = GeminiAnalyzer(timing_mode=timing_mode)
    logger.info(f"开始分析单个图片: {image_name}")

    for prompt_name in prompt_names:
        logger.info(f"使用 prompt '{prompt_name}' 处理图片...")
        result = analyzer.analyze_image(image_name, prompt_name, True)
        # 打印结果
        if result.get('success'):
            print(f"\n分析结果: {result.get('response_text')}")
        else:
            print(f"\n分析失败: {result.get('error', '未知错误')}")

        # 打印时间分析
        if 'timings' in result:
            analyzer.print_timing_analysis(result)


def process_batch_images(prompt_name: str = None, output_filename: str = None, timing_mode: str = 'standard'):
    """批量处理图片"""
    processor = BatchProcessor(timing_mode=timing_mode)

    logger.info("开始批量处理图片...")

    # 处理批量图片
    results = processor.process_batch(prompt_name=prompt_name)

    # 保存结果
    if results:
        saved_path = processor.save_batch_results(output_filename)

        # 生成并打印报告
        report = processor.generate_report()
        print("\n" + report)

        # 显示统计信息
        stats = processor.get_processing_statistics()
        if stats:
            print(f"\n详细统计:")
            print(f"处理图片总数: {stats['total_images_processed']}")
            print(f"成功率: {stats['summary']['success_rate']:.1f}%")

        logger.info(f"批量处理完成！结果已保存到: {saved_path}")
    else:
        logger.error("批量处理失败，没有生成结果")


def process_with_multiple_prompts(output_filename: str = None, timing_mode: str = 'standard'):
    """使用多个 prompt 处理图片"""
    processor = BatchProcessor(timing_mode=timing_mode)

    logger.info("开始多 prompt 批量处理...")

    # 使用所有 prompt 处理
    all_results = processor.process_with_multiple_prompts()

    # 保存汇总结果
    if all_results:
        if output_filename:
            # 保存汇总结果
            summary_filename = f"summary_{output_filename}"
            processor.save_batch_results(summary_filename)

        logger.info("多 prompt 处理完成！")
    else:
        logger.error("多 prompt 处理失败")


if __name__ == "__main__":
    main()