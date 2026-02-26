import os
import re
import sys


def get_imports(directory: str) -> list[str]:
    import_regex = re.compile(r"^(?:from|import)\s+([a-zA-Z0-9_]+)")
    all_imports = set()

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                with open(
                    os.path.join(root, file), "r", encoding="utf-8", errors="ignore"
                ) as f:
                    for line in f:
                        match = import_regex.match(line.strip())
                        if match:
                            all_imports.add(match.group(1))

    return sorted(list(all_imports))


if __name__ == "__main__":
    src_dir = os.path.abspath("src")
    if not os.path.exists(src_dir):
        print(f"Error: {src_dir} not found")
        sys.exit(1)

    imports = get_imports(src_dir)
    print("\n".join(imports))
