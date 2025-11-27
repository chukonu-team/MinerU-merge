#!/usr/bin/env python3

import subprocess
import json
import time
from datetime import datetime, timedelta
import logging
import sys

# 配置参数
NAMESPACE = "default"
POD_LABEL = "name=pdf-ds"
LOW_UTIL_THRESHOLD = 3.0
CONSECUTIVE_CHECKS = 3
CHECK_INTERVAL = 30
MIN_POD_AGE_MINUTES = 30

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def run_shell_command(cmd, check=True):
    """执行shell命令并返回结果"""
    try:
        logger.debug(f"执行命令: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check, timeout=300)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"命令执行失败: {cmd}, 错误: {e}")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"命令执行超时: {cmd}")
        return None


def get_pods():
    """获取所有符合条件的Pod"""
    cmd = f"kubectl get pods -n {NAMESPACE} -l {POD_LABEL} --field-selector=status.phase=Running -o json"
    output = run_shell_command(cmd)
    if not output:
        return []

    try:
        data = json.loads(output)
        return [item['metadata']['name'] for item in data.get('items', [])]
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        return []


def get_gpu_util(pod_name):
    """获取Pod的GPU利用率"""
    cmd = f"kubectl exec -n {NAMESPACE} {pod_name} --container mineru-processor -- nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits"
    output = run_shell_command(cmd, check=False)

    if not output:
        return 0.0

    try:
        # 处理多GPU情况，计算平均值
        utilizations = []
        for line in output.split('\n'):
            line = line.strip()
            if line and line.replace('.', '').replace('-', '').isdigit():
                utilizations.append(float(line))

        if utilizations:
            return sum(utilizations) / len(utilizations)
        else:
            return 0.0
    except (ValueError, ZeroDivisionError) as e:
        logger.error(f"GPU利用率计算失败 for {pod_name}: {e}")
        return 0.0


def get_pod_status(pod_name):
    """获取Pod状态"""
    cmd = f"kubectl get pod -n {NAMESPACE} {pod_name} -o jsonpath='{{.status.phase}}'"
    return run_shell_command(cmd)


def get_pod_creation_time(pod_name):
    """获取Pod创建时间"""
    cmd = f"kubectl get pod -n {NAMESPACE} {pod_name} -o jsonpath='{{.metadata.creationTimestamp}}'"
    creation_timestamp = run_shell_command(cmd)

    if not creation_timestamp:
        return None

    try:
        # 解析Kubernetes时间格式，如: 2024-01-01T10:00:00Z
        if creation_timestamp.endswith('Z'):
            creation_timestamp = creation_timestamp[:-1] + '+00:00'

        creation_time = datetime.fromisoformat(creation_timestamp)
        return creation_time
    except ValueError as e:
        logger.error(f"时间解析失败 for {pod_name}: {e}")
        return None


def is_pod_eligible(pod_name):
    """检查Pod是否满足监控条件（创建时间超过阈值）"""
    creation_time = get_pod_creation_time(pod_name)
    if not creation_time:
        return False

    current_time = datetime.now().astimezone(creation_time.tzinfo) if creation_time.tzinfo else datetime.now()
    age_minutes = (current_time - creation_time).total_seconds() / 60

    return age_minutes >= MIN_POD_AGE_MINUTES


def delete_pod(pod_name):
    """删除Pod"""
    cmd = f"kubectl delete pod -n {NAMESPACE} {pod_name}"
    result = run_shell_command(cmd)
    if result:
        logger.info(f"✅ 成功删除Pod: {pod_name}")
        return True
    else:
        logger.error(f"❌ 删除Pod失败: {pod_name}")
        return False


class PodMonitor:
    def __init__(self):
        self.pod_status = {}  # {pod_name: {'low_count': int, 'eligible': bool, 'age_minutes': float}}

    def update_pod_list(self):
        """更新Pod列表并维护状态"""
        current_pods = get_pods()

        # 移除已经不存在的Pod
        for pod in list(self.pod_status.keys()):
            if pod not in current_pods:
                logger.info(f"Pod {pod} 已不存在，从监控列表中移除")
                del self.pod_status[pod]

        # 添加新发现的Pod
        for pod in current_pods:
            if pod not in self.pod_status:
                creation_time = get_pod_creation_time(pod)
                self.pod_status[pod] = {
                    'low_count': 0,
                    'eligible': False,
                    'age_minutes': 0,
                    'creation_time': creation_time
                }
                logger.info(f"发现新Pod: {pod}")

        return current_pods

    def check_pod_eligibility(self, pod_name):
        """检查Pod资格并更新状态"""
        if pod_name not in self.pod_status:
            return False

        creation_time = self.pod_status[pod_name]['creation_time']
        if not creation_time:
            return False

        current_time = datetime.now().astimezone(creation_time.tzinfo) if creation_time.tzinfo else datetime.now()
        age_minutes = (current_time - creation_time).total_seconds() / 60
        self.pod_status[pod_name]['age_minutes'] = age_minutes

        is_eligible = age_minutes >= MIN_POD_AGE_MINUTES
        self.pod_status[pod_name]['eligible'] = is_eligible

        return is_eligible

    def monitor_cycle(self, check_num):
        """执行一次监控循环"""
        logger.info("=" * 50)
        logger.info(f"第 {check_num}/{CONSECUTIVE_CHECKS} 次检查 - {datetime.now()}")

        # 更新Pod列表
        current_pods = self.update_pod_list()

        if not current_pods:
            logger.warning(f"在命名空间 {NAMESPACE} 中未找到标签为 {POD_LABEL} 的Pod")
            return True  # 继续执行

        logger.info(f"当前监控的Pod: {current_pods}")

        # 检查每个Pod
        for pod in current_pods:
            # 检查Pod状态
            status = get_pod_status(pod)
            if status != "Running":
                logger.warning(f"Pod {pod} 不在运行状态: {status}，跳过")
                continue

            # 检查Pod资格
            is_eligible = self.check_pod_eligibility(pod)

            if not is_eligible:
                age_minutes = self.pod_status[pod]['age_minutes']
                logger.info(f"Pod {pod} 不符合监控条件 (运行时间: {age_minutes:.1f} 分钟)")
                continue

            # 获取GPU利用率
            util = get_gpu_util(pod)
            logger.info(f"Pod {pod} - GPU利用率: {util:.1f}%")

            # 更新低利用率计数
            if util < LOW_UTIL_THRESHOLD:
                self.pod_status[pod]['low_count'] += 1
                logger.info(
                    f"✓ 检测到低利用率。Pod {pod} 计数: {self.pod_status[pod]['low_count']}/{CONSECUTIVE_CHECKS}")
            else:
                self.pod_status[pod]['low_count'] = 0
                logger.info(f"✗ 利用率超过阈值。重置Pod {pod} 的计数")

        # 打印当前状态
        logger.info("当前状态:")
        for pod, status in self.pod_status.items():
            if pod in current_pods:
                if status['eligible']:
                    logger.info(
                        f"  {pod}: {status['low_count']}/{CONSECUTIVE_CHECKS} (运行时间: {status['age_minutes']:.1f}分钟)")
                else:
                    logger.info(f"  {pod}: 不符合条件 (运行时间: {status['age_minutes']:.1f}分钟)")

        return True  # 继续执行

    def final_check_and_cleanup(self):
        """最终检查并清理Pod"""
        logger.info("=" * 50)
        logger.info("=== 最终结果 ===")

        # 最终更新一次Pod列表
        current_pods = self.update_pod_list()
        any_pod_deleted = False

        for pod in current_pods:
            if pod not in self.pod_status:
                continue

            status = self.pod_status[pod]
            if not status['eligible']:
                logger.info(f"Pod {pod} - 不符合删除条件 (运行时间: {status['age_minutes']:.1f} 分钟)")
                continue

            count = status['low_count']
            logger.info(f"Pod {pod} - 最终低利用率计数: {count}/{CONSECUTIVE_CHECKS}")

            if count >= CONSECUTIVE_CHECKS:
                logger.info(f"🚨 删除Pod {pod}，因为连续GPU利用率低")
                if delete_pod(pod):
                    any_pod_deleted = True
            else:
                logger.info(f"✅ Pod {pod} 符合标准 (计数: {count}/{CONSECUTIVE_CHECKS})")

        return any_pod_deleted


def get_terminating_pods(namespace):
    """获取当前处于 Terminating 状态的 Pod 列表"""
    command = f"kubectl get pods -n {namespace} | grep Terminating | awk '{{print $1}}'"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        return [pod for pod in result.stdout.strip().split('\n') if pod]
    return []


def force_delete_terminating_pods(wait_time=60):
    """
    强制删除长时间处于 Terminating 状态的 Pod
    Args:
        namespace: 命名空间
        wait_time: 等待时间（秒），默认10秒
    """
    print(f"检查命名空间 {NAMESPACE} 中的 Terminating Pod...")

    # 第一次获取 Terminating Pod
    first_check = get_terminating_pods(NAMESPACE)

    if not first_check:
        print("没有找到 Terminating 状态的 Pod")
        return

    print(f"发现 {len(first_check)} 个 Terminating Pod: {', '.join(first_check)}")
    print(f"等待 {wait_time} 秒，让 Pod 有机会正常终止...")
    time.sleep(wait_time)

    # 第二次检查，获取仍然处于 Terminating 状态的 Pod
    second_check = get_terminating_pods(NAMESPACE)
    if not second_check:
        print("所有 Pod 已正常终止，无需强制删除")
        return
    # 找出仍然存在的 Pod（需要强制删除的）
    pods_to_delete = [pod for pod in first_check if pod in second_check]

    if not pods_to_delete:
        print("所有 Pod 已正常终止，无需强制删除")
        return
    print(f"仍有 {len(pods_to_delete)} 个 Pod 处于 Terminating 状态，开始强制删除: {', '.join(pods_to_delete)}")
    # 强制删除仍然处于 Terminating 状态的 Pod
    for pod in pods_to_delete:
        delete_cmd = f"kubectl delete pod {pod} -n {NAMESPACE} --force --grace-period=0"
        result = subprocess.run(delete_cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ 成功强制删除 Pod: {pod}")
        else:
            print(f"❌ 删除 Pod {pod} 失败: {result.stderr}")

def delete_pending_pods():
    cmd = f"kubectl delete pods -n {NAMESPACE} --field-selector=status.phase=Pending"
    result = run_shell_command(cmd)
    if result:
        print("delete_pending_pods succeeded")
    else:
        print("delete_pending_pods failed")


def main():
    delete_pending_pods()

    force_delete_terminating_pods()

    logger.info(f"开始GPU利用率监控，连续检查次数: {CONSECUTIVE_CHECKS}")
    logger.info(f"仅监控创建时间超过 {MIN_POD_AGE_MINUTES} 分钟的Pod")

    monitor = PodMonitor()
    # 执行连续检查
    for check_num in range(1, CONSECUTIVE_CHECKS + 1):
        monitor.monitor_cycle(check_num)

        # 如果不是最后一次检查，则等待
        if check_num < CONSECUTIVE_CHECKS:
            logger.info(f"等待 {CHECK_INTERVAL} 秒后进行下一次检查...")
            try:
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                logger.info("收到中断信号，退出监控")
                break

    # 最终处理
    any_pod_deleted = monitor.final_check_and_cleanup()

    if any_pod_deleted:
        logger.info("Pod删除完成。退出。")
    else:
        logger.info("没有Pod符合删除条件。退出。")


if __name__ == "__main__":
    main()