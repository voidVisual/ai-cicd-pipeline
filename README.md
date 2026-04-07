# AI-Powered CI/CD Pipeline

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
- AI security review via Claude API

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
- `ANTHROPIC_API_KEY` - Claude API key for security review

## Architecture

```
┌─────────────────────┐
│   GitHub Push       │
│   to main branch    │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────┐
│  Security Scan Job       │◄─── Trivy, Semgrep, GitLeaks
│  - Unit Tests            │     Claude AI Review
│  - Security Checks       │
└──────────┬───────────────┘
           │ (Passed)
           ▼
┌──────────────────────────┐
│  Build & Push Job        │
│  - Docker Build          │
│  - ECR Push              │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Deploy Job              │
│  - ECS Service Update    │
│  - Rolling Deployment    │
│  - Health Check Wait     │
└──────────────────────────┘
           │
           ▼
┌──────────────────────────┐
│   Running on ECS Fargate │
│   - Auto-scaling         │
│   - Health monitored     │
└──────────────────────────┘
```

## Troubleshooting

### Deployment Fails

1. Check GitHub Actions logs for the specific job failure
2. Verify AWS credentials and permissions in repository secrets
3. Confirm ECS cluster and service exist in the correct region
4. Review ECS task logs in CloudWatch

### Claude AI Review Not Running

Claude review only runs on pull requests to `main`, not direct pushes. Create a feature branch and open a PR to trigger the review.

## License

MIT
