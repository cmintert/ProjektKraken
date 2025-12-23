import datetime
import subprocess
from pathlib import Path


def get_git_logs():
    """Get git log messages since the last tag or start of project."""
    try:
        # Get all logs with format "sha|subject|body"
        result = subprocess.run(
            ["git", "log", "--pretty=format:%h|%s"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.splitlines()
    except Exception as e:
        print(f"Error fetching git logs: {e}")
        return []


def parse_logs(logs):
    """Parse logs into categories based on conventional commit prefixes."""
    categories = {
        "Added": [],
        "Fixed": [],
        "Changed": [],
        "Documentation": [],
        "Internal": [],
    }

    # Mapping prefixes to categories
    mapping = {
        "feat": "Added",
        "add": "Added",
        "fix": "Fixed",
        "bug": "Fixed",
        "change": "Changed",
        "refactor": "Changed",
        "docs": "Documentation",
        "chore": "Internal",
        "ci": "Internal",
        "test": "Internal",
    }

    for line in logs:
        if not line:
            continue
        sha, subject = line.split("|", 1)

        # Determine category
        found = False
        lower_subject = subject.lower()
        for prefix, cat in mapping.items():
            if lower_subject.startswith(prefix):
                categories[cat].append(subject)
                found = True
                break

        if not found:
            categories["Internal"].append(subject)

    return categories


def generate_markdown(categories, version="Development"):
    """Generate the markdown content for the changelog."""
    date_str = datetime.date.today().isoformat()
    lines = [f"## [{version}] - {date_str}"]

    for cat, items in categories.items():
        if items:
            lines.append(f"### {cat}")
            # Use a set to avoid duplicates in the same category
            unique_items = sorted(list(set(items)))
            for item in unique_items:
                lines.append(f"- {item}")
            lines.append("")

    return "\n".join(lines)


def main():
    """Main execution entry point."""
    print("Generating automated changelog...")
    logs = get_git_logs()
    if not logs:
        print("No logs found.")
        return

    categories = parse_logs(logs)

    # For now, we'll just prepend the new development changes to the existing file
    # Or overwrite if it's the first time.
    changelog_path = Path("docs/CHANGELOG.md")

    new_content = generate_markdown(categories)

    # Header for the file
    header = (
        "# Changelog\n\nAll notable changes to this project "
        "will be documented in this file.\n\n"
    )

    # In a real scenario, we might want to compare with existing entries to avoid
    # duplication but for a simple automation, we'll just write the full history
    # grouped by type.

    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(new_content)
        f.write("\n\n*This changelog was automatically generated.*")

    print(f"Changelog generated at {changelog_path}")


if __name__ == "__main__":
    main()
