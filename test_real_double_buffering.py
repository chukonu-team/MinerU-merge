#!/usr/bin/env python3
"""测试真实场景的双缓冲队列系统"""

import time
import sys
import os
import json
import tempfile
import random

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

from process_pool import SimpleProcessPool

def create_test_pdf_files(num_files=3):
    """创建测试用的虚拟PDF文件"""
    test_files = []
    for i in range(num_files):
        # 创建临时文件模拟PDF
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        temp_file.write(b'%PDF-1.4\n% fake pdf content for testing\n')
        temp_file.close()
        test_files.append(temp_file.name)

    return test_files

def cleanup_test_files(files):
    """清理测试文件"""
    for file_path in files:
        try:
            os.unlink(file_path)
        except:
            pass

def main():
    print("=== 测试真实场景双缓冲队列系统 ===")

    # 创建测试PDF文件
    test_pdf_files = create_test_pdf_files(3)
    print(f"创建了 {len(test_pdf_files)} 个测试PDF文件")

    # 创建临时输出目录
    temp_output_dir = tempfile.mkdtemp(prefix="mineru_test_")
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
            'total_pages': len(test_pdf_files) * 5  # 假设每个文件5页
        }

        print(f"\n提交测试批次: {test_batch['file_names']}")

        # 导入gpu_worker_task函数
        from ocr_pdf_batch import gpu_worker_task

        # 提交任务到双缓冲系统
        task_id = pool.submit_task(gpu_worker_task, test_batch, temp_output_dir)
        print(f"提交任务 {task_id}")

        print(f"\n提交后的状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 等待处理完成
        print("\n等待处理完成...")
        time.sleep(30)  # 给预处理和GPU处理足够的时间

        print(f"\n处理后的状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 发送完成信号
        pool.set_complete_signal()

        # 收集结果
        print("\n收集结果...")
        result = pool.get_result(timeout=30.0)

        if result:
            task_id, status, data = result
            print(f"收到结果: task_id={task_id}, status={status}")
            if status == 'success':
                print("处理成功!")
                if hasattr(data, 'get'):
                    print(f"结果数据: {data}")
            elif status == 'error':
                print(f"处理失败: {data}")
        else:
            print("未收到结果，可能处理时间不够")

        print("\n测试完成!")

    finally:
        # 清理资源
        pool.shutdown()
        print("进程池已关闭")

        # 清理测试文件和目录
        cleanup_test_files(test_pdf_files)

        # 清理输出目录
        import shutil
        shutil.rmtree(temp_output_dir, ignore_errors=True)
        print("临时文件已清理")

if __name__ == "__main__":
    main()