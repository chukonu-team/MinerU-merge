#!/bin/bash

# 使用服务器名称的列表
SERVERS=(
"qdd10nb24a01g1"
"qdd10nb24a02g1"
"qdd10nb24a03g1"
"qdd10nb24a04g1"
"qdd10nb24a05g1"
"qdd10nb24a06g1"
"qdd10nb24a07g1"
"qdd10nb24a08g1"
"qdd10nb24a09g1"
"qdd10nb24a10g1"
"qdd10nb24a11g1"
"qdd10nb24a12g1"
"qdd10nb24a13g1"
"qdd10nb24a14g1"
"qdd10nb24b01g1"
"qdd10nb24b02g1"
"qdd10nb24b03g1"
"qdd10nb24b04g1"
"qdd10nb24b05g1"
"qdd10nb24b06g1"
"qdd10nb24b07g1"
"qdd10nb24b08g1"
"qdd10nb24b09g1"
"qdd10nb24b10g1"
"qdd10nb24b11g1"
"qdd10nb24b12g1"
"qdd10nb24b13g1"
"qdd10nb24b14g1"
"qdd10nb24c01g1"
"qdd10nb24c02g1"
"qdd10nb24c03g1"
"qdd10nb24c04g1"
"qdd10nb24c05g1"
"qdd10nb24c06g1"
"qdd10nb24c07g1"
"qdd10nb24c08g1"
"qdd10nb24c09g1"
"qdd10nb24c10g1"
"qdd10nb24c11g1"
"qdd10nb24c12g1"
"qdd10nb24d01g1"
"qdd10nb24d02g1"
"qdd10nb24d03g1"
"qdd10nb24d04g1"
"qdd10nb24d05g1"
"qdd10nb24d06g1"
"qdd10nb24d07g1"
"qdd10nb24d08g1"
"qdd10nb24d09g1"
"qdd10nb24d10g1"
"qdd10nb24d11g1"
"qdd10nb24d12g1"
"qdd10nb24d13g1"
"qdd10nb24d14g1"
"qdd10nb24e01g1"
"qdd10nb24e02g1"
"qdd10nb24e03g1"
"qdd10nb24e04g1"
"qdd10nb24e05g1"
"qdd10nb24e06g1"
"qdd10nb24e07g1"
"qdd10nb24e08g1"
"qdd10nb24e09g1"
"qdd10nb24e10g1"
"qdd10nb24e11g1"
"qdd10nb24e12g1"
"qdd10nb24e13g1"
"qdd10nb24e14g1"
"qdd10nb24f01g1"
"qdd10nb24f02g1"
"qdd10nb24f03g1"
"qdd10nb24f04g1"
"qdd10nb24f05g1"
"qdd10nb24f06g1"
"qdd10nb24f07g1"
"qdd10nb24f08g1"
"qdd10nb24f09g1"
"qdd10nb24f10g1"
"qdd10nb24f11g1"
"qdd10nb24f12g1"
"qdd10nb24g01g1"
"qdd10nb24g02g1"
"qdd10nb24g03g1"
"qdd10nb24g04g1"
"qdd10nb24g05g1"
"qdd10nb24g06g1"
"qdd10nb24g07g1"
"qdd10nb24g08g1"
"qdd10nb24g09g1"
"qdd10nb24g10g1"
"qdd10nb24g11g1"
"qdd10nb24g12g1"
"qdd10nb24g13g1"
"qdd10nb24g14g1"
"qdd10nb24h01g1"
"qdd10nb24h02g1"
"qdd10nb24h03g1"
"qdd10nb24h04g1"
"qdd10nb24h05g1"
"qdd10nb24h06g1"
"qdd10nb24h07g1"
"qdd10nb24h08g1"
"qdd10nb24h09g1"
"qdd10nb24h10g1"
"qdd10nb24h11g1"
"qdd10nb24h12g1"
"qdd10nb24h13g1"
"qdd10nb24h14g1"
"qdd10nb24i01g1"
"qdd10nb24i02g1"
"qdd10nb24i03g1"
"qdd10nb24i04g1"
"qdd10nb24i05g1"
"qdd10nb24i06g1"
"qdd10nb24i07g1"
"qdd10nb24i08g1"
"qdd10nb24i09g1"
"qdd10nb24i10g1"
"qdd10nb24i11g1"
"qdd10nb24i12g1"
"qdd10nb24j01g1"
"qdd10nb24j02g1"
"qdd10nb24j03g1"
"qdd10nb24j04g1"
"qdd10nb24j05g1"
)

#!/bin/bash

# 日志文件
LOG_FILE="/root/wangshd/batch6/logs/remote_execution_$(date +%Y%m%d_%H%M%S).log"

