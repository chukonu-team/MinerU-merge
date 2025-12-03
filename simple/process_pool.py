#!/usr/bin/env python3
"""
Simple Process Pool - 基于 pool.md 设计的三级队列进程池
preprocess_queue -> gpu_queue -> post_queue
"""

import multiprocessing as mp
import time
import os
import traceback
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from queue import Empty, Full


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: int
    func: Callable
    args: tuple
    kwargs: dict


def _preprocessing_worker(worker_id: int, preprocess_queue: mp.Queue,
                          gpu_queue: mp.Queue, max_gpu_queue_size: int,
                          shutdown_event: mp.Event):
    """
    预处理工作进程 - 处理CPU密集型任务
    """
    processed_count = 0

    print(f"预处理工作进程 {worker_id} 启动, PID: {os.getpid()}")

    while not shutdown_event.is_set():
        try:
            # 从预处理队列获取任务
            task_data = preprocess_queue.get(timeout=1.0)
            if task_data is None:
                break

            task_id, func, args, kwargs = task_data
            print(f"预处理工作进程 {worker_id} 开始处理任务 {task_id}")

            # 执行预处理任务
            try:
                preprocessed_result = func(*args, **kwargs)
                processed_count += 1
                print(f"预处理工作进程 {worker_id} 完成任务 {task_id}")

                # 等待GPU队列有空间
                while gpu_queue.qsize() >= max_gpu_queue_size and not shutdown_event.is_set():
                    print(f"预处理工作进程 {worker_id}: GPU队列已满 ({gpu_queue.qsize()}/{max_gpu_queue_size}), 等待...")
                    time.sleep(1)

                if shutdown_event.is_set():
                    break

                # 将预处理结果传递给GPU队列
                from ocr_pdf_pool import gpu_inference_task
                gpu_task = (task_id, gpu_inference_task, (preprocessed_result,), {})
                gpu_queue.put(gpu_task)
                print(f"预处理工作进程 {worker_id} 已将任务 {task_id} 提交到GPU队列")

            except Exception as preprocess_error:
                print(f"预处理工作进程 {worker_id} 处理任务 {task_id} 失败: {preprocess_error}")
                # 即使预处理失败，也要将错误信息传递给GPU队列
                error_result = {
                    'success': False,
                    'error': str(preprocess_error),
                    'traceback': traceback.format_exc(),
                    'preprocessing_failed': True,
                    'task_id': task_id,
                    'preprocess_time': time.time()
                }

                from ocr_pdf_pool import gpu_inference_task
                error_task = (task_id, gpu_inference_task, (error_result,), {})
                gpu_queue.put(error_task)

        except Empty:
            continue
        except Exception as e:
            print(f"预处理工作进程 {worker_id} 错误: {e}")
            break

    print(f"预处理工作进程 {worker_id} 退出, 处理了 {processed_count} 个任务")


def _gpu_worker(worker_id: int, gpu_id: int, gpu_queue: mp.Queue,
                post_queue: mp.Queue, shutdown_event: mp.Event):
    """
    GPU工作进程 - 处理GPU推理任务
    """
    task_count = 0

    # 设置GPU设备
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.set_device(0)
            torch.cuda.empty_cache()
            gpu_name = torch.cuda.get_device_name(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
            print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 初始化完成: {gpu_name} ({total_memory:.1f}GB)")
    except ImportError:
        print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 警告: PyTorch未安装")

    print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 启动, PID: {os.getpid()}")

    while not shutdown_event.is_set():
        try:
            # 从GPU队列获取预处理后的数据
            task_data = gpu_queue.get(timeout=600.0)  # 10分钟超时
            if task_data is None:
                break

            task_id, func, args, kwargs = task_data
            print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 开始处理任务 {task_id}")

            try:
                # 执行GPU推理任务
                kwargs_with_gpu = kwargs.copy()
                kwargs_with_gpu['gpu_id'] = gpu_id

                gpu_result = func(*args, **kwargs_with_gpu)
                task_count += 1
                print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 完成任务 {task_id}")

                # 将GPU结果传递给后处理队列
                # 需要传递预处理数据作为kwargs
                preprocess_kwargs = args[0] if args else {}
                from ocr_pdf_pool import postprocessing_task
                post_task = (task_id, postprocessing_task, (gpu_result,), preprocess_kwargs)
                post_queue.put(post_task)
                print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 已将任务 {task_id} 提交到后处理队列")

            except Exception as gpu_error:
                print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 处理任务 {task_id} 失败: {gpu_error}")
                # 即使GPU推理失败，也要将错误结果传递给后处理队列
                error_result = {
                    'success': False,
                    'error': str(gpu_error),
                    'traceback': traceback.format_exc(),
                    'gpu_failed': True,
                    'task_id': task_id,
                    'gpu_id': gpu_id,
                    'gpu_time': 0,
                    'total_time': 0
                }

                from ocr_pdf_pool import postprocessing_task
                error_task = (task_id, postprocessing_task, (error_result,), {})
                post_queue.put(error_task)

        except Empty:
            print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) GPU队列为空，等待预处理任务...")
            time.sleep(2.0)
            continue
        except Exception as e:
            print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 意外错误: {e}")
            break

    # 清理GPU内存
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except:
        pass

    print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 退出, 处理了 {task_count} 个任务")


