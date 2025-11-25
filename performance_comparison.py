#!/usr/bin/env python3
"""
性能对比脚本 - 运行批量和分步处理测试，并生成对比报告
"""
import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

def run_test(script_path, test_name):
    """运行测试脚本并返回结果"""
    print(f"\n{'='*80}")
    print(f"🚀 开始运行: {test_name}")
    print(f"{'='*80}")

    try:
        # 运行测试脚本
        result = subprocess.run([sys.executable, str(script_path)],
                              capture_output=True, text=True, cwd="/home/ubuntu/MinerU")

        if result.returncode == 0:
            print(f"✅ {test_name} 运行成功")
            print(result.stdout)
            return True, result.stdout
        else:
            print(f"❌ {test_name} 运行失败")
            print(f"错误输出: {result.stderr}")
            return False, result.stderr

    except Exception as e:
        print(f"❌ 运行 {test_name} 时发生异常: {e}")
        return False, str(e)

def parse_results(results_text):
    """解析测试结果文本，提取性能数据"""
    metrics = {}

    lines = results_text.split('\n')
    for line in lines:
        line = line.strip()

        # 提取总处理时间
        if "总处理时间:" in line:
            try:
                time_str = line.split("总处理时间:")[1].strip().split()[0]
                metrics["total_time"] = float(time_str)
            except:
                pass

        # 提取平均每PDF时间
        elif "平均每PDF:" in line:
            try:
                time_str = line.split("平均每PDF:")[1].strip().split()[0]
                metrics["avg_time_per_pdf"] = float(time_str)
            except:
                pass

        # 提取处理速度
        elif "处理速度:" in line and "页/秒" in line:
            try:
                speed_str = line.split("处理速度:")[1].strip().split()[0]
                metrics["processing_speed"] = float(speed_str)
            except:
                pass

        # 提取总生成文件数
        elif "总生成文件:" in line:
            try:
                files_str = line.split("总生成文件:")[1].strip().split()[0]
                metrics["total_files"] = int(files_str)
            except:
                pass

    return metrics

def generate_comparison_report(batch_results, step_results):
    """生成对比报告"""
    print(f"\n{'='*80}")
    print("🏆 性能对比分析报告")
    print(f"{'='*80}")
    print(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 解析结果
    batch_metrics = parse_results(batch_results)
    step_metrics = parse_results(step_results)

    print(f"\n📊 批量处理结果:")
    for key, value in batch_metrics.items():
        if key == "total_time":
            print(f"  总处理时间: {value:.2f} 秒")
        elif key == "avg_time_per_pdf":
            print(f"  平均每PDF: {value:.2f} 秒")
        elif key == "processing_speed":
            print(f"  处理速度: {value:.2f} 页/秒")
        elif key == "total_files":
            print(f"  总生成文件: {value} 个")

    print(f"\n📈 分步处理结果:")
    for key, value in step_metrics.items():
        if key == "total_time":
            print(f"  总处理时间: {value:.2f} 秒")
        elif key == "avg_time_per_pdf":
            print(f"  平均每PDF: {value:.2f} 秒")
        elif key == "processing_speed":
            print(f"  处理速度: {value:.2f} 页/秒")
        elif key == "total_files":
            print(f"  总生成文件: {value} 个")

    # 性能对比分析
    if "total_time" in batch_metrics and "total_time" in step_metrics:
        if step_metrics["total_time"] > 0:
            speedup = step_metrics["total_time"] / batch_metrics["total_time"]
            time_saved = step_metrics["total_time"] - batch_metrics["total_time"]
            efficiency_gain = (time_saved / step_metrics["total_time"]) * 100

            print(f"\n🎯 性能提升分析:")
            print(f"  加速比: {speedup:.2f}x")
            print(f"  节省时间: {time_saved:.2f} 秒")
            print(f"  效率提升: {efficiency_gain:.1f}%")

            if speedup > 1:
                print(f"  ✅ 批量处理比分步处理快 {speedup:.2f} 倍")
            else:
                print(f"  ⚠️ 批量处理性能提升有限")

    # 处理速度对比
    if "processing_speed" in batch_metrics and "processing_speed" in step_metrics:
        if step_metrics["processing_speed"] > 0:
            speed_ratio = batch_metrics["processing_speed"] / step_metrics["processing_speed"]
            print(f"\n⚡ 处理速度对比:")
            print(f"  批量处理: {batch_metrics['processing_speed']:.2f} 页/秒")
            print(f"  分步处理: {step_metrics['processing_speed']:.2f} 页/秒")
            print(f"  速度比: {speed_ratio:.2f}x")

    # 生成报告文件
    report_dir = Path("/home/ubuntu/MinerU/performance_reports")
    report_dir.mkdir(exist_ok=True)

    report_file = report_dir / f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"MinerU VLM性能对比报告\n")
        f.write(f"{'='*50}\n")
        f.write(f"报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write(f"📊 批量处理结果:\n")
        for key, value in batch_metrics.items():
            f.write(f"  {key}: {value}\n")

        f.write(f"\n📈 分步处理结果:\n")
        for key, value in step_metrics.items():
            f.write(f"  {key}: {value}\n")

        f.write(f"\n🎯 性能提升分析:\n")
        if "total_time" in batch_metrics and "total_time" in step_metrics:
            speedup = step_metrics["total_time"] / batch_metrics["total_time"]
            time_saved = step_metrics["total_time"] - batch_metrics["total_time"]
            efficiency_gain = (time_saved / step_metrics["total_time"]) * 100
            f.write(f"  加速比: {speedup:.2f}x\n")
            f.write(f"  节省时间: {time_saved:.2f} 秒\n")
            f.write(f"  效率提升: {efficiency_gain:.1f}%\n")

    print(f"\n💾 详细报告已保存到: {report_file}")

def main():
    """主函数"""
    print("🚀 MinerU VLM性能对比测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 设置脚本路径
    batch_script = Path("/home/ubuntu/MinerU/simple_batch_test.py")
    step_script = Path("/home/ubuntu/MinerU/simple_step_test.py")

    # 检查脚本是否存在
    if not batch_script.exists():
        print(f"❌ 批量处理脚本不存在: {batch_script}")
        return

    if not step_script.exists():
        print(f"❌ 分步处理脚本不存在: {step_script}")
        return

    # 运行测试
    batch_success, batch_results = run_test(batch_script, "批量处理测试")
    step_success, step_results = run_test(step_script, "分步处理测试")

    # 生成对比报告
    if batch_success and step_success:
        generate_comparison_report(batch_results, step_results)
    else:
        print(f"❌ 测试未全部成功，无法生成对比报告")
        print(f"  批量处理: {'成功' if batch_success else '失败'}")
        print(f"  分步处理: {'成功' if step_success else '失败'}")

if __name__ == "__main__":
    main()