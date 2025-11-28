#!/usr/bin/env python3
"""测试队列大小限制"""

import time
import sys
import os

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

from process_pool import SimpleProcessPool

def simple_task(task_name, duration=0.1, gpu_id=None):
    """快速的测试任务"""
    return f"Task '{task_name}' completed on GPU {gpu_id}"

def test_queue_limit():
    """测试队列大小限制"""
    print("=== 测试队列大小限制 (最大3个任务) ===")

    # 创建队列限制很小的进程池
    pool = SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        enable_preprocessing=True,
        max_gpu_queue_size=3  # 设置很小的队列限制
    )

    try:
        print(f"提交多个任务来测试队列限制...")

        # 快速提交多个任务，测试队列限制
        for i in range(5):
            task_id = pool.submit_task(simple_task, f"Task-{i}", duration=0.1)
            print(f"提交任务 {task_id}")

            # 显示队列状态
            preproc_size = pool.get_preprocessing_queue_size()
            gpu_size = pool.get_gpu_queue_size()
            print(f"  预处理队列: {preproc_size}, GPU队列: {gpu_size}")

            time.sleep(0.5)  # 短暂等待

        print("\n等待所有预处理完成...")
        time.sleep(20)  # 等待预处理完成

        print(f"\n最终队列状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 发送完成信号并收集结果
        pool.set_complete_signal()

        print("\n收集结果...")
        for i in range(5):
            result = pool.get_result(timeout=5.0)
            if result:
                task_id, status, data = result
                print(f"结果: {data}")

        print("\n测试完成!")

    finally:
        pool.shutdown()
        print("进程池已关闭")

if __name__ == "__main__":
    test_queue_limit()