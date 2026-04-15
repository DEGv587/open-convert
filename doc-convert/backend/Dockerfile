FROM debian:bullseye-slim

# 构建参数：USE_MIRROR=true 使用阿里云镜像（本地开发），false 使用官方源（生产环境）
ARG USE_MIRROR=false

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 条件性配置镜像源
RUN if [ "$USE_MIRROR" = "true" ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    fi

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-calc \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libheif-dev \
    libheif1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# 条件性使用 pip 镜像源
RUN if [ "$USE_MIRROR" = "true" ]; then \
        pip3 install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt; \
    else \
        pip3 install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

RUN mkdir -p /tmp/docconv

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
