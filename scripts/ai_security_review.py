#!/usr/bin/env python3
"""
AI Security Reviewer — calls Claude API with scan results
and posts a security verdict as a GitHub PR comment.

Called by GitHub Actions on every pull_request event.
Exits with code 1 if Claude returns CRITICAL / BLOCK MERGE
so the pipeline fails and the PR cannot be merged.
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
import google.generativeai as genai


# ── Config ──────────────────────────────────────────────────────

MODEL         = "claude-haiku-4-5"        # Fast + cheap for CI. Switch to
                                            # claude-sonnet-4-5 for richer reviews
MAX_TOKENS    = 1000                        # Enough for a thorough review
DIFF_LIMIT    = 3000                        # Chars — keeps prompt cost low
SCAN_LIMIT    = 2000                        # Chars per scan file


# ── Step 1: Get the PR diff ─────────────────────────────────────

def get_pr_diff() -> str:
    """
    Returns a summary of what changed in this PR.
    Uses --stat (file names + line counts) not the full diff —
    keeps token usage low while still giving Claude useful context.
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
            # Truncate large scan files — Claude doesn't need
            # every single CVE, just the key findings
            results[label] = raw[:SCAN_LIMIT]
        else:
            results[label] = f"No {fname} found (scan may have been skipped)"
    return results


# ── Step 3: Call Claude API ─────────────────────────────────────

def review_with_claude(diff: str, scan_results: dict) -> str:
    """
    Sends the PR diff + all scan results to Claude.
    Returns Claude's plain-text security verdict.
    The structured prompt forces a consistent output format
    so the exit-code logic below can parse it reliably.
    """
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")

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

    response = model.generate_content(prompt)
    return response.text


# ── Step 4: Post comment to GitHub PR ───────────────────────────

def post_pr_comment(review_text: str, pr_number: str, repo: str) -> None:
    """
    Posts Claude's review as a comment on the GitHub PR
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
        "> Automated review powered by Claude (Anthropic API)\n\n"
        + review_text
        + "\n\n---\n*Pipeline: GitLeaks → Semgrep → Trivy → Claude AI Review*"
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
    Looks for BLOCK MERGE or CRITICAL / HIGH risk in Claude's output.
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

    # Ask Claude
    print("\nCalling Claude API...")
    review = review_with_claude(diff, scan_results)

    # Print to Actions log (visible in GitHub Actions output)
    print("\n=== Claude's Review ===")
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
        print("\nClaude flagged CRITICAL/HIGH risk — failing pipeline.")
        sys.exit(1)
    else:
        print("\nClaude approved — pipeline continues.")
        sys.exit(0)
