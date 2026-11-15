"""Validate every commit message in a PR or in the local branch range."""

import argparse
import json
import os
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

PATTERN = re.compile(r"^(feat|fix|refactor|tests): [a-z][a-z0-9 ,.'()/+-]*$")
MAX_PAGES = 100


def validate(messages: list[tuple[str, str]]) -> list[str]:
    errors = []
    for sha, message in messages:
        if not PATTERN.fullmatch(message):
            subject = message.splitlines()[0] if message else ""
            errors.append(f"{sha[:12]}: invalid commit message: {subject!r}")
    return errors


def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def local_messages(base: str) -> list[tuple[str, str]]:
    run_git("fetch", "origin", base)
    base_sha = run_git("rev-parse", f"origin/{base}")
    head_sha = run_git("rev-parse", "HEAD")
    merge_base = run_git("merge-base", base_sha, head_sha)
    raw = run_git("log", "--format=%H%x00%B%x00", f"{merge_base}..{head_sha}")
    entries = [part for part in raw.split("\x00") if part.strip()]
    return [(entries[index], entries[index + 1].strip()) for index in range(0, len(entries), 2)]


def pr_messages(repository: str, number: str, token: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    repository = quote(repository, safe="/")
    for page in range(1, MAX_PAGES + 1):
        request = Request(
            f"https://api.github.com/repos/{repository}/pulls/{number}/commits?per_page=100&page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ctrlx-commit-message-validation",
            },
        )
        with urlopen(request, timeout=30) as response:
            page_items = json.load(response)
        result.extend((item["sha"], item["commit"]["message"]) for item in page_items)
        if len(page_items) < 100:
            return result
    raise RuntimeError("PR exceeds the 10,000 commit validation limit")


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", action="store_true")
    group.add_argument("--pr", action="store_true")
    parser.add_argument("--base", default="develop")
    parser.add_argument("--repository")
    parser.add_argument("--number")
    parser.add_argument("--token")
    args = parser.parse_args()
    try:
        if args.local:
            messages = local_messages(args.base)
        else:
            repository = args.repository or os.environ.get("GH_REPOSITORY")
            number = args.number or os.environ.get("PR_NUMBER")
            token = args.token or os.environ.get("GH_TOKEN")
            if not all((repository, number, token)):
                parser.error("--pr requires GH_REPOSITORY, PR_NUMBER and GH_TOKEN")
            messages = pr_messages(repository, number, token)
        if not messages:
            print("No commits to validate")
            return 0
        errors = validate(messages)
        if errors:
            print("Commit message validation failed:", file=sys.stderr)
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"Validated {len(messages)} commit message(s)")
        return 0
    except (HTTPError, OSError, RuntimeError, KeyError, ValueError) as error:
        print(f"Commit message validation could not complete: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
