"""House-brand detection, pack sizes, type keys, GTIN — golden cases from real slips.

    python tests/test_brand_attributes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from item_normalizer import normalize_item, parse_pack_size, extract_gtin  # noqa: E402
from brand_registry import infer_chain, detect_house_brand  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


# ── chain inference ──────────────────────────────────────────────────────────
check(infer_chain("Checkers Hyper Bay West Hunters Retreat") == "Shoprite Group", "Checkers -> Shoprite Group")
check(infer_chain("SHOPRITE Brackenfell") == "Shoprite Group", "Shoprite -> Shoprite Group")
check(infer_chain("Pick n Pay Douglasdale") == "Pick n Pay Group", "PnP branch -> Pick n Pay Group")
check(infer_chain("Boxer Superstore Tembisa") == "Pick n Pay Group", "Boxer -> Pick n Pay Group")
check(infer_chain("Woolworths Douglasdale") == "Woolworths", "Woolworths")
check(infer_chain("SUPERSPAR Premier") == "SPAR", "SUPERSPAR -> SPAR")
check(infer_chain("Dis-Chem Claremont Pharmacy") == "Dis-Chem", "Dis-Chem")
check(infer_chain("Chicken Licken Bryanston") is None, "non-chain shop -> None")

# ── house-brand detection with the chain guard ───────────────────────────────
check(detect_house_brand("RITEBRAND WHITE SUGAR 2KG", "Shoprite Group")["tier"] == "value", "Ritebrand at Shoprite")
check(detect_house_brand("RITEBRAND WHITE SUGAR 2KG", None) is not None, "Ritebrand confirmed -> matches without chain")
check(detect_house_brand("SPAR WHITE BREAD 700G", "Shoprite Group") is None, "SPAR token at Shoprite -> NOT the SPAR brand")
check(detect_house_brand("SPAR WHITE BREAD 700G", "SPAR") is not None, "SPAR token at SPAR -> house brand")
check(detect_house_brand("QUALISAVE RICE 2KG", None) is None, "unverified entry needs chain corroboration")
check(detect_house_brand("QUALISAVE RICE 2KG", "Pick n Pay Group") is not None, "unverified entry matches at its own chain")
check(detect_house_brand("CLOVER FC MILK 2L", "Shoprite Group") is None, "national brand is not a house brand")

# ── full normalization: the apples-to-apples path ────────────────────────────
a = normalize_item("RITEBRAND WHITE SUGAR 2KG", chain="Shoprite Group")
b = normalize_item("NO NAME WHITE SUGAR 2.5KG", chain="Pick n Pay Group")
check(a["brand_type"] == "house" and a["brand_owner"] == "Shoprite Group", "Ritebrand sugar attributed")
check(b["brand_type"] == "house" and b["brand_owner"] == "Pick n Pay Group", "No Name sugar attributed")
check(a["type_key"] == b["type_key"] and a["type_key"], f"same type_key across chains: {a['type_key']!r}")
check((a["pack_size"], a["pack_unit"]) == (2000, "g"), "2KG -> 2000 g")
check((b["pack_size"], b["pack_unit"]) == (2500, "g"), "2.5KG -> 2500 g")

c = normalize_item("CRYSTAL VALLEY FULL CREAM MILK 1L", chain="Shoprite Group")
check(c["brand"] == "Crystal Valley" and c["brand_type"] == "house", "Crystal Valley = Shoprite dairy label")
check((c["pack_size"], c["pack_unit"]) == (1000, "ml"), "1L -> 1000 ml")

d = normalize_item("PNP UHT MILK FULL CREAM 1L", chain="Pick n Pay Group")
check(d["brand"] == "PnP" and d["brand_type"] == "house", "PNP prefix = PnP own brand")

e = normalize_item("CLOVER FRESH MILK 2L", chain="Pick n Pay Group")
check(e["brand"] == "Clover" and e["brand_type"] == "national", "Clover stays national")
check(c["type_key"] is not None and "milk" in c["type_key"], "milk type_key survives brand strip")

w = normalize_item("AVOCADO RITTER 200G", chain="Woolworths")
check(w["brand"] == "Woolworths" and w["brand_type"] == "house", "unbranded line at Woolworths -> own brand")
w2 = normalize_item("SIMBA CHIPS 120G", chain="Woolworths")
check(w2["brand"] == "Simba" and w2["brand_type"] == "national", "national brand at Woolworths stays national")

# ── pack sizes ───────────────────────────────────────────────────────────────
check(parse_pack_size("COKE 6X330ML") == (1980, "ml"), "multipack 6x330ml")
check(parse_pack_size("EGGS 18'S") == (18, "each"), "18'S -> 18 each")
check(parse_pack_size("EGGS 1 DOZ") == (12, "each"), "dozen -> 12")
check(parse_pack_size("LABELLO CARDED 4.8G HYDR") == (4.8, "g"), "4.8G lip balm")
check(parse_pack_size("2 @ 17.99") == (None, None), "qty@price is not a size")
check(parse_pack_size("BREAD") == (None, None), "no size printed -> None")
check(parse_pack_size("MILK 1,5LT") == (1500, "ml"), "comma decimal 1,5LT")

# ── GTIN ─────────────────────────────────────────────────────────────────────
check(extract_gtin("Item/GTIN 6001051005710") == "6001051005710", "labelled GTIN accepted (Dis-Chem style)")
check(extract_gtin("6001051005710") == "6001051005710", "bare 13-digit with SA prefix + valid check digit")
check(extract_gtin("6001051005711") is None, "bad check digit rejected")
check(extract_gtin("9991020348007") is None, "13 digits, non-SA prefix, unlabelled -> rejected")
check(extract_gtin("BREAD 700G") is None, "no number -> None")

# ── non-products stay excluded ───────────────────────────────────────────────
n = normalize_item("SUBTOTAL", chain="Shoprite Group")
check(n["category"] == "Non-product" and n["brand"] is None and n["type_key"] is None, "non-product gets no attributes")

print()
print("RESULT:", "ALL PASS" if not FAILS else f"{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
