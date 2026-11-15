"""Validate allowed PR directions without relying on untrusted shell interpolation."""

import json
import os
import re
from pathlib import Path


def target_branch(branch):
    if branch == "develop":
        return "prod"
    if re.fullmatch(r"feature/[a-z0-9]+(?:-[a-z0-9]+)*", branch):
        return "develop"
    raise ValueError("Only feature/<english-kebab-case> or develop may be promoted")


def validate_pull_request(pr, repository):
    if (pr["head"]["repo"]["full_name"] != repository
            or pr["base"]["repo"]["full_name"] != repository
            or pr["base"]["ref"] != target_branch(pr["head"]["ref"])):
        raise ValueError("Allowed PR directions: feature/* to develop; develop to prod, same repository")


def main():
    if os.environ["GITHUB_EVENT_NAME"] == "pull_request":
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        validate_pull_request(event["pull_request"], os.environ["GITHUB_REPOSITORY"])
    elif os.environ["GITHUB_EVENT_NAME"] == "push":
        branch = os.environ["GITHUB_REF_NAME"]
        if branch != "prod":
            target_branch(branch)
    else:
        raise ValueError("Unsupported CI event")


if __name__ == "__main__":
    main()
