# Kubernetes Deployment Guide

Complete setup guide for deploying the Financial RAG application to Kubernetes with automatic scaling.

## Prerequisites

- Docker Desktop
- kubectl
- minikube

## Quick Setup

### 1. Start minikube with sufficient resources

```bash
minikube start --disk-size=50g --memory=8192 --cpus=4
minikube addons enable metrics-server
```

### 2. Configure secrets

Edit `k8s-secrets.yaml` with your API keys:

```yaml
stringData:
  GOOGLE_API_KEY: "your-google-api-key"
  LLAMA_API_KEY: "your-llama-api-key" 
  GEMINI_API_KEY: "your-gemini-api-key"
```

Apply secrets:
```bash
kubectl apply -f k8s-secrets.yaml
```

### 3. Deploy the application

```bash
kubectl apply -f k8s-deployment.yaml
```

### 4. Check deployment status

```bash
kubectl get pods -l app=financial-rag-api
kubectl get hpa
```

Wait for pods to be `1/1 Running` (may take 5-10 minutes for image download).

### 5. Access the application

```bash
kubectl port-forward svc/financial-rag-service 8200:8200
```

Open your frontend at `http://localhost:3002` - it will connect to the API at `http://localhost:8200`.

## What's Deployed

- **API**: Financial RAG application with 2-10 auto-scaling pods
- **Storage**: Persistent volumes for ChromaDB and documents
- **Scaling**: HPA scales based on CPU (70%) and memory (80%) usage
- **Service**: Load balancer distributing requests across pods

## Monitoring

```bash
# Check pod status
kubectl get pods -l app=financial-rag-api

# Check scaling
kubectl get hpa

# View logs
kubectl logs -l app=financial-rag-api --tail=10
```

## Troubleshooting

**Pods not starting?**
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

**Port forwarding issues?**
```bash
kubectl port-forward svc/financial-rag-service 8200:8200
```

**API not responding?**
- Check if pods are `1/1 Running`
- Verify port forwarding is active
- Check logs for errors

## Cleanup

```bash
kubectl delete -f k8s-deployment.yaml
kubectl delete -f k8s-secrets.yaml
minikube delete
```