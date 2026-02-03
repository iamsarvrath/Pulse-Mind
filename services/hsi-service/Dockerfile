FROM python:3.11-slim

# Create a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY hsi-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module first
COPY shared /app/shared

COPY hsi-service/ .

# Change ownership to the non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8002/health', timeout=5)"

CMD ["python", "hsi_service.py"]
