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
