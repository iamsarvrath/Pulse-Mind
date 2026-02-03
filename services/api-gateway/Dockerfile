FROM python:3.11-slim

# Create a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module first
COPY shared /app/shared

COPY api-gateway/ .

# Change ownership to the non-root user
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

CMD ["uvicorn", "api_gateway_service:app", "--host", "0.0.0.0", "--port", "8000"]
