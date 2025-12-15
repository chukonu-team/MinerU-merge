import argparse
import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

node_list = [
"10.100.1.8",
"10.100.1.39",
"10.100.1.26",
"10.100.1.35",
"10.100.1.28",
"10.100.1.33",
"10.100.1.41",
"10.100.1.42",
"10.100.1.38",
"10.100.1.17",
"10.100.1.31",
"10.100.1.18",
"10.100.1.27",
"10.100.1.29",
"10.100.1.11",
"10.100.1.9",
"10.100.1.34",
"10.100.1.32",
"10.100.1.30",
"10.100.1.43",
"10.100.1.25",
"10.100.1.36",
"10.100.1.37",
"10.100.1.44",
"10.100.1.24",
"10.100.1.16",
"10.100.1.4",
"10.100.1.10",
"10.100.1.15",
"10.100.1.5",
"10.100.1.22",
"10.100.1.23",
"10.100.1.40",
"10.100.2.3",
"10.100.2.5",
"10.100.2.2",
"10.100.2.33",
"10.100.2.6",
"10.100.2.20",
"10.100.2.14",
"10.100.2.4",
"10.100.2.8",
"10.100.2.36",
"10.100.2.17",
"10.100.2.12",
"10.100.2.37",
"10.100.2.7",
"10.100.2.10",
"10.100.2.35",
"10.100.2.13",
"10.100.2.9",
"10.100.2.38",
"10.100.2.32",
"10.100.2.18",
"10.100.2.19",
"10.100.2.15",
"10.100.2.39",
"10.100.2.40",
"10.100.2.16",
"10.100.1.7"
]

def process_node(node, script_path, input_path, output_path):
    """处理单个节点的任务"""
    # 执行远程Python脚本
    cmd = f"ssh {node} -o 'StrictHostKeyChecking no' python3 {script_path} --input {input_path} --output {output_path}"
    exec_result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if exec_result.returncode != 0:
        logger.error(f"Node {node}: ssh python failed, error: {exec_result.stdout} {exec_result.stderr}")
        return None

    # 读取输出文件
    read_json_cmd = f"ssh {node} -o 'StrictHostKeyChecking no' cat {output_path}"
    json_result = subprocess.run(read_json_cmd, shell=True, capture_output=True, text=True)

    if json_result.returncode != 0:
        logger.error(f"Node {node}: ssh cat failed, error: {json_result.stdout} {json_result.stderr}")
        return None

    try:
        json_data = json.loads(json_result.stdout)
        json_data['node'] = node  # 添加节点标识
        return json_data
    except json.JSONDecodeError as e:
        logger.error(f"Node {node}: JSON decode error: {e}")
        return None


def count_result(script_path, input_path, output_path, csv_path, upload_path, max_workers=10):
    """多线程处理所有节点"""
    result_list = []

    # 使用ThreadPoolExecutor并行处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_node = {
            executor.submit(
                process_node,
                node,
                script_path,
                input_path,
                output_path
            ): node for node in node_list
        }

        # 处理完成的任务
        for future in as_completed(future_to_node):
            node = future_to_node[future]
            try:
                result = future.result()
                if result:
                    result_list.append(result)
                    logger.info(f"Node {node}: task completed successfully")
                else:
                    logger.warning(f"Node {node}: task failed or returned no result")
            except Exception as e:
                logger.error(f"Node {node}: task generated an exception: {e}")

    # 保存结果到CSV
    if result_list:
        now = datetime.now()
        current_hour = now.strftime("%Y%m%d%H")
        item_file_path = os.path.join(csv_path, "item", f"item_{current_hour}.csv")
        df = pd.DataFrame(result_list)
        df.to_csv(item_file_path, index=False, encoding='utf-8')
        logger.info(f"Results saved to {csv_path}, total records: {len(result_list)}")
        # 上传到OSS
        upload_cmd = f"rclone copy {item_file_path} {upload_path}"
        result = subprocess.run(upload_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to upload {csv_path} to OSS: {result.stderr}")
            return False

        sum_file_path = os.path.join(csv_path,"sum",f"sum_{current_hour}.csv")
        # 直接创建一行 DataFrame
        sum_data = {
            "total_files": df["total_files"].sum(),
            "total_page_count": df["total_page_count"].sum(),
            "total_file_size": df["total_file_size"].sum(),
            "node": df["node"].count(),
            "hour": current_hour
        }
        # 创建 DataFrame（注意列表包装）
        sum_df = pd.DataFrame([sum_data])  # 用列表包裹，使其成为一行
        sum_df.to_csv(sum_file_path, index=False, encoding='utf-8')

        #汇总所有的记录
        # 读取目录下所有 CSV 文件
        sum_folder_path = os.path.join(csv_path,"sum")
        all_files = [f for f in os.listdir(sum_folder_path) if f.endswith('.csv')]

        dfs = []
        for file in all_files:
            file_path = os.path.join(sum_folder_path, file)
            df = pd.read_csv(file_path)
            dfs.append(df)

        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            all_path = os.path.join(csv_path,"all.csv")
            combined_df.to_csv(all_path, index=False, encoding='utf-8')

            all_upload_cmd = f"rclone copy {all_path} {upload_path}"
            all_result = subprocess.run(all_upload_cmd, shell=True, capture_output=True, text=True)
            if all_result.returncode != 0:
                logger.error(f"Failed to upload {sum_file_path} to OSS: {result.stderr}")
                return False

        logger.info(f"Successfully uploaded to OSS")
        return True
    else:
        logger.warning("No results to save")
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--script_path", required=True, help="远程脚本路径")
    parser.add_argument("--input_path", required=True, help="输入文件路径")
    parser.add_argument("--output_path", required=True, help="输出文件路径")
    parser.add_argument("--csv_path", required=True, help="本地CSV保存路径")
    parser.add_argument("--upload_path", required=True, help="OSS上传路径")
    parser.add_argument("--max_workers", type=int, default=10, help="最大并发线程数")
    args = parser.parse_args()

    # 执行多线程处理
    success = count_result(
        args.script_path,
        args.input_path,
        args.output_path,
        args.csv_path,
        args.upload_path,
        args.max_workers
    )

    if success:
        logger.info("All tasks completed successfully")
    else:
        logger.error("Some tasks failed")