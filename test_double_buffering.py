#!/usr/bin/env python3
"""测试双缓冲队列系统"""

import time
import sys
import os

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

from process_pool import SimpleProcessPool

def simple_task(task_name, duration=2, gpu_id=None):
    """简单的测试任务"""
    print(f"Starting task '{task_name}' on GPU {gpu_id}")
    time.sleep(duration)
    print(f"Completed task '{task_name}' on GPU {gpu_id}")
    return f"Task '{task_name}' completed on GPU {gpu_id}"

def test_double_buffering():
    """测试双缓冲系统"""
    print("=== 测试双缓冲队列系统 ===")

    # 创建启用预处理的进程池
    with SimpleProcessPool(
        gpu_ids=[0],  # 使用单个GPU进行测试
        workers_per_gpu=1,
        enable_preprocessing=True,
        max_gpu_queue_size=100  # 最大队列长度100
    ) as pool:

        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
        print(f"总队列大小: {pool.get_queue_size()}")

        # 提交几个任务
        task_ids = []
        for i in range(3):
            task_id = pool.submit_task(simple_task, f"Task-{i}", duration=2)
            task_ids.append(task_id)
            print(f"Submitted task {task_id}")

        print(f"\n提交后的队列状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
        print(f"总队列大小: {pool.get_queue_size()}")

        # 等待一段时间让预处理进程工作
        print("\n等待预处理进程工作...")
        time.sleep(15)

        print(f"\n预处理后的队列状态:")
        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
        print(f"总队列大小: {pool.get_queue_size()}")

        # 发送完成信号
        pool.set_complete_signal()

        # 收集结果
        print("\n收集结果...")
        results = []
        start_time = time.time()

        while len(results) < len(task_ids) and time.time() - start_time < 60:  # 最多等待60秒
            result = pool.get_result(timeout=5.0)
            if result:
                task_id, status, data = result
                print(f"收到结果: task_id={task_id}, status={status}, data={data}")
                results.append(result)

        print(f"\n最终结果: 收到 {len(results)}/{len(task_ids)} 个结果")

def test_without_preprocessing():
    """测试不启用预处理的情况"""
    print("\n=== 测试不启用预处理的情况 ===")

    # 创建不启用预处理的进程池
    with SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        enable_preprocessing=False
    ) as pool:

        print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 提交一个任务
        task_id = pool.submit_task(simple_task, "Direct-Task", duration=1)
        print(f"Submitted direct task {task_id}")

        print(f"提交后的队列状态:")
        print(f"GPU队列大小: {pool.get_gpu_queue_size()}")

        # 发送完成信号并收集结果
        pool.set_complete_signal()

        result = pool.get_result(timeout=10.0)
        if result:
            task_id, status, data = result
            print(f"收到直接任务结果: {data}")

if __name__ == "__main__":
    test_double_buffering()
    test_without_preprocessing()
    print("\n测试完成!")