#!/usr/bin/env python3
"""测试多进程预处理系统"""

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
    print("=== 测试多进程预处理系统 ===")

    # 创建启用多进程预处理的进程池
    pool = SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        enable_preprocessing=True,
        max_gpu_queue_size=100,
        preprocessing_workers=4  # 4个预处理工作进程
    )

    try:
        print(f"\n初始状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
        print(f"预处理工作进程数: {pool.preprocessing_workers}")

        # 快速提交8个任务，测试多进程并行预处理
        print("\n快速提交8个任务...")
        task_ids = []
        for i in range(8):
            task_id = pool.submit_task(simple_task, f"Task-{i}", duration=1)
            task_ids.append(task_id)
            print(f"提交任务 {task_id}")

        print(f"\n提交后的状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 等待预处理工作（4个进程并行处理）
        print("\n等待多进程预处理工作 (15秒)...")
        time.sleep(15)

        print(f"\n预处理后的状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 发送完成信号
        pool.set_complete_signal()

        # 收集结果
        print("\n收集结果...")
        results = []
        start_time = time.time()

        while len(results) < len(task_ids) and time.time() - start_time < 60:
            result = pool.get_result(timeout=5.0)
            if result:
                task_id, status, data = result
                print(f"结果: {data}")
                results.append(result)

        print(f"\n最终结果: 收到 {len(results)}/{len(task_ids)} 个结果")
        print("测试完成!")

    finally:
        pool.shutdown()
        print("进程池已关闭")

if __name__ == "__main__":
    main()