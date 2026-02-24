import json
import os

# Check current dir to decide path
path = "data/merged.json" if os.path.exists("data/merged.json") else "../recc-engine/data/merged.json"

if not os.path.exists(path):
    print(f"Cannot find {path}")
    exit(1)

with open(path, "r") as f:
    data = json.load(f)
    
found = False
for m in data:
    if m.get("title") == "Parasite" and m.get("release_date", "").startswith("2019"):
        print(f"Found Parasite (2019): ID {m['id']}")
        found = True

if not found:
    print("Parasite (2019) NOT found in merged.json")