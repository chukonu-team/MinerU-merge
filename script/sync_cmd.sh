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

# 日志文件
LOG_FILE="remote_execution_$(date +%Y%m%d_%H%M%S).log"

# 远程执行命令的函数
execute_remote_command() {
    local SERVER=$1
    local COMMAND=$2
    local LOG_FILE=$3

    echo "$(date): 开始在服务器 $SERVER 上执行命令" | tee -a "$LOG_FILE"
    echo "执行的命令: $COMMAND" | tee -a "$LOG_FILE"

    # 使用ssh执行远程命令
    ssh -o ConnectTimeout=10 -o BatchMode=yes -o "StrictHostKeyChecking no" "$SERVER" "$COMMAND" >> "$LOG_FILE" 2>&1

    # 检查执行结果
    if [ $? -eq 0 ]; then
        echo "$(date): $SERVER 命令执行成功" | tee -a "$LOG_FILE"
    else
        echo "$(date): 错误: $SERVER 命令执行失败" | tee -a "$LOG_FILE"
    fi
}

# 主函数
main() {
    if [ $# -lt 1 ]; then
        echo "用法: $0 \"要执行的命令\""
        exit 1
    fi

    COMMAND="$1"
    
    echo "$(date): 开始在所有服务器上执行命令" | tee -a "$LOG_FILE"
    echo "命令内容: $COMMAND" | tee -a "$LOG_FILE"
    
    # 添加并发控制，最多同时5个连接
    MAX_CONCURRENT=5
    PIDS=()
    
    for SERVER in "${SERVERS[@]}"; do
        execute_remote_command "$SERVER" "$COMMAND" "$LOG_FILE" &
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
    
    echo "$(date): 所有服务器命令执行完成" | tee -a "$LOG_FILE"
}

main "$@"
