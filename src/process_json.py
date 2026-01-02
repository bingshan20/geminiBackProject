import json
import csv
import os
import glob
import re
from collections import defaultdict


def natural_sort_key(s):
    """
    自然排序键函数，用于处理包含数字的文件名排序
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def extract_number_from_filename(filename):
    """
    从文件名中提取数字用于排序
    例如：'image_123.png' -> 123
    """
    # 尝试从文件名中提取数字
    numbers = re.findall(r'\d+', filename)
    return int(numbers[0]) if numbers else float('inf')


def enhanced_process_json_files(json_folder, output_csv, sort_method='natural', secondary_sort='prompt'):
    """
    批量处理JSON文件到CSV，支持多级排序

    Args:
        json_folder: JSON文件所在文件夹
        output_csv: 输出CSV文件路径
        sort_method: 主排序方式，可选 'natural', 'numeric', 'alphabetical'
        secondary_sort: 次级排序方式，可选 'prompt', 'none'
    """

    fieldnames = [
        'image_file', 'prompt_used', 'response_text',
        'namelookup_time', 'connect_time', 'appconnect_time',
        'pretransfer_time', 'starttransfer_time', 'total_time',
        'redirect_time', 'dns_time', 'tcp_handshake',
        'ssl_handshake', 'request_send', 'server_processing', 'response_transfer'
    ]

    # 统计信息
    stats = defaultdict(int)
    all_data = []

    # 获取JSON文件列表
    json_files = glob.glob(os.path.join(json_folder, "*.json"))

    print(f"找到 {len(json_files)} 个JSON文件")

    for json_file in json_files:
        stats['total_files'] += 1
        filename = os.path.basename(json_file)

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if data.get('success') is True:
                # 检查必需字段
                required_fields = ['image_file', 'prompt_used', 'response_text']
                missing_fields = [field for field in required_fields if field not in data]

                if missing_fields:
                    print(f"警告: {filename} 缺少字段: {missing_fields}")
                    stats['missing_fields'] += 1
                    continue

                # 检查timings字段（可选，但如果有的话需要处理）
                has_timings = 'timings' in data
                if not has_timings:
                    stats['no_timings'] += 1
                    print(f"警告: {filename} 缺少timings字段")

                # 提取数据
                row_data = {
                    'image_file': data['image_file'],
                    'prompt_used': data['prompt_used'],
                    'response_text': data['response_text']
                }

                # 提取timings并转换为微秒（如果有的话）
                if has_timings:
                    timings = data['timings']
                    for field in fieldnames[3:]:
                        if field in timings:
                            row_data[field] = timings[field] * 1000000
                        else:
                            row_data[field] = 0
                else:
                    # 如果没有timings，填充默认值
                    for field in fieldnames[3:]:
                        row_data[field] = 0

                all_data.append(row_data)
                stats['processed'] += 1
                print(f"✓ 处理成功: {filename}")

            else:
                stats['skipped_success_false'] += 1
                print(f"✗ 跳过 (success=false): {filename}")

        except json.JSONDecodeError:
            stats['json_decode_error'] += 1
            print(f"✗ JSON解析错误: {filename}")
        except Exception as e:
            stats['other_errors'] += 1
            print(f"✗ 处理错误 {filename}: {e}")

    # 对最终数据进行多级排序
    if all_data:
        if secondary_sort == 'prompt':
            # 先按image_file排序，再按prompt_used排序
            if sort_method == 'natural':
                all_data.sort(key=lambda x: (natural_sort_key(x['image_file']), x['prompt_used'].lower()))
            elif sort_method == 'numeric':
                all_data.sort(key=lambda x: (extract_number_from_filename(x['image_file']), x['prompt_used'].lower()))
            else:  # alphabetical
                all_data.sort(key=lambda x: (x['image_file'].lower(), x['prompt_used'].lower()))
        else:
            # 只按image_file排序
            if sort_method == 'natural':
                all_data.sort(key=lambda x: natural_sort_key(x['image_file']))
            elif sort_method == 'numeric':
                all_data.sort(key=lambda x: extract_number_from_filename(x['image_file']))
            else:  # alphabetical
                all_data.sort(key=lambda x: x['image_file'].lower())

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)

        # 写入CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_data)

        # 生成统计报告
        print("\n" + "=" * 60)
        print("处理统计报告:")
        print("=" * 60)
        print(f"总文件数: {stats['total_files']}")
        print(f"成功处理: {stats['processed']}")
        print(f"跳过(success=false): {stats['skipped_success_false']}")
        print(f"JSON解析错误: {stats['json_decode_error']}")
        print(f"缺少必需字段: {stats['missing_fields']}")
        print(f"缺少timings字段: {stats['no_timings']}")
        print(f"其他错误: {stats['other_errors']}")
        print(f"CSV文件: {output_csv}")
        print(f"生成记录数: {len(all_data)}")
        print(f"主排序方式: {sort_method}")
        print(f"次级排序方式: {secondary_sort}")

        # 显示排序后的记录
        print("\n排序后的记录 (前15条):")
        current_image = None
        for i, item in enumerate(all_data[:15]):
            # 如果image_file发生变化，显示分隔线
            if item['image_file'] != current_image:
                if current_image is not None:
                    print("  " + "-" * 40)
                current_image = item['image_file']

            print(f"  {i + 1:2d}. {item['image_file']} | {item['prompt_used']} | {item['response_text']}")

        if len(all_data) > 15:
            print(f"  ... 共 {len(all_data)} 条记录")

        # 显示分组统计
        print(f"\n分组统计:")
        image_groups = defaultdict(list)
        for item in all_data:
            image_groups[item['image_file']].append(item)

        for image_file, items in list(image_groups.items())[:5]:  # 只显示前5个分组
            prompts = [item['prompt_used'] for item in items]
            print(f"  {image_file}: {len(items)} 个prompt ({', '.join(prompts)})")

        if len(image_groups) > 5:
            print(f"  ... 共 {len(image_groups)} 个不同的image_file")

    else:
        print("没有找到可处理的数据")


def get_sorting_options():
    """获取排序选项"""
    print("\n选择排序方式:")
    print("1. 自然排序 (推荐，处理 img1.png, img2.png, img10.png)")
    print("2. 数字排序 (按文件名中的第一个数字)")
    print("3. 字母排序 (按文件名ASCII顺序)")

    choice = input("请输入主排序选择 (默认:1): ").strip()
    sort_methods = {'1': 'natural', '2': 'numeric', '3': 'alphabetical'}
    sort_method = sort_methods.get(choice, 'natural')

    print("\n选择次级排序方式:")
    print("1. 按prompt_used排序 (先按image_file，再按prompt_used)")
    print("2. 不进行次级排序 (只按image_file排序)")

    choice = input("请输入次级排序选择 (默认:3): ").strip()
    secondary_sorts = {'1': 'prompt', '2': 'none'}
    secondary_sort = secondary_sorts.get(choice, 'prompt')

    return sort_method, secondary_sort


# 使用示例
if __name__ == "__main__":
    json_folder = input("JSON文件夹路径 (默认:../json_files/0101): ").strip() or "../json_files/0101"
    output_csv = input("输出CSV路径 (默认: ../json_files/csv/output4.csv): ").strip() or "../json_files/csv/output4.csv"

    sort_method, secondary_sort = get_sorting_options()

    enhanced_process_json_files(json_folder, output_csv, sort_method, secondary_sort)