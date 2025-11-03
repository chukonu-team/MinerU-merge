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

    def download_chunk_results(self, chunk_id: str, save_path: str) -> bool:
        """下载整个chunk的结果"""
        response = self.session.get(f"{self.base_url}/download_chunk_results/{chunk_id}")
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
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

    def list_tasks(self) -> Dict:
        """列出所有任务"""
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

def submit_batch(client: MinerUAPIClient, pdf_files: List[str], delay: float = 1.0, chunk_id: str = None) -> List[Dict]:
    """批量提交任务"""
    results = []
    for pdf_file in pdf_files:
        if not os.path.exists(pdf_file):
            print(f"文件不存在: {pdf_file}")
            continue

        print(f"提交任务: {pdf_file}")
        try:
            result = client.submit_task(pdf_file, chunk_id)
            results.append(result)
            print(f"  ✓ 任务ID: {result.get('task_id')}")
            if delay > 0:
                time.sleep(delay)
        except Exception as e:
            print(f"  ✗ 提交失败: {e}")

    return results

def monitor_tasks(client: MinerUAPIClient, task_ids: List[str], interval: int = 5, timeout: int = 1800) -> Dict:
    """监控任务进度"""
    start_time = time.time()
    completed = []
    failed = []

    print(f"监控 {len(task_ids)} 个任务...")

    while task_ids and (time.time() - start_time) < timeout:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 检查任务状态...")

        remaining_tasks = []
        for task_id in task_ids:
            try:
                status = client.get_status(task_id)
                task_status = status.get('status')

                if task_status == 'completed':
                    completed.append(task_id)
                    print(f"  ✓ {task_id}: 已完成")
                elif task_status == 'failed':
                    failed.append(task_id)
                    print(f"  ✗ {task_id}: 失败 - {status.get('error', 'Unknown error')}")
                else:
                    remaining_tasks.append(task_id)
                    print(f"  ⟳ {task_id}: {task_status}")
            except Exception as e:
                print(f"  ✗ {task_id}: 状态检查失败 - {e}")
                failed.append(task_id)

        task_ids = remaining_tasks

        if task_ids:
            print(f"等待 {interval} 秒...")
            time.sleep(interval)

    print(f"\n监控完成!")
    print(f"已完成: {len(completed)}")
    print(f"失败: {len(failed)}")
    print(f"超时/未完成: {len(task_ids)}")

    return {
        'completed': completed,
        'failed': failed,
        'timeout': task_ids
    }

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

def cleanup_tasks(client: MinerUAPIClient, older_than_hours: int = 24) -> Dict:
    """清理旧任务"""
    tasks = client.list_tasks().get('tasks', [])
    current_time = datetime.now()

    deleted = []
    failed = []

    for task in tasks:
        created_time = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
        age_hours = (current_time - created_time).total_seconds() / 3600

        if age_hours > older_than_hours:
            task_id = task['task_id']
            try:
                client.delete_task(task_id)
                deleted.append(task_id)
                print(f"删除任务: {task_id} (年龄: {age_hours:.1f}小时)")
            except Exception as e:
                failed.append({'task_id': task_id, 'reason': str(e)})
                print(f"删除失败: {task_id} - {e}")

    return {'deleted': deleted, 'failed': failed}

