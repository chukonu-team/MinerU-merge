FROM docker.m.daocloud.io/vllm/vllm-openai:v0.11.0

ENV TZ=Asia/Shanghai
RUN apt-get update && \
    apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    fonts-noto-core \
    fonts-noto-cjk \
    fontconfig \
    libgl1 && \
    fc-cache -fv  && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


RUN mkdir /data

COPY ./MinerU/  /data/MinerU/
WORKDIR /data/MinerU

RUN pip install -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -e .[all]
RUN pip install PyMuPDF -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY ./modelscope/ /opt/modelscope/
ENV MODELSCOPE_CACHE="/opt/modelscope/hub"
ENV PYTHONPATH="/data/MinerU:$PYTHONPATH"

ENTRYPOINT ["/bin/bash"]




