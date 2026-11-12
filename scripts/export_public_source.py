"""Export an exact, clean commit without Git history; never overwrite a destination."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = args.destination.resolve()
    checksum = destination.with_suffix(destination.suffix + ".sha256")
    try:
        if destination.is_relative_to(root):
            raise ValueError("The publication artifact must be outside the repository.")
        if destination.exists() or checksum.exists():
            raise ValueError("The artifact and checksum destinations must not exist.")
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
        if status:
            raise ValueError("Commit or remove all working-tree changes before export.")
        subprocess.run([sys.executable, "scripts/check_public_source.py"], cwd=root, check=True)
        # git archive exports one tree only. It does not carry refs, objects, or logs.
        with destination.open("xb") as output:
            try:
                subprocess.run(["git", "archive", "--format=zip", "--prefix=lpx-keepmorrow/", "HEAD"],
                               cwd=root, stdout=output, check=True)
            except BaseException:
                output.close()
                destination.unlink(missing_ok=True)
                raise
        with destination.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        with checksum.open("x", encoding="utf-8") as output:
            output.write(f"{digest}  {destination.name}\n")
        print(f"Created {destination.name}; SHA-256 {digest}.")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
