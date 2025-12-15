# 基础镜像配置 vLLM 或 LMDeploy ，请根据实际需要选择其中一个，要求 ARM(AArch64) CPU + Ascend NPU。
FROM quay.m.daocloud.io/ascend/vllm-ascend:v0.11.0rc2

# Set the user ma-user whose UID is 1000 and the user group ma-group whose GID is 100
USER root
RUN default_user=$(getent passwd 1000 | awk -F ':' '{print $1}') || echo "uid: 1000 does not exist" && \
    default_group=$(getent group 100 | awk -F ':' '{print $1}') || echo "gid: 100 does not exist" && \
    if [ ! -z ${default_user} ] && [ ${default_user} != "ma-user" ]; then \
        userdel -r ${default_user}; \
    fi && \
    if [ ! -z ${default_group} ] && [ ${default_group} != "ma-group" ]; then \
        groupdel -f ${default_group}; \
    fi && \
    groupadd -g 100 ma-group && useradd -d /home/ma-user -m -u 1000 -g 100 -s /bin/bash ma-user && \
    chmod -R 750 /home/ma-user

# Install libgl for opencv support & Noto fonts for Chinese characters
RUN apt-get update && \
    apt-get install -y \
        fonts-noto-core \
        fonts-noto-cjk \
        fontconfig \
        libgl1 \
        libglib2.0-0 && \
    fc-cache -fv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ./MinerU-merge/  /data/MinerU/
WORKDIR /data/MinerU
# Install mineru latest
RUN python3 -m pip install -U pip -i https://mirrors.aliyun.com/pypi/simple && \
    python3 -m pip install -e .[all] &&  \
    python3 -m pip install numpy==1.26.4 \
                            opencv-python==4.11.0.86 \
                            loguru==0.7.3 \
                            -i https://mirrors.aliyun.com/pypi/simple && \
    python3 -m pip cache purge
    

# ====== 关键修复：在切换到ma-user之前设置目录权限 ======
# 设置Python目录权限
RUN chown -R ma-user:ma-group /usr/local/python3.11.13 && \
    chmod -R 775 /usr/local/python3.11.13

# 设置Ascend目录权限
RUN if [ -d "/usr/local/Ascend" ]; then \
        chown -R ma-user:ma-group /usr/local/Ascend && \
        chmod -R 775 /usr/local/Ascend; \
    fi
# 设置Ascend目录权限
RUN if [ -d "/data" ]; then \
        chown -R ma-user:ma-group /data && \
        chmod -R 775 /data; \
    fi


# 设置site-packages目录权限
RUN find /usr/local -name "site-packages" -type d -exec chown -R ma-user:ma-group {} \; && \
    find /usr/local -name "site-packages" -type d -exec chmod -R 775 {} \;

# 为ma-user创建可写的Python目录
RUN mkdir -p /home/ma-user/.local/lib/python3.11/site-packages && \
    chown -R ma-user:ma-group /home/ma-user/.local && \
    chmod -R 775 /home/ma-user/.local

# 设置环境变量
RUN echo 'export PYTHONPATH=/home/ma-user/.local/lib/python3.11/site-packages:/usr/local/python3.11.13/lib/python3.11/site-packages:$PYTHONPATH' >> /home/ma-user/.bashrc

RUN apt-get update && apt-get install -y sudo && \
    echo "ma-user ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/ma-user && \
    chmod 0440 /etc/sudoers.d/ma-user

# Switch to ma-user for remaining operations
USER ma-user

# 设置工作目录
WORKDIR /home/ma-user/work

# 设置环境变量
ENV PYTHONPATH=/home/ma-user/.local/lib/python3.11/site-packages:/usr/local/python3.11.13/lib/python3.11/site-packages:$PYTHONPATH
ENV MINERU_MODEL_SOURCE=local

# Download models as root before switching to ma-user
RUN TORCH_DEVICE_BACKEND_AUTOLOAD=0 /bin/bash -c "mineru-models-download -s modelscope -m all"

# Set the entry point to activate the virtual environment and run the command line tool
ENTRYPOINT ["/bin/bash", "-l", "-c", "export MINERU_MODEL_SOURCE=local && exec \"$@\"", "--"]