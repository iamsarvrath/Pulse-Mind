import os
import sys
from datetime import datetime
from typing import Dict

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.logger import setup_logger  # noqa: E402

# Initialize logger
logger = setup_logger("api-gateway", level="INFO")

app = FastAPI(title="PulseMind - API Gateway")

# Service registry
SERVICES = {
    "signal-service": "http://signal-service:8001",
    "hsi-service": "http://hsi-service:8002",
    "ai-inference": "http://ai-inference:8003",
    "control-engine": "http://control-engine:8004",
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def call_service_with_retry(url: str, timeout: int = 5) -> Dict:
    """Make HTTP request with retry logic.

    Args:
        url: Service URL to call
        timeout: Request timeout in seconds

    Returns:
        JSON response from service
    """
    logger.info(f"Calling service: {url}")
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    result: Dict = response.json()
    return result


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    logger.info("Health check requested")
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "api-gateway",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return {
        "service": "api-gateway",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/services")
async def list_services():
    """List all available services with their health status.

    Returns:
        Dictionary of services with their status
    """
    logger.info("Services endpoint requested")

    services_status = {}

    for service_name, service_url in SERVICES.items():
        try:
            health_url = f"{service_url}/health"
            health_data = call_service_with_retry(health_url, timeout=5)

            services_status[service_name] = {
                "url": service_url,
                "status": "healthy",
                "health_data": health_data,
            }
            logger.info(f"Service {service_name} is healthy")

        except requests.RequestException as e:
            services_status[service_name] = {
                "url": service_url,
                "status": "unhealthy",
                "error": str(e),
            }
            logger.error(f"Service {service_name} is unhealthy: {str(e)}")
        except Exception as e:
            services_status[service_name] = {
                "url": service_url,
                "status": "error",
                "error": str(e),
            }
            logger.error(f"Error checking service {service_name}: {str(e)}")

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_services": len(SERVICES),
        "services": services_status,
    }


@app.get("/services/{service_name}")
async def get_service_info(service_name: str):
    """Get information about a specific service.

    Args:
        service_name: Name of the service

    Returns:
        Service information and health status
    """
    logger.info(f"Service info requested for: {service_name}")

    if service_name not in SERVICES:
        logger.warning(f"Service not found: {service_name}")
        raise HTTPException(
            status_code=404, detail=f"Service '{service_name}' not found"
        )

    service_url = SERVICES[service_name]

    try:
        health_url = f"{service_url}/health"
        health_data = call_service_with_retry(health_url, timeout=5)

        logger.info(f"Successfully retrieved info for {service_name}")
        return {
            "service_name": service_name,
            "url": service_url,
            "status": "healthy",
            "health_data": health_data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except requests.RequestException as e:
        logger.error(f"Failed to get info for {service_name}: {str(e)}")
        raise HTTPException(
            status_code=503, detail=f"Service '{service_name}' is unavailable: {str(e)}"
        )