# 远程执行命令的函数
execute_remote_command() {
    local SERVER=$1
    local COMMAND=$2
    local LOG_FILE=$3

    echo "$(date): 在服务器 $SERVER 上执行命令: $COMMAND" | tee -a "$LOG_FILE"
    
    # 使用ssh执行远程命令并捕获输出
    local OUTPUT
    OUTPUT=$(ssh -o ConnectTimeout=10 -o BatchMode=yes "$SERVER" "$COMMAND" 2>&1)
    local EXIT_CODE=$?
    
    if [ $EXIT_CODE -ne 0 ]; then
        echo "$(date): 错误: $SERVER 命令执行失败，退出码: $EXIT_CODE" | tee -a "$LOG_FILE"
        echo "$OUTPUT" | tee -a "$LOG_FILE"
        return $EXIT_CODE
    else
        echo "$(date): $SERVER 执行成功, 结果: $OUTPUT" | tee -a "$LOG_FILE"
        # 只返回纯净的命令输出，不包含任何日志信息
        echo "$OUTPUT"
        return 0
    fi
}

# 主函数
main() {
    local COMMAND="find /ssd/mnt/data/pdf -name '*.pdf' | wc -l"
    local TOTAL_COUNT=0
    local SERVER_COUNT=0
    
    # 添加并发控制，最多同时5个连接
    local MAX_CONCURRENT=5
    local PIDS=()
    
    # 创建临时文件用于存储各服务器结果
    local RESULT_FILE=$(mktemp)
    
    echo "开始在所有服务器上统计文件数量..." | tee -a "$LOG_FILE"
    echo "命令: $COMMAND" | tee -a "$LOG_FILE"
    echo "服务器列表: ${SERVERS[*]}" | tee -a "$LOG_FILE"
    
    for SERVER in "${SERVERS[@]}"; do
        (
            # 初始化结果为0（连接失败时的默认值）
            local CLEAN_RESULT="0"
            
            # 执行远程命令，如果成功则处理结果，如果失败则使用默认值0
            local RESULT
            if RESULT=$(execute_remote_command "$SERVER" "$COMMAND" "$LOG_FILE" 2>/dev/null); then
                # 只取最后一行作为命令输出
                local COMMAND_OUTPUT
                COMMAND_OUTPUT=$(echo "$RESULT" | tail -1)
                
                # 清理结果：移除所有非数字字符，只保留纯数字
                local TEMP_RESULT
                TEMP_RESULT=$(echo "$COMMAND_OUTPUT" | tr -cd '0-9')
                
                # 如果清理后不为空，则使用清理后的结果
                if [ -n "$TEMP_RESULT" ]; then
                    CLEAN_RESULT="$TEMP_RESULT"
                fi
            else
                # 连接失败，已经在execute_remote_command中记录了错误日志
                # 这里使用默认值0
                echo "$(date): 注意: 服务器 $SERVER 连接失败，使用默认值 0" | tee -a "$LOG_FILE"
            fi
            
            # 将结果写入临时文件
            echo "$SERVER:$CLEAN_RESULT" >> "$RESULT_FILE"
        ) &
        PIDS+=($!)
        
        # 控制并发数量
        while [ $(jobs -r | wc -l) -gt $MAX_CONCURRENT ]; do
            sleep 1
        done
    done
    
    # 等待所有后台任务完成
    for PID in "${PIDS[@]}"; do
        wait $PID
    done
    
    # 处理结果并求和
    echo "" | tee -a "$LOG_FILE"
    echo "各服务器文件数量统计:" | tee -a "$LOG_FILE"
    echo "======================" | tee -a "$LOG_FILE"
    
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            local SERVER_NAME="${line%:*}"
            local COUNT="${line#*:}"
            
            # 确保COUNT是数字
            if [[ "$COUNT" =~ ^[0-9]+$ ]]; then
                echo "服务器 $SERVER_NAME: $COUNT 个文件" | tee -a "$LOG_FILE"
                TOTAL_COUNT=$((TOTAL_COUNT + COUNT))
                SERVER_COUNT=$((SERVER_COUNT + 1))
            else
                echo "服务器 $SERVER_NAME: 无效的结果 '$COUNT'，计为0" | tee -a "$LOG_FILE"
            fi
        fi
    done < "$RESULT_FILE"
    
    # 删除临时文件
    rm -f "$RESULT_FILE"
    
    echo "======================" | tee -a "$LOG_FILE"
    echo "总计: 在 $SERVER_COUNT 个服务器上找到 $TOTAL_COUNT 个文件" | tee -a "$LOG_FILE"
    echo "统计完成，详细信息请查看日志文件: $LOG_FILE" | tee -a "$LOG_FILE"
}

# 脚本入口
if [ "$0" = "$BASH_SOURCE" ]; then
    main "$@"
fi

