"""Bootstrap reviewed public-repository controls using an operator's GitHub CLI.

Default mode only prints the requested configuration. --apply requires an already
public destination and successful aggregate checks at both branch heads. It never
changes visibility, creates repositories, accesses tokens, or publishes history.
Operations are not transactional: an API failure is reported, not hidden.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

TARGET = "fabiocnd/keepmorrow"
CHECKS = ["CI required", "Security required"]


def api(method: str, path: str, body: dict | None = None) -> object:
    """Delegate authentication to gh; keep credentials out of arguments and output."""
    command = ["gh", "api", "--method", method, path]
    if body is not None:
        command.extend(["--input", "-"])
    completed = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                               text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"GitHub rejected {method} {path}; no completion claim is valid.")
    return json.loads(completed.stdout) if completed.stdout.strip() else None


def contains(actual: object, expected: object) -> bool:
    """Compare expected configuration fields without depending on API-added URLs."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value)
                                               for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and all(value in actual for value in expected)
    return actual == expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reviews", type=int, choices=(0, 1), default=0,
                        help="Use 1 only when an independent maintainer can approve PRs.")
    args = parser.parse_args()
    protection = {
        "required_status_checks": {"strict": True, "contexts": CHECKS},
        "enforce_admins": True,
        "required_pull_request_reviews": {"dismiss_stale_reviews": True,
                                          "require_code_owner_reviews": False,
                                          "required_approving_review_count": args.reviews},
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_conversation_resolution": True,
    }
    settings = {"allow_squash_merge": True, "allow_merge_commit": False,
                "allow_rebase_merge": False, "allow_auto_merge": False,
                "allow_update_branch": True, "delete_branch_on_merge": False,
                "security_and_analysis": {"secret_scanning": {"status": "enabled"},
                                          "secret_scanning_push_protection": {"status": "enabled"}}}
    if not args.apply:
        print(json.dumps({"repository": TARGET, "repository_settings": settings,
                          "branch_protection": protection,
                          "also_enable": ["vulnerability-alerts", "automated-security-fixes",
                                          "private-vulnerability-reporting"],
                          "default_workflow_permissions": "read"}, indent=2))
        return 0
    try:
        repository = api("GET", f"repos/{TARGET}")
        if not isinstance(repository, dict) or repository.get("private") is not False:
            raise RuntimeError("The separate reviewed destination must already be public.")
        if not repository.get("permissions", {}).get("admin"):
            raise RuntimeError("An authenticated repository administrator is required.")
        branches = {}
        for branch in ("main", "develop"):
            info = api("GET", f"repos/{TARGET}/branches/{branch}")
            if not isinstance(info, dict):
                raise RuntimeError("Branch metadata is missing.")
            runs = api("GET", f"repos/{TARGET}/commits/{info['commit']['sha']}/check-runs?per_page=100")
            latest = {}
            for run in sorted(runs["check_runs"], key=lambda item: item["id"], reverse=True):
                if run["name"] not in latest:
                    latest[run["name"]] = run
            if any(name not in latest or latest[name].get("conclusion") != "success" for name in CHECKS):
                raise RuntimeError(f"Both required checks must pass at the exact {branch} head.")
            # Do not replace existing protections, which may be stronger or unrelated.
            if info.get("protected"):
                raise RuntimeError(f"{branch} is already protected; review existing rules manually.")
            branches[branch] = info
        api("PATCH", f"repos/{TARGET}", settings)
        for endpoint in ("vulnerability-alerts", "automated-security-fixes", "private-vulnerability-reporting"):
            api("PUT", f"repos/{TARGET}/{endpoint}")
        api("PUT", f"repos/{TARGET}/actions/permissions/workflow",
            {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False})
        for branch in branches:
            api("PUT", f"repos/{TARGET}/branches/{branch}/protection", protection)
            observed = api("GET", f"repos/{TARGET}/branches/{branch}/protection")
            required = {"required_status_checks": {"strict": True, "contexts": CHECKS},
                        "enforce_admins": {"enabled": True},
                        "allow_force_pushes": {"enabled": False},
                        "allow_deletions": {"enabled": False}}
            if not contains(observed, required):
                raise RuntimeError(f"Could not verify the expected protection on {branch}.")
        observed = api("GET", f"repos/{TARGET}")
        if not contains(observed, {"security_and_analysis": settings["security_and_analysis"]}):
            raise RuntimeError("Could not verify native secret scanning and push protection.")
        print("Branch gates and native secret-scanning settings were applied and read back.")
        print("Security-update and private-reporting enable requests succeeded; inspect their UI status.")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        print("Earlier successful API changes may remain. Inspect them before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
