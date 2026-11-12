"""Fetch release notes from GitHub."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime

import httpx

API = "https://api.github.com"


def github_token() -> str | None:
    """Use GITHUB_TOKEN if set, otherwise the GitHub CLI's token if it is logged in."""
    if token := os.environ.get("GITHUB_TOKEN"):
        return token
    if shutil.which("gh"):
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    return None


def fetch_releases(repo: str, since: datetime, client: httpx.Client, max_pages: int = 5) -> list[dict]:
    """Return published, non-draft releases of `repo` newer than `since`, newest first.

    GitHub lists releases newest first, so paging stops at the first page that reaches
    past `since`.
    """
    releases: list[dict] = []
    for page in range(1, max_pages + 1):
        resp = client.get(f"{API}/repos/{repo}/releases", params={"per_page": 100, "page": page})
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        done = False
        for r in batch:
            if r.get("draft") or not r.get("published_at"):
                continue
            published = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
            if published < since:
                done = True
                continue
            releases.append(
                {
                    "repo": repo,
                    "tag": r["tag_name"],
                    "published_at": r["published_at"],
                    "prerelease": r.get("prerelease", False),
                    "url": r["html_url"],
                    "body": r.get("body") or "",
                }
            )
        if done:
            break
    return releases


def make_client() -> httpx.Client:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "driftbench"}
    if token := github_token():
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(headers=headers, timeout=30, follow_redirects=True)
