#!/usr/bin/env python3
"""
AI Security Reviewer — calls Amazon Bedrock with scan results
and posts a security verdict as a GitHub PR comment.

Called by GitHub Actions on every pull_request event.
Exits with code 1 if the model returns CRITICAL / BLOCK MERGE
so the pipeline fails and the PR cannot be merged.
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
import boto3


# ── Config ──────────────────────────────────────────────────────

MODEL         = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
MAX_TOKENS    = 1000                        # Enough for a thorough review
DIFF_LIMIT    = 3000                        # Chars — keeps prompt cost low
SCAN_LIMIT    = 2000                        # Chars per scan file


# ── Step 1: Get the PR diff ─────────────────────────────────────

def get_pr_diff() -> str:
    """
    Returns a summary of what changed in this PR.
    Uses --stat (file names + line counts) not the full diff —
    keeps token usage low while still giving the reviewer useful context.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "origin/main...HEAD", "--stat"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        diff = result.stdout.strip()
        if not diff:
            return "No diff available (possibly first commit or no changes vs main)"
        return diff[:DIFF_LIMIT]
    except Exception as e:
        return f"Could not retrieve diff: {e}"


# ── Step 2: Read scan result files ──────────────────────────────

def read_scan_results() -> dict:
    """
    Reads JSON output files written by Trivy and Semgrep
    in earlier pipeline steps. GitLeaks failures already
    stopped the pipeline — its output isn't needed here.
    Returns a dict of filename -> truncated content.
    """
    scan_files = {
        "trivy":   "trivy-results.json",
        "semgrep": "semgrep-results.json",
    }
    results = {}
    for label, fname in scan_files.items():
        if os.path.exists(fname):
            with open(fname, "r") as f:
                raw = f.read()
            # Truncate large scan files — the reviewer does not need
            # every single CVE, just the key findings
            results[label] = raw[:SCAN_LIMIT]
        else:
            results[label] = f"No {fname} found (scan may have been skipped)"
    return results


# ── Step 3: Call Amazon Bedrock ─────────────────────────────────

def _extract_bedrock_text(model_id: str, payload: dict) -> str:
    """
    Extract plain text from common Bedrock response shapes.
    Supports Amazon model response shapes.
    """
    if model_id.startswith("amazon."):
        content = (
            payload.get("output", {})
            .get("message", {})
            .get("content", [])
        )
        return "\n".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        ).strip()

    # Fallback for unknown providers
    return (
        payload.get("outputText")
        or payload.get("completion")
        or json.dumps(payload)[:1000]
    )


def review_with_bedrock(diff: str, scan_results: dict) -> str:
    """
    Sends the PR diff + all scan results to Amazon Bedrock.
    Returns the model's plain-text security verdict.
    The structured prompt forces a consistent output format
    so the exit-code logic below can parse it reliably.
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    # Build the scan summary block
    scan_summary = "\n\n".join(
        f"### {label.upper()} SCAN RESULTS\n{content}"
        for label, content in scan_results.items()
    )

    prompt = f"""You are a senior DevSecOps engineer doing a security review of a pull request.

## PR CHANGES
{diff}

## SECURITY SCAN RESULTS
{scan_summary}

Respond in exactly this format:

**RISK LEVEL:** [CRITICAL / HIGH / MEDIUM / LOW / CLEAN]
**SUMMARY:** 2-3 sentences plain English summary.
**TOP FINDINGS:**
- Finding 1 (or None)
- Finding 2
- Finding 3
**RECOMMENDATION:** [BLOCK MERGE / APPROVE WITH NOTES / APPROVE]
**REASON:** One sentence explanation."""

    if MODEL.startswith("amazon."):
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            "inferenceConfig": {
                "maxTokens": MAX_TOKENS,
                "temperature": 0.2,
            },
        }
    else:
        raise ValueError(
            f"Unsupported BEDROCK_MODEL_ID '{MODEL}'. Use an Amazon Bedrock model ID such as amazon.nova-lite-v1:0."
        )

    response = bedrock.invoke_model(
        modelId=MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_payload = json.loads(response["body"].read())
    review_text = _extract_bedrock_text(MODEL, response_payload)

    if not review_text:
        raise RuntimeError("Bedrock returned an empty review response")

    return review_text


# ── Step 4: Post comment to GitHub PR ───────────────────────────

def post_pr_comment(review_text: str, pr_number: str, repo: str) -> None:
    """
    Posts the AI review as a comment on the GitHub PR
    using the GitHub REST API.
    Requires GITHUB_TOKEN with pull-requests: write permission
    (automatically provided by GitHub Actions).
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not set — skipping PR comment")
        return

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    body = (
        "## AI Security Review\n\n"
        "> Automated review powered by Amazon Bedrock\n\n"
        + review_text
        + "\n\n---\n*Pipeline: GitLeaks -> Semgrep -> Trivy -> Bedrock AI Review*"
    )

    payload = json.dumps({"body": body}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":         "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"PR comment posted — HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"Failed to post PR comment: HTTP {e.code} — {e.read().decode()}")
    except urllib.error.URLError as e:
        print(f"Network error posting PR comment: {e.reason}")


# ── Step 5: Decide pass / fail ───────────────────────────────────

def should_fail_pipeline(review_text: str) -> bool:
    """
    Returns True if the pipeline should fail (exit 1).
    Looks for BLOCK MERGE or CRITICAL / HIGH risk in model output.
    This is what actually prevents a bad PR from being merged.
    """
    upper = review_text.upper()
    fail_signals = [
        "BLOCK MERGE",
        "RISK LEVEL:** CRITICAL",
        "RISK LEVEL:** HIGH",
        "**RISK LEVEL:** CRITICAL",
        "**RISK LEVEL:** HIGH",
    ]
    return any(signal in upper for signal in fail_signals)


# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=== AI Security Review starting ===")

    # Collect all inputs
    diff         = get_pr_diff()
    scan_results = read_scan_results()

    print(f"Diff length:  {len(diff)} chars")
    print(f"Scan files:   {list(scan_results.keys())}")

    # Ask Bedrock
    print(f"\nCalling Amazon Bedrock model: {MODEL}...")
    review = review_with_bedrock(diff, scan_results)

    # Print to Actions log (visible in GitHub Actions output)
    print("\n=== AI Review ===")
    print(review)
    print("======================")

    # Post as PR comment (only when running inside GitHub Actions)
    pr_number = os.environ.get("PR_NUMBER")
    repo      = os.environ.get("GITHUB_REPOSITORY")

    if pr_number and repo:
        print(f"\nPosting comment to PR #{pr_number} in {repo}...")
        post_pr_comment(review, pr_number, repo)
    else:
        print("\nPR_NUMBER or GITHUB_REPOSITORY not set — skipping comment (local run)")

    # Pass or fail the pipeline
    if should_fail_pipeline(review):
        print("\nAI review flagged CRITICAL/HIGH risk - failing pipeline.")
        sys.exit(1)
    else:
        print("\nAI review approved - pipeline continues.")
        sys.exit(0)
