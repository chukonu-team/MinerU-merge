import os
import sys
from multiprocessing import Pool, cpu_count
import boto3
from botocore.config import Config


def get_s3_client(endpoint_url, access_key_id, secret_access_key, region_name):
    """创建S3客户端"""
    config = None
    s3_type = os.environ.get('S3_TYPE', 's3')
    if s3_type != 's3':
        config = Config(
            s3={"addressing_style": "virtual"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required"
        )

    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region_name,
        config=config
    )


def process_prefix(args):
    """处理单个前缀的进程函数"""
    endpoint_url, access_key_id, secret_access_key, region_name, bucket_name, prefix = args

    s3_client = get_s3_client(endpoint_url, access_key_id, secret_access_key, region_name)
    keys = []
    continuation_token = None

    try:
        while True:
            kwargs = {'Bucket': bucket_name, 'Prefix': prefix, 'MaxKeys': 10000}
            if continuation_token:
                kwargs['ContinuationToken'] = continuation_token

            response = s3_client.list_objects_v2(**kwargs)

            if 'Contents' in response:
                keys.extend([obj['Key'] for obj in response['Contents']])

            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break

        return keys
    except Exception as e:
        print(f"处理前缀 {prefix} 时出错: {e}")
        return []


def main():
    """主函数"""
    # 配置
    endpoint_url = "https://obs.cn-north-4.myhuaweicloud.com"
    access_key_id = "HPUAH2YIGS6CIVOYMTP4"
    secret_access_key = "7QYOzrsAe253N9DK391uKjhq56cbbwyK7Erq1qGS"
    region_name = "cn-north-4"
    bucket_name = "google-scholar"

    # 读取前缀列表
    prefixes_file = "/root/wangshd/batch6/prefixes.txt"
    with open(prefixes_file, 'r') as f:
        prefixes = [line.strip() for line in f if line.strip()]

    print(f"开始处理 {len(prefixes)} 个前缀，使用 {cpu_count()} 个进程...")

    # 准备任务
    tasks = []
    for prefix in prefixes:
        tasks.append((endpoint_url, access_key_id, secret_access_key,
                      region_name, bucket_name, prefix))

    # 打开输出文件，准备写入
    output_file = "/root/wangshd/batch6/keys/all_keys.txt"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    total_keys = 0

    with open(output_file, 'w') as f_out, Pool(processes=cpu_count()) as pool:
        # 使用imap_unordered获取结果
        results = pool.imap_unordered(process_prefix, tasks)

        for i, keys in enumerate(results, 1):
            # 将当前前缀的所有key写入文件
            for key in keys:
                f_out.write(f"{key}\n")

            total_keys += len(keys)
            print(f"进度: {i}/{len(prefixes)} - 已写入 {len(keys)} 个key")

    print(f"\n处理完成！总共找到并写入 {total_keys} 个key到 {output_file}")


if __name__ == '__main__':
    main()