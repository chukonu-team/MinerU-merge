#!/usr/bin/env python3
"""
MinerU API 高级管理工具
提供更复杂的API操作和批量处理功能
"""

import argparse
import json
import time
import os
import sys
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

class MinerUAPIClient:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = requests.Session()

    def submit_task(self, pdf_path: str, chunk_id: str = None) -> Dict:
        """提交PDF处理任务"""
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            data = {}
            if chunk_id:
                data['chunk_id'] = chunk_id
            response = self.session.post(f"{self.base_url}/submit_task", files=files, data=data)
        response.raise_for_status()
        return response.json()

    def batch_submit(self, input_dir: str, chunk_id: str = None) -> Dict:
        """批次提交PDF处理任务"""
        data = {
            "input_dir": input_dir
        }
        if chunk_id:
            data["chunk_id"] = chunk_id

        response = self.session.post(f"{self.base_url}/batch_submit", json=data)
        response.raise_for_status()
        return response.json()

    def list_tasks_by_chunk(self, chunk_id: str) -> Dict:
        """按chunk_id列出任务"""
        response = self.session.get(f"{self.base_url}/list_tasks_by_chunk/{chunk_id}")
        response.raise_for_status()
        return response.json()

    def download_chunk_results(self, chunk_id: str, output_dir: str) -> bool:
        """下载整个chunk的结果并解压到目录"""
        response = self.session.get(f"{self.base_url}/download_chunk_results/{chunk_id}")
        if response.status_code == 200:
            # 先保存为临时zip文件
            import zipfile
            import tempfile
            import shutil

            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            # 保存临时zip文件
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                temp_zip_path = temp_zip.name
                temp_zip.write(response.content)

            # 解压到输出目录
            try:
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                return True
            finally:
                # 清理临时文件
                if os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)
        return False

    def get_status(self, task_id: str) -> Dict:
        """获取任务状态"""
        response = self.session.get(f"{self.base_url}/get_status/{task_id}")
        response.raise_for_status()
        return response.json()

    def download_result(self, task_id: str, save_path: str) -> bool:
        """下载处理结果"""
        response = self.session.get(f"{self.base_url}/download_result/{task_id}")
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        return False

    def list_tasks(self, chunk_id: str = None) -> Dict:
        """列出任务（可选按chunk_id过滤）"""
        if chunk_id:
            response = self.session.get(f"{self.base_url}/list_tasks_by_chunk/{chunk_id}")
        else:
            response = self.session.get(f"{self.base_url}/list_tasks")
        response.raise_for_status()
        return response.json()

    def delete_task(self, task_id: str) -> Dict:
        """删除任务"""
        response = self.session.delete(f"{self.base_url}/delete_task/{task_id}")
        response.raise_for_status()
        return response.json()

    def health_check(self) -> Dict:
        """健康检查"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

def download_results(client: MinerUAPIClient, task_ids: List[str], output_dir: str = "downloads") -> Dict:
    """批量下载结果"""
    results = {'success': [], 'failed': []}

    os.makedirs(output_dir, exist_ok=True)

    for task_id in task_ids:
        output_path = os.path.join(output_dir, f"result_{task_id}.zip")
        print(f"下载 {task_id} 到 {output_path}")

        try:
            if client.download_result(task_id, output_path):
                file_size = os.path.getsize(output_path)
                results['success'].append({
                    'task_id': task_id,
                    'path': output_path,
                    'size': file_size
                })
                print(f"  ✓ 成功 ({file_size} bytes)")
            else:
                results['failed'].append({'task_id': task_id, 'reason': 'Download failed'})
                print(f"  ✗ 下载失败")
        except Exception as e:
            results['failed'].append({'task_id': task_id, 'reason': str(e)})
            print(f"  ✗ 下载出错: {e}")

    return results
def main():
    parser = argparse.ArgumentParser(description='MinerU API 高级管理工具')
    parser.add_argument('--url', default='http://localhost:8001', help='API服务器地址')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # 服务器状态
    subparsers.add_parser('health', help='检查服务器健康状态')

    # 任务列表
    list_parser = subparsers.add_parser('list', help='列出任务（可选按chunk_id过滤）')
    list_parser.add_argument('--chunk-id', help='指定chunk_id过滤任务')

    # 批次提交目录
    batch_dir_parser = subparsers.add_parser('batch-dir', help='批量提交目录中的PDF')
    batch_dir_parser.add_argument('input_dir', help='输入目录路径')
    batch_dir_parser.add_argument('--chunk-id', help='chunk_id标识')

    # 同步批量处理目录（提交并等待完成）
    batch_process_parser = subparsers.add_parser('batch-process', help='同步批量处理目录中的PDF（提交并等待完成）')
    batch_process_parser.add_argument('input_dir', help='输入目录路径')
    batch_process_parser.add_argument('output_dir', help='输出目录路径')
    batch_process_parser.add_argument('--chunk-id', help='chunk_id标识')
    batch_process_parser.add_argument('--interval', type=int, default=5, help='检查间隔(秒)')
    batch_process_parser.add_argument('--timeout', type=int, default=1800, help='超时时间(秒)')

    # 下载任务结果
    task_download_parser = subparsers.add_parser('task-download', help='下载指定任务结果')
    task_download_parser.add_argument('task_ids', nargs='+', help='任务ID列表')
    task_download_parser.add_argument('output_dir', help='输出目录路径')

    # 下载chunk结果
    chunk_download_parser = subparsers.add_parser('chunk-download', help='下载整个chunk结果到目录')
    chunk_download_parser.add_argument('chunk_id', help='chunk_id标识')
    chunk_download_parser.add_argument('output_dir', help='输出目录路径')

    args = parser.parse_args()
    client = MinerUAPIClient(args.url)

    try:
        if args.command == 'health':
            health = client.health_check()
            print("服务器健康状态:")
            print(json.dumps(health, indent=2, ensure_ascii=False))

        elif args.command == 'list':
            # 任务列表
            chunk_id = getattr(args, 'chunk_id', None)
            if chunk_id:
                print(f"查询 chunk_id: {chunk_id}")
            print("=" * 80)

            try:
                result = client.list_tasks(chunk_id)
                tasks = result.get('tasks', [])

                # 计算统计信息
                total = len(tasks)
                pending = len([t for t in tasks if t.get('status') == 'pending'])
                processing = len([t for t in tasks if t.get('status') == 'processing'])
                completed = len([t for t in tasks if t.get('status') == 'completed'])
                failed = len([t for t in tasks if t.get('status') == 'failed'])

                # 显示统计信息
                print(f"\n📊 任务统计 (共 {total} 个)")
                print(f"  总数:     {total}")
                print(f"  等待:     {pending}")
                print(f"  处理中:   {processing}")
                print(f"  已完成:   {completed}")
                print(f"  失败:     {failed}")

                # 计算进度
                if total > 0:
                    progress = (completed + failed) / total * 100
                    print(f"\n📈 处理进度: {progress:.1f}%")

                    # 创建进度条
                    bar_length = 50
                    filled = int(bar_length * progress / 100)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    print(f"  [{bar}]")

                print("\n" + "=" * 100)
                print(f"{'任务ID':<40} {'文件名':<30} {'Chunk ID':<20} {'状态':<15}")
                print("-" * 100)

                # 显示任务列表
                if tasks:
                    for task in tasks:
                        task_id = task.get('task_id', '')
                        task_id_short = task_id[:37] + '...' if len(task_id) > 40 else task_id
                        pdf_name = task.get('pdf_name', '未知文件')
                        pdf_name_short = pdf_name[:27] + '...' if len(pdf_name) > 30 else pdf_name
                        chunk_id = task.get('chunk_id', '') or '-'
                        chunk_id_short = chunk_id[:17] + '...' if len(chunk_id) > 20 else chunk_id
                        status = task.get('status', 'unknown')

                        # 状态颜色标记
                        status_icons = {
                            'pending': '⏳',
                            'processing': '⟳',
                            'completed': '✅',
                            'failed': '❌'
                        }
                        icon = status_icons.get(status, '❓')

                        print(f"{task_id_short:<40} {pdf_name_short:<30} {chunk_id_short:<20} {icon} {status:<12}")

                else:
                    print("(暂无任务)")

                print("=" * 80)

            except Exception as e:
                print(f"✗ 获取任务列表失败: {e}")

        elif args.command == 'batch-dir':
            print(f"批量提交目录: {args.input_dir}")
            print(f"Chunk ID: {args.chunk_id}")
            print("-" * 60)

            # 检查目录是否存在
            if not os.path.exists(args.input_dir):
                print(f"✗ 目录不存在: {args.input_dir}")
                sys.exit(1)

            if not os.path.isdir(args.input_dir):
                print(f"✗ 路径不是目录: {args.input_dir}")
                sys.exit(1)

            # 查找所有PDF文件
            pdf_files = []
            for ext in ['*.pdf', '*.PDF']:
                pdf_files.extend(Path(args.input_dir).glob(ext))

            if not pdf_files:
                print(f"✗ 目录中没有找到PDF文件: {args.input_dir}")
                sys.exit(1)

            print(f"找到 {len(pdf_files)} 个PDF文件")
            print(f"开始批量上传...")
            print("-" * 60)

            # 逐个上传文件
            successful = 0
            failed = 0
            task_ids = []
            errors = []

            for i, pdf_file in enumerate(pdf_files, 1):
                print(f"[{i}/{len(pdf_files)}] 上传: {pdf_file.name}")
                try:
                    result = client.submit_task(str(pdf_file), args.chunk_id)
                    task_id = result.get('task_id')
                    task_ids.append(task_id)
                    successful += 1
                    print(f"  ✓ 成功 - 任务ID: {task_id}")
                except Exception as e:
                    failed += 1
                    error_msg = str(e)
                    errors.append((pdf_file.name, error_msg))
                    print(f"  ✗ 失败: {error_msg}")

            print("-" * 60)
            print(f"批量上传完成!")
            print(f"  成功: {successful}/{len(pdf_files)}")
            print(f"  失败: {failed}/{len(pdf_files)}")

            if errors:
                print("\n失败的文件:")
                for filename, error in errors:
                    print(f"  - {filename}: {error}")

            if task_ids:
                print(f"\n✓ 批次提交成功")
                print(f"  Chunk ID: {args.chunk_id}")
                print(f"  任务数量: {successful}/{len(pdf_files)}")
                if len(task_ids) <= 5:
                    print(f"  任务IDs: {', '.join(task_ids)}")
                else:
                    print(f"  任务IDs: {', '.join(task_ids[:3])}... (共{len(task_ids)}个)")

        elif args.command == 'batch-process':
            print(f"同步批量处理目录: {args.input_dir}")
            print(f"输出目录: {args.output_dir}")
            print(f"Chunk ID: {args.chunk_id or '自动生成'}")
            print(f"检查间隔: {args.interval}秒")
            print(f"超时时间: {args.timeout}秒")
            print("=" * 80)

            # 检查目录
            if not os.path.exists(args.input_dir):
                print(f"✗ 目录不存在: {args.input_dir}")
                sys.exit(1)

            if not os.path.isdir(args.input_dir):
                print(f"✗ 路径不是目录: {args.input_dir}")
                sys.exit(1)

            # 创建输出目录
            os.makedirs(args.output_dir, exist_ok=True)

            # 查找PDF文件
            pdf_files = []
            for ext in ['*.pdf', '*.PDF']:
                pdf_files.extend(Path(args.input_dir).glob(ext))

            if not pdf_files:
                print(f"✗ 目录中没有找到PDF文件: {args.input_dir}")
                sys.exit(1)

            print(f"\n📁 找到 {len(pdf_files)} 个PDF文件")
            print(f"\n🚀 开始上传文件...")
            print("-" * 80)

            # 上传所有文件
            task_ids = []
            for i, pdf_file in enumerate(pdf_files, 1):
                print(f"[{i}/{len(pdf_files)}] 上传: {pdf_file.name}")
                try:
                    result = client.submit_task(str(pdf_file), args.chunk_id)
                    task_id = result.get('task_id')
                    task_ids.append(task_id)
                    print(f"  ✓ 任务ID: {task_id}")
                except Exception as e:
                    print(f"  ✗ 上传失败: {e}")
                    sys.exit(1)

            if not task_ids:
                print("\n✗ 没有成功上传的文件")
                sys.exit(1)

            print("-" * 80)
            print(f"\n✅ 上传完成! 共 {len(task_ids)} 个任务")
            print(f"\n⏳ 开始监控任务进度...")
            print("=" * 80)

            # 监控任务
            start_time = time.time()
            completed_tasks = []
            failed_tasks = []
            pending_tasks = list(task_ids)

            while pending_tasks:
                elapsed = int(time.time() - start_time)
                print(f"\n[{elapsed // 60:02d}:{elapsed % 60:02d}] 检查任务状态...")
                print(f"  待处理: {len(pending_tasks)}, 已完成: {len(completed_tasks)}, 失败: {len(failed_tasks)}")

                remaining = []
                for task_id in pending_tasks:
                    try:
                        status = client.get_status(task_id)
                        task_status = status.get('status')

                        if task_status == 'completed':
                            completed_tasks.append(task_id)
                            print(f"  ✅ {task_id[:8]}... - 已完成")
                        elif task_status == 'failed':
                            failed_tasks.append(task_id)
                            error_msg = status.get('error', 'Unknown error')
                            print(f"  ❌ {task_id[:8]}... - 失败: {error_msg[:50]}")
                        elif task_status in ['pending', 'processing']:
                            remaining.append(task_id)
                            status_icon = '⏳' if task_status == 'pending' else '⟳'
                            print(f"  {status_icon} {task_id[:8]}... - {task_status}")
                        else:
                            remaining.append(task_id)
                            print(f"  ❓ {task_id[:8]}... - 未知状态: {task_status}")
                    except Exception as e:
                        failed_tasks.append(task_id)
                        print(f"  ❌ {task_id[:8]}... - 检查失败: {str(e)[:50]}")

                pending_tasks = remaining

                # 检查超时
                if time.time() - start_time > args.timeout:
                    print(f"\n⏰ 任务处理超时 ({args.timeout}秒)")
                    print(f"剩余未完成任务: {len(pending_tasks)}")
                    break

                # 如果还有未完成的任务，等待一段时间再检查
                if pending_tasks:
                    print(f"\n⏳ 等待 {args.interval} 秒后继续检查...")
                    time.sleep(args.interval)

            # 显示最终结果
            total_time = int(time.time() - start_time)
            print("\n" + "=" * 80)
            print("🎉 任务处理完成!")
            print(f"  总任务数: {len(task_ids)}")
            print(f"  ✅ 已完成: {len(completed_tasks)}")
            print(f"  ❌ 失败: {len(failed_tasks)}")
            print(f"  ⏱️  总耗时: {total_time // 60}:{total_time % 60:02d}")
            print("=" * 80)

            # 下载结果
            if completed_tasks:
                print(f"\n💾 开始下载结果到: {args.output_dir}")
                print("-" * 80)
                results = download_results(client, completed_tasks, args.output_dir)
                print("-" * 80)
                print(f"📦 下载完成!")
                print(f"  成功下载: {len(results['success'])}/{len(completed_tasks)}")
                if results['failed']:
                    print(f"  下载失败: {len(results['failed'])}")
                    for failure in results['failed']:
                        print(f"    - {failure['task_id'][:8]}... : {failure['reason']}")
            else:
                print(f"\n⚠️  没有完成的任务可以下载")

        elif args.command == 'task-download':
            print(f"下载任务结果")
            print(f"任务IDs: {', '.join(args.task_ids)}")
            print(f"输出目录: {args.output_dir}")
            print("-" * 60)

            results = download_results(client, args.task_ids, args.output_dir)
            print(f"\n下载完成: {len(results['success'])}/{len(args.task_ids)}")

        elif args.command == 'chunk-download':
            print(f"下载chunk结果: {args.chunk_id}")
            print(f"输出目录: {args.output_dir}")
            print("-" * 60)

            try:
                if client.download_chunk_results(args.chunk_id, args.output_dir):
                    print(f"✓ 下载成功")
                    print(f"  输出目录: {args.output_dir}")

                    # 列出下载的文件
                    print(f"\n下载的文件:")
                    for root, dirs, files in os.walk(args.output_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, args.output_dir)
                            file_size = os.path.getsize(file_path)
                            size_mb = file_size / (1024 * 1024)
                            print(f"  - {rel_path} ({size_mb:.2f} MB)")
                else:
                    print("✗ 下载失败，可能没有完成的任务或chunk_id不存在")
            except Exception as e:
                print(f"✗ 下载失败: {e}")

    except requests.exceptions.ConnectionError:
        print(f"错误: 无法连接到API服务器 {args.url}")
        print("请确保服务器正在运行")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()