def _postprocessing_worker(worker_id: int, post_queue: mp.Queue,
                           result_queue: mp.Queue, shutdown_event: mp.Event):
    """
    后处理工作进程 - 处理文件保存等CPU密集型任务
    """
    processed_count = 0

    print(f"后处理工作进程 {worker_id} 启动, PID: {os.getpid()}")

    while not shutdown_event.is_set():
        try:
            # 从后处理队列获取GPU处理结果
            task_data = post_queue.get(timeout=600.0)  # 10分钟超时
            if task_data is None:
                break

            task_id, func, args, kwargs = task_data
            print(f"后处理工作进程 {worker_id} 开始处理任务 {task_id}")

            try:
                # 执行后处理任务（文件保存等）
                postprocessing_result = func(*args, **kwargs)
                processed_count += 1
                print(f"后处理工作进程 {worker_id} 完成任务 {task_id}")

                # 将最终结果放入结果队列
                result_queue.put((task_id, 'success', postprocessing_result))

            except Exception as post_error:
                print(f"后处理工作进程 {worker_id} 处理任务 {task_id} 失败: {post_error}")
                # 后处理失败，也要将错误信息放入结果队列
                result_queue.put((task_id, 'error', str(post_error)))

        except Empty:
            continue
        except Exception as e:
            print(f"后处理工作进程 {worker_id} 错误: {e}")
            break

    print(f"后处理工作进程 {worker_id} 退出, 处理了 {processed_count} 个任务")


@dataclass
class WorkerInfo:
    """工作进程信息"""
    worker_id: int
    process: mp.Process
    worker_type: str  # 'gpu', 'preprocessing', 'postprocessing'
    gpu_id: Optional[int] = None
    pid: Optional[int] = None
    status: str = "running"


