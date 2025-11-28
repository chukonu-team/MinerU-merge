#!/usr/bin/env python3
"""仅测试GPU工作进程"""

import time
import sys
import os

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

from process_pool import SimpleProcessPool

def simple_gpu_task(data, save_dir):
    """简单的GPU任务，测试基本功能"""
    print(f"GPU工作进程收到任务: {type(data)}")
    print(f"save_dir: {save_dir}")

    # 模拟一些处理时间
    print("开始GPU处理...")
    time.sleep(2)
    print("GPU处理完成")

    return {
        'status': 'success',
        'message': '简单GPU任务完成',
        'timestamp': time.time()
    }

def main():
    print("=== 测试GPU工作进程 ===")

    # 创建简单的进程池（禁用预处理）
    pool = SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        enable_preprocessing=False,  # 禁用预处理，直接GPU处理
        max_gpu_queue_size=100,
        preprocessing_workers=0  # 无预处理工作进程
    )

    print(f"初始状态:")
    print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
    print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

    # 创建简单测试数据
    test_data = {
        'files': ['test1.pdf'],
        'message': '这是一个测试任务'
    }

    temp_output_dir = "/tmp/gpu_worker_test"
    print(f"提交测试任务到GPU队列...")

    # 直接提交到GPU任务队列
    task_id = pool.submit_task(simple_gpu_task, test_data, temp_output_dir)
    print(f"任务ID: {task_id}")

    print(f"\n提交后的状态:")
    print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
    print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

    # 等待结果
    print("\n等待GPU处理结果...")
    start_time = time.time()

    result = pool.get_result(timeout=30.0)
    if result:
        task_id_result, status, data = result
        print(f"收到结果: task_id={task_id_result}, status={status}")
        if status == 'success':
            print(f"处理成功: {data}")
        else:
            print(f"处理失败: {data}")
    else:
        print("未收到结果")

    elapsed = time.time() - start_time
    print(f"总耗时: {elapsed:.2f}秒")

    # 清理
    pool.shutdown()
    print("进程池已关闭")

if __name__ == "__main__":
    main()