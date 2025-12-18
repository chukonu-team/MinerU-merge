import json
import os

from pathlib import Path

def analyze_json_files(folder_path):
    """使用pathlib实现的版本"""
    stats = {
        'total_files': 0, 'total_page_count': 0, 'total_file_size': 0,
        'total_fast_page_count': 0, 'success_true': 0, 'success_false': 0,
        'processed_files': 0, 'failed_files': 0, 'avg_page_count': 0,
        'avg_file_size': 0, 'avg_fast_page_count': 0
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

    return stats

class MinerUProcessor:

    def process(self, input_path, output_path):
        # 从环境变量获取作业索引
        gpu_ids = os.getenv("GPU_IDS")
        vram_size_gb = os.getenv("VRAM_SIZE_GB")
        workers_per_gpu = os.getenv("WORKERS_PER_GPU")
        max_pages = os.getenv("MAX_PAGES")
        shuffle_env = os.getenv("SHUFFLE")
        shuffle = True if shuffle_env == "true" else False
        batch_size = os.getenv("BATCH_SIZE")
        proportion = os.getenv("PROPORTION", 0)
        use_batch = bool(os.getenv("USE_BATCH", "True"))

        if use_batch:
            from main.ocr_pdf_batch import process_pdfs
        else:
            from main.ocr_pdf import process_pdfs
        # 运行处理任务
        process_pdfs(
            input_dir=input_path,
            output_dir=output_path,
            vram_size_gb=int(vram_size_gb),
            gpu_ids=gpu_ids,
            workers_per_gpu=int(workers_per_gpu),
            max_pages=int(max_pages),
            shuffle=shuffle,
            batch_size=int(batch_size)
        )
        return analyze_json_files(f"{output_path}/page_result")