class SimpleProcessPool:
    """
    简化的进程池 - 实现三级队列架构
    根据pool.md设计：
    - preprocess_queue: 不限长度
    - gpu_queue: 定长队列，maxlen 100
    - post_queue: 不限长度
    """

    def __init__(self, gpu_ids: List[int] = None, workers_per_gpu: int = 2,
                 enable_preprocessing: bool = True, max_gpu_queue_size: int = 100,
                 preprocessing_workers: int = 2, postprocessing_workers: int = 2):
        """
        初始化三级队列进程池

        Args:
            gpu_ids: GPU设备ID列表
            workers_per_gpu: 每个GPU的工作进程数
            enable_preprocessing: 是否启用预处理队列
            max_gpu_queue_size: GPU队列最大长度
            preprocessing_workers: 预处理工作进程数
            postprocessing_workers: 后处理工作进程数
        """
        if gpu_ids is None:
            gpu_ids = [0]

        self.gpu_ids = gpu_ids
        self.workers_per_gpu = workers_per_gpu
        self.max_gpu_workers = len(gpu_ids) * workers_per_gpu
        self.enable_preprocessing = enable_preprocessing
        self.max_gpu_queue_size = max_gpu_queue_size
        self.preprocessing_workers = preprocessing_workers
        self.postprocessing_workers = postprocessing_workers

        # 工作进程管理
        self.workers: Dict[int, WorkerInfo] = {}
        self.next_worker_id = 0

        # 三级队列系统（按照pool.md设计）
        self.preprocess_queue = mp.Queue()  # 不限长度
        self.gpu_queue = mp.Queue(maxsize=max_gpu_queue_size)  # 定长队列，maxlen 100
        self.post_queue = mp.Queue()  # 不限长度
        self.result_queue = mp.Queue()

        # 关闭事件
        self.shutdown_event = mp.Event()

        # 进程管理器
        self.preprocessing_manager: Optional[mp.Process] = None
        self.postprocessing_manager: Optional[mp.Process] = None

        print(f"=== 启动三级队列进程池 ===")
        print(f"预处理工作进程数: {self.preprocessing_workers}")
        print(f"GPU工作进程数: {self.max_gpu_workers} (GPU设备: {self.gpu_ids}, 每GPU工作进程: {workers_per_gpu})")
        print(f"后处理工作进程数: {self.postprocessing_workers}")
        print(f"GPU队列最大长度: {self.max_gpu_queue_size}")

        # 启动预处理工作进程
        if self.enable_preprocessing:
            self._start_preprocessing_workers()

        # 启动GPU工作进程
        self._start_gpu_workers()

        # 启动后处理工作进程
        self._start_postprocessing_workers()

    def _start_preprocessing_workers(self):
        """启动预处理工作进程管理器"""
        self.preprocessing_manager = mp.Process(
            target=self._run_preprocessing_workers
        )
        self.preprocessing_manager.start()
        print(f"预处理管理器已启动, PID: {self.preprocessing_manager.pid}")

    def _run_preprocessing_workers(self):
        """运行预处理工作进程"""
        workers = []
        for i in range(self.preprocessing_workers):
            worker = mp.Process(
                target=_preprocessing_worker,
                args=(i, self.preprocess_queue, self.gpu_queue,
                      self.max_gpu_queue_size, self.shutdown_event)
            )
            worker.start()
            workers.append(worker)
            print(f"预处理工作进程 {i} 已启动, PID: {worker.pid}")

        # 等待所有预处理工作进程完成
        for worker in workers:
            worker.join()

    def _start_gpu_workers(self):
        """启动GPU工作进程"""
        for gpu_id in self.gpu_ids:
            for i in range(self.workers_per_gpu):
                worker_id = self._create_gpu_worker(gpu_id)

    def _create_gpu_worker(self, gpu_id: int) -> int:
        """创建单个GPU工作进程"""
        worker_id = self.next_worker_id
        self.next_worker_id += 1

        process = mp.Process(
            target=_gpu_worker,
            args=(worker_id, gpu_id, self.gpu_queue, self.post_queue, self.shutdown_event)
        )

        worker_info = WorkerInfo(
            worker_id=worker_id,
            process=process,
            worker_type='gpu',
            gpu_id=gpu_id
        )

        process.start()
        worker_info.pid = process.pid
        self.workers[worker_id] = worker_info

        print(f"GPU工作进程 {worker_id} (GPU {gpu_id}) 已创建, PID: {process.pid}")
        return worker_id

    def _start_postprocessing_workers(self):
        """启动后处理工作进程管理器"""
        self.postprocessing_manager = mp.Process(
            target=self._run_postprocessing_workers
        )
        self.postprocessing_manager.start()
        print(f"后处理管理器已启动, PID: {self.postprocessing_manager.pid}")

    def _run_postprocessing_workers(self):
        """运行后处理工作进程"""
        workers = []
        for i in range(self.postprocessing_workers):
            worker = mp.Process(
                target=_postprocessing_worker,
                args=(i, self.post_queue, self.result_queue, self.shutdown_event)
            )
            worker.start()
            workers.append(worker)
            print(f"后处理工作进程 {i} 已启动, PID: {worker.pid}")

        # 等待所有后处理工作进程完成
        for worker in workers:
            worker.join()

    def submit_task(self, func: Callable, *args, **kwargs) -> int:
        """
        提交任务到预处理队列

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            int: 任务ID
        """
        task_id = int(time.time() * 1000000)
        task = (task_id, func, args, kwargs)

        # 提交到预处理队列
        self.preprocess_queue.put(task)
        print(f"任务 {task_id} 已提交到预处理队列")

        return task_id

    def get_result(self, timeout: float = None) -> Optional[tuple]:
        """
        从结果队列获取处理结果

        Args:
            timeout: 超时时间（秒）

        Returns:
            tuple: (task_id, status, result_data) 或 None
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except Empty:
            return None

    def is_task_queue_empty(self) -> bool:
        """检查所有任务队列是否为空"""
        return (self.preprocess_queue.empty() and
                self.gpu_queue.empty() and
                self.post_queue.empty())

    def get_preprocessing_queue_size(self) -> int:
        """获取预处理队列大小"""
        if self.enable_preprocessing:
            return self.preprocess_queue.qsize()
        return 0

    def get_gpu_queue_size(self) -> int:
        """获取GPU队列大小"""
        return self.gpu_queue.qsize()

    def get_postprocessing_queue_size(self) -> int:
        """获取后处理队列大小"""
        return self.post_queue.qsize()

    def all_tasks_completed(self) -> bool:
        """检查所有任务是否已完成"""
        return self.is_task_queue_empty() and len(self.workers) == 0

    def shutdown(self, timeout: float = 10.0):
        """关闭进程池"""
        print("开始关闭三级队列进程池...")
        self.shutdown_event.set()

        # 关闭预处理工作进程
        if self.enable_preprocessing and self.preprocessing_manager:
            print("关闭预处理管理器...")
            for _ in range(self.preprocessing_workers):
                self.preprocess_queue.put(None)

            self.preprocessing_manager.join(timeout=10.0)
            if self.preprocessing_manager.is_alive():
                self.preprocessing_manager.terminate()
                self.preprocessing_manager.join(timeout=5.0)

        # 关闭GPU工作进程
        print("关闭GPU工作进程...")
        for _ in range(len(self.workers)):
            self.gpu_queue.put(None)

        start_time = time.time()
        while time.time() - start_time < timeout and self.workers:
            dead_workers = []
            for worker_id, worker_info in self.workers.items():
                if not worker_info.process.is_alive():
                    dead_workers.append(worker_id)
                else:
                    worker_info.process.join(timeout=1.0)

            for worker_id in dead_workers:
                if worker_id in self.workers:
                    del self.workers[worker_id]

        # 强制终止仍在运行的GPU工作进程
        for worker_info in self.workers.values():
            if worker_info.process.is_alive():
                worker_info.process.terminate()
                worker_info.process.join(timeout=2.0)
                if worker_info.process.is_alive():
                    worker_info.process.kill()
                    worker_info.process.join()

        self.workers.clear()

        # 关闭后处理工作进程
        if self.postprocessing_manager:
            print("关闭后处理管理器...")
            for _ in range(self.postprocessing_workers):
                self.post_queue.put(None)

            self.postprocessing_manager.join(timeout=10.0)
            if self.postprocessing_manager.is_alive():
                self.postprocessing_manager.terminate()
                self.postprocessing_manager.join(timeout=5.0)

        print("三级队列进程池已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


if __name__ == "__main__":
    # 测试三级队列进程池
    print("测试三级队列进程池...")

    with SimpleProcessPool(
        gpu_ids=[0],
        workers_per_gpu=1,
        max_gpu_queue_size=100,
        preprocessing_workers=2,
        postprocessing_workers=2
    ) as pool:
        # 提交一些测试任务
        def test_func(x):
            time.sleep(1)
            return f"处理结果: {x}"

        for i in range(5):
            pool.submit_task(test_func, f"test_task_{i}")

        # 等待结果
        results_received = 0
        start_time = time.time()

        while results_received < 5 and time.time() - start_time < 60:
            result = pool.get_result(timeout=5.0)
            if result:
                task_id, status, result_data = result
                print(f"收到结果: 任务 {task_id}, 状态: {status}, 数据: {result_data}")
                results_received += 1

            # 打印队列状态
            print(f"队列状态 - 预处理: {pool.get_preprocessing_queue_size()}, "
                  f"GPU: {pool.get_gpu_queue_size()}, "
                  f"后处理: {pool.get_postprocessing_queue_size()}")

        print(f"测试完成，收到 {results_received} 个结果")