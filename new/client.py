import requests
import json
import argparse
import time
from typing import Dict, Any, Optional, List


class PDFClient:
    """PDF处理客户端"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """
        初始化客户端

        Args:
            base_url: 服务器基础URL
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        发送HTTP请求

        Args:
            method: HTTP方法
            endpoint: API端点
            **kwargs: 请求参数

        Returns:
            Dict: 响应数据
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "error": True,
                "message": f"请求失败: {str(e)}",
                "url": url,
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return self._make_request("GET", "/health")

    def get_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        return self._make_request("GET", "/status")

    def scan_directory(self, pdf_dir: str) -> Dict[str, Any]:
        """
        扫描目录并添加所有PDF文件到队列

        Args:
            pdf_dir: PDF文件目录路径
        """
        return self._make_request("POST", f"/scan/{pdf_dir}")

    def add_pdf_file(self, pdf_path: str) -> Dict[str, Any]:
        """
        添加单个PDF文件到队列

        Args:
            pdf_path: PDF文件路径
        """
        return self._make_request("POST", "/add", params={"pdf_path": pdf_path})

    def process_all(self) -> Dict[str, Any]:
        """处理队列中的所有PDF文件"""
        return self._make_request("POST", "/process")

    def process_one(self, pdf_path: str) -> Dict[str, Any]:
        """
        处理单个PDF文件

        Args:
            pdf_path: PDF文件路径
        """
        return self._make_request("POST", "/process-one", params={"pdf_path": pdf_path})

    def get_results(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        获取处理结果

        Args:
            limit: 限制返回结果数量
            offset: 偏移量
        """
        params = {"limit": limit, "offset": offset}
        return self._make_request("GET", "/results", params=params)

    def clear_queue(self) -> Dict[str, Any]:
        """清空处理队列"""
        return self._make_request("DELETE", "/clear-queue")

    def clear_results(self) -> Dict[str, Any]:
        """清空结果历史"""
        return self._make_request("DELETE", "/clear-results")

    def save_results(self, output_file: str = "pdf_results.json") -> Dict[str, Any]:
        """
        保存处理结果到文件

        Args:
            output_file: 输出文件路径
        """
        params = {"output_file": output_file}
        return self._make_request("POST", "/save-results", params=params)

    def list_files(self, pdf_dir: str) -> Dict[str, Any]:
        """
        列出目录中的所有PDF文件

        Args:
            pdf_dir: PDF文件目录路径
        """
        return self._make_request("GET", f"/files/{pdf_dir}")

    def wait_for_completion(self, check_interval: int = 2) -> Dict[str, Any]:
        """
        等待所有任务处理完成

        Args:
            check_interval: 检查间隔（秒）
        """
        print("等待所有任务处理完成...")
        while True:
            status = self.get_status()
            if status.get("error"):
                print(f"获取状态失败: {status.get('message')}")
                break

            print(f"队列状态: {status.get('queue_size', 0)} 个任务待处理")
            if status.get('queue_size', 0) == 0:
                print("所有任务处理完成!")
                break

            time.sleep(check_interval)

        return status

    def print_server_info(self):
        """打印服务器信息"""
        print("=== PDF处理服务器信息 ===")

        # 健康检查
        health = self.health_check()
        if health.get("error"):
            print(f"❌ 服务器不可用: {health.get('message')}")
            return False

        print("✅ 服务器健康状态: 正常")

        # 获取状态
        status = self.get_status()
        if status.get("error"):
            print(f"❌ 获取状态失败: {status.get('message')}")
            return False

        print(f"📊 服务器状态:")
        print(f"   队列大小: {status.get('queue_size', 0)}/{status.get('max_queue_size', 0)}")
        print(f"   工作线程数: {status.get('num_workers', 0)}")
        print(f"   已处理总数: {status.get('total_processed', 0)}")
        print(f"   成功处理: {status.get('successful_processed', 0)}")
        print(f"   失败处理: {status.get('failed_processed', 0)}")

        return True

    def print_results_summary(self):
        """打印处理结果摘要"""
        results = self.get_results(limit=1000)
        if results.get("error"):
            print(f"❌ 获取结果失败: {results.get('message')}")
            return

        total = results.get("total", 0)
        result_list = results.get("results", [])

        print(f"\n=== 处理结果摘要 ===")
        print(f"总结果数: {total}")

        if total > 0:
            success_count = len([r for r in result_list if r.get("status") == "success"])
            failed_count = len([r for r in result_list if r.get("status") == "failed"])

            print(f"✅ 成功: {success_count}")
            print(f"❌ 失败: {failed_count}")

            # 显示最近的失败结果
            failed_results = [r for r in result_list if r.get("status") == "failed"]
            if failed_results:
                print(f"\n❌ 失败的文件:")
                for result in failed_results[:5]:  # 只显示前5个
                    print(f"   {result.get('pdf_name', 'Unknown')}: {result.get('error', 'Unknown error')}")

            # 显示处理时间
            successful_results = [r for r in result_list if r.get("status") == "success"]
            if successful_results:
                total_time = sum(r.get("processing_time", 0) for r in successful_results)
                avg_time = total_time / len(successful_results) if successful_results else 0
                print(f"\n⏱️  处理时间统计:")
                print(f"   总处理时间: {total_time:.2f}秒")
                print(f"   平均处理时间: {avg_time:.3f}秒/文件")


def main():
    """客户端主函数"""
    parser = argparse.ArgumentParser(description='PDF处理客户端')
    parser.add_argument('--server', default='http://127.0.0.1:8000', help='服务器地址')
    parser.add_argument('--action', choices=[
        'info', 'health', 'status', 'scan', 'add', 'process', 'process-one',
        'results', 'wait', 'clear-queue', 'clear-results', 'save', 'files'
    ], required=True, help='执行的操作')
    parser.add_argument('--pdf-dir', help='PDF文件目录')
    parser.add_argument('--pdf-file', help='PDF文件路径')
    parser.add_argument('--output', default='pdf_results.json', help='输出文件路径')
    parser.add_argument('--limit', type=int, default=20, help='结果显示限制')
    parser.add_argument('--wait-interval', type=int, default=2, help='等待检查间隔（秒）')
    parser.add_argument('--auto-wait', action='store_true', help='自动等待处理完成')

    args = parser.parse_args()

    # 创建客户端
    client = PDFClient(args.server)

    try:
        if args.action == 'info':
            client.print_server_info()

        elif args.action == 'health':
            health = client.health_check()
            if health.get("error"):
                print(f"❌ 健康检查失败: {health.get('message')}")
            else:
                print("✅ 服务器健康状态: 正常")
                print(f"服务器类型: {health.get('server_type')}")

        elif args.action == 'status':
            status = client.get_status()
            if status.get("error"):
                print(f"❌ 获取状态失败: {status.get('message')}")
            else:
                print("📊 服务器状态:")
                for key, value in status.items():
                    print(f"   {key}: {value}")

        elif args.action == 'scan':
            if not args.pdf_dir:
                print("❌ 请指定 --pdf-dir 参数")
                return
            result = client.scan_directory(args.pdf_dir)
            if result.get("error"):
                print(f"❌ 扫描失败: {result.get('message')}")
            else:
                print(f"✅ {result.get('message')}")
                print(f"📊 添加文件数: {result.get('added_count')}")
                status = result.get('queue_status', {})
                print(f"📊 队列状态: {status.get('queue_size', 0)} 个文件待处理")

        elif args.action == 'add':
            if not args.pdf_file:
                print("❌ 请指定 --pdf-file 参数")
                return
            result = client.add_pdf_file(args.pdf_file)
            if result.get("error"):
                print(f"❌ 添加文件失败: {result.get('message')}")
            else:
                print(f"✅ {result.get('message')}")

        elif args.action == 'process':
            result = client.process_all()
            if result.get("error"):
                print(f"❌ 处理失败: {result.get('message')}")
            else:
                stats = result.get("statistics", {})
                print("✅ 处理完成!")
                print(f"📊 成功: {stats.get('total_processed', 0)}")
                print(f"📊 失败: {stats.get('total_failed', 0)}")
                print(f"⏱️  总耗时: {stats.get('total_time', 0):.2f}秒")

                if args.auto_wait:
                    client.wait_for_completion(args.wait_interval)
                    client.print_results_summary()

        elif args.action == 'process-one':
            if not args.pdf_file:
                print("❌ 请指定 --pdf-file 参数")
                return
            result = client.process_one(args.pdf_file)
            if result.get("error"):
                print(f"❌ 处理失败: {result.get('message')}")
            else:
                print(f"✅ {result.get('message')}")
                result_data = result.get("result", {})
                if result_data.get("status") == "success":
                    print(f"📊 文件大小: {result_data.get('pdf_bytes_size', 0)} 字节")
                    print(f"⏱️  处理时间: {result_data.get('processing_time', 0):.3f}秒")
                else:
                    print(f"❌ 处理错误: {result_data.get('error', 'Unknown error')}")

        elif args.action == 'results':
            results = client.get_results(limit=args.limit)
            if results.get("error"):
                print(f"❌ 获取结果失败: {results.get('message')}")
            else:
                total = results.get("total", 0)
                result_list = results.get("results", [])
                print(f"📊 结果总数: {total}")
                print(f"📊 显示: {len(result_list)} 条")

                for i, result in enumerate(result_list, 1):
                    status = result.get("status", "unknown")
                    pdf_name = result.get("pdf_name", "unknown")
                    if status == "success":
                        processing_time = result.get("processing_time", 0)
                        print(f"{i:2d}. ✅ {pdf_name} ({processing_time:.3f}s)")
                    else:
                        error = result.get("error", "Unknown error")
                        print(f"{i:2d}. ❌ {pdf_name} - {error}")

        elif args.action == 'wait':
            client.wait_for_completion(args.wait_interval)
            client.print_results_summary()

        elif args.action == 'clear-queue':
            result = client.clear_queue()
            if result.get("error"):
                print(f"❌ 清空队列失败: {result.get('message')}")
            else:
                print(f"✅ {result.get('message')}")

        elif args.action == 'clear-results':
            result = client.clear_results()
            if result.get("error"):
                print(f"❌ 清空结果失败: {result.get('message')}")
            else:
                print(f"✅ {result.get('message')}")

        elif args.action == 'save':
            result = client.save_results(args.output)
            if result.get("error"):
                print(f"❌ 保存结果失败: {result.get('message')}")
            else:
                print(f"✅ 结果已保存到: {args.output}")
                print(f"📊 保存结果数: {result.get('results_count', 0)}")

        elif args.action == 'files':
            if not args.pdf_dir:
                print("❌ 请指定 --pdf-dir 参数")
                return
            result = client.list_files(args.pdf_dir)
            if result.get("error"):
                print(f"❌ 列出文件失败: {result.get('message')}")
            else:
                total_files = result.get("total_files", 0)
                files = result.get("files", [])
                print(f"📁 目录: {result.get('directory')}")
                print(f"📊 PDF文件总数: {total_files}")
                for i, file_path in enumerate(files, 1):
                    print(f"{i:3d}. {file_path}")

    except KeyboardInterrupt:
        print("\n❌ 用户中断操作")
    except Exception as e:
        print(f"❌ 操作失败: {str(e)}")


if __name__ == "__main__":
    main()