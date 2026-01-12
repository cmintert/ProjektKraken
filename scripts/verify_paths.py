import os
import sys

# Add src to pythonpath
sys.path.insert(0, os.path.abspath("."))

from src.core.paths import get_resource_path


def test_paths() -> None:
    print("Testing Path Resolution...")

    # Test 1: Check root assets
    assets_path = get_resource_path("assets")
    print(f"Resolved 'assets': {assets_path}")
    if os.path.exists(assets_path):
        print("  [OK] Path exists")
    else:
        print("  [FAIL] Path does not exist")

    # Test 2: Check themes.json
    theme_path = get_resource_path("themes.json")
    print(f"Resolved 'themes.json': {theme_path}")
    if os.path.exists(theme_path):
        print("  [OK] Path exists")
    else:
        print("  [FAIL] Path does not exist")

    # Test 3: Check marker icons logic (simulated)
    marker_path = get_resource_path(os.path.join("assets", "icons", "markers"))
    print(f"Resolved 'assets/icons/markers': {marker_path}")
    if os.path.exists(marker_path):
        print("  [OK] Path exists")
    else:
        print("  [FAIL] Path does not exist")


if __name__ == "__main__":
    test_paths()
