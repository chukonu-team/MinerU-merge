import uvicorn
import argparse
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from server import PDFServer

# 创建FastAPI应用
app = FastAPI(
    title="PDF处理服务器API",
    description="用于批量处理PDF文件的RESTful API",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局PDF服务器实例
pdf_server: Optional[PDFServer] = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化PDF服务器"""
    global pdf_server
    pdf_server = PDFServer(num_workers=4, max_queue_size=1000)
    print("FastAPI服务器启动，PDF处理服务器已初始化")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    global pdf_server
    if pdf_server:
        pdf_server.shutdown()
        print("FastAPI服务器关闭，PDF处理服务器已关闭")


@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "PDF处理服务器API",
        "version": "1.0.0",
        "endpoints": [
            "/health",
            "/status",
            "/scan/{pdf_dir}",
            "/add",
            "/process",
            "/process-one",
            "/results",
            "/clear-queue",
            "/clear-results",
            "/save-results"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "server_type": "PDF Processing Server"
    }


@app.get("/status")
async def get_status():
    """获取服务器状态"""
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    return pdf_server.get_queue_status()


@app.post("/scan/{pdf_dir:path}")
async def scan_directory(pdf_dir: str):
    """
    扫描目录并添加所有PDF文件到队列

    Args:
        pdf_dir: PDF文件目录路径
    """
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    added_count = pdf_server.add_pdf_files_from_directory(pdf_dir)

    return {
        "message": f"已扫描目录: {pdf_dir}",
        "added_count": added_count,
        "queue_status": pdf_server.get_queue_status()
    }


@app.post("/add")
async def add_pdf_file(pdf_path: str):
    """
    添加单个PDF文件到队列

    Args:
        pdf_path: PDF文件路径
    """
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    success = pdf_server.add_pdf_file(pdf_path)

    if success:
        return {
            "message": f"已添加PDF文件: {pdf_path}",
            "queue_status": pdf_server.get_queue_status()
        }
    else:
        raise HTTPException(status_code=400, detail=f"添加PDF文件失败: {pdf_path}")


@app.post("/process")
async def process_all_files(background_tasks: BackgroundTasks):
    """
    处理队列中的所有PDF文件
    """
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    # 在后台运行处理任务
    def process_task():
        try:
            results = pdf_server.process_all()
            # 可以在这里添加处理完成后的回调
            return results
        except Exception as e:
            print(f"后台处理任务失败: {e}")
            return None

    # 异步启动处理任务
    # background_tasks.add_task(process_task)

    # 同步处理（更适合演示）
    try:
        results = pdf_server.process_all()
        return {
            "message": "处理完成",
            "statistics": results["statistics"],
            "queue_status": pdf_server.get_queue_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.post("/process-one")
async def process_one_file(pdf_path: str):
    """
    处理单个PDF文件

    Args:
        pdf_path: PDF文件路径
    """
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    try:
        result = pdf_server.process_one(pdf_path)
        return {
            "message": f"处理完成: {pdf_path}",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.get("/results")
async def get_results(limit: int = 100, offset: int = 0):
    """
    获取处理结果

    Args:
        limit: 限制返回结果数量 (默认: 100)
        offset: 偏移量 (默认: 0)
    """
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    return pdf_server.get_results(limit=limit, offset=offset)


@app.delete("/clear-queue")
async def clear_queue():
    """清空处理队列"""
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    result = pdf_server.clear_queue()
    return result


@app.delete("/clear-results")
async def clear_results():
    """清空结果历史"""
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    result = pdf_server.clear_results()
    return result


@app.post("/save-results")
async def save_results(output_file: str = "pdf_results.json"):
    """
    保存处理结果到文件

    Args:
        output_file: 输出文件路径 (默认: pdf_results.json)
    """
    global pdf_server
    if not pdf_server:
        raise HTTPException(status_code=500, detail="PDF服务器未初始化")

    try:
        result = pdf_server.save_results_to_file(output_file)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@app.get("/files/{pdf_dir:path}")
async def list_pdf_files(pdf_dir: str):
    """
    列出目录中的所有PDF文件

    Args:
        pdf_dir: PDF文件目录路径
    """
    import glob

    if not os.path.exists(pdf_dir):
        raise HTTPException(status_code=404, detail=f"目录不存在: {pdf_dir}")

    # 获取所有PDF文件
    pdf_pattern = os.path.join(pdf_dir, "*.pdf")
    pdf_files = glob.glob(pdf_pattern)
    pdf_pattern_recursive = os.path.join(pdf_dir, "**/*.pdf")
    pdf_files.extend(glob.glob(pdf_pattern_recursive, recursive=True))
    pdf_files = sorted(list(set(pdf_files)))

    return {
        "directory": pdf_dir,
        "total_files": len(pdf_files),
        "files": pdf_files
    }


def main():
    """主函数 - 启动FastAPI服务器"""
    parser = argparse.ArgumentParser(description='PDF处理FastAPI服务器')
    parser.add_argument('--host', default='127.0.0.1', help='服务器地址')
    parser.add_argument('--port', type=int, default=8000, help='服务器端口')
    parser.add_argument('--workers', type=int, default=4, help='PDF处理工作线程数')
    parser.add_argument('--queue-size', type=int, default=1000, help='队列大小')
    parser.add_argument('--reload', action='store_true', help='开启热重载（开发模式）')
    parser.add_argument('--debug', action='store_true', help='开启调试模式')

    args = parser.parse_args()

    print("=== PDF处理FastAPI服务器 ===")
    print(f"服务器地址: http://{args.host}:{args.port}")
    print(f"工作线程数: {args.workers}")
    print(f"队列大小: {args.queue_size}")
    print(f"API文档: http://{args.host}:{args.port}/docs")

    try:
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="debug" if args.debug else "info"
        )
    except KeyboardInterrupt:
        print("\n用户中断服务器")
    except Exception as e:
        print(f"服务器启动失败: {e}")


if __name__ == "__main__":
    main()