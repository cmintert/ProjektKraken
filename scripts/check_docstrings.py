import ast
import os
import sys
from typing import List, Tuple


def check_file(filepath: str, root_dir: str) -> Tuple[List[str], int, int]:
    missing_docs = []
    total = 0
    documented = 0
    rel_path = os.path.relpath(filepath, root_dir)

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError:
            print(f"Syntax error in {filepath}")
            return [], 0, 0

    # Check module docstring
    total += 1
    if ast.get_docstring(tree):
        documented += 1
    else:
        missing_docs.append(f"[MODULE] {rel_path}")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            total += 1
            if ast.get_docstring(node):
                documented += 1
            else:
                type_ = "CLASS" if isinstance(node, ast.ClassDef) else "FUNCTION"
                missing_docs.append(f"[{type_}] {rel_path}:{node.lineno} - {name}")

    return missing_docs, total, documented


def check_docstrings(path: str) -> Tuple[List[str], int, int]:
    all_missing = []
    total_items = 0
    documented_items = 0

    # Determine files to process
    files_to_check = []
    root_dir = path

    if os.path.isfile(path):
        files_to_check.append(path)
        root_dir = os.path.dirname(path)
    else:
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                if filename.endswith(".py"):
                    files_to_check.append(os.path.join(dirpath, filename))

    for filepath in files_to_check:
        missing, count, doc_count = check_file(filepath, root_dir)
        all_missing.extend(missing)
        total_items += count
        documented_items += doc_count

    return all_missing, total_items, documented_items


if __name__ == "__main__":
    default_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    paths_to_check = sys.argv[1:] if len(sys.argv) > 1 else [default_src]

    grand_missing = []
    grand_total = 0
    grand_documented = 0

    print(f"Checking docstrings in: {', '.join(paths_to_check)}...\n")

    for path in paths_to_check:
        missing, total, documented = check_docstrings(path)
        grand_missing.extend(missing)
        grand_total += total
        grand_documented += documented

    print(f"Checked {grand_total} items.")
    if grand_total > 0:
        print(f"Documented: {grand_documented} ({grand_documented / grand_total:.1%})")
    else:
        print("Documented: 0 (0.0%)")

    print(f"Missing: {grand_total - grand_documented}")
    if grand_missing:
        print("\nMissing Docstrings:")
        for item in grand_missing:
            print(item)
