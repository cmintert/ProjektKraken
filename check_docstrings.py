import ast
import os
import sys


def check_docstrings(root_dir):
    missing_docs = []
    total_items = 0
    documented_items = 0

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, root_dir)

            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=filepath)
                except SyntaxError:
                    print(f"Syntax error in {filepath}")
                    continue

            # Check module docstring
            total_items += 1
            if ast.get_docstring(tree):
                documented_items += 1
            else:
                missing_docs.append(f"[MODULE] {rel_path}")

            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    # Skip private methods/classes if desired, but user said "Always create google docstrings"
                    # We will flag everything for now.
                    name = node.name
                    total_items += 1
                    if ast.get_docstring(node):
                        documented_items += 1
                    else:
                        type_ = (
                            "CLASS" if isinstance(node, ast.ClassDef) else "FUNCTION"
                        )
                        missing_docs.append(
                            f"[{type_}] {rel_path}:{node.lineno} - {name}"
                        )

    return missing_docs, total_items, documented_items


if __name__ == "__main__":
    src_dir = "src"
    if len(sys.argv) > 1:
        src_dir = sys.argv[1]

    missing, total, documented = check_docstrings(src_dir)

    print(f"Checked {total} items in '{src_dir}'.")
    print(f"Documented: {documented} ({documented / total:.1%})")
    print(f"Missing: {total - documented}")
    print("\nMissing Docstrings:")
    for item in missing:
        print(item)
