import requests
import datetime
import os
import json

SERVICES = {
    "api-gateway": "http://localhost:8000/health",
    "signal-service": "http://localhost:8001/health",
    "hsi-service": "http://localhost:8002/health",
    "ai-inference": "http://localhost:8003/health",
    "control-engine": "http://localhost:8004/health"
}

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'health_check.md')

def check_health():
    results = []
    print("Starting Health Check...")
    
    with open(OUTPUT_FILE, 'w') as f:
        f.write("# Service Health Check Report\n\n")
        f.write(f"**Date:** {datetime.datetime.utcnow().isoformat()}\n\n")
        f.write("| Service | URL | Status Code | Response Time (ms) | Status |\n")
        f.write("|---|---|---|---|---|\n")
        
        for name, url in SERVICES.items():
            try:
                start = datetime.datetime.now()
                resp = requests.get(url, timeout=5)
                duration = (datetime.datetime.now() - start).total_seconds() * 1000
                
                status_icon = "PASS" if resp.status_code == 200 else "FAIL"
                row = f"| {name} | {url} | {resp.status_code} | {duration:.2f} | {status_icon} |"
                print(f"{name}: {resp.status_code} ({duration:.2f}ms)")
                f.write(row + "\n")
                
            except Exception as e:
                print(f"{name}: Failed - {e}")
                f.write(f"| {name} | {url} | ERROR | - | FAIL |\n")

    print(f"Health check report saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    check_health()
