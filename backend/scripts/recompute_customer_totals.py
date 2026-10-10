"""
Recompute the running totals on `customers` (total_receipts, total_spent, total_wins,
total_winnings) from receipts + draws. The counters drift because they are only
adjusted on insert/delete; admin amount edits never reach them.

    python scripts/recompute_customer_totals.py           # dry run — prints the differences
    python scripts/recompute_customer_totals.py --apply   # write the corrected totals
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from supabase import create_client  # noqa: E402
from customer_totals import compute_customer_totals  # noqa: E402

FIELDS = ("total_receipts", "total_spent", "total_wins", "total_winnings")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write corrected totals")
    args = ap.parse_args()

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    customers = client.table("customers").select("id,phone_number," + ",".join(FIELDS)).execute().data
    changed = 0
    for c in customers:
        real = compute_customer_totals(client, c["phone_number"])
        diff = {f: (c.get(f), real[f]) for f in FIELDS
                if round(float(c.get(f) or 0), 2) != round(float(real[f]), 2)}
        if not diff:
            continue
        changed += 1
        print(f"{c['phone_number'][-4:]:>6}  " + "  ".join(f"{f}: {old} -> {new}" for f, (old, new) in diff.items()))
        if args.apply:
            client.table("customers").update({f: real[f] for f in diff}).eq("id", c["id"]).execute()
    print(f"\n{changed} of {len(customers)} customers {'updated' if args.apply else 'would change'}"
          + ("" if args.apply else " — re-run with --apply to write"))


if __name__ == "__main__":
    main()
