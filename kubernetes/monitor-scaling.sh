#!/bin/bash

# Kubernetes Scaling Monitor Script
# This script monitors the HPA and pod scaling in real-time

echo "🔍 Kubernetes Scaling Monitor"
echo "=============================="
echo "Press Ctrl+C to stop monitoring"
echo ""

# Function to get current status
get_status() {
    echo "📊 Current Status - $(date '+%H:%M:%S')"
    echo "----------------------------------------"
    
    # Get pod count
    POD_COUNT=$(kubectl get pods -l app=financial-rag-api --no-headers | wc -l)
    echo "📦 Pods: $POD_COUNT"
    
    # Get HPA status
    HPA_STATUS=$(kubectl get hpa financial-rag-hpa -o jsonpath='{.status.currentReplicas}/{.spec.minReplicas}-{.spec.maxReplicas}' 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "📈 HPA: $HPA_STATUS"
    else
        echo "📈 HPA: Not available"
    fi
    
    # Get resource usage if metrics-server is available
    if kubectl top pods -l app=financial-rag-api >/dev/null 2>&1; then
        echo "💻 Resource Usage:"
        kubectl top pods -l app=financial-rag-api --no-headers | while read line; do
            echo "   $line"
        done
    else
        echo "💻 Resource Usage: Metrics server not available"
    fi
    
    # Get recent events
    echo "📝 Recent Events:"
    kubectl get events --field-selector involvedObject.name=financial-rag-hpa --sort-by='.lastTimestamp' --no-headers | tail -3 | while read line; do
        echo "   $line"
    done
    
    echo ""
}

# Function to run load test
run_load_test() {
    echo "🚀 Starting load test..."
    API_URL="http://localhost:8200"
    
    # Check if port forwarding is active
    if ! curl -s $API_URL >/dev/null 2>&1; then
        echo "❌ API not accessible. Make sure port forwarding is active:"
        echo "   kubectl port-forward svc/financial-rag-service 8200:8200 &"
        return 1
    fi
    
    # Run load test in background
    for i in $(seq 1 100); do
        curl -s $API_URL >/dev/null &
        sleep 0.1
    done &
    
    echo "✅ Load test started (100 requests)"
}

# Main monitoring loop
monitor() {
    while true; do
        clear
        get_status
        
        echo "Options:"
        echo "  [L] Start load test"
        echo "  [S] Scale up manually (5 replicas)"
        echo "  [D] Scale down manually (2 replicas)"
        echo "  [R] Reset to HPA control"
        echo "  [Q] Quit"
        echo ""
        echo "Press any key to refresh..."
        
        # Read input with timeout
        read -t 5 -n 1 input
        case $input in
            [Ll]) run_load_test ;;
            [Ss]) 
                echo "📈 Scaling up to 5 replicas..."
                kubectl scale deployment financial-rag-api --replicas=5
                ;;
            [Dd]) 
                echo "📉 Scaling down to 2 replicas..."
                kubectl scale deployment financial-rag-api --replicas=2
                ;;
            [Rr]) 
                echo "🔄 Resetting to HPA control..."
                kubectl delete hpa financial-rag-hpa 2>/dev/null
                kubectl apply -f k8s-deployment.yaml
                ;;
            [Qq]) 
                echo "👋 Goodbye!"
                exit 0
                ;;
        esac
    done
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if we can connect to cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    exit 1
fi

# Check if the deployment exists
if ! kubectl get deployment financial-rag-api &> /dev/null; then
    echo "❌ Deployment 'financial-rag-api' not found. Please deploy first:"
    echo "   kubectl apply -f k8s-deployment.yaml"
    exit 1
fi

# Start monitoring
monitor
