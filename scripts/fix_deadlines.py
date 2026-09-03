"""One-off: set deadline_days based on network default."""
import json
from pathlib import Path

DEFAULTS = {"visa": 30, "mastercard": 45}

path = Path("corpus/reason_codes.json")
data = json.loads(path.read_text(encoding="utf-8"))

for entry in data:
    net = entry.get("network", "").lower()
    if net in DEFAULTS:
        entry["deadline_days"] = DEFAULTS[net]

path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"updated {len(data)} entries")