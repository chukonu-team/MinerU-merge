#!/usr/bin/env python3
"""
测试Simple MinerU系统的基本功能
"""

import sys
import time
from pathlib import Path

# 添加main目录到路径以便导入模块
sys.path.insert(0, '/home/ubuntu/MinerU-merge/main')

from common import get_subdirectories, has_files

# 添加simple目录到路径以便导入模块
sys.path.insert(0, str(Path('.')))

from process_pool import SimpleProcessPool

def test_basic_functions():
    """测试基本函数导入"""
    print("=== 测试基本函数 ===")

    # 测试common模块
    pdf_dir = "/home/ubuntu/MinerU-merge/demo/pdfs"
    list_dir = get_subdirectories(pdf_dir)
    has_file = has_files(pdf_dir)

    print(f"目录扫描: {pdf_dir}")
    print(f"  子目录数: {len(list_dir)}")
    print(f"  有文件: {has_file}")

    return True

def test_process_pool():
    """测试三级队列进程池"""
    print("\n=== 测试三级队列进程池 ===")

    # 创建简单的测试函数
    def preprocess_func(task_data):
        """模拟预处理函数"""
        time.sleep(0.5)  # 模拟预处理时间
        return {
            'task_id': task_data,
            'preprocessed_data': f"preprocessed_{task_data}",
            'success': True
        }

    def gpu_func(preprocessed_data, gpu_id=0):
        """模拟GPU推理函数"""
        time.sleep(1.0)  # 模拟GPU推理时间
        return {
            **preprocessed_data,
            'gpu_result': f"gpu_processed_{preprocessed_data['task_id']}_on_gpu_{gpu_id}",
            'gpu_id': gpu_id,
            'success': True
        }

    def postprocess_func(gpu_result_data, save_dir="/tmp/test_output"):
        """模拟后处理函数"""
        time.sleep(0.3)  # 模拟后处理时间
        import os
        os.makedirs(save_dir, exist_ok=True)

        output_file = os.path.join(save_dir, f"result_{gpu_result_data['task_id']}.txt")
        with open(output_file, 'w') as f:
            f.write(f"Task: {gpu_result_data['task_id']}\n")
            f.write(f"Status: {gpu_result_data['success']}\n")
            f.write(f"GPU ID: {gpu_result_data['gpu_id']}\n")

        return {
            **gpu_result_data,
            'output_file': output_file,
            'postprocessed': True
        }

    # 创建三级队列进程池
    with SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        enable_preprocessing=True,
        max_gpu_queue_size=5,  # 小队列用于测试
        preprocessing_workers=2,
        postprocessing_workers=2
    ) as pool:

        print("✓ 三级队列进程池创建成功")
        print(f"  预处理队列大小: {pool.get_preprocessing_queue_size()}")
        print(f"  GPU队列大小: {pool.get_gpu_queue_size()}")
        print(f"  后处理队列大小: {pool.get_postprocessing_queue_size()}")

        # 提交测试任务
        print("\n提交测试任务...")
        task_ids = []
        for i in range(3):
            task_id = pool.submit_task(preprocess_func, f"test_task_{i}")
            task_ids.append(task_id)
            print(f"  提交任务 {task_id}: test_task_{i}")

        # 收集结果
        print("\n等待任务完成...")
        results = []
        timeout = time.time() + 30  # 30秒超时

        while len(results) < len(task_ids) and time.time() < timeout:
            # 打印队列状态
            pre_size = pool.get_preprocessing_queue_size()
            gpu_size = pool.get_gpu_queue_size()
            post_size = pool.get_postprocessing_queue_size()
            print(f"  队列状态 - 预处理: {pre_size}, GPU: {gpu_size}, 后处理: {post_size}")

            # 获取结果
            result = pool.get_result(timeout=2.0)
            if result:
                task_id, status, result_data = result
                print(f"  收到结果: 任务 {task_id}, 状态: {status}")
                results.append((task_id, status, result_data))

        print(f"\n✓ 收到 {len(results)} 个结果")

        # 检查结果
        success_count = sum(1 for _, status, _ in results if status == 'success')
        print(f"✓ 成功处理: {success_count}/{len(task_ids)} 个任务")

        # 检查输出文件
        import os
        test_output_dir = "/tmp/test_output"
        if os.path.exists(test_output_dir):
            output_files = os.listdir(test_output_dir)
            print(f"✓ 输出文件数: {len(output_files)}")
            for filename in output_files:
                print(f"  - {filename}")

        return success_count == len(task_ids)

def main():
    """主测试函数"""
    print("Simple MinerU 系统测试")
    print("=" * 50)

    try:
        # 测试基本函数
        basic_test = test_basic_functions()
        print(f"✓ 基本函数测试: {'通过' if basic_test else '失败'}")

        # 测试进程池
        pool_test = test_process_pool()
        print(f"✓ 三级队列测试: {'通过' if pool_test else '失败'}")

        print("\n" + "=" * 50)
        print("测试完成!")

        if basic_test and pool_test:
            print("🎉 所有测试通过！三级队列系统工作正常。")
            return True
        else:
            print("❌ 部分测试失败，请检查系统配置。")
            return False

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)