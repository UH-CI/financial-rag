# Kubernetes Testing & Scaling Verification Guide

## 1. Deploy and Initial Testing

### Deploy the Application
```bash
# Apply the configurations
kubectl apply -f k8s-secrets.yaml
kubectl apply -f k8s-deployment.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=financial-rag-api --timeout=300s
```

### Check Initial Status
```bash
# Check if pods are running
kubectl get pods -l app=financial-rag-api

# Check deployment status
kubectl get deployment financial-rag-api

# Check service
kubectl get svc financial-rag-service

# Check HPA status
kubectl get hpa financial-rag-hpa
```

## 2. Basic Functionality Test

### Port Forward and Test API
```bash
# Port forward to access the API
kubectl port-forward svc/financial-rag-service 8200:8200 &

# Test the API (in another terminal)
curl http://localhost:8200/

# Test a specific endpoint (adjust based on your API)
curl http://localhost:8200/health
curl http://localhost:8200/api/query -X POST -H "Content-Type: application/json" -d '{"query": "test query"}'
```

### Check Logs
```bash
# View logs from all pods
kubectl logs -l app=financial-rag-api -f

# View logs from specific pod
kubectl logs <pod-name> -f
```

## 3. Load Testing for Scaling Verification

### Install Load Testing Tools
```bash
# Install hey (simple load testing tool)
# On macOS:
brew install hey

# On Ubuntu/Debian:
sudo apt-get install hey

# Or use curl in a loop for basic testing
```

### Create Load Test Script
```bash
# Create a simple load test script
cat > load_test.sh << 'EOF'
#!/bin/bash

API_URL="http://localhost:8200"
DURATION=300  # 5 minutes
RATE=10       # 10 requests per second

echo "Starting load test for $DURATION seconds at $RATE RPS..."

# Using hey (if installed)
if command -v hey &> /dev/null; then
    hey -n 1000 -c 10 -q 10 -z ${DURATION}s $API_URL
else
    # Fallback to curl loop
    for i in $(seq 1 $((DURATION * RATE))); do
        curl -s $API_URL > /dev/null &
        sleep 0.1
    done
    wait
fi

echo "Load test completed!"
EOF

chmod +x load_test.sh
```

### Run Load Test
```bash
# Start port forwarding in background
kubectl port-forward svc/financial-rag-service 8200:8200 &

# Run the load test
./load_test.sh
```

## 4. Monitor Scaling in Real-Time

### Watch Pod Scaling
```bash
# Watch pods scaling up/down
watch kubectl get pods -l app=financial-rag-api

# Watch HPA status
watch kubectl get hpa financial-rag-hpa

# Watch deployment status
watch kubectl get deployment financial-rag-api
```

### Monitor Resource Usage
```bash
# Check resource usage (requires metrics-server)
kubectl top pods -l app=financial-rag-api

# Watch resource usage
watch kubectl top pods -l app=financial-rag-api
```

### Detailed HPA Information
```bash
# Get detailed HPA information
kubectl describe hpa financial-rag-hpa

# Watch HPA events
kubectl get events --field-selector involvedObject.name=financial-rag-hpa --sort-by='.lastTimestamp'
```

## 5. Advanced Load Testing

### Create a More Sophisticated Load Test
```bash
# Create a Python load test script
cat > advanced_load_test.py << 'EOF'
#!/usr/bin/env python3
import requests
import time
import threading
import json
from concurrent.futures import ThreadPoolExecutor
import sys

API_URL = "http://localhost:8200"
NUM_THREADS = 20
REQUESTS_PER_THREAD = 50
DELAY_BETWEEN_REQUESTS = 0.1

def make_request(thread_id, request_id):
    try:
        # Test different endpoints
        endpoints = [
            "/",
            "/health",
            "/api/query"
        ]
        
        endpoint = endpoints[request_id % len(endpoints)]
        url = f"{API_URL}{endpoint}"
        
        if endpoint == "/api/query":
            # POST request with JSON data
            response = requests.post(url, 
                json={"query": f"Test query {request_id} from thread {thread_id}"},
                timeout=10)
        else:
            # GET request
            response = requests.get(url, timeout=10)
        
        print(f"Thread {thread_id}, Request {request_id}: {response.status_code}")
        return response.status_code == 200
        
    except Exception as e:
        print(f"Thread {thread_id}, Request {request_id}: Error - {e}")
        return False

def run_load_test():
    print(f"Starting load test with {NUM_THREADS} threads, {REQUESTS_PER_THREAD} requests each")
    
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = []
        
        for thread_id in range(NUM_THREADS):
            for request_id in range(REQUESTS_PER_THREAD):
                future = executor.submit(make_request, thread_id, request_id)
                futures.append(future)
                time.sleep(DELAY_BETWEEN_REQUESTS)
        
        # Wait for all requests to complete
        results = [future.result() for future in futures]
        
        successful = sum(results)
        total = len(results)
        print(f"\nLoad test completed: {successful}/{total} requests successful")

if __name__ == "__main__":
    run_load_test()
EOF

chmod +x advanced_load_test.py
```

