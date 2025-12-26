import zipfile
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
import traceback
import csv
import tempfile
import boto3
from botocore.exceptions import ClientError

from obs import GetObjectHeader, CompletePart, CompleteMultipartUploadRequest, PutObjectHeader
from obs import ObsClient

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TARGET_OBS_AK = "******"
TARGET_OBS_SK = "******"
TARGET_OBS_URL = "https://obs.cn-north-4.myhuaweicloud.com"
TARGET_OBS_BUCKET = "google-scholar"


# 源S3的配置
S3_ACCESS_KEY = "******"  # 请替换为S3的访问密钥
S3_SECRET_KEY = "******"  # 请替换为S3的秘密密钥
S3_ENDPOINT = "http://s3.bz1stor1.paratera.com"  # 请替换为S3的端点URL
S3_REGION = "us-east-1"  # 请替换为S3的区域
S3_BUCKET = "batch2"

proxy_host = None
proxy_port = None


def init_obs_cli(func):
    def wrapper(self, *args, **kwargs):
        self.init()
        res = func(self, *args, **kwargs)
        return res

    return wrapper


class OBSCli:
    def __init__(self, bucket_name, server=None, ak=None, sk=None, proxy_host=proxy_host, proxy_port=proxy_port):
        self.bucket_name = bucket_name
        self.server = server
        if not server:
            self.server = TARGET_OBS_URL
        self.ak = ak
        self.sk = sk
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.obs_cli = None

    def init(self):
        if self.obs_cli:
            return
        ak = self.ak
        sk = self.sk
        server = self.server
        # 创建obsClient实例
        obs_cli = ObsClient(
            access_key_id=ak,
            secret_access_key=sk,
            server=server,
            proxy_host=self.proxy_host,
            proxy_port=self.proxy_port
        )
        self.obs_cli = obs_cli

    def close(self):
        if self.obs_cli:
            # 关闭obsClient
            self.obs_cli.close()

    @init_obs_cli
    def get_object(self, bucket_key, local_path):
        # 下载对象到本地
        resp = self.obs_cli.getObject(self.bucket_name, bucket_key, local_path)
        # 返回码为2xx时，接口调用成功，否则接口调用失败
        if resp.status >= 300:
            print('get object Failed')
            print('requestId:', resp.requestId)
            print('errorCode:', resp.errorCode)
            print('errorMessage:', resp.errorMessage)
            raise Exception()

    @init_obs_cli
    def get_object_meta(self, bucket_key):
        resp = self.obs_cli.getObjectMetadata(self.bucket_name, bucket_key)
        # 返回码为2xx时，接口调用成功，否则接口调用失败
        if resp.status >= 300:
            print('get object Failed')
            print('requestId:', resp.requestId)
            print('errorCode:', resp.errorCode)
            print('errorMessage:', resp.errorMessage)
        return dict(resp.body)

    @init_obs_cli
    def exist_object(self, bucket_key):
        resp = self.obs_cli.getObjectMetadata(self.bucket_name, bucket_key)
        if resp.status >= 300:
            return False
        return True

    def standard_key(self, origin_key: str):
        if origin_key.startswith("obs://"):
            return re.sub(r"obs://.*?/", '', origin_key)
        elif origin_key.startswith(self.bucket_name):
            return origin_key.replace(f"{self.bucket_name}/", "", 1)
        elif origin_key.startswith("/"):
            raise ValueError("对象名不能以 '/' 开头")

        return origin_key

    @init_obs_cli
    def upload_file(self, bucket_key, local_path):
        objectkey = self.standard_key(bucket_key)
        try:
            # 待上传文件的完整路径，如aa/bb.txt
            file_path = local_path
            # 分段上传的并发数
            taskNum = 10
            # 分段的大小，单位字节
            partSize = 50 * 1024 * 1024
            # True表示开启断点续传
            enableCheckpoint = False
            headers = PutObjectHeader()
            # 【可选】设置校验crc64
            isAttachCrc64 = True
            if self.bucket_name in ["mb-serverless-spark"]:
                isAttachCrc64 = False
            headers.isAttachCrc64 = isAttachCrc64
            # 上传文件
            resp = self.obs_cli.uploadFile(self.bucket_name, objectkey, file_path, partSize, taskNum, enableCheckpoint,
                                           isAttachCrc64=isAttachCrc64)  # 返回码为2xx时，接口调用成功，否则接口调用失败
            if resp.status < 300:
                # print('Upload File Succeeded')
                # print('requestId:', resp.requestId)
                # print('crc64:', resp.body.crc64)
                return resp.body
            else:
                print(f'Upload File Failed local_file:{local_path} target bucket_key:{bucket_key}')
                print('requestId:', resp.requestId)
                print('errorCode:', resp.errorCode)
                print('errorMessage:', resp.errorMessage)
        except Exception as e:
            print(f'Upload File Failed local_file:{local_path} target bucket_key:{bucket_key}')
            print(traceback.format_exc())
            # raise


