"""
A customer's totals computed from the source tables — not from the running counters
on `customers`, which drift (they are +/- adjusted on insert/delete, never on edits).

    receipts / spent : receipts that are not 'rejected' (same rule as customer_spend_summary)
    wins / winnings  : completed draws this customer won

Used by the WhatsApp BALANCE command and scripts/recompute_customer_totals.py.
"""
from typing import Dict


def _rows(query):
    out, start = [], 0
    while True:
        batch = query.range(start, start + 999).execute().data or []
        out += batch
        if len(batch) < 1000:
            return out
        start += 1000


def compute_customer_totals(client, phone: str) -> Dict:
    bare = phone.lstrip("+")
    receipts = _rows(client.table("receipts").select("amount,status")
                     .in_("customer_phone", [bare, f"+{bare}"]).neq("status", "rejected"))
    draws = _rows(client.table("draws").select("prize_amount")
                  .in_("winner_customer_phone", [bare, f"+{bare}"]).eq("status", "completed"))
    return {
        "total_receipts": len(receipts),
        "total_spent": round(sum(float(r["amount"] or 0) for r in receipts), 2),
        "total_wins": len(draws),
        "total_winnings": round(sum(float(d["prize_amount"] or 0) for d in draws), 2),
    }