### Run Advanced Load Test
```bash
# Install requests if not available
pip install requests

# Run the advanced load test
python3 advanced_load_test.py
```

## 6. Scaling Verification Commands

### Check Current Scaling Status
```bash
# Get current replica count
kubectl get deployment financial-rag-api -o jsonpath='{.spec.replicas}'

# Get current pod count
kubectl get pods -l app=financial-rag-api --no-headers | wc -l

# Get HPA current metrics
kubectl get hpa financial-rag-hpa -o yaml
```

### Force Scaling (for testing)
```bash
# Manually scale up (for testing)
kubectl scale deployment financial-rag-api --replicas=5

# Manually scale down
kubectl scale deployment financial-rag-api --replicas=2

# Let HPA take over again
kubectl delete hpa financial-rag-hpa
kubectl apply -f k8s-deployment.yaml
```

## 7. Monitoring and Debugging

### Check Pod Resource Usage
```bash
# Get detailed pod information
kubectl describe pods -l app=financial-rag-api

# Check resource limits and requests
kubectl get pods -l app=financial-rag-api -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].resources}{"\n"}{end}'
```

### Check Events and Logs
```bash
# Check all events
kubectl get events --sort-by='.lastTimestamp'

# Check specific events
kubectl get events --field-selector involvedObject.kind=HorizontalPodAutoscaler

# Check pod events
kubectl get events --field-selector involvedObject.kind=Pod
```

### Debug HPA Issues
```bash
# Check if metrics-server is running
kubectl get pods -n kube-system | grep metrics-server

# Check HPA conditions
kubectl describe hpa financial-rag-hpa | grep -A 10 "Conditions:"

# Check if metrics are available
kubectl top nodes
kubectl top pods -l app=financial-rag-api
```

## 8. Expected Scaling Behavior

### Normal Scaling Pattern
1. **Initial**: 2 pods running
2. **Load increases**: CPU/Memory usage rises above thresholds
3. **Scale up**: HPA adds more pods (up to 10)
4. **Load decreases**: CPU/Memory usage drops
5. **Scale down**: HPA removes pods (down to 2)

### Scaling Thresholds
- **CPU**: 70% average utilization
- **Memory**: 80% average utilization
- **Min replicas**: 2
- **Max replicas**: 10

### Scaling Timing
- **Scale up**: Can happen every 15 seconds
- **Scale down**: Can happen every 60 seconds
- **Stabilization**: 60s for scale up, 300s for scale down

## 9. Troubleshooting Common Issues

### HPA Not Scaling
```bash
# Check if metrics-server is installed
kubectl get pods -n kube-system | grep metrics-server

# Check HPA status
kubectl describe hpa financial-rag-hpa

# Check if pods have resource requests
kubectl get pods -l app=financial-rag-api -o yaml | grep -A 5 resources
```

### Pods Not Starting
```bash
# Check pod status
kubectl get pods -l app=financial-rag-api

# Check pod logs
kubectl logs <pod-name>

# Check pod events
kubectl describe pod <pod-name>
```

### API Not Responding
```bash
# Check service endpoints
kubectl get endpoints financial-rag-service

# Check service details
kubectl describe svc financial-rag-service

# Test connectivity
kubectl run test-pod --image=busybox --rm -it -- wget -qO- http://financial-rag-service:8200/
```

## 10. Cleanup After Testing

```bash
# Stop port forwarding
pkill -f "kubectl port-forward"

# Remove test files
rm -f load_test.sh advanced_load_test.py

# Scale down for cleanup
kubectl scale deployment financial-rag-api --replicas=1
```
