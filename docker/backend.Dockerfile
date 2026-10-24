# CPU-only backend image. data/ and models/ are mounted as volumes, never baked in.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend ./backend
COPY config ./config
COPY dev_data ./dev_data
COPY scripts ./scripts
COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh && mkdir -p /app/models /app/data /app/outputs
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
ENTRYPOINT ["/entrypoint.sh"]
