#!/usr/bin/env python3
"""测试增强版双缓冲队列系统 - 包含图像加载预处理"""

import time
import sys
import os
import json
import tempfile
import random

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

from process_pool import SimpleProcessPool

def get_real_pdf_files():
    """获取真实的PDF文件进行测试"""
    demo_pdfs_dir = os.path.join(os.path.dirname(__file__), 'demo', 'pdfs')

    if not os.path.exists(demo_pdfs_dir):
        print(f"错误: demo/pdfs 目录不存在: {demo_pdfs_dir}")
        return []

    # 获取所有PDF文件
    pdf_files = []
    for file_name in os.listdir(demo_pdfs_dir):
        if file_name.endswith('.pdf'):
            pdf_files.append(os.path.join(demo_pdfs_dir, file_name))

    return pdf_files

def cleanup_test_files(files):
    """清理测试文件"""
    for file_path in files:
        try:
            os.unlink(file_path)
        except:
            pass

def main():
    print("=== 测试增强版双缓冲队列系统（包含图像加载预处理）===")

    # 获取真实的PDF文件
    test_pdf_files = get_real_pdf_files()
    print(f"找到 {len(test_pdf_files)} 个真实PDF文件:")
    for file_path in test_pdf_files:
        print(f"  - {os.path.basename(file_path)}")

    # 创建临时输出目录
    temp_output_dir = tempfile.mkdtemp(prefix="mineru_enhanced_test_")
    print(f"输出目录: {temp_output_dir}")

    try:
        # 创建启用多进程预处理的进程池
        pool = SimpleProcessPool(
            gpu_ids=[0],
            workers_per_gpu=1,
            enable_preprocessing=True,
            max_gpu_queue_size=100,
            preprocessing_workers=2  # 2个预处理工作进程
        )

        print(f"\n初始状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
        print(f"预处理工作进程数: {pool.preprocessing_workers}")

        # 创建测试批次
        test_batch = {
            'files': test_pdf_files,
            'file_names': [os.path.basename(f) for f in test_pdf_files],
            'total_pages': None  # 让系统自动检测页数
        }

        print(f"\n提交测试批次: {test_batch['file_names']}")

        # 导入增强版gpu_worker_task函数
        from ocr_pdf_batch import gpu_worker_task

        # 提交任务到双缓冲系统
        task_id = pool.submit_task(gpu_worker_task, test_batch, temp_output_dir)
        print(f"提交任务 {task_id}")

        print(f"\n提交后的状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 发送完成信号
        pool.set_complete_signal()

        # 收集结果 - 使用与ocr_pdf_batch.py相同的机制
        print("\n收集结果...")
        start_time = time.time()

        # 等待所有任务完成
        for _ in range(1):  # 我们只有一个批次
            result = pool.get_result(timeout=120.0)  # 足够长的超时时间
            if result:
                task_id, status, data = result
                print(f"收到结果: task_id={task_id}, status={status}")
                break
            else:
                elapsed = time.time() - start_time
                print(f"等待结果中...已等待{elapsed:.1f}秒")
                if elapsed > 100:  # 超时保护
                    print("等待超时，退出")
                    break

        if result:
            task_id, status, data = result
            print(f"收到结果: task_id={task_id}, status={status}")
            if status == 'success':
                print("处理成功!")
                if hasattr(data, 'get'):
                    result_data = data
                    if 'preprocess_time' in result_data:
                        print(f"  预处理时间: {result_data['preprocess_time']:.2f}秒")
                    if 'image_loading_time' in result_data:
                        print(f"  图像加载时间: {result_data['image_loading_time']:.2f}秒")
                    if 'gpu_time' in result_data:
                        print(f"  GPU处理时间: {result_data['gpu_time']:.2f}秒")
                    if 'total_preprocess_time' in result_data:
                        print(f"  总预处理时间: {result_data['total_preprocess_time']:.2f}秒")
                    if 'total_time' in result_data:
                        print(f"  总处理时间: {result_data['total_time']:.2f}秒")
                    if 'results' in result_data:
                        print(f"  处理文件数: {len(result_data['results'])}")
            elif status == 'error':
                print(f"处理失败: {data}")
        else:
            print("未收到结果，可能处理时间不够")

        print("\n测试完成!")

    finally:
        # 清理资源
        pool.shutdown()
        print("进程池已关闭")

        # 不清理真实PDF文件，只清理输出目录
        import shutil
        shutil.rmtree(temp_output_dir, ignore_errors=True)
        print("临时输出目录已清理")

if __name__ == "__main__":
    main()