class S3Client:
    def __init__(self, access_key, secret_key, endpoint=None, region=None):
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = endpoint
        self.region = region
        self.s3_client = None
        self._init_client()

    def _init_client(self):
        """初始化S3客户端"""
        try:
            session = boto3.Session(
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )

            if self.endpoint:
                self.s3_client = session.client('s3', endpoint_url=self.endpoint)
            else:
                self.s3_client = session.client('s3')

        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise

    def list_objects(self, bucket_name, prefix=None, max_keys=1000):
        """列出S3桶中的对象"""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=bucket_name,
                Prefix=prefix,
                PaginationConfig={'PageSize': max_keys}
            )

            objects = []
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified']
                        })

            return objects
        except ClientError as e:
            logger.error(f"Error listing objects in bucket {bucket_name}: {str(e)}")
            return []

    def download_file(self, bucket_name, key, local_path):
        """从S3下载文件到本地"""
        try:
            self.s3_client.download_file(bucket_name, key, local_path)
            return True
        except ClientError as e:
            logger.error(f"Error downloading file {key} from bucket {bucket_name}: {str(e)}")
            return False

    def object_exists(self, bucket_name, key):
        """检查S3对象是否存在"""
        try:
            self.s3_client.head_object(Bucket=bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking object {key} in bucket {bucket_name}: {str(e)}")
                return False


class S3ToOBSZipUploader:
    def __init__(self, s3_client, obs_cli, s3_bucket_name, s3_base_key, obs_base_key,
                 chunk_range=None, max_workers=5, temp_dir=None):
        self.s3_client = s3_client
        self.obs_cli = obs_cli
        self.s3_bucket_name = s3_bucket_name
        self.s3_base_key = s3_base_key.rstrip('/')
        self.obs_base_key = obs_base_key.rstrip('/')
        self.chunk_range = self._parse_chunk_range(chunk_range)
        self.success_files = set()
        self.failed_files = set()
        self.max_workers = max_workers
        self.lock = threading.Lock()  # 用于线程安全的锁

        # 设置临时目录
        if temp_dir is None:
            temp_dir = tempfile.gettempdir()
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

        # 加载已存在的成功记录
        self.success_csv_path = 'upload_success.csv'
        self.failed_csv_path = 'upload_failed.csv'
        self._load_existing_records()

    def _load_existing_records(self):
        """加载已存在的成功和失败记录"""
        # 加载成功记录
        if os.path.exists(self.success_csv_path):
            with open(self.success_csv_path, 'r', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        self.success_files.add((row[0], row[1]))
            logger.info(f"Loaded {len(self.success_files)} existing success records")

        # 加载失败记录
        if os.path.exists(self.failed_csv_path):
            with open(self.failed_csv_path, 'r', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        self.failed_files.add((row[0], row[1]))
            logger.info(f"Loaded {len(self.failed_files)} existing failed records")

    def _parse_chunk_range(self, chunk_range):
        if not chunk_range:
            return None
        try:
            start, end = chunk_range.split('-')
            return (int(start), int(end))
        except:
            logger.error(f"Invalid chunk range format: {chunk_range}. Should be like '0000-0020'")
            return None

    def _is_chunk_in_range(self, chunk_name):
        if not self.chunk_range:
            return True

        # 提取chunk名称中的数字部分 - 修改为适配6位数字格式
        # 新的chunk格式是 000001, 000002 等6位数字
        if re.match(r'^\d{6}$', chunk_name):
            chunk_num = int(chunk_name)
            return self.chunk_range[0] <= chunk_num <= self.chunk_range[1]
        else:
            # 如果不符合6位数字格式，则尝试匹配旧的chunk_xxxx格式
            match = re.search(r'chunk_(\d+)', chunk_name)
            if match:
                chunk_num = int(match.group(1))
                return self.chunk_range[0] <= chunk_num <= self.chunk_range[1]

        return False

    def _is_zip_valid(self, zip_path):
        """检查zip文件是否能够正常解压"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 测试zip文件是否完整
                bad_file = zip_ref.testzip()
                if bad_file is not None:
                    logger.warning(f"Zip file {zip_path} is corrupted. Bad file: {bad_file}")
                    return False
                return True
        except zipfile.BadZipFile:
            logger.warning(f"Zip file {zip_path} is not a valid zip file")
            return False
        except Exception as e:
            logger.warning(f"Error checking zip file {zip_path}: {str(e)}")
            return False

    def _record_success(self, chunk_name, file_name):
        """记录成功上传的文件（线程安全）"""
        with self.lock:
            # 检查是否已记录
            if (chunk_name, file_name) in self.success_files:
                return

            # 添加到内存集合
            self.success_files.add((chunk_name, file_name))

            # 立即写入CSV文件
            with open(self.success_csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([chunk_name, file_name])

    def _record_failure(self, chunk_name, file_name, reason):
        """记录失败的文件（线程安全）"""
        with self.lock:
            # 检查是否已记录
            if (chunk_name, file_name) in self.failed_files:
                return

            # 添加到内存集合
            self.failed_files.add((chunk_name, file_name))

            # 立即写入CSV文件
            with open(self.failed_csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([chunk_name, file_name, reason])

    def _download_file_with_retry(self, s3_key, local_path, max_retries=3):
        """带重试机制的从S3下载文件函数"""
        for attempt in range(max_retries):
            try:
                # 下载文件
                success = self.s3_client.download_file(self.s3_bucket_name, s3_key, local_path)
                if success:
                    logger.info(f"Successfully downloaded {s3_key} to {local_path} (attempt {attempt + 1})")
                    return True
                else:
                    logger.error(f"Download failed for {s3_key} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed to download {s3_key}: {str(e)}")

            if attempt == max_retries - 1:
                return False
            # 等待一段时间后重试
            time.sleep(2 ** attempt)  # 指数退避策略

        return False

    def _upload_file_with_retry(self, local_path, obs_key, max_retries=3):
        """带重试机制的上传到OBS函数"""
        for attempt in range(max_retries):
            try:
                # 检查文件是否已存在
                if self.obs_cli.exist_object(obs_key):
                    logger.info(f"File {obs_key} already exists in OBS, skipping upload")
                    return True

                # 上传文件
                self.obs_cli.upload_file(obs_key, local_path)
                logger.info(f"Successfully uploaded {local_path} to {obs_key} (attempt {attempt + 1})")
                return True
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for {local_path}: {str(e)}")
                if attempt == max_retries - 1:
                    return False
                # 等待一段时间后重试
                time.sleep(2 ** attempt)  # 指数退避策略

    def _get_chunk_directories(self):
        """从S3获取所有chunk目录"""
        logger.info(f"Listing chunk directories from S3 with prefix: {self.s3_base_key}/")

        # 列出S3基础路径下的所有对象
        objects = self.s3_client.list_objects(self.s3_bucket_name, prefix=self.s3_base_key + '/')

        # 提取chunk目录名 - 修改为适配新的6位数字格式
        chunk_dirs = set()
        for obj in objects:
            key = obj['key']
            # 提取chunk目录部分
            relative_path = key.replace(self.s3_base_key + '/', '', 1)
            parts = relative_path.split('/')
            if len(parts) > 0:
                # 检查是否为6位数字格式的chunk目录
                if re.match(r'^\d{6}$', parts[0]):
                    chunk_dirs.add(parts[0])
                # 同时保留对旧格式chunk_xxxx的支持
                elif parts[0].startswith('chunk_'):
                    chunk_dirs.add(parts[0])

        chunk_dirs = list(chunk_dirs)

        # 根据范围过滤chunk目录
        if self.chunk_range:
            chunk_dirs = [d for d in chunk_dirs if self._is_chunk_in_range(d)]

        logger.info(f"Found {len(chunk_dirs)} chunk directories to process")
        return chunk_dirs

    def _get_zip_files_in_chunk(self, chunk_name):
        """获取指定chunk目录下的所有zip文件"""
        chunk_prefix = f"{self.s3_base_key}/{chunk_name}/"
        objects = self.s3_client.list_objects(self.s3_bucket_name, prefix=chunk_prefix)

        zip_files = []
        for obj in objects:
            key = obj['key']
            # 提取文件名
            file_name = key.replace(chunk_prefix, '', 1)
            if file_name.endswith('.zip') and '/' not in file_name:  # 确保是直接文件，不是子目录
                zip_files.append(file_name)

        return zip_files

    def _process_single_file(self, chunk_name, zip_file):
        """处理单个文件（线程安全）"""
        # 检查是否已经在成功记录中
        if (chunk_name, zip_file) in self.success_files:
            logger.info(f"Skipping already processed file: {chunk_name}/{zip_file}")
            return

        # 创建临时文件路径
        temp_file_path = os.path.join(self.temp_dir, f"{chunk_name}_{zip_file}")

        try:
            # 构建S3 key和OBS key
            s3_key = f"{self.s3_base_key}/{chunk_name}/{zip_file}"
            obs_key = f"{self.obs_base_key}/{zip_file}"

            # 从S3下载文件到临时目录（带重试机制）
            download_success = self._download_file_with_retry(s3_key, temp_file_path)
            if not download_success:
                self._record_failure(chunk_name, zip_file, 'S3 download failed after retries')
                return

            # 检查zip文件是否有效
            if not self._is_zip_valid(temp_file_path):
                self._record_failure(chunk_name, zip_file, 'Invalid zip file')
                return

            # 上传文件到OBS（带重试机制）
            upload_success = self._upload_file_with_retry(temp_file_path, obs_key)

            # 记录结果
            if upload_success:
                self._record_success(chunk_name, zip_file)
            else:
                self._record_failure(chunk_name, zip_file, 'OBS upload failed after retries')

        except Exception as e:
            logger.error(f"Error processing file {chunk_name}/{zip_file}: {str(e)}")
            self._record_failure(chunk_name, zip_file, f'Processing error: {str(e)}')
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_file_path}: {str(e)}")

    def process_chunk_directories(self):
        """处理所有chunk目录（使用多线程）"""
        # 获取所有chunk目录
        chunk_dirs = self._get_chunk_directories()

        # 收集所有需要处理的文件
        all_files = []
        for chunk_dir in chunk_dirs:
            zip_files = self._get_zip_files_in_chunk(chunk_dir)
            for zip_file in zip_files:
                # 检查是否已经在成功记录中
                if (chunk_dir, zip_file) not in self.success_files:
                    all_files.append((chunk_dir, zip_file))

        logger.info(f"Found {len(all_files)} zip files to process (excluding already successful ones)")

        # 使用线程池处理文件
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(self._process_single_file, chunk, file): (chunk, file)
                for chunk, file in all_files
            }

            # 等待所有任务完成
            for future in as_completed(futures):
                chunk, file = futures[future]
                try:
                    future.result()  # 获取结果，如果有异常会抛出
                except Exception as e:
                    logger.error(f"Error processing file {chunk}/{file}: {str(e)}")
                    self._record_failure(chunk, file, f'Processing error: {str(e)}')

        # 输出结果摘要
        self._print_summary()

    def _print_summary(self):
        """打印处理结果摘要"""
        logger.info("=" * 50)
        logger.info("PROCESSING SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Successfully uploaded files: {len(self.success_files)}")
        logger.info(f"Failed files: {len(self.failed_files)}")


# 使用示例
if __name__ == '__main__':
    # 初始化S3客户端（数据来源）
    s3_client = S3Client(
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        endpoint=S3_ENDPOINT,
        region=S3_REGION
    )

    # 初始化OBS客户端（上传到的OBS）
    obs_cli = OBSCli(
        bucket_name=TARGET_OBS_BUCKET,
        ak=TARGET_OBS_AK,
        sk=TARGET_OBS_SK
    )

    # 创建上传器实例
    uploader = S3ToOBSZipUploader(
        s3_client=s3_client,
        obs_cli=obs_cli,
        s3_bucket_name=S3_BUCKET,  # 替换为S3桶名
        s3_base_key="batch6/vlm/output/result",  # S3的基础路径
        obs_base_key="25Q3/google-scholar/houdu/mineru264/1108/",  # OBS的基础路径
        chunk_range="000000-000000",  # 可选参数，指定chunk范围
        max_workers=50,  # 并发线程数
        temp_dir="/tmp/s3_to_obs_upload_temp"  # 临时目录，可选
    )

    # 处理所有chunk目录
    uploader.process_chunk_directories()

    # 关闭OBS客户端
    obs_cli.close()