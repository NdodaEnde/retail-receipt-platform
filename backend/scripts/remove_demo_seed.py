"""
Remove the January 2026 demo seed data from production, using the exact row IDs in
the backup file (written before anything is deleted):

    backups/demo_seed_backup_2026-10-10.json
      6 customers · 87 receipts · 261 receipt_items · 1 draw · 12 shops · 12 shop_aliases

    python scripts/remove_demo_seed.py           # dry run — shows what would be deleted
    python scripts/remove_demo_seed.py --apply   # delete, then verify the counts

Only rows listed in the backup are touched. To undo, re-insert them from the backup.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from supabase import create_client  # noqa: E402

BACKUP = ROOT.parent / "backups" / "demo_seed_backup_2026-10-10.json"
# children first; the schema also cascades, but explicit order keeps every step checkable
ORDER = ["receipt_items", "draws", "receipts", "shop_aliases", "shops", "customers"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete")
    args = ap.parse_args()

    backup = json.loads(BACKUP.read_text())
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    count = lambda t: client.table(t).select("id", count="exact").limit(1).execute().count  # noqa: E731

    # safety: every customer in the backup must still look like demo seed data
    for c in backup["customers"]:
        assert c["phone_number"].startswith("+") and c["created_at"].startswith("2026-01-06"), c

    before = {t: count(t) for t in ORDER}
    for t in ORDER:
        print(f"{t:14} {before[t]:5} rows, would delete {len(backup[t])}")
    if not args.apply:
        print("\nDry run — nothing deleted. Re-run with --apply to delete.")
        return

    for t in ORDER:
        ids = [r["id"] for r in backup[t]]
        for i in range(0, len(ids), 100):
            client.table(t).delete().in_("id", ids[i:i + 100]).execute()

    print()
    ok = True
    for t in ORDER:
        after, expected = count(t), before[t] - len(backup[t])
        ok &= after == expected
        print(f"{t:14} {before[t]:5} -> {after:5}  {'OK' if after == expected else f'MISMATCH (expected {expected})'}")
    print("\nDone — demo data removed." if ok else "\nCounts differ — check the rows above.")


if __name__ == "__main__":
    main()
