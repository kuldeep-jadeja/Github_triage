"""
GitHub API wrapper using PyGithub.
Handles: issues, labels, comments, templates, PR diffs.
Label cache is shared across all workers via functools.lru_cache.
"""

import logging
import time
from functools import lru_cache
from typing import List, Optional, Dict, Any

from github import Github, GithubException, RateLimitExceededException

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger(__name__)


class GitHubTools:
    """Thread-safe GitHub API client with caching and rate limit handling."""

    def __init__(self, token: Optional[str] = None, repo_name: Optional[str] = None):
        self.token = token or settings.github_token
        self.repo_name = repo_name
        self._g: Optional[Github] = None
        self._repo = None

    @property
    def g(self) -> Github:
        if self._g is None:
            self._g = Github(self.token)
        return self._g

    @property
    def repo(self):
        if self._repo is None:
            self._repo = self.g.get_repo(self.repo_name)
        return self._repo

    @lru_cache(maxsize=1)
    def get_available_labels(self) -> List[str]:
        """Fetch repo's actual labels. Cached for the lifetime of the process."""
        try:
            labels = [l.name for l in self.repo.get_labels()]
            logger.info(f"Fetched {len(labels)} labels from {self.repo_name}")
            return labels
        except RateLimitExceededException:
            logger.warning("Rate limited while fetching labels")
            return []
        except GithubException as e:
            logger.error(f"Failed to fetch labels: {e}")
            return []

    def get_issue(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Fetch full issue details."""
        try:
            issue = self.repo.get_issue(issue_number)
            return {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body or "",
                "state": issue.state,
                "author": issue.user.login if issue.user else "",
                "labels": [l.name for l in issue.labels],
                "created_at": issue.created_at.isoformat() if issue.created_at else "",
                "html_url": issue.html_url,
                "locked": issue.locked,
            }
        except GithubException as e:
            logger.error(f"Failed to fetch issue #{issue_number}: {e}")
            return None

    def apply_labels(self, issue_number: int, labels: List[str]) -> Dict[str, Any]:
        """Apply labels that exist in the repo. Silently skips non-existent labels."""
        available = set(self.get_available_labels())
        valid_labels = [l for l in labels if l in available]
        invalid_labels = [l for l in labels if l not in available]

        if invalid_labels:
            logger.warning(f"Skipping invalid labels: {invalid_labels}")

        if not valid_labels:
            return {"status": "no_valid_labels", "requested": labels}

        try:
            issue = self.repo.get_issue(issue_number)
            for label in valid_labels:
                issue.add_to_labels(label)
            logger.info(f"Applied labels {valid_labels} to #{issue_number}")
            return {"status": "applied", "labels": valid_labels}
        except RateLimitExceededException:
            logger.warning(f"Rate limited applying labels to #{issue_number}")
            return {"status": "rate_limited", "labels": valid_labels}
        except GithubException as e:
            logger.error(f"Failed to apply labels to #{issue_number}: {e}")
            return {"status": "error", "error": str(e)}

    def post_comment(self, issue_number: int, body: str) -> Dict[str, Any]:
        """Post a comment on the issue. Checks if issue is locked first."""
        try:
            issue = self.repo.get_issue(issue_number)
            if issue.locked:
                logger.warning(f"Issue #{issue_number} is locked, skipping comment")
                return {"status": "locked", "issue_number": issue_number}

            comment = issue.create_comment(body)
            logger.info(f"Posted comment on #{issue_number} (id={comment.id})")
            return {"status": "posted", "comment_id": comment.id}
        except RateLimitExceededException:
            logger.warning(f"Rate limited posting comment to #{issue_number}")
            return {"status": "rate_limited"}
        except GithubException as e:
            logger.error(f"Failed to post comment on #{issue_number}: {e}")
            return {"status": "error", "error": str(e)}

    def get_issue_templates(self) -> List[Dict[str, Any]]:
        """Fetch issue templates from .github/ISSUE_TEMPLATE/."""
        templates = []
        try:
            contents = self.repo.get_contents(".github/ISSUE_TEMPLATE")
            if not isinstance(contents, list):
                contents = [contents]
            for item in contents:
                if item.name.endswith((".md", ".yml", ".yaml")):
                    try:
                        content = item.decoded_content.decode("utf-8")
                        templates.append({
                            "name": item.name,
                            "path": item.path,
                            "content": content,
                        })
                    except Exception as e:
                        logger.warning(f"Failed to read template {item.name}: {e}")
        except GithubException:
            logger.info("No .github/ISSUE_TEMPLATE/ directory found")
        return templates

    def get_pr_diff_summary(self, pr_number: int, max_chars: int = 2000) -> Dict[str, Any]:
        """Get a summary of a PR diff: changed files list + truncated diff."""
        try:
            pr = self.repo.get_pull(pr_number)
            files = pr.get_files()

            changed_files = []
            for f in files:
                changed_files.append({
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                })

            # Get truncated diff content
            diff_text = ""
            try:
                diff_text = pr.as_raw_diff().decode("utf-8", errors="replace")[:max_chars]
            except Exception:
                pass

            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body or "",
                "changed_files": changed_files,
                "diff_summary": diff_text,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "mergeable": pr.mergeable,
                "mergeable_state": pr.mergeable_state,
            }
        except GithubException as e:
            logger.error(f"Failed to get PR #{pr_number} diff: {e}")
            return {"error": str(e)}

    def get_suggested_reviewers(self, pr_number: int, top_n: int = 3) -> List[str]:
        """Suggest reviewers based on who touched the changed files."""
        try:
            pr = self.repo.get_pull(pr_number)
            files = pr.get_files()

            # Get recent contributors to the changed files
            file_authors = {}
            for f in files:
                try:
                    commits = self.repo.get_commits(path=f.filename)
                    for commit in list(commits[:5]):
                        author = commit.author
                        if author and author.login != pr.user.login:
                            file_authors[author.login] = file_authors.get(author.login, 0) + 1
                except Exception:
                    pass

            # Sort by frequency and return top N
            sorted_authors = sorted(file_authors.items(), key=lambda x: -x[1])
            return [author for author, _ in sorted_authors[:top_n]]
        except Exception as e:
            logger.warning(f"Failed to suggest reviewers for PR #{pr_number}: {e}")
            return []
