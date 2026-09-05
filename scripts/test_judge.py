import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import json
from src.eval.judge import judge_letter

letter = """Dear Mastercard Chargeback Department,
Dispute ID disp_2004, transaction txn_1004, amount 12499.0 INR, cardholder Priya Nair.
FedEx tracking TRK4504793184 shows delivery on 2026-08-13.
The cardholder confirmed receipt via email."""

out = judge_letter(letter, "4855", "mastercard", "present: proof_of_delivery\nmissing: signed_pod")
print(json.dumps(out, indent=2))
