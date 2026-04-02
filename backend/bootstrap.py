"""
Bootstrap script to seed the vector DB with historical issues.
Run once during setup: python -m backend.bootstrap
"""

import logging
import sys

from github import Github, GithubException

from backend.config import settings
from backend.vector_db import embed_and_store_issue, get_collection_size, verify_embedder
from backend.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def bootstrap_vector_db(repo_name: str, max_issues: int = 500) -> int:
    """
    Seed the vector DB with historical issues from the repository.

    Args:
        repo_name: GitHub repo in "owner/repo" format.
        max_issues: Maximum number of issues to index.

    Returns:
        Number of issues indexed.
    """
    setup_logging()

    # Verify embedding model first
    if not verify_embedder():
        logger.error("Embedding model verification failed. Aborting bootstrap.")
        return 0

    logger.info(f"Bootstrapping vector DB for {repo_name} (max {max_issues} issues)")

    g = Github(settings.github_token)
    try:
        repo = g.get_repo(repo_name)
    except GithubException as e:
        logger.error(f"Failed to access repo {repo_name}: {e}")
        return 0

    issues = repo.get_issues(state="all", sort="created", direction="desc")

    count = 0
    skipped = 0
    for issue in issues:
        if count >= max_issues:
            break

        # Skip PRs (GitHub returns them as issues)
        if issue.pull_request:
            skipped += 1
            continue

        # Skip empty issues
        if not issue.title and not issue.body:
            skipped += 1
            continue

        embed_and_store_issue({
            "number": issue.number,
            "title": issue.title or "",
            "body": issue.body or "",
            "state": issue.state,
            "labels": [l.name for l in issue.labels],
            "created_at": issue.created_at.isoformat() if issue.created_at else "",
            "html_url": issue.html_url,
        })
        count += 1

        if count % 50 == 0:
            logger.info(f"Indexed {count} issues...")

    total = get_collection_size()
    logger.info(f"Bootstrap complete: {count} issues indexed, {skipped} skipped, {total} total in DB")
    return count


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "your-org/your-demo-repo"
    max_issues = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    bootstrap_vector_db(repo, max_issues)
