# MinerU 多 GPU Docker 使用指南

## 构建多 GPU Docker 镜像

```bash
# 在项目根目录执行
docker build -f docker/china/Dockerfile.multi_gpu -t mineru:multi_gpu .
```

## 运行多 GPU 容器

### 基本用法（每个 GPU 1 个 worker）

```bash
# 基础运行，使用所有可用 GPU
docker run -d \
  --gpus all \
  -p 8000:8000 \
  -v /host/output:/tmp/mineru_output \
  mineru:multi_gpu

# 查看日志
docker logs -f <container_id>
```

### 高级用法（每个 GPU 多个 worker）

如果你有 2 个 GPU 并希望每个 GPU 启动 2 个工作实例（总共 4 个并行实例）：

```bash
# 创建自定义 server.py 配置
cat > /tmp/server_custom.py << 'EOF'
import os
import base64
import tempfile
from pathlib import Path
import litserve as ls
from fastapi import HTTPException
from loguru import logger

from mineru.cli.common import do_parse, read_fn
from mineru.utils.config_reader import get_device
from mineru.utils.model_utils import get_vram
from _config_endpoint import config_endpoint

class MinerUAPI(ls.LitAPI):
    def __init__(self, output_dir='/tmp'):
        super().__init__()
        self.output_dir = output_dir

    def setup(self, device):
        """Setup environment variables exactly like MinerU CLI does"""
        logger.info(f"Setting up on device: {device}")

        if os.getenv('MINERU_DEVICE_MODE', None) == None:
            os.environ['MINERU_DEVICE_MODE'] = device if device != 'auto' else get_device()

        device_mode = os.environ['MINERU_DEVICE_MODE']
        if os.getenv('MINERU_VIRTUAL_VRAM_SIZE', None) == None:
            if device_mode.startswith("cuda") or device_mode.startswith("npu"):
                vram = round(get_vram(device_mode))
                os.environ['MINERU_VIRTUAL_VRAM_SIZE'] = str(vram)
            else:
                os.environ['MINERU_VIRTUAL_VRAM_SIZE'] = '1'
        logger.info(f"MINERU_VIRTUAL_VRAM_SIZE: {os.environ['MINERU_VIRTUAL_VRAM_SIZE']}")

        if os.getenv('MINERU_MODEL_SOURCE', None) in ['huggingface', None]:
            config_endpoint()
        logger.info(f"MINERU_MODEL_SOURCE: {os.environ['MINERU_MODEL_SOURCE']}")

    def decode_request(self, request):
        """Decode file and options from request"""
        file_b64 = request['file']
        options = request.get('options', {})

        file_bytes = base64.b64decode(file_b64)
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp:
            temp.write(file_bytes)
            temp_file = Path(temp.name)
        return {
            'input_path': str(temp_file),
            'backend': options.get('backend', 'pipeline'),
            'method': options.get('method', 'auto'),
            'lang': options.get('lang', 'ch'),
            'formula_enable': options.get('formula_enable', True),
            'table_enable': options.get('table_enable', True),
            'start_page_id': options.get('start_page_id', 0),
            'end_page_id': options.get('end_page_id', None),
            'server_url': options.get('server_url', None),
        }

    def predict(self, inputs):
        """Call MinerU's do_parse - same as CLI"""
        input_path = inputs['input_path']
        output_dir = Path(self.output_dir)

        try:
            os.makedirs(output_dir, exist_ok=True)

            file_name = Path(input_path).stem
            pdf_bytes = read_fn(Path(input_path))

            do_parse(
                output_dir=str(output_dir),
                pdf_file_names=[file_name],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=[inputs['lang']],
                backend=inputs['backend'],
                parse_method=inputs['method'],
                formula_enable=inputs['formula_enable'],
                table_enable=inputs['table_enable'],
                server_url=inputs['server_url'],
                start_page_id=inputs['start_page_id'],
                end_page_id=inputs['end_page_id']
            )

            return str(output_dir/Path(input_path).stem)

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # Cleanup temp file
            if Path(input_path).exists():
                Path(input_path).unlink()

    def encode_response(self, response):
        return {'output_dir': response}

if __name__ == '__main__':
    # 自定义 workers_per_device=2（每个 GPU 2 个 worker）
    server = ls.LitServer(
        MinerUAPI(output_dir='/tmp/mineru_output'),
        accelerator='auto',
        devices='auto',
        workers_per_device=2,  # 关键参数：每个 GPU 的 worker 数量
        timeout=False
    )
    logger.info("Starting MinerU multi-GPU server on port 8000")
    server.run(port=8000, generate_client_file=False)
EOF

# 运行容器并使用自定义配置
docker run -d \
  --gpus all \
  -p 8000:8000 \
  -v /host/output:/tmp/mineru_output \
  -v /tmp/server_custom.py:/app/multi_gpu_v2/server.py \
  mineru:multi_gpu
```

### 指定特定数量的 GPU

如果你只想使用前 2 个 GPU：

```bash
docker run -d \
  --gpus '"device=0,1"' \
  -p 8000:8000 \
  -v /host/output:/tmp/mineru_output \
  mineru:multi_gpu
```

## 使用 Docker Compose（推荐）

创建 `docker-compose.multi_gpu.yml`：

```yaml
version: '3.8'

services:
  mineru-multi-gpu:
    build:
      context: ..
      dockerfile: docker/china/Dockerfile.multi_gpu
    ports:
      - "8000:8000"
    volumes:
      - ./output:/tmp/mineru_output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    environment:
      - MINERU_MODEL_SOURCE=local
      - MINERU_DEVICE_MODE=auto
    command: python3 /app/multi_gpu_v2/server.py
```

启动服务：

```bash
docker compose -f docker-compose.multi_gpu.yml up -d
```

## 参数调优建议

### workers_per_device 参数说明

- **默认值**: 1（每个 GPU 1 个 worker）
- **推荐设置**:
  - 如果 GPU 显存 >= 24GB: `workers_per_device=2`
  - 如果 GPU 显存 >= 48GB: `workers_per_device=4`
  - 如果 GPU 显存 < 12GB: `workers_per_device=1`

### 性能测试

使用 `client.py` 测试性能：

```bash
# 在容器内执行
docker exec -it <container_id> python3 /app/multi_gpu_v2/client.py
```

## 监控 GPU 使用情况

```bash
# 查看 GPU 使用率
docker exec <container_id> nvidia-smi

# 实时监控
docker exec <container_id> watch -n 1 nvidia-smi
```

## 故障排除

### 常见问题

1. **CUDA out of memory**
   - 减少 `workers_per_device` 值
   - 检查 GPU 显存大小

2. **端口被占用**
   - 修改端口映射 `-p 8001:8000`
   - 或停止占用 8000 端口的进程

3. **模型加载失败**
   - 检查 `/tmp/mineru_output` 权限
   - 确认模型下载完整

## API 使用

容器启动后，API 端点为 `http://localhost:8000/docs`

参考 `projects/multi_gpu_v2/client.py` 了解 API 调用方式。