def generate_report(client: MinerUAPIClient, output_file: str = "api_report.json", chunk_id: str = None) -> Dict:
    """生成API使用报告"""
    if chunk_id:
        # 按chunk_id生成报告
        chunk_data = client.list_tasks_by_chunk(chunk_id)
        tasks = chunk_data.get('tasks', [])
    else:
        # 生成所有任务的报告
        tasks = client.list_tasks().get('tasks', [])

    health = client.health_check()

    # 统计数据
    total_tasks = len(tasks)
    status_counts = {}
    for task in tasks:
        status = task.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    # 时间分析
    if tasks:
        earliest = min(task['created_at'] for task in tasks)
        latest = max(task['created_at'] for task in tasks)
    else:
        earliest = latest = None

    # 文件大小统计（仅对已完成任务）
    completed_tasks = [t for t in tasks if t.get('status') == 'completed']
    total_size = 0

    # 对于已完成的任务，尝试获取更详细的信息
    detailed_tasks = []
    for task in tasks:
        task_detail = task.copy()
        if task.get('status') == 'completed':
            try:
                # 获取任务的详细状态信息
                detailed_status = client.get_status(task['task_id'])
                if detailed_status.get('progress') and detailed_status['progress'].get('file_size'):
                    total_size += detailed_status['progress']['file_size']
                    task_detail['file_size'] = detailed_status['progress']['file_size']
            except:
                pass  # 如果无法获取详细信息，继续处理其他任务
        detailed_tasks.append(task_detail)

    report = {
        'generated_at': datetime.now().isoformat(),
        'chunk_id': chunk_id,
        'api_health': health,
        'statistics': {
            'total_tasks': total_tasks,
            'status_breakdown': status_counts,
            'completed_tasks': len(completed_tasks),
            'total_output_size_bytes': total_size,
            'average_size_mb': total_size / len(completed_tasks) / (1024*1024) if completed_tasks else 0
        },
        'time_period': {
            'earliest_task': earliest,
            'latest_task': latest
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report

def generate_detailed_report(client: MinerUAPIClient, output_file: str = "detailed_report.json", chunk_id: str = None) -> Dict:
    """生成详细的任务报告，包含表格信息"""
    if chunk_id:
        # 按chunk_id生成报告
        chunk_data = client.list_tasks_by_chunk(chunk_id)
        tasks = chunk_data.get('tasks', [])
    else:
        # 生成所有任务的报告
        tasks = client.list_tasks().get('tasks', [])

    # 获取每个任务的详细信息
    detailed_tasks = []
    for task in tasks:
        task_id = task['task_id']
        try:
            # 获取详细的任务状态
            detailed_status = client.get_status(task_id)

            # 构建详细的任务信息
            detailed_task = {
                'task_id': task_id,
                'pdf_name': task.get('pdf_name', '未知文件'),
                'chunk_id': task.get('chunk_id', '无分组'),
                'status': task.get('status', 'unknown'),
                'created_at': task.get('created_at', ''),
                'updated_at': task.get('updated_at', ''),
                'message': detailed_status.get('message', ''),
                'error': detailed_status.get('error', ''),
                'file_size': None,
                'result_path': detailed_status.get('result_path', ''),
                'progress': detailed_status.get('progress', {})
            }

            # 获取文件大小信息
            if detailed_status.get('progress') and detailed_status['progress'].get('file_size'):
                detailed_task['file_size'] = detailed_status['progress']['file_size']

            detailed_tasks.append(detailed_task)
        except Exception as e:
            # 如果无法获取详细信息，使用基本任务信息
            detailed_tasks.append({
                'task_id': task_id,
                'pdf_name': task.get('pdf_name', '未知文件'),
                'chunk_id': task.get('chunk_id', '无分组'),
                'status': task.get('status', 'unknown'),
                'created_at': task.get('created_at', ''),
                'updated_at': task.get('updated_at', ''),
                'message': '无法获取详细信息',
                'error': str(e),
                'file_size': None,
                'result_path': '',
                'progress': {}
            })

    # 生成统计信息
    total_tasks = len(detailed_tasks)
    status_counts = {}
    chunk_stats = {}

    for task in detailed_tasks:
        # 状态统计
        status = task.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

        # chunk统计
        chunk = task.get('chunk_id', '无分组')
        if chunk not in chunk_stats:
            chunk_stats[chunk] = {'total': 0, 'completed': 0, 'failed': 0, 'pending': 0, 'processing': 0}
        chunk_stats[chunk]['total'] += 1
        chunk_stats[chunk][status] = chunk_stats[chunk].get(status, 0) + 1

    report = {
        'generated_at': datetime.now().isoformat(),
        'chunk_id': chunk_id,
        'summary': {
            'total_tasks': total_tasks,
            'status_breakdown': status_counts,
            'chunk_statistics': chunk_stats
        },
        'tasks': detailed_tasks
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report

def print_task_table(tasks: List[Dict]):
    """打印任务表格"""
    if not tasks:
        print("没有任务显示")
        return

    print(f"\n{'任务ID':<36} {'文件名':<30} {'Chunk ID':<20} {'状态':<12} {'文件大小':<12}")
    print("-" * 120)

    for task in tasks:
        task_id = task.get('task_id', '')[:34] + '..' if len(task.get('task_id', '')) > 36 else task.get('task_id', '')
        pdf_name = task.get('pdf_name', '')[:28] + '..' if len(task.get('pdf_name', '')) > 30 else task.get('pdf_name', '')
        chunk_id = task.get('chunk_id', '')[:18] + '..' if len(task.get('chunk_id', '')) > 20 else task.get('chunk_id', '')
        status = task.get('status', '')
        file_size = task.get('file_size', '')

        if file_size:
            # 转换为MB
            size_mb = file_size / (1024 * 1024)
            file_size_str = f"{size_mb:.1f}MB"
        else:
            file_size_str = "N/A"

        print(f"{task_id:<36} {pdf_name:<30} {chunk_id:<20} {status:<12} {file_size_str:<12}")

def generate_html_report(client: MinerUAPIClient, json_file: str, output_html: str = "report.html") -> str:
    """生成HTML可视化报告"""
    import json

    # 读取JSON报告
    with open(json_file, 'r', encoding='utf-8') as f:
        report_data = json.load(f)

    summary = report_data['summary']
    tasks = report_data['tasks']
    chunk_id = report_data.get('chunk_id', 'All')

    # 计算统计数据
    total_tasks = summary['total_tasks']
    status_breakdown = summary['status_breakdown']

    # 创建HTML内容
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MinerU 任务报告 - {chunk_id}</title>
    <style>
        /* 防止滚动条闪烁 */
        html {{
            scroll-behavior: smooth;
        }}
        /* 优化表格滚动性能 */
        #virtualScrollContainer {{
            overflow-anchor: none;
        }}
        /* 表格行优化 */
        #tableBody tr {{
            will-change: transform;
        }}
    </style>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 20px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
                .progress-container {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #45a049);
            transition: width 0.3s ease;
        }}
        .table-container {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            position: relative;
        }}
        th:hover {{
            background: #e9ecef;
        }}
        th.sortable::after {{
            content: '↕';
            position: absolute;
            right: 8px;
            opacity: 0.3;
        }}
        th.sort-asc::after {{
            content: '↑';
            opacity: 1;
        }}
        th.sort-desc::after {{
            content: '↓';
            opacity: 1;
        }}
        .status-completed {{
            color: #28a745;
            font-weight: 600;
        }}
        .status-processing {{
            color: #007bff;
            font-weight: 600;
        }}
        .status-failed {{
            color: #dc3545;
            font-weight: 600;
        }}
        .status-pending {{
            color: #6c757d;
            font-weight: 600;
        }}
        .search-box {{
            margin-bottom: 20px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            width: 100%;
            font-size: 16px;
        }}
        .file-size {{
            color: #666;
            font-size: 0.9em;
        }}
        .chunk-id {{
            background: #e9ecef;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-family: monospace;
        }}
        .task-id {{
            font-family: monospace;
            font-size: 0.8em;
            color: #666;
        }}
        @media (max-width: 768px) {{
            .chart-container {{
                grid-template-columns: 1fr;
            }}
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .container {{
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 MinerU 任务报告</h1>
            <p>Chunk ID: <strong>{chunk_id}</strong> | 生成时间: {report_data['generated_at'][:19].replace('T', ' ')}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{total_tasks}</div>
                <div class="stat-label">总任务数</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #28a745, #20c997);">
                <div class="stat-number">{status_breakdown.get('completed', 0)}</div>
                <div class="stat-label">已完成</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #007bff, #6610f2);">
                <div class="stat-number">{status_breakdown.get('processing', 0)}</div>
                <div class="stat-label">处理中</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #dc3545, #fd7e14);">
                <div class="stat-number">{status_breakdown.get('failed', 0)}</div>
                <div class="stat-label">失败</div>
            </div>
        </div>

        <div class="progress-container">
            <h3>📈 处理进度</h3>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {(status_breakdown.get('completed', 0) + status_breakdown.get('failed', 0)) / total_tasks * 100:.1f}%"></div>
            </div>
            <p>已完成: {status_breakdown.get('completed', 0) + status_breakdown.get('failed', 0)} / {total_tasks} ({(status_breakdown.get('completed', 0) + status_breakdown.get('failed', 0)) / total_tasks * 100:.1f}%)</p>
        </div>

        
        <div class="table-container">
            <h3>📋 任务详情</h3>
            <div style="margin-bottom: 20px;">
                <input type="text" class="search-box" id="searchBox" placeholder="搜索任务ID、文件名或状态..." style="margin-bottom: 10px;">
                <div id="searchResults" style="color: #666; font-size: 14px;"></div>
            </div>
            <div id="virtualScrollContainer" style="border: 1px solid #e0e0e0; border-radius: 5px; max-height: 600px; overflow-y: auto; position: relative;">
                <table id="tasksTable" style="width: 100%; border-collapse: collapse;">
                    <thead style="position: sticky; top: 0; background: #f8f9fa; z-index: 10;">
                        <tr>
                            <th class="sortable" data-column="task_id" style="width: 180px;">任务ID</th>
                            <th class="sortable" data-column="pdf_name" style="width: 200px;">文件名</th>
                            <th class="sortable" data-column="chunk_id" style="width: 100px;">Chunk ID</th>
                            <th class="sortable" data-column="status" style="width: 80px;">状态</th>
                            <th class="sortable" data-column="file_size" style="width: 80px;">文件大小</th>
                            <th class="sortable" data-column="created_at" style="width: 150px;">创建时间</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <!-- 动态加载内容 -->
                    </tbody>
                </table>
                <div id="scrollSpacer" style="height: 0px;"></div>
            </div>
        </div>
"""

    # 添加任务行
    for task in tasks:
        status_class = f"status-{task.get('status', 'unknown')}"
        file_size = task.get('file_size', 0)
        if file_size and file_size > 0:
            size_mb = file_size / (1024 * 1024)
            size_str = f"{size_mb:.1f} MB"
        else:
            size_str = "N/A"

        created_time = task.get('created_at', '')[:19].replace('T', ' ') if task.get('created_at') else 'N/A'

        html_content += f"""
                    <tr>
                        <td class="task-id">{task.get('task_id', '')}</td>
                        <td>{task.get('pdf_name', 'N/A')}</td>
                        <td><span class="chunk-id">{task.get('chunk_id', 'N/A')}</span></td>
                        <td class="{status_class}">{task.get('status', 'N/A')}</td>
                        <td class="file-size">{size_str}</td>
                        <td>{created_time}</td>
                    </tr>
"""

    html_content += f"""
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // 任务数据
        const allTasks = {json.dumps(tasks, ensure_ascii=False)};

        // 虚拟滚动配置
        const ROW_HEIGHT = 40; // 每行高度
        const BUFFER_SIZE = 10; // 缓冲区行数
        let filteredTasks = [...allTasks];
        let sortDirection = {{}};
        let currentSort = null;
        let scrollTop = 0;
        let containerHeight = 600;

        // 防抖函数
        function debounce(func, wait) {{
            let timeout;
            return function executedFunction(...args) {{
                const later = () => {{
                    clearTimeout(timeout);
                    func(...args);
                }};
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            }};
        }}

        // 虚拟滚动渲染 - 优化版本
        function renderVirtualTable() {{
            const tbody = document.getElementById('tableBody');
            const container = document.getElementById('virtualScrollContainer');
            const spacer = document.getElementById('scrollSpacer');

            // 计算可见范围
            const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - BUFFER_SIZE);
            const visibleCount = Math.ceil(containerHeight / ROW_HEIGHT);
            const endIndex = Math.min(filteredTasks.length, startIndex + visibleCount + BUFFER_SIZE * 2);

            // 设置spacer高度
            spacer.style.height = `${{filteredTasks.length * ROW_HEIGHT}}px`;

            // 清空表格
            tbody.innerHTML = '';

            // 批量创建DOM元素
            const fragment = document.createDocumentFragment();

            for (let i = startIndex; i < endIndex; i++) {{
                const task = filteredTasks[i];
                if (!task) continue;

                const row = document.createElement('tr');
                row.style.cssText = `height: ${{ROW_HEIGHT}}px; position: absolute; top: ${{i * ROW_HEIGHT}}px; width: 100%; display: flex;`;

                const file_size = task.file_size && task.file_size > 0
                    ? `${{(task.file_size / 1024 / 1024).toFixed(1)}} MB`
                    : 'N/A';
                const created_time = task.created_at ? task.created_at.substring(0, 19).replace('T', ' ') : 'N/A';
                const status_class = `status-${{task.status || 'unknown'}}`;

                row.innerHTML = `
                    <td class="task-id" style="width: 180px; padding: 12px; border-bottom: 1px solid #e0e0e0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${{task.task_id || 'N/A'}}</td>
                    <td style="width: 200px; padding: 12px; border-bottom: 1px solid #e0e0e0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${{task.pdf_name || 'N/A'}}</td>
                    <td style="width: 100px; padding: 12px; border-bottom: 1px solid #e0e0e0;"><span class="chunk-id">${{task.chunk_id || 'N/A'}}</span></td>
                    <td class="${{status_class}}" style="width: 80px; padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 600;">${{task.status || 'N/A'}}</td>
                    <td class="file-size" style="width: 80px; padding: 12px; border-bottom: 1px solid #e0e0e0;">${{file_size}}</td>
                    <td style="width: 150px; padding: 12px; border-bottom: 1px solid #e0e0e0;">${{created_time}}</td>
                `;

                fragment.appendChild(row);
            }}

            tbody.appendChild(fragment);
            updateSearchResults();
        }}

        // 滚动事件处理 - 节流优化
        let scrollTimer = null;
        function handleScroll() {{
            const container = document.getElementById('virtualScrollContainer');
            scrollTop = container.scrollTop;

            if (scrollTimer) {{
                cancelAnimationFrame(scrollTimer);
            }}
            scrollTimer = requestAnimationFrame(renderVirtualTable);
        }}

        // 排序功能
        function sortTasks(column) {{
            if (currentSort === column) {{
                sortDirection[column] = sortDirection[column] === 'asc' ? 'desc' : 'asc';
            }} else {{
                currentSort = column;
                sortDirection[column] = 'asc';
            }}

            // 更新排序箭头
            document.querySelectorAll('th.sortable').forEach(th => {{
                th.classList.remove('sort-asc', 'sort-desc');
            }});
            document.querySelector(`th[data-column="${{column}}"]`).classList.add(sortDirection[column] === 'asc' ? 'sort-asc' : 'sort-desc');

            // 排序数据
            filteredTasks.sort((a, b) => {{
                let aValue = a[column] || '';
                let bValue = b[column] || '';

                if (column === 'file_size') {{
                    aValue = aValue || 0;
                    bValue = bValue || 0;
                }}

                if (sortDirection[column] === 'asc') {{
                    return aValue > bValue ? 1 : -1;
                }} else {{
                    return aValue < bValue ? 1 : -1;
                }}
            }});

            scrollTop = 0;
            document.getElementById('virtualScrollContainer').scrollTop = 0;
            renderVirtualTable();
        }}

        // 搜索功能
        const debouncedSearch = debounce((searchTerm) => {{
            if (!searchTerm) {{
                filteredTasks = [...allTasks];
            }} else {{
                filteredTasks = allTasks.filter(task => {{
                    const searchStr = `${{task.task_id}} ${{task.pdf_name}} ${{task.status}} ${{task.chunk_id}}`.toLowerCase();
                    return searchStr.includes(searchTerm.toLowerCase());
                }});
            }}

            scrollTop = 0;
            document.getElementById('virtualScrollContainer').scrollTop = 0;
            renderVirtualTable();
        }}, 300);

        // 更新搜索结果信息
        function updateSearchResults() {{
            const resultInfo = document.getElementById('searchResults');
            const searchBox = document.getElementById('searchBox');
            const searchTerm = searchBox.value.trim();

            if (searchTerm) {{
                resultInfo.textContent = `找到 ${{filteredTasks.length}} 条记录 (共 ${{allTasks.length}} 条)`;
            }} else {{
                resultInfo.textContent = `共 ${{allTasks.length}} 条记录`;
            }}
        }}

        // 事件监听器 - 简化版本
        document.addEventListener('DOMContentLoaded', function() {{
            const container = document.getElementById('virtualScrollContainer');

            // 初始化容器高度
            containerHeight = Math.min(600, window.innerHeight - 400);
            container.style.maxHeight = `${{containerHeight}}px`;

            // 排序监听器
            document.querySelectorAll('th.sortable').forEach(header => {{
                header.addEventListener('click', () => {{
                    sortTasks(header.dataset.column);
                }});
            }});

            // 搜索监听器
            document.getElementById('searchBox').addEventListener('input', (e) => {{
                debouncedSearch(e.target.value);
            }});

            // 滚动监听器
            container.addEventListener('scroll', handleScroll);

            // 初始渲染
            renderVirtualTable();
        }});
    </script>
</body>
</html>
"""

    # 保存HTML文件
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return output_html

def print_progress_bar(tasks: List[Dict], chunk_id: str = None):
    """显示进度条"""
    if not tasks:
        print("没有任务")
        return

    total_tasks = len(tasks)
    completed = len([t for t in tasks if t.get('status') == 'completed'])
    failed = len([t for t in tasks if t.get('status') in ['failed', 'error']])
    processing = len([t for t in tasks if t.get('status') == 'processing'])
    pending = len([t for t in tasks if t.get('status') == 'pending'])

    # 计算进度百分比 (成功+失败+skip)/总数
    processed = completed + failed
    progress_percentage = (processed / total_tasks) * 100 if total_tasks > 0 else 0

    # 创建进度条
    bar_length = 50
    filled_length = int(bar_length * progress_percentage / 100)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)

    print(f"\n=== 进度条 ===")
    if chunk_id:
        print(f"Chunk ID: {chunk_id}")
    print(f"进度: [{bar}] {progress_percentage:.1f}%")
    print(f"已处理: {processed}/{total_tasks} (成功: {completed}, 失败: {failed})")
    print(f"进行中: {processing}, 等待: {pending}")

    # 显示统计信息
    print(f"\n=== 统计信息 ===")
    print(f"任务总数: {total_tasks}")
    print(f"✓ 成功: {completed} ({completed/total_tasks*100:.1f}%)")
    print(f"✗ 失败: {failed} ({failed/total_tasks*100:.1f}%)")
    if processing > 0:
        print(f"⟳ 处理中: {processing} ({processing/total_tasks*100:.1f}%)")
    if pending > 0:
        print(f"⏳ 等待: {pending} ({pending/total_tasks*100:.1f}%)")

def main():
    parser = argparse.ArgumentParser(description='MinerU API 高级管理工具')
    parser.add_argument('--url', default='http://localhost:8001', help='API服务器地址')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # 服务器状态
    subparsers.add_parser('health', help='检查服务器健康状态')
    subparsers.add_parser('list', help='列出所有任务')

    # 批量提交
    batch_parser = subparsers.add_parser('batch', help='批量提交任务')
    batch_parser.add_argument('pdf_files', nargs='+', help='PDF文件路径')
    batch_parser.add_argument('--delay', type=float, default=1.0, help='提交间隔(秒)')
    batch_parser.add_argument('--chunk-id', help='chunk_id标识')

    # 批次提交目录
    batch_dir_parser = subparsers.add_parser('batch-dir', help='批量提交目录中的PDF')
    batch_dir_parser.add_argument('input_dir', help='输入目录路径')
    batch_dir_parser.add_argument('--chunk-id', help='chunk_id标识')

    # 按chunk查询
    chunk_list_parser = subparsers.add_parser('chunk-list', help='按chunk_id查询任务')
    chunk_list_parser.add_argument('chunk_id', help='chunk_id标识')

    # 下载chunk结果
    chunk_download_parser = subparsers.add_parser('chunk-download', help='下载chunk结果')
    chunk_download_parser.add_argument('chunk_id', help='chunk_id标识')
    chunk_download_parser.add_argument('--output', default='chunk_results.zip', help='输出文件路径')

    # 监控任务
    monitor_parser = subparsers.add_parser('monitor', help='监控任务进度')
    monitor_parser.add_argument('task_ids', nargs='*', help='任务ID列表(留空监控所有)')
    monitor_parser.add_argument('--interval', type=int, default=5, help='检查间隔(秒)')
    monitor_parser.add_argument('--timeout', type=int, default=1800, help='超时时间(秒)')

    # 下载结果
    download_parser = subparsers.add_parser('download', help='下载任务结果')
    download_parser.add_argument('task_ids', nargs='*', help='任务ID列表(留空下载所有完成的)')
    download_parser.add_argument('--output-dir', default='downloads', help='输出目录')

    # 清理任务
    cleanup_parser = subparsers.add_parser('cleanup', help='清理旧任务')
    cleanup_parser.add_argument('--older-than', type=int, default=24, help='清理多少小时前的任务')

    # 生成报告
    report_parser = subparsers.add_parser('report', help='生成使用报告')
    report_parser.add_argument('--output', default='api_report.json', help='报告文件路径')
    report_parser.add_argument('--output-dir', default='.', help='输出目录路径')
    report_parser.add_argument('--chunk-id', help='指定chunk_id生成报告')

    # 生成详细报告
    detailed_report_parser = subparsers.add_parser('detailed-report', help='生成详细任务报告')
    detailed_report_parser.add_argument('--output', default='detailed_report.json', help='报告文件路径')
    detailed_report_parser.add_argument('--output-dir', default='.', help='输出目录路径')
    detailed_report_parser.add_argument('--chunk-id', help='指定chunk_id生成报告')
    detailed_report_parser.add_argument('--show-table', action='store_true', help='显示任务表格')
    detailed_report_parser.add_argument('--html', action='store_true', help='生成HTML可视化报告')

    # 查看进度
    progress_parser = subparsers.add_parser('progress', help='查看任务处理进度')
    progress_parser.add_argument('--chunk-id', help='指定chunk_id查看进度')

    # 生成HTML可视化报告
    html_parser = subparsers.add_parser('html-report', help='生成HTML可视化报告')
    html_parser.add_argument('json_file', help='JSON报告文件路径')
    html_parser.add_argument('--output', default='report.html', help='HTML输出文件路径')

    args = parser.parse_args()
    client = MinerUAPIClient(args.url)

    try:
        if args.command == 'health':
            health = client.health_check()
            print("服务器健康状态:")
            print(json.dumps(health, indent=2, ensure_ascii=False))

        elif args.command == 'list':
            tasks = client.list_tasks()
            print(f"任务列表 (共 {len(tasks['tasks'])} 个):")
            for task in tasks['tasks']:
                print(f"  {task['task_id']}: {task['status']}")

        elif args.command == 'batch':
            results = submit_batch(client, args.pdf_files, args.delay, args.chunk_id)
            print(f"\n提交完成: {len(results)}/{len(args.pdf_files)}")

        elif args.command == 'batch-dir':
            print(f"批量提交目录: {args.input_dir}")
            try:
                result = client.batch_submit(args.input_dir, args.chunk_id)
                print(f"✓ 批次提交成功")
                print(f"  chunk_id: {result.get('chunk_id')}")
                print(f"  任务数量: {result.get('successful_submissions', 0)}/{result.get('total_files', 0)}")
                print(f"  任务IDs: {', '.join(result.get('task_ids', [])[:3])}{'...' if len(result.get('task_ids', [])) > 3 else ''}")
            except Exception as e:
                print(f"✗ 批次提交失败: {e}")

        elif args.command == 'chunk-list':
            print(f"查询chunk: {args.chunk_id}")
            try:
                result = client.list_tasks_by_chunk(args.chunk_id)
                print(f"✓ 查询成功")
                print(f"  总任务数: {result.get('total_tasks', 0)}")
                breakdown = result.get('status_breakdown', {})
                print(f"  状态分布: 待处理({breakdown.get('pending', 0)}) | 处理中({breakdown.get('processing', 0)}) | 已完成({breakdown.get('completed', 0)}) | 失败({breakdown.get('failed', 0)})")
            except Exception as e:
                print(f"✗ 查询失败: {e}")

        elif args.command == 'chunk-download':
            print(f"下载chunk结果: {args.chunk_id}")
            try:
                if client.download_chunk_results(args.chunk_id, args.output):
                    file_size = os.path.getsize(args.output)
                    print(f"✓ 下载成功: {args.output}")
                    print(f"  文件大小: {file_size} bytes")
                else:
                    print("✗ 下载失败")
            except Exception as e:
                print(f"✗ 下载失败: {e}")

        elif args.command == 'monitor':
            if not args.task_ids:
                # 获取所有任务ID
                tasks = client.list_tasks().get('tasks', [])
                args.task_ids = [t['task_id'] for t in tasks]

            if not args.task_ids:
                print("没有找到任务")
                return

            results = monitor_tasks(client, args.task_ids, args.interval, args.timeout)

        elif args.command == 'download':
            if not args.task_ids:
                # 获取所有已完成任务的ID
                tasks = client.list_tasks().get('tasks', [])
                args.task_ids = [t['task_id'] for t in tasks if t.get('status') == 'completed']

            if not args.task_ids:
                print("没有找到可下载的任务")
                return

            results = download_results(client, args.task_ids, args.output_dir)
            print(f"\n下载完成: {len(results['success'])}/{len(args.task_ids)}")

        elif args.command == 'cleanup':
            results = cleanup_tasks(client, args.older_than)
            print(f"\n清理完成: 删除 {len(results['deleted'])} 个任务")
            if results['failed']:
                print(f"失败 {len(results['failed'])} 个任务")

        elif args.command == 'report':
            # 构建完整的输出路径
            output_dir = getattr(args, 'output_dir', '.')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, args.output)

            report = generate_report(client, output_path, getattr(args, 'chunk_id', None))
            print(f"报告已生成: {output_path}")
            if getattr(args, 'chunk_id', None):
                print(f"Chunk ID: {args.chunk_id}")
            print(json.dumps(report, indent=2, ensure_ascii=False))

        elif args.command == 'detailed-report':
            chunk_id = getattr(args, 'chunk_id', None)

            # 构建完整的输出路径
            output_dir = getattr(args, 'output_dir', '.')
            os.makedirs(output_dir, exist_ok=True)
            json_path = os.path.join(output_dir, args.output)

            report = generate_detailed_report(client, json_path, chunk_id)
            print(f"详细报告已生成: {json_path}")

            # 显示进度条
            print_progress_bar(report['tasks'], chunk_id)

            # 生成HTML可视化报告
            if getattr(args, 'html', False):
                html_file = args.output.replace('.json', '.html') if args.output.endswith('.json') else 'report.html'
                html_path = os.path.join(output_dir, html_file)
                html_full_path = generate_html_report(client, json_path, html_path)
                print(f"HTML可视化报告已生成: {html_full_path}")
                print(f"请在浏览器中打开: file://{os.path.abspath(html_full_path)}")
            else:
                # 只在没有生成HTML时显示命令行表格
                if getattr(args, 'show_table', False):
                    print_task_table(report['tasks'])

        elif args.command == 'progress':
            chunk_id = getattr(args, 'chunk_id', None)
            if chunk_id:
                # 获取指定chunk的任务
                chunk_data = client.list_tasks_by_chunk(chunk_id)
                tasks = chunk_data.get('tasks', [])
            else:
                # 获取所有任务
                tasks_data = client.list_tasks()
                tasks = tasks_data.get('tasks', [])

            # 获取详细任务信息
            detailed_tasks = []
            for task in tasks:
                task_id = task['task_id']
                try:
                    detailed_status = client.get_status(task_id)
                    detailed_task = {
                        'task_id': task_id,
                        'pdf_name': task.get('pdf_name', '未知文件'),
                        'chunk_id': task.get('chunk_id', '无分组'),
                        'status': task.get('status', 'unknown'),
                        'created_at': task.get('created_at', ''),
                        'updated_at': task.get('updated_at', ''),
                        'file_size': None
                    }

                    # 获取文件大小信息
                    if detailed_status.get('progress') and detailed_status['progress'].get('file_size'):
                        detailed_task['file_size'] = detailed_status['progress']['file_size']

                    detailed_tasks.append(detailed_task)
                except:
                    # 如果无法获取详细信息，使用基本任务信息
                    detailed_tasks.append({
                        'task_id': task_id,
                        'pdf_name': task.get('pdf_name', '未知文件'),
                        'chunk_id': task.get('chunk_id', '无分组'),
                        'status': task.get('status', 'unknown'),
                        'created_at': task.get('created_at', ''),
                        'updated_at': task.get('updated_at', ''),
                        'file_size': None
                    })

            # 显示进度条
            print_progress_bar(detailed_tasks, chunk_id)

        elif args.command == 'html-report':
            # 检查JSON文件是否存在
            if not os.path.exists(args.json_file):
                print(f"错误: JSON文件不存在: {args.json_file}")
                sys.exit(1)

            # 生成HTML可视化报告
            html_path = generate_html_report(client, args.json_file, args.output)
            print(f"HTML可视化报告已生成: {html_path}")
            print(f"请在浏览器中打开: file://{os.path.abspath(html_path)}")

    except requests.exceptions.ConnectionError:
        print(f"错误: 无法连接到API服务器 {args.url}")
        print("请确保服务器正在运行")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()