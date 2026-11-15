"""Trusted workflow_run handler: request auto-merge, never bypass reviews or checks."""

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from scripts.branch_policy import target_branch, validate_pull_request


def api(path, method="GET", data=None):
    request = Request(
        "https://api.github.com" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28"}, method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"GitHub {method} failed (HTTP {error.code})") from None
    if isinstance(result, dict) and result.get("errors"):
        raise RuntimeError("GitHub rejected the auto-merge request; inspect PR requirements")
    return result


def candidate(event, repository):
    run = event["workflow_run"]
    if (run["conclusion"] != "success" or run["event"] not in {"push", "pull_request"}
            or run["head_repository"]["full_name"] != repository
            or event["repository"]["full_name"] != repository):
        raise ValueError("Only successful same-repository CI may request promotion")
    if not re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]):
        raise ValueError("Invalid CI commit")
    return run["head_branch"], target_branch(run["head_branch"]), run["head_sha"]


def require_protection(repository, base):
    rules = api(f"/repos/{repository}/rules/branches/{base}?per_page=100")
    by_type = {rule["type"]: rule for rule in rules}
    if not {"pull_request", "required_status_checks", "deletion", "non_fast_forward"} <= by_type.keys():
        raise RuntimeError("Install the active branch rulesets before enabling automation")
    reviews = by_type["pull_request"]["parameters"]
    checks = by_type["required_status_checks"]["parameters"]
    contexts = {item["context"] for item in checks["required_status_checks"]}
    if (reviews["required_approving_review_count"] < 1
            or not reviews["dismiss_stale_reviews_on_push"]
            or not reviews["require_last_push_approval"]
            or not {"Backend CI", "Branch policy"} <= contexts
            or (base == "develop" and not checks["strict_required_status_checks_policy"])):
        raise RuntimeError("Required reviews or CI protections are missing")


def promote(event, repository):
    branch, base, sha = candidate(event, repository)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    metadata = api(f"/repos/{repository}")
    if not metadata["allow_auto_merge"] or not metadata["allow_merge_commit"]:
        raise RuntimeError("Enable auto-merge and merge commits in repository settings")
    require_protection(repository, base)
    ref = api(f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}")
    if ref["object"]["sha"] != sha:
        print("Skipping obsolete CI run: branch has advanced")
        return
    comparison = api(f"/repos/{repository}/compare/{quote(base, safe='')}...{quote(branch, safe='')}")
    if comparison["ahead_by"] == 0:
        print("Nothing to promote; branch is already included in the target")
        return
    owner = repository.split("/")[0]
    query = urlencode({"state": "open", "base": base, "head": f"{owner}:{branch}", "per_page": 100})
    prs = api(f"/repos/{repository}/pulls?{query}")
    if len(prs) > 1:
        raise RuntimeError("Ambiguous promotion PR")
    title = ("refactor: promote develop to prod" if base == "prod"
             else f"feat: integrate {branch.removeprefix('feature/')}")
    pr = prs[0] if prs else api(f"/repos/{repository}/pulls", "POST", {
        "base": base, "head": branch, "title": title,
        "body": f"Promote `{branch}` to `{base}` after required CI and human approvals.\n\n"
                f"Source CI commit: `{sha}`. Auto-merge does not bypass branch protections.",
        "maintainer_can_modify": False,
    })
    validate_pull_request(pr, repository)
    if pr["head"]["sha"] != sha or pr["draft"]:
        print("Skipping draft or changed PR")
        return
    if pr.get("auto_merge"):
        print(f"Auto-merge already enabled for PR #{pr['number']}")
        return
    api("/graphql", "POST", {
        "query": "mutation($id: ID!, $title: String!) { enablePullRequestAutoMerge(input: "
                 "{pullRequestId: $id, mergeMethod: MERGE, commitHeadline: $title}) "
                 "{pullRequest {number}} }",
        "variables": {"id": pr["node_id"], "title": title},
    })
    print(f"Auto-merge requested for PR #{pr['number']}; required approvals and checks remain enforced")


def main():
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_run":
        raise RuntimeError("Promotion is restricted to the trusted workflow_run handler")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    promote(event, os.environ["GITHUB_REPOSITORY"])


if __name__ == "__main__":
    main()
