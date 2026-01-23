#!/usr/bin/env python3
"""
多进程启动脚本，用于并行执行 pipeline.py
"""
import multiprocessing as mp
import os
import time
import argparse
from pathlib import Path
from tasks.pipeline_sort import main_func


def worker_process(process_id, save_dir=None):
    """
    工作进程函数

    Args:
        process_id: 进程ID
        save_dir: 保存目录
    """
    if save_dir:
        # 为每个进程创建独立的保存目录
        process_save_dir = os.path.join(save_dir, f"process_{process_id}")
        os.makedirs(process_save_dir, exist_ok=True)
    else:
        process_save_dir = None

    print(f"[Process {process_id}] Starting...")
    start_time = time.time()

    try:
        main_func(save_dir=process_save_dir)
        elapsed = time.time() - start_time
        print(f"[Process {process_id}] Completed in {elapsed:.2f}s")
    except Exception as e:
        print(f"[Process {process_id}] Error: {e}")
        raise


def run_multiprocess(num_processes=None, save_dir=None):
    """
    启动多个进程并行执行 pipeline

    Args:
        num_processes: 进程数量，默认为 CPU 核心数
        save_dir: 保存目录
    """
    if num_processes is None:
        num_processes = mp.cpu_count()

    print(f"Starting {num_processes} processes...")
    print(f"Save directory: {save_dir if save_dir else 'Not specified'}")

    # 创建主保存目录
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    start_time = time.time()

    # 创建进程池
    processes = []
    for i in range(num_processes):
        p = mp.Process(target=worker_process, args=(i, save_dir))
        processes.append(p)
        p.start()

    # 等待所有进程完成
    for p in processes:
        p.join()

    total_time = time.time() - start_time
    print("\n" + "="*60)
    print(f"All {num_processes} processes completed!")
    print(f"Total execution time: {total_time:.2f}s")
    print(f"Average time per process: {total_time/num_processes:.2f}s")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Multi-process launcher for pipeline.py"
    )
    parser.add_argument(
        "-n", "--num-processes",
        type=int,
        default=None,
        help="Number of processes to launch (default: number of CPU cores)"
    )
    parser.add_argument(
        "-s", "--save-dir",
        type=str,
        default="./result/multiprocess_run",
        help="Directory to save results (default: ./result/multiprocess_run)"
    )

    args = parser.parse_args()

    run_multiprocess(
        num_processes=args.num_processes,
        save_dir=args.save_dir
    )


if __name__ == "__main__":
    # 设置 multiprocessing 启动方法
    mp.set_start_method('spawn', force=True)
    main()
