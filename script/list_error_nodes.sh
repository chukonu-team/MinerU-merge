#!/bin/bash

# 使用kubectl的field-selector和标签选择器
echo "没有运行中Pod的节点（排除control-plane）:"
kubectl get nodes -o name --selector='!node-role.kubernetes.io/control-plane' | while read node; do
    node_name=${node#node/}
    if [ $(kubectl get pods --field-selector=status.phase=Running,spec.nodeName=$node_name -o name | wc -l) -eq 0 ]; then
        echo $node_name
    fi
done
