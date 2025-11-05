# MinerU API Curl 使用指南

## 概述

本文档展示如何使用 `curl` 命令直接调用 MinerU API，适用于命令行操作、脚本自动化或直接HTTP请求。

**API Base URL:** `http://localhost:8001`

## 常用操作

### 1. 健康检查

```bash
curl -X GET http://localhost:8001/health
```

**响应示例：**
```json
{
  "status": "healthy",
  "workers": 1,
  "pending_tasks": 0,
  "processing_tasks": 0,
  "completed_tasks": 6
}
```

### 2. 列出所有任务

```bash
curl -X GET http://localhost:8001/list_tasks
```

**响应示例：**
```json
{
  "tasks": [
    {
      "task_id": "471a933e-8574-4cfc-9a50-e44c6f78a563",
      "status": "completed",
      "pdf_name": "0062.pdf",
      "chunk_id": "0001"
    }
  ],
  "total_count": 1,
  "status_breakdown": {
    "pending": 0,
    "processing": 0,
    "completed": 1,
    "failed": 0
  }
}
```

### 3. 按chunk_id列出任务

```bash
curl -X GET http://localhost:8001/list_tasks_by_chunk/0001
```

**响应示例：**
```json
{
  "chunk_id": "0001",
  "tasks": [
    {
      "task_id": "471a933e-8574-4cfc-9a50-e44c6f78a563",
      "status": "completed",
      "pdf_name": "0062.pdf",
      "chunk_id": "0001"
    }
  ],
  "total_tasks": 1,
  "status_breakdown": {
    "pending": 0,
    "processing": 0,
    "completed": 1,
    "failed": 0
  }
}
```

### 4. 提交单个任务

```bash
curl -X POST http://localhost:8001/submit_task \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_name": "example.pdf",
    "pdf_data": "'"$(base64 -w 0 /path/to/example.pdf)"'",
    "chunk_id": "0001"
  }'
```

**参数说明：**
- `pdf_name`: PDF文件名
- `pdf_data`: PDF文件的base64编码内容
- `chunk_id`: 分组ID（可选）

**响应示例：**
```json
{
  "task_id": "471a933e-8574-4cfc-9a50-e44c6f78a563",
  "status": "pending",
  "pdf_name": "example.pdf",
  "chunk_id": "0001"
}
```

### 5. 获取任务状态

```bash
curl -X GET http://localhost:8001/get_status/{task_id}
```

**示例：**
```bash
curl -X GET http://localhost:8001/get_status/471a933e-8574-4cfc-9a50-e44c6f78a563
```

**响应示例：**
```json
{
  "task_id": "471a933e-8574-4cfc-9a50-e44c6f78a563",
  "status": "completed",
  "message": "Task completed successfully",
  "error": null,
  "result_path": "/path/to/result",
  "progress": {
    "file_size": 2702012
  }
}
```

### 6. 下载单个任务结果

```bash
curl -X GET http://localhost:8001/download_result/{task_id} \
  -o result_{task_id}.zip
```

**示例：**
```bash
curl -X GET http://localhost:8001/download_result/471a933e-8574-4cfc-9a50-e44c6f78a563 \
  -o result_471a933e-8574-4cfc-9a50-e44c6f78a563.zip
```

### 7. 下载chunk所有结果

```bash
curl -X GET http://localhost:8001/download_chunk_results/{chunk_id} \
  -o chunk_{chunk_id}_results.zip
```

**示例：**
```bash
curl -X GET http://localhost:8001/download_chunk_results/0001 \
  -o chunk_0001_results.zip
```

## 高级用法

### 批量提交脚本示例

