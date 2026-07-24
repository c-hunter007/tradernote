FROM python:3.10.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=600 -r requirements.txt

COPY . .

RUN mkdir -p data uploads

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]