FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY analytics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy analytics folder and services (for persistence logic)
COPY analytics/ /app/analytics/
COPY services/ /app/services/

# Create a shell script to run both ETL and Streamlit
RUN echo '#!/bin/sh\n\
    python analytics/etl_pipeline.py & \n\
    streamlit run analytics/dashboard_app.py --server.port 8502 --server.address 0.0.0.0\n\
    ' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8502

ENTRYPOINT ["/app/start.sh"]
