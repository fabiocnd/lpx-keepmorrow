"""Validate the distributable source contract without reading operational data.

This is a deterministic policy check, not a general secret scanner. Gitleaks and
manual privacy review provide separate evidence. Only Git-tracked files belong
to the source inventory; private history is never part of the published ZIP.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib

BLOCKED_ROOTS = frozenset({".git", ".venv", "node_modules", "local-data", "local-archives",
                          "local-restores", "local-consent", "local-service", "service-state"})
BLOCKED_PATHS = ("docs/provenance/", "docs/research/company-and-creator.md",
                 ".github/workflows/source-review.yml", ".github/workflows/prepare-source.yml",
                 ".github/source-preparation.patch.b64")


def path_problem(path: str, mode: str = "100644") -> str | None:
    """Reject unsafe Git entries and known private material; inspect no file bytes."""
    value = PurePosixPath(path)
    if value.is_absolute() or ".." in value.parts or "\\" in path or not value.parts:
        return "unsafe relative path"
    if mode not in {"100644", "100755"}:
        return "only regular source files are allowed"
    folded = path.casefold()
    if any(part.casefold() in BLOCKED_ROOTS for part in value.parts) or any(folded.startswith(p) for p in BLOCKED_PATHS):
        return "private or temporary preparation material"
    name = value.name.casefold()
    if (name == ".env" or name.startswith(".env.")) and name != ".env.example":
        return "environment credentials must not be distributed"
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db")):
        return "key or operational database extension"
    if re.search(r"\.(?:sqlite3?|db)-", name):
        return "database sidecar"
    return None


def tracked_files(root: Path) -> list[tuple[str, str]]:
    """Read an unambiguous, NUL-delimited Git index; reject unresolved merges."""
    result = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=root,
                            capture_output=True, check=True)
    entries = []
    for record in result.stdout.decode("utf-8").split("\0"):
        if not record:
            continue
        info, path = record.split("\t", 1)
        mode, _, stage = info.split()
        if stage != "0":
            raise ValueError("Resolve the merge before preparing a source release.")
        entries.append((path, mode))
    return entries


def metadata_problems(root: Path) -> list[str]:
    """Check source-license declarations and exact packaged policy copies."""
    problems: list[str] = []
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    package = json.loads((root / "ui/chatgpt/package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "ui/chatgpt/package-lock.json").read_text(encoding="utf-8"))
    if any(value != "Apache-2.0" for value in (
        project.get("license"), package.get("license"), lock["packages"][""].get("license"))):
        problems.append("Root, Python, and UI license metadata must agree on Apache-2.0.")
    if package.get("version") != project["version"] or lock["packages"][""].get("version") != project["version"]:
        problems.append("Python and UI release versions must agree.")
    if set(project.get("license-files", [])) != {"LICENSE", "NOTICE"}:
        problems.append("Python distributions must include LICENSE and NOTICE.")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    if "Version 2.0, January 2004" not in license_text or "END OF TERMS AND CONDITIONS" not in license_text:
        problems.append("The Apache-2.0 license text is missing or incomplete.")
    module = ast.parse((root / "src/keepmorrow/consent.py").read_text(encoding="utf-8"))
    versions = {node.targets[0].id: ast.literal_eval(node.value) for node in module.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in {"CURRENT_TERMS_VERSION", "CURRENT_PRIVACY_VERSION"}}
    for filename, key in (("terms-of-use.md", "CURRENT_TERMS_VERSION"),
                          ("privacy-notice.md", "CURRENT_PRIVACY_VERSION")):
        canonical = (root / "legal" / filename).read_bytes()
        if canonical != (root / "src/keepmorrow/policies" / filename).read_bytes():
            problems.append(f"Packaged policy differs from canonical bytes: {filename}.")
        if f"`{versions[key]}`".encode() not in canonical:
            problems.append(f"Declared policy version differs from code: {filename}.")
    notices = (root / "ui/chatgpt/THIRD-PARTY-NOTICES.txt").read_bytes()
    if notices != (root / "src/keepmorrow/integrations/chatgpt/assets/THIRD-PARTY-NOTICES.txt").read_bytes():
        problems.append("Bundled third-party notice copies differ.")
    if b"Project source: Apache-2.0" not in notices:
        problems.append("The generated notices have stale project-license metadata.")
    return problems


def workflow_problems(text: str) -> list[str]:
    """Enforce a narrow Actions policy; GitHub remains the YAML/schema validator."""
    problems = []
    if re.search(r"^\s*pull_request_target\s*:", text, re.M):
        problems.append("Privileged pull_request_target execution is not allowed.")
    for reference in re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", text, re.M):
        if reference.startswith("./"):
            continue
        if not re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", reference):
            problems.append("External Actions must use full commit SHAs.")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Require the exact v<project version> release tag.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        entries = tracked_files(root)
        problems = [f"{path}: {problem}" for path, mode in entries
                    if (problem := path_problem(path, mode))]
        problems.extend(metadata_problems(root))
        for path, _ in entries:
            if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
                problems.extend(f"{path}: {p}" for p in workflow_problems((root / path).read_text()))
        if args.tag:
            version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
            if args.tag != "v" + version:
                problems.append("The release tag does not match the package version.")
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(f"Source contract passed: {len(entries)} regular tracked files.")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Source validation could not complete: {type(error).__name__}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
