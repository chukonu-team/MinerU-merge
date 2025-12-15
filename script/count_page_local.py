import argparse
from pathlib import Path
import json


def analyze_json_files(folder_path , output_path):
    """使用pathlib实现的版本"""
    stats = {
        'total_files': 0, 'total_page_count': 0, 'total_file_size': 0,
        'total_fast_page_count': 0, 'success_true': 0, 'success_false': 0,
        'processed_files': 0, 'failed_files': 0, 'avg_page_count': 0,
        'avg_file_size': 0, 'avg_fast_page_count': 0, 'file_list': []
    }

    folder = Path(folder_path)
    if not folder.exists():
        print(f"错误: 文件夹 '{folder_path}' 不存在")
        return stats

    # 递归查找所有JSON文件
    json_files = list(folder.glob("**/*.json"))

    if not json_files:
        print(f"在文件夹 '{folder_path}' 及其子目录中未找到JSON文件")
        return stats

    print(f"找到 {len(json_files)} 个JSON文件，开始分析...")

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)

            # 更新统计信息（与之前相同）
            stats['total_files'] += 1
            stats['total_page_count'] += data.get('page_count', 0)
            stats['total_file_size'] += data.get('file_size', 0)
            stats['total_fast_page_count'] += data.get('fast_page_count', 0)

            if data.get('success') is True:
                stats['success_true'] += 1
            elif data.get('success') is False:
                stats['success_false'] += 1

            stats['processed_files'] += 1
            stats['file_list'].append(str(file_path))

        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            stats['failed_files'] += 1
            continue

    # 计算平均值（与之前相同）
    if stats['processed_files'] > 0:
        stats['avg_page_count'] = stats['total_page_count'] / stats['processed_files']
        stats['avg_file_size'] = stats['total_file_size'] / stats['processed_files']
        stats['avg_fast_page_count'] = stats['total_fast_page_count'] / stats['processed_files']

    # 打印结果（与之前相同）
    print("\n分析完成! 统计结果:")
    print(f"总文件数: {stats['total_files']}")
    print(f"成功处理: {stats['processed_files']}")
    print(f"处理失败: {stats['failed_files']}")
    print(f"成功为True的文件数: {stats['success_true']}")
    print(f"成功为False的文件数: {stats['success_false']}")
    print(f"总页数: {stats['total_page_count']}")
    print(f"平均页数: {stats['avg_page_count']:.2f}")
    print(f"总文件大小: {stats['total_file_size']} 字节")
    print(f"平均文件大小: {stats['avg_file_size']:.2f} 字节")
    print(f"总快速页数: {stats['total_fast_page_count']}")
    print(f"平均快速页数: {stats['avg_fast_page_count']:.2f}")

    result = {
        'total_files': stats['total_files'],
        'total_page_count': stats['total_page_count'],
        'total_file_size': stats['total_file_size']
    }

    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=4)


    return stats

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,  required=True , help="folder path")
    parser.add_argument("--output", type=Path, required=True , help="output file path")
    args = parser.parse_args()
    analyze_json_files(args.input, args.output)