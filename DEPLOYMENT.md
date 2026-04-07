# ECS Deployment Guide

This document describes how to deploy the AI-powered CI/CD pipeline application to AWS ECS Fargate.

## Prerequisites

- AWS account with ECS, ECR, and IAM access
- AWS CLI configured with credentials
- Docker installed locally
- GitHub repository with CI/CD pipeline enabled

## Infrastructure Setup

### 1. Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name ai-cicd-cluster \
  --region us-east-1
```

### 2. Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name ai-cicd-app \
  --region us-east-1
```

### 3. Register ECS Task Definition

```bash
aws ecs register-task-definition \
  --cli-input-json file://task-def.json.json \
  --region us-east-1
```

### 4. Create ECS Service with Fargate

```bash
aws ecs create-service \
  --cluster ai-cicd-cluster \
  --service-name ai-cicd-service \
  --task-definition ai-cicd-task:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
  --region us-east-1
```

## CI/CD Pipeline

The GitHub Actions workflow automatically:

1. **Security scan** - Runs on all PRs
   - Unit tests
   - GitLeaks secret scanning
   - Semgrep SAST analysis
   - Trivy CVE scanning
   - Claude AI security review

2. **Build & Push** - Runs on merge to main
   - Builds Docker image
   - Pushes to ECR
   - Tags with commit SHA and latest

3. **Deploy** - Runs on merge to main
   - Updates ECS service with new image
   - Triggers rolling deployment
   - Waits for service to stabilize

## Monitoring

- CloudWatch logs: `/ecs/ai-cicd-task`
- ECS console: View running tasks and service status
- GitHub Actions: View workflow runs and logs

## Troubleshooting

### Service Rollback

If deployment rolls back, check:
1. ECS task logs in CloudWatch
2. Service events in ECS console
3. Health check passes on port 8000

### Image Pull Errors

Ensure:
1. ECR repository exists in the same region
2. IAM role has ECR pull permissions
3. Image URI is correct in task definition

## Rollback

To rollback to previous image:

```bash
aws ecs update-service \
  --cluster ai-cicd-cluster \
  --service ai-cicd-service \
  --force-new-deployment \
  --region us-east-1
```

Then update task definition to use previous image version.
