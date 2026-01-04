import re
import subprocess
import sys
import tomllib  # Requires Python 3.11+
from pathlib import Path
from typing import Any

# Constants
ROOT_DIR = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
CONSTANTS_PATH = ROOT_DIR / "src" / "app" / "constants.py"
CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_result(label: str, value: Any, status: str = "info") -> None:
    color = RESET
    if status == "success":
        color = GREEN
    elif status == "error":
        color = RED
    elif status == "warning":
        color = YELLOW

    print(f"{label:<30} {color}{value}{RESET}")


def get_pyproject_version() -> str:
    try:
        with open(PYPROJECT_PATH, "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception as e:
        return f"Error reading pyproject.toml: {e}"


def get_constant_version() -> str:
    try:
        content = CONSTANTS_PATH.read_text(encoding="utf-8")
        # Look for WINDOW_TITLE = "Project Kraken - v0.5.0 (Beta)"
        match = re.search(r'WINDOW_TITLE\s*=\s*".*v(\d+\.\d+\.\d+).*?"', content)
        if match:
            return match.group(1)
        return "Version not found in WINDOW_TITLE"
    except Exception as e:
        return f"Error reading constants.py: {e}"


def check_changelog(current_version: str) -> dict[str, Any]:
    try:
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        has_unreleased = "## [Unreleased]" in content

        # Check if current version is in changelog
        header_pattern = f"## \\[{re.escape(current_version)}\\]"
        has_current_version = re.search(header_pattern, content) is not None

        return {
            "has_unreleased": has_unreleased,
            "has_current_version": has_current_version,
        }
    except Exception as e:
        return {"error": str(e)}


def check_git_status() -> dict[str, Any]:
    try:
        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True
        )
        is_clean = not result.stdout.strip()

        # Check current tag
        tag_result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
        )
        current_tag = tag_result.stdout.strip() if tag_result.returncode == 0 else None

        return {"clean": is_clean, "tag": current_tag}
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    print(f"{BOLD}=== Project Kraken Release Status Checker ==={RESET}\n")

    errors = []

    # 1. Version Check
    v_toml = get_pyproject_version()
    v_const = get_constant_version()

    match = v_toml == v_const
    print_result("Version (pyproject.toml):", v_toml)
    print_result("Version (constants.py):", v_const, "success" if match else "error")

    if not match:
        errors.append("Version Mismatch: pyproject.toml and constants.py do not match.")

    current_version = v_toml

    # 2. Changelog Check
    cl_status = check_changelog(current_version)
    if "error" in cl_status:
        print_result("Changelog:", cl_status["error"], "error")
        errors.append("Changelog not readable.")
    else:
        has_unreleased = cl_status["has_unreleased"]
        has_current = cl_status["has_current_version"]

        print_result(
            "Changelog [Unreleased]:",
            "Present" if has_unreleased else "Missing",
            "info" if has_unreleased else "warning",
        )
        print_result(
            f"Changelog [{current_version}]:",
            "Present" if has_current else "Not found",
            "success" if has_current else "info",
        )

    # 3. Git Status
    git_status = check_git_status()
    if "error" in git_status:
        print_result("Git:", git_status["error"], "error")
    else:
        is_clean = git_status["clean"]
        tag = git_status["tag"]

        print_result(
            "Git Working Tree:",
            "Clean" if is_clean else "Dirty (Uncommitted changes)",
            "success" if is_clean else "warning",
        )
        print_result("Current Git Tag:", tag if tag else "None", "info")

    print("\n" + "-" * 40 + "\n")

    # Final Analysis
    if errors:
        print(f"{RED}❌ Issues Found:{RESET}")
        for err in errors:
            print(f"- {err}")
        print("\nFix these issues before releasing.")
        sys.exit(1)

    # Logic for "Where am I?"
    if not git_status.get("clean"):
        print(f"{YELLOW}🚧 Working Directory Dirty{RESET}")
        print(
            "You have uncommitted changes. \n-> Commit them or stash them before "
            "releasing."
        )
    elif git_status.get("tag") == f"v{current_version}":
        print(f"{GREEN}✅ Released{RESET}")
        print(
            f"Current commit is tagged as v{current_version}. You are sitting on a "
            "release."
        )
    elif cl_status.get("has_unreleased"):
        print(f"{GREEN}🛠️  Development Mode{RESET}")
        print(f"Version is {current_version}. Changelog has [Unreleased] section.")
        print(
            "-> Continue developing. When ready, rename [Unreleased] to next version "
            "to\nstart release."
        )
    elif not cl_status.get("has_unreleased") and not cl_status.get(
        "has_current_version"
    ):
        print(f"{YELLOW}⚠️  State unclear{RESET}")
        print("Changelog is missing sections.")
    else:
        print(f"{GREEN}🚀 Ready to Release?{RESET}")
        print(f"Versions match ({current_version}). Git is clean.")
        has_entry = "Yes" if cl_status.get("has_current_version") else "No"
        print(
            f"-> If you want to release {current_version}, ensure Changelog has entry "
            f"for it (currently {has_entry})."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
