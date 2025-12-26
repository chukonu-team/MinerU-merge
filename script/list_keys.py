import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_rclone_command(cmd):
    """执行rclone命令并返回输出"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip().split('\n') if result.stdout else []
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {cmd}")
        print(f"错误信息: {e.stderr}")
        return []


def get_all_subdirectories_rclone(remote, prefix):
    """
    使用rclone lsd命令获取所有子目录
    rclone lsd会列出指定路径下的所有目录
    """
    print(f"正在使用rclone获取子目录列表...")

    # 构建rclone lsd命令
    cmd = f"rclone lsd {remote}:{prefix}"
    print(f"执行命令: {cmd}")

    output_lines = run_rclone_command(cmd)

    subdirectories = set()

    # 解析rclone lsd输出，格式通常为: -1 2023-01-01 00:00:00        -1 dir_name
    for line in output_lines:
        if line.strip():
            # 提取目录名，通常是最后一列
            parts = line.strip().split()
            if parts:
                dir_name = parts[-1]
                full_path = os.path.join(prefix, dir_name).replace('\\', '/')
                subdirectories.add(full_path)
                print(f"发现子目录: {full_path}")

    # 添加根目录本身
    subdirectories.add(prefix)

    print(f"共发现 {len(subdirectories)} 个子目录")
    return list(subdirectories)


def list_keys_in_prefix_rclone(remote, prefix, results_dict, lock):
    """
    使用rclone ls命令列出指定前缀下的所有对象键
    """
    print(f"开始遍历子目录: {prefix}")

    keys_list = []

    try:
        # 构建rclone ls命令，确保获取所有文件
        cmd = f"rclone ls {remote}:{prefix}"
        output_lines = run_rclone_command(cmd)

        # 解析rclone ls输出，格式通常为: 文件大小 文件路径
        for line in output_lines:
            if line.strip():
                # 提取文件路径，通常是第二列开始的部分
                parts = line.strip().split()
                if len(parts) >= 2:
                    # 合并除了文件大小之外的所有部分作为文件路径
                    file_path = ' '.join(parts[1:])
                    keys_list.append(file_path)

        # 使用锁来安全地更新共享字典
        with lock:
            results_dict[prefix] = keys_list

        print(f"子目录 {prefix} 遍历完成，找到 {len(keys_list)} 个对象")

    except Exception as e:
        print(f"遍历子目录 {prefix} 时出错: {str(e)}")
        with lock:
            results_dict[prefix] = []


def list_all_keys_with_rclone(remote, prefix, output_file, max_workers=10):
    """
    使用rclone多线程列出所有对象键
    """
    # 步骤1: 获取所有子目录
    print("步骤1: 使用rclone获取所有子目录...")
    subdirectories = get_all_subdirectories_rclone(remote, prefix)

    # 步骤2: 多线程遍历每个子目录
    print(f"步骤2: 使用 {max_workers} 个线程并发遍历子目录...")

    results_dict = {}
    lock = threading.Lock()

    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_prefix = {
            executor.submit(
                list_keys_in_prefix_rclone,
                remote, subdir, results_dict, lock
            ): subdir for subdir in subdirectories
        }

        # 等待所有任务完成
        for future in as_completed(future_to_prefix):
            prefix_name = future_to_prefix[future]
            try:
                future.result()
            except Exception as e:
                print(f"子目录 {prefix_name} 处理时发生异常: {str(e)}")

    # 步骤3: 合并所有结果
    print("步骤3: 合并所有结果...")
    all_keys = []
    for subdir_keys in results_dict.values():
        all_keys.extend(subdir_keys)

    # 去重并排序
    all_keys = sorted(set(all_keys))

    # 写入文件
    with open(output_file, 'w') as f:
        for key in all_keys:
            f.write(f"{key}\n")

    print(f"成功列出 {len(all_keys)} 个对象Key，并保存到 {output_file}")
    return len(all_keys)


def add_prefix(input_file, prefix, output_file):
    """为文件中的每一行添加前缀"""
    url_list = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for url in f:
            url = url.strip()
            url = f'{prefix}{url}'
            url_list.append(url)

    with open(output_file, 'w', encoding='utf-8') as f:
        for url in url_list:
            f.write(url + '\n')


# 优化版本：使用rclone的更多特性
def optimized_list_all_keys_with_rclone(remote, prefix, output_file, max_workers=20):
    """
    优化版本：使用rclone的更多特性来提高性能
    """
    print("使用优化版本的rclone多线程列表...")

    # 首先检查rclone是否可用
    try:
        subprocess.run(["rclone", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("错误: rclone未安装或未在PATH中")
        return 0

    # 获取所有子目录
    subdirectories = get_all_subdirectories_rclone(remote, prefix)

    if not subdirectories:
        print("未找到任何子目录，尝试直接列出文件...")
        # 如果没有子目录，直接列出该前缀下的文件
        cmd = f"rclone ls {remote}:{prefix}"
        output_lines = run_rclone_command(cmd)

        all_keys = []
        for line in output_lines:
            if line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    file_path = ' '.join(parts[1:])
                    all_keys.append(file_path)

        # 写入文件
        with open(output_file, 'w') as f:
            for key in sorted(set(all_keys)):
                f.write(f"{key}\n")

        print(f"直接列出完成，找到 {len(all_keys)} 个对象Key")
        return len(all_keys)

    # 多线程处理子目录
    results_dict = {}
    lock = threading.Lock()

    print(f"使用 {max_workers} 个线程处理 {len(subdirectories)} 个子目录...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for subdir in subdirectories:
            future = executor.submit(
                list_keys_in_prefix_rclone, remote, subdir, results_dict, lock
            )
            futures.append(future)

        # 等待所有任务完成
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"任务执行异常: {e}")

    # 合并结果
    all_keys = []
    for keys in results_dict.values():
        all_keys.extend(keys)

    all_keys = sorted(set(all_keys))

    with open(output_file, 'w') as f:
        for key in all_keys:
            f.write(f"{key}\n")

    print(f"优化版本完成，共找到 {len(all_keys)} 个对象Key")
    return len(all_keys)


if __name__ == '__main__':
    print("开始使用rclone多线程列出对象键...")

    # 配置参数
    remote = "obs"  # rclone配置的远程名称
    prefix = "google-scholar/25Q3/google-scholar/houdu/mineru264"
    list_output_file = "/root/wangshd/batch6/result_list_key_1.txt"

    # 使用rclone多线程方式列出所有key
    count = optimized_list_all_keys_with_rclone(
        remote, prefix, list_output_file, max_workers=50
    )

    # 添加前缀生成完整URL
    output_file = "/root/wangshd/batch6/result_full_key_1.txt"
    bucket_prefix = "obs://google-scholar/"
    add_prefix(list_output_file, bucket_prefix, output_file)

    print(f"处理完成！共处理 {count} 个对象")