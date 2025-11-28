#!/usr/bin/env python3
"""简单的双缓冲系统测试"""

import time
import sys
import os

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

from process_pool import SimpleProcessPool

def simple_task(task_name, duration=1, gpu_id=None):
    """简单的测试任务"""
    result = f"Task '{task_name}' completed on GPU {gpu_id} at {time.strftime('%H:%M:%S')}"
    return result

def main():
    print("=== 简单双缓冲系统测试 ===")

    # 创建启用预处理的进程池
    pool = SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        enable_preprocessing=True,
        max_gpu_queue_size=100
    )

    try:
        print(f"\n初始状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 提交任务
        print("\n提交任务...")
        for i in range(2):
            task_id = pool.submit_task(simple_task, f"Task-{i}", duration=1)
            print(f"提交任务 {task_id}")

        print(f"\n提交后的状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 等待预处理工作
        print("\n等待预处理工作 (15秒)...")
        time.sleep(15)

        print(f"\n预处理后的状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 发送完成信号
        pool.set_complete_signal()

        # 收集结果
        print("\n收集结果...")
        for i in range(2):
            result = pool.get_result(timeout=10.0)
            if result:
                task_id, status, data = result
                print(f"结果: {data}")

        print("\n测试完成!")

    finally:
        pool.shutdown()
        print("进程池已关闭")

if __name__ == "__main__":
    main()