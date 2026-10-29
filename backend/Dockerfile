FROM python:3.11-slim

# System deps: ffmpeg for video, libgl1/libglib2.0-0 for opencv & mediapipe
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/* 2>/dev/null; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Use one index: extra-index-url is not a fallback and can select the broken mirror.
ARG PYTHON_PACKAGE_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple/

# pip 25.2 resumes incomplete downloads by default; keep wheel hash verification.
# Pre-install large packages separately for better layer caching.
RUN python -m pip install --no-cache-dir \
    --index-url "${PYTHON_PACKAGE_INDEX}" \
    --timeout 120 --retries 10 pip==25.2 \
    && python -m pip install --no-cache-dir \
    --index-url "${PYTHON_PACKAGE_INDEX}" \
    --timeout 120 --retries 10 --resume-retries 10 \
    opencv-python==4.9.0.80 \
    mediapipe==0.10.9

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    --index-url "${PYTHON_PACKAGE_INDEX}" \
    --timeout 120 --retries 10 --resume-retries 10

COPY . .

RUN mkdir -p uploads

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
