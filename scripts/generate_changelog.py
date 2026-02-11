#!/usr/bin/env python3
"""Generate changelog.md from git log.

Parses git log and groups commits by year/month. Categorizes commits
by type based on commit message prefixes.

Usage:
    python scripts/generate_changelog.py > docs/changelog.md
"""

import subprocess
from collections import defaultdict
from datetime import datetime


def get_git_log():
    """Get git log as list of (date, hash, message) tuples."""
    result = subprocess.run(
        ["git", "log", "--pretty=format:%ai|%h|%s", "--no-merges"],
        capture_output=True,
        text=True,
    )
    entries = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            date_str, commit_hash, message = parts
            date = datetime.fromisoformat(date_str.strip())
            entries.append((date, commit_hash.strip(), message.strip()))
    return entries


def categorize_commit(message):
    """Categorize commit by message prefix."""
    lower = message.lower()
    if lower.startswith(("fix", "bugfix", "hotfix")):
        return "Fixed"
    elif lower.startswith(("add", "feat", "new", "implement")):
        return "Added"
    elif lower.startswith(("update", "improve", "enhance", "refactor")):
        return "Changed"
    elif lower.startswith(("remove", "delete", "drop")):
        return "Removed"
    elif lower.startswith(("doc", "readme")):
        return "Documentation"
    elif lower.startswith(("test",)):
        return "Testing"
    else:
        return "Other"


def generate_changelog():
    """Generate changelog markdown from git log."""
    entries = get_git_log()
    if not entries:
        return "# Changelog\n\nNo commits found.\n"

    # Group by year-month
    by_month = defaultdict(list)
    for date, commit_hash, message in entries:
        key = date.strftime("%Y-%m")
        by_month[key].append((date, commit_hash, message))

    lines = ["# Changelog\n"]

    current_year = None
    for month_key in sorted(by_month.keys(), reverse=True):
        year = month_key[:4]
        if year != current_year:
            current_year = year
            lines.append(f"\n## {year}\n")

        month_name = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
        lines.append(f"\n### {month_name}\n")

        # Group by category
        by_category = defaultdict(list)
        for date, commit_hash, message in by_month[month_key]:
            category = categorize_commit(message)
            by_category[category].append((date, commit_hash, message))

        for category in ["Added", "Changed", "Fixed", "Removed", "Documentation", "Testing", "Other"]:
            if category in by_category:
                lines.append(f"\n**{category}**\n")
                for date, commit_hash, message in by_category[category]:
                    lines.append(f"- {message} (`{commit_hash}`)")

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_changelog())