```bash
#!/bin/bash
CHUNK_ID="0001"
INPUT_DIR="/path/to/pdf/directory"

for pdf_file in "$INPUT_DIR"/*.pdf; do
  echo "Submitting: $pdf_file"

  # 获取文件名（不包含路径）
  pdf_name=$(basename "$pdf_file")

  # 转换为base64并提交
  response=$(curl -s -X POST http://localhost:8001/submit_task \
    -H "Content-Type: application/json" \
    -d "{
      \"pdf_name\": \"$pdf_name\",
      \"pdf_data\": \"$(base64 -w 0 "$pdf_file")\",
      \"chunk_id\": \"$CHUNK_ID\"
    }")

  # 提取task_id
  task_id=$(echo "$response" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
  echo "Task ID: $task_id"
done
```

### 监控任务进度脚本

```bash
#!/bin/bash
TASK_IDS=("task-id-1" "task-id-2" "task-id-3")

for task_id in "${TASK_IDS[@]}"; do
  while true; do
    status=$(curl -s http://localhost:8001/get_status/$task_id | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

    if [ "$status" == "completed" ]; then
      echo "Task $task_id completed!"
      break
    elif [ "$status" == "failed" ]; then
      echo "Task $task_id failed!"
      break
    else
      echo "Task $task_id is $status, waiting..."
      sleep 5
    fi
  done
done
```

### 下载chunk结果脚本

```bash
#!/bin/bash
CHUNK_ID="0001"
OUTPUT_DIR="chunk_$CHUNK_ID"

# 下载zip文件
curl -X GET http://localhost:8001/download_chunk_results/$CHUNK_ID \
  -o chunk_${CHUNK_ID}_results.zip

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 解压到目录
unzip -o chunk_${CHUNK_ID}_results.zip -d "$OUTPUT_DIR"

echo "Results downloaded to: $OUTPUT_DIR"
```

## 完整工作流示例

```bash
# 1. 检查服务器健康状态
curl -X GET http://localhost:8001/health

# 2. 提交PDF文件
TASK_RESPONSE=$(curl -s -X POST http://localhost:8001/submit_task \
  -H "Content-Type: application/json" \
  -d "{
    \"pdf_name\": \"document.pdf\",
    \"pdf_data\": \"$(base64 -w 0 /path/to/document.pdf)\",
    \"chunk_id\": \"0001\"
  }")

# 提取task_id
TASK_ID=$(echo "$TASK_RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
echo "Task ID: $TASK_ID"

# 3. 监控任务状态
while true; do
  STATUS=$(curl -s http://localhost:8001/get_status/$TASK_ID | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
  echo "Status: $STATUS"

  if [ "$STATUS" == "completed" ] || [ "$STATUS" == "failed" ]; then
    break
  fi

  sleep 5
done

# 4. 下载结果（如果完成）
if [ "$STATUS" == "completed" ]; then
  curl -X GET http://localhost:8001/download_result/$TASK_ID \
    -o result_${TASK_ID}.zip
  echo "Result downloaded"
fi
```

## 错误处理

### 常见HTTP状态码

- **200 OK**: 请求成功
- **400 Bad Request**: 请求参数错误
- **404 Not Found**: 任务或资源不存在
- **500 Internal Server Error**: 服务器内部错误

### 错误响应示例

```json
{
  "detail": "Task not found"
}
```

### 检查错误状态

```bash
response=$(curl -s -w "\n%{http_code}" -X GET http://localhost:8001/get_status/invalid_task_id)
http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | head -n -1)

if [ "$http_code" != "200" ]; then
  echo "Error: $body"
fi
```

## 注意事项

1. **Base64编码**: PDF文件需要转换为base64格式
2. **文件大小**: 注意HTTP请求的大小限制
3. **编码格式**: 使用 `-w 0` 参数确保base64输出不换行
4. **JSON格式**: 提交时确保JSON格式正确
5. **错误处理**: 总是检查HTTP响应状态码
6. **速率限制**: 根据需要添加适当的延迟

## 常用curl参数

- `-X`: 指定HTTP方法 (GET, POST, DELETE等)
- `-H`: 添加HTTP头
- `-d`: 发送POST数据
- `-o`: 保存响应到文件
- `-s`: 静默模式（不显示进度条）
- `-w "\n%{http_code}"`: 输出HTTP状态码
- `-f`: 失败时返回非零状态码
