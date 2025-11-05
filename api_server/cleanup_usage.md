# MinerU API Server 清理端点使用说明

## 功能介绍

清理端点提供了多种清理策略来管理API服务器上的历史文件，防止磁盘空间被占满。

## 端点信息

- **URL**: `POST /cleanup`
- **Content-Type**: `application/json`

## 清理策略

### 1. 按时间清理
清理指定天数之前的所有已完成和失败的任务。

```json
{
    "older_than_days": 7
}
```

### 2. 按任务状态清理
清理指定状态的任务。

```json
{
    "task_status": "completed",
    "keep_recent": 10
}
```

- `task_status`: 可选值包括 `"completed"`, `"failed"`, `"all"`
- `keep_recent`: 保留最新的N个任务（可选）

### 3. 按批次ID清理
清理指定chunk_id的所有任务。

```json
{
    "chunk_id": "chunk_20231201_143022_50"
}
```

### 4. 清理所有历史文件
清理所有历史任务（不包括正在处理的任务）。

```json
{
    "cleanup_all": true
}
```

### 5. 预览模式
在实际删除之前预览将要清理的内容。

```json
{
    "older_than_days": 7,
    "dry_run": true
}
```

## 使用示例

### 使用API管理器工具

```bash
# 预览7天前的清理任务
python3 api_manager.py cleanup --older-than-days 7 --dry-run

# 实际清理7天前的文件
python3 api_manager.py cleanup --older-than-days 7

# 清理所有失败的任务，但保留最新的10个
python3 api_manager.py cleanup --task-status failed --keep-recent 10

# 清理指定批次的所有任务
python3 api_manager.py cleanup --chunk-id "chunk_20231201_143022_50"

# 清理所有历史文件
python3 api_manager.py cleanup --cleanup-all
```

### 使用curl直接调用API

```bash
# 预览清理
curl -X POST "http://localhost:8001/cleanup" \
     -H "Content-Type: application/json" \
     -d '{
       "older_than_days": 7,
       "dry_run": true
     }'

# 实际清理
curl -X POST "http://localhost:8001/cleanup" \
     -H "Content-Type: application/json" \
     -d '{
       "older_than_days": 7
     }'

# 清理所有已完成任务，保留最新的20个
curl -X POST "http://localhost:8001/cleanup" \
     -H "Content-Type: application/json" \
     -d '{
       "task_status": "completed",
       "keep_recent": 20
     }'
```

## 返回格式

```json
{
    "message": "清理完成：删除了 15 个任务，释放了 1024.50 MB 空间",
    "files_deleted": 30,
    "space_freed_mb": 1024.50,
    "tasks_deleted": 15,
    "details": {
        "temp_files_deleted": 15,
        "result_files_deleted": 15,
        "chunk_files_deleted": 0,
        "tasks_removed": [
            {
                "task_id": "uuid-here-1234",
                "status": "completed",
                "pdf_name": "document.pdf",
                "chunk_id": "chunk_20231201_143022_50"
            }
        ],
        "errors": []
    }
}
```

## 安全说明

1. **预览模式**: 建议先使用 `--dry-run` 预览要删除的内容
2. **正在处理的任务**: 系统会自动保护正在处理中的任务（`pending` 和 `processing` 状态）
3. **批量清理**: 按状态清理时，可以使用 `keep_recent` 保留最新的任务
4. **权限**: 确保API服务有足够的权限删除文件

## 文件类型说明

- **临时文件**: 上传的原始PDF文件，位于 `{output_dir}/temp/{task_id}/`
- **结果文件**: 处理后的ZIP文件，位于 `{output_dir}/results/{task_id}/`
- **Chunk文件**: 批次下载的压缩包，位于 `{output_dir}/chunk_{chunk_id}_results.zip`