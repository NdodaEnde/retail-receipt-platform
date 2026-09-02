#!/usr/bin/env python3
"""
ontologyCoverage — the ontology auditing its own honesty.

For key declared properties, report what share of live rows actually carries a
value. A declared function is only as real as the coverage of what it reads:
this is the gate report for itemPriceIndex, paydayPulse, the suburb products, etc.

    python scripts/ontology_coverage.py
"""
import os
import sys
import urllib.request
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for line in open(ROOT / "backend" / ".env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
BASE = os.environ["SUPABASE_URL"].rstrip("/")
HEADERS = {"apikey": os.environ["SUPABASE_KEY"], "Authorization": "Bearer " + os.environ["SUPABASE_KEY"],
           "Prefer": "count=exact", "Range": "0-0"}


def count(path: str) -> int:
    req = urllib.request.Request(BASE + "/rest/v1/" + path, headers=HEADERS)
    return int(urllib.request.urlopen(req, timeout=20).headers.get("Content-Range").split("/")[1])


# (label, total_path, covered_path, functions gated by it)
CHECKS = [
    ("receipt.receipt_date", "receipts?select=id", "receipts?select=id&receipt_date=not.is.null",
     "paydayPulse, sassaGrantCycleImpact, streaks, today-only draw"),
    ("receipt.geocode_precision good", "receipts?select=id",
     "receipts?select=id&geocode_precision=in.(verified,rooftop,street,suburb)",
     "all suburb-bound geographic functions"),
    ("receipt.shop_id -> place_id branch", "receipts?select=id",
     "receipts?select=id,shops!inner(place_id)&shops.place_id=not.is.null",
     "shopMissions, coPatronage, branchContext"),
    ("receipt_item.canonical_name", "receipt_items?select=id", "receipt_items?select=id&canonical_name=not.is.null",
     "itemPriceIndex, promoLift, pricePremiumByBranch"),
    ("receipt_item.category (real)", "receipt_items?select=id",
     "receipt_items?select=id&category=not.is.null&category=not.in.(Non-product,Other)",
     "categorySpend, basketAffinity, shopMissions"),
    ("receipt_item.unit_price", "receipt_items?select=id", "receipt_items?select=id&unit_price=not.is.null",
     "itemPriceIndex"),
    ("shop.place_id", "shops?select=id", "shops?select=id&place_id=not.is.null",
     "branchContext, all branch-level products"),
    ("customer.registered", "customers?select=id", "customers?select=id&registration_status=eq.registered",
     "behavioralArchetypes, tiers"),
]

print(f"{'property':38} {'coverage':>12}   gates")
print("-" * 100)
worst = []
for label, total_p, covered_p, gates in CHECKS:
    total = count(total_p)
    covered = count(covered_p) if total else 0
    pct = 100.0 * covered / total if total else 0.0
    print(f"{label:38} {covered:>5}/{total:<5} {pct:5.1f}%  {gates}")
    worst.append((pct, label))
worst.sort()
print("\nBiggest gates first: " + " · ".join(f"{l} ({p:.0f}%)" for p, l in worst[:3]))
