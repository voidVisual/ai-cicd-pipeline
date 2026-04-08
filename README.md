# AI-Powered CI/CD Pipeline

This project is a production-style DevSecOps pipeline for a FastAPI application. It combines automated testing, multi-layer security scanning, AI-assisted security review, container build and push to Amazon ECR, and rolling deployment to Amazon ECS Fargate through GitHub Actions.

## Project Summary

- Goal: Ship code safely with security gates before deployment.
- Stack: FastAPI, Docker, GitHub Actions, AWS ECR, AWS ECS Fargate, Bedrock AI review.
- Security controls: Pytest, GitLeaks, Semgrep, Trivy, and AI PR risk review.
- Deployment model: Build once, push immutable image tags, then roll out service update.

## Architecture Diagram

![DevOps CI/CD pipeline architecture](docs/screenshots/devops-cicd-architecture.jpeg)

## Full Workflow Diagram

![Vertical end-to-end CI/CD workflow](docs/screenshots/vertical-cicd-workflow.jpeg)

## GitHub Actions Proof

Below are screenshots of real GitHub Actions runs for visitors to verify pipeline behavior:

### 1) Security Scan Blocked on Critical Risk

![Security scan failed due to critical findings](docs/screenshots/security-scan-failed.png)

### 2) Bedrock Security Review Passed

![Bedrock AI security review passed](docs/screenshots/bedrock-review-passed.png)

### 3) Full Pipeline Success

![Complete pipeline success in GitHub Actions](docs/screenshots/full-pipeline-success.png)


## Required Setup

### Local Requirements

- Python 3.11+
- Docker Desktop
- Git
- Optional but recommended CLIs for local checks:
    - gitleaks
    - semgrep
    - trivy

### AWS Requirements

- AWS account and target region configured.
- ECR repository created for this service image.
- ECS cluster and ECS service created (Fargate launch type).
- IAM user/role with minimum required permissions for:
    - ECR push/pull
    - ECS service update
    - Bedrock model invoke

### GitHub Repository Requirements

Configure these repository secrets:

- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

Optional variable/environment override:

- BEDROCK_MODEL_ID (default used by workflow: amazon.nova-lite-v1:0)

## Getting Started

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Application

```bash
python run.py
```

The app will be available at `http://localhost:8000`.

### Run Tests

```bash
pytest tests/
```

## Local Security Checks

### GitLeaks

Scan only the current working tree first:

```bash
gitleaks detect --source . --config .gitleaks.toml --no-git
```

Then scan git history too:

```bash
gitleaks detect --source . --config .gitleaks.toml
```

### Semgrep

```bash
semgrep --config .semgrep.yml
```

Notes:
- GitLeaks scans full history unless `--no-git` is used.
- `print()` in `app/` is intentionally `INFO` and non-blocking.
- A clean app should have zero `ERROR` findings in Semgrep.

## CI/CD Pipeline

This project uses GitHub Actions for automated security scanning, building, and deployment to AWS ECS Fargate.


### Workflow Stages

**Security Scan** (runs on all PRs)
- Unit tests via pytest
- Secret detection via GitLeaks
- SAST analysis via Semgrep
- CVE scanning via Trivy
- AI security review via Amazon Bedrock

**Build & Push** (runs on merge to main)
- Docker image build
- ECR push with commit SHA tag and latest tag

**Deploy** (runs on merge to main)
- ECS service update with new image
- Rolling deployment strategy
- Health check stabilization wait

### Deployment

For detailed ECS deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

### API Endpoints

- `GET /` - Root endpoint returns welcome message
- `GET /health` - Health check for ECS
- `GET /items` - List all items
- `POST /items` - Create a new item

### Environment Variables

For GitHub Actions, set these repository secrets:
- `AWS_ACCESS_KEY_ID` - AWS IAM user access key
- `AWS_SECRET_ACCESS_KEY` - AWS IAM user secret key

Optional workflow variable/environment override:
- `BEDROCK_MODEL_ID` - Bedrock model ID for security review (default: `amazon.nova-lite-v1:0`)

## Troubleshooting

### Deployment Fails

1. Check GitHub Actions logs for the specific job failure
2. Verify AWS credentials and permissions in repository secrets
3. Confirm ECS cluster and service exist in the correct region
4. Review ECS task logs in CloudWatch

### Bedrock AI Review Not Running

Bedrock review only runs on pull requests to `main`, not direct pushes. Create a feature branch and open a PR to trigger the review.
Also verify the AWS credentials configured in GitHub Secrets have permission for `bedrock:InvokeModel` in your selected region.


