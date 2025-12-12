import json
import os

try:
    with open("themes.json", "r") as f:
        data = json.load(f)
        print("JSON Load Success")
        fantasy = data.get("fantasy_mode", {})
        print(f"Fantasy H1: {fantasy.get('font_size_h1')}")

        dark = data.get("dark_mode", {})
        print(f"Dark H1: {dark.get('font_size_h1')}")

except Exception as e:
    print(f"JSON Load Failed: {e}")
