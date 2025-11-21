#!/usr/bin/env python3
"""
比较MinerU两种后端的结果
"""
import json
from pathlib import Path

def load_content_list(file_path):
    """加载content_list.json文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_content(content_list, backend_name):
    """分析content_list的内容"""
    print(f"\n=== {backend_name} 后端分析结果 ===")

    # 统计不同类型的内容
    type_counts = {}
    for item in content_list:
        content_type = item.get('type', 'unknown')
        if content_type not in type_counts:
            type_counts[content_type] = 0
        type_counts[content_type] += 1

    print(f"内容类型统计:")
    for content_type, count in sorted(type_counts.items()):
        print(f"  {content_type}: {count} 个")

    # 统计页面
    pages = set()
    for item in content_list:
        if 'page_idx' in item:
            pages.add(item['page_idx'])
    print(f"页面数量: {len(pages)} 页 (页面 {min(pages) if pages else 0}-{max(pages) if pages else 0})")

    # 提取一些示例内容
    print(f"\n前5个内容块:")
    for i, item in enumerate(content_list[:5]):
        content_type = item.get('type', 'unknown')
        if 'text' in item:
            text = item['text'][:100] + "..." if len(item['text']) > 100 else item['text']
            print(f"  {i+1}. [{content_type}] {text}")
        else:
            print(f"  {i+1}. [{content_type}] (无文本内容)")

    return type_counts

def compare_backends():
    """比较两种后端的结果"""
    # 文件路径
    pipeline_file = Path("/home/ubuntu/MinerU/test_output/demo1/auto/demo1_content_list.json")
    vlm_file = Path("/home/ubuntu/MinerU/test_output/demo1/vlm/demo1_content_list.json")

    if not pipeline_file.exists():
        print(f"Pipeline后端结果文件不存在: {pipeline_file}")
        return

    if not vlm_file.exists():
        print(f"VLM后端结果文件不存在: {vlm_file}")
        return

    # 加载数据
    pipeline_content = load_content_list(pipeline_file)
    vlm_content = load_content_list(vlm_file)

    # 分析结果
    pipeline_counts = analyze_content(pipeline_content, "Pipeline")
    vlm_counts = analyze_content(vlm_content, "VLM (vllm-engine)")

    # 对比统计
    print(f"\n=== 对比总结 ===")
    print(f"Pipeline后端总内容块: {len(pipeline_content)}")
    print(f"VLM后端总内容块: {len(vlm_content)}")

    print(f"\n内容类型对比:")
    all_types = set(pipeline_counts.keys()) | set(vlm_counts.keys())
    for content_type in sorted(all_types):
        pipeline_count = pipeline_counts.get(content_type, 0)
        vlm_count = vlm_counts.get(content_type, 0)
        diff = vlm_count - pipeline_count
        diff_str = f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "0"
        print(f"  {content_type}: Pipeline={pipeline_count}, VLM={vlm_count} ({diff_str})")

if __name__ == "__main__":
    compare_backends()