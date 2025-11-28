#!/usr/bin/env python3
"""测试增强版双缓冲队列系统 - 包含详细调试日志"""

import time
import sys
import os
import json
import tempfile
import random
import traceback
import signal

# 添加main目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

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
    print("=== 测试增强版双缓冲队列系统（详细调试版）===")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.path}")

    # 获取真实的PDF文件
    test_pdf_files = get_real_pdf_files()
    print(f"找到 {len(test_pdf_files)} 个真实PDF文件:")
    for file_path in test_pdf_files:
        print(f"  - {os.path.basename(file_path)}")

    if not test_pdf_files:
        print("错误: 没有找到PDF文件，无法进行测试")
        return

    # 创建临时输出目录
    temp_output_dir = tempfile.mkdtemp(prefix="mineru_debug_test_")
    print(f"输出目录: {temp_output_dir}")

    # 添加信号处理来捕获异常
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在清理...")
        import shutil
        shutil.rmtree(temp_output_dir, ignore_errors=True)
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 导入process_pool模块，添加错误处理
        try:
            from process_pool import SimpleProcessPool
            print("成功导入 SimpleProcessPool")
        except Exception as e:
            print(f"导入 SimpleProcessPool 失败: {e}")
            traceback.print_exc()
            return

        # 创建启用多进程预处理的进程池
        print("\n创建 SimpleProcessPool...")
        try:
            pool = SimpleProcessPool(
                gpu_ids=[0],
                workers_per_gpu=1,
                enable_preprocessing=True,
                max_gpu_queue_size=100,
                preprocessing_workers=2  # 2个预处理工作进程
            )
            print("SimpleProcessPool 创建成功")
        except Exception as e:
            print(f"创建 SimpleProcessPool 失败: {e}")
            traceback.print_exc()
            return

        print(f"\n初始状态:")
        try:
            print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
            print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
            print(f"预处理工作进程数: {pool.preprocessing_workers}")
            print(f"工作进程数: {len(pool.workers)}")
            for worker_id, worker_info in pool.workers.items():
                print(f"  Worker {worker_id}: GPU {worker_info.gpu_id}, PID {worker_info.pid}, 状态 {worker_info.status}")
        except Exception as e:
            print(f"获取初始状态失败: {e}")
            traceback.print_exc()

        # 创建测试批次
        test_batch = {
            'files': test_pdf_files,
            'file_names': [os.path.basename(f) for f in test_pdf_files],
            'total_pages': None  # 让系统自动检测页数
        }

        print(f"\n提交测试批次: {test_batch['file_names']}")

        # 导入增强版gpu_worker_task函数，添加错误处理
        try:
            from ocr_pdf_batch import gpu_worker_task
            print("成功导入 gpu_worker_task")
        except Exception as e:
            print(f"导入 gpu_worker_task 失败: {e}")
            traceback.print_exc()
            return

        # 提交任务到双缓冲系统，添加详细日志
        print("\n提交任务到预处理队列...")
        try:
            task_id = pool.submit_task(gpu_worker_task, test_batch, temp_output_dir)
            print(f"成功提交任务 {task_id}")
        except Exception as e:
            print(f"提交任务失败: {e}")
            traceback.print_exc()
            return

        print(f"\n提交后的状态:")
        try:
            print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
            print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
        except Exception as e:
            print(f"获取提交后状态失败: {e}")
            traceback.print_exc()

        # 等待一下，让预处理开始工作
        print("\n等待预处理开始工作...")
        time.sleep(2)

        print(f"等待2秒后的状态:")
        try:
            print(f"预处理队列大小: {pool.get_preprocessing_queue_size()}")
            print(f"GPU队列大小: {pool.get_gpu_queue_size()}")
        except Exception as e:
            print(f"获取等待后状态失败: {e}")
            traceback.print_exc()

        # 发送完成信号
        print("\n发送完成信号...")
        try:
            pool.set_complete_signal()
            print("完成信号发送成功")
        except Exception as e:
            print(f"发送完成信号失败: {e}")
            traceback.print_exc()

        # 收集结果 - 使用与ocr_pdf_batch.py相同的机制
        print("\n开始收集结果...")
        start_time = time.time()
        result = None
        max_wait_time = 120  # 最大等待时间

        # 持续检查状态，直到获得结果或超时
        while time.time() - start_time < max_wait_time:
            elapsed = time.time() - start_time
            print(f"\n等待结果中...已等待{elapsed:.1f}秒")

            # 检查队列状态
            try:
                preprocess_size = pool.get_preprocessing_queue_size()
                gpu_size = pool.get_gpu_queue_size()
                print(f"  队列状态 - 预处理: {preprocess_size}, GPU: {gpu_size}")
            except Exception as e:
                print(f"  获取队列状态失败: {e}")

            # 尝试获取结果
            try:
                result = pool.get_result(timeout=5.0)  # 5秒超时
                if result:
                    print(f"  收到结果: {result}")
                    break
                else:
                    print(f"  没有收到结果，继续等待...")
            except Exception as e:
                print(f"  获取结果时出错: {e}")

            # 如果等待时间过长，检查工作进程状态
            if elapsed > 30:
                print("  检查工作进程状态:")
                try:
                    for worker_id, worker_info in pool.workers.items():
                        if worker_info.process.is_alive():
                            print(f"    Worker {worker_id}: 活跃")
                        else:
                            print(f"    Worker {worker_id}: 已退出，退出代码 {worker_info.process.exitcode}")
                except Exception as e:
                    print(f"    检查工作进程状态失败: {e}")

            time.sleep(5)  # 每5秒检查一次

        # 分析结果
        if result:
            print(f"\n最终结果: {result}")
            task_id, status, data = result
            print(f"任务ID: {task_id}")
            print(f"状态: {status}")

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
            print("\n未收到结果，可能处理超时")
            print("可能的原因:")
            print("1. GPU工作进程异常退出")
            print("2. 预处理工作进程无法提交任务到GPU队列")
            print("3. 任务执行时间过长")
            print("4. 队列阻塞或其他系统问题")

        print("\n测试完成!")

    except Exception as e:
        print(f"\n测试过程中发生异常: {e}")
        traceback.print_exc()

    finally:
        # 清理资源
        print("\n清理资源...")
        try:
            if 'pool' in locals():
                pool.shutdown()
                print("进程池已关闭")
        except Exception as e:
            print(f"关闭进程池时出错: {e}")

        # 清理临时目录
        try:
            import shutil
            shutil.rmtree(temp_output_dir, ignore_errors=True)
            print("临时输出目录已清理")
        except Exception as e:
            print(f"清理临时目录时出错: {e}")

if __name__ == "__main__":
    main()