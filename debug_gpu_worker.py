#!/usr/bin/env python3
"""调试GPU工作进程问题"""

import time
import sys
import os

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

def simple_gpu_task(data, save_dir):
    """简单的GPU任务，用于测试"""
    print(f"GPU工作进程收到任务: {data}")
    print(f"save_dir: {save_dir}")

    # 模拟一些处理时间
    time.sleep(2)

    # 返回简单结果
    return {
        'status': 'success',
        'message': 'GPU任务完成',
        'data': data,
        'timestamp': time.time()
    }

def main():
    print("=== 调试GPU工作进程 ===")

    from process_pool import SimpleProcessPool

    # 创建进程池（不启用预处理）
    pool = SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        enable_preprocessing=False  # 直接GPU处理
    )

    print("进程池创建完成")

    # 测试数据
    test_data = {
        'files': ['test.pdf'],
        'message': '这是一个测试任务'
    }

    save_dir = "/tmp/debug_gpu_test"

    try:
        # 提交任务
        print("提交GPU任务...")
        task_id = pool.submit_task(simple_gpu_task, test_data, save_dir)
        print(f"任务ID: {task_id}")

        # 设置完成信号
        pool.set_complete_signal()

        # 等待结果
        print("等待GPU结果...")
        start_time = time.time()

        for _ in range(1):  # 只有一个任务
            result = pool.get_result(timeout=30.0)
            if result:
                task_id_result, status, data = result
                print(f"收到结果: task_id={task_id_result}, status={status}")
                print(f"返回数据: {data}")
                break
            else:
                elapsed = time.time() - start_time
                print(f"等待中...已等待{elapsed:.1f}秒")
                if elapsed > 25:
                    print("等待超时")
                    break

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 关闭进程池
        print("关闭进程池...")
        pool.shutdown()
        print("清理完成")

if __name__ == "__main__":
    main()