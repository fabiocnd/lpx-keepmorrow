"""Copy the canonical reviewed draft bytes into the distributable Python package."""

from pathlib import Path
import shutil


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "src/keepmorrow/policies"
    target.mkdir(exist_ok=True)
    for name in ("terms-of-use.md", "privacy-notice.md"):
        shutil.copyfile(root / "legal" / name, target / name)


if __name__ == "__main__":
    main()
