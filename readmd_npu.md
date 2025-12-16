# npu

```sh
export MINERU_TOOLS_CONFIG_JSON="/data/MinerU/api_server/mineru.json"
```

## 下载模型

```sh
# 1. 清理所有相关文件和目录
rm -f /home/ma-user/work/MinerU/mineru.json
unset MINERU_TOOLS_CONFIG_JSON 2>/dev/null || true

# 2. 确保使用正确的模型源
export MINERU_MODEL_SOURCE=modelscope

# 3. 创建正确的配置目录
mkdir -p /home/ma-user/work/MinerU

# 4. 重新下载模型
TORCH_DEVICE_BACKEND_AUTOLOAD=0 /bin/bash -c "mineru-models-download -s modelscope -m all"
```
