"""
Extraction verifier — the LLM proposes, the receipt's structure verifies.

LandingAI's schema extraction reads context well but will happily fill a field
with *something* (a store number under "Store Cash." became a postal code and sent
a Douglasdale receipt to Koster). Rules are poor extractors (a bare 4-digit scan
had ~4% precision on real receipts) but excellent verifiers. So:

  * every proposed field must be corroborated by the OCR text, in the right kind of
    line (an address block, not a transaction row, not a phone number);
  * absence is the normal answer — nothing is invented;
  * every decision is recorded in `evidence` so it can be audited and tested.

Public entry point: verify_extraction(raw_text, proposal) -> dict
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── vocabulary ───────────────────────────────────────────────────────────────

# Words that mark a transaction / card-slip row. A 4-digit number on such a row,
# or directly beneath a header row made of these words, is never a postcode.
TRANSACTION_WORDS = re.compile(
    r"\b(store|cash|till|trans|transaction|txn|batch|terminal|term|auth|approval|"
    r"date|time|seq|ref|rrn|stan|mid|tid|aid|invoice|inv|receipt|slip|cashier|"
    r"operator|clerk|card|acc|account|pan|app|apv|resp|response|code|no|nr|number|"
    r"reg|register|pos|doc|ticket|order|table|guest|covers|server|id|attendant|"
    r"staff|employee|shift|chk|check|tbl|gst)\b", re.I)

# Words that mark an address line. Street types, premises and SA cities.
PLACE_WORDS = re.compile(
    r"\b(cnr|corner|c/o|street|str|st|road|rd|avenue|ave|drive|dr|blvd|boulevard|"
    r"lane|ln|crescent|cres|way|close|place|pl|mall|centre|center|shop|shops|"
    r"shopping|plaza|square|park|estate|village|precinct|arcade|complex|building|"
    r"hotel|lodge|waterfront|harbour|farm|club|stadium|airport|station|hospital|"
    r"university|campus|office park|centre|junction|crossing|gardens|heights|"
    r"cape town|johannesburg|joburg|pretoria|durban|gqeberha|port elizabeth|"
    r"east london|bloemfontein|polokwane|nelspruit|mbombela|kimberley|rustenburg|"
    r"pietermaritzburg|sandton|midrand|centurion|soweto|umhlanga|stellenbosch|"
    r"bellville|durbanville|randburg|roodepoort|boksburg|benoni|germiston|alberton|"
    r"mthatha|george|knysna|paarl|somerset west|kuils river|brackenfell|constantia|"
    r"claremont|rondebosch|wynberg|tokai|fourways|bryanston|douglasdale|rosebank|"
    r"parktown|melville|greenside|hillbrow|braamfontein|edenvale|kempton park|"
    r"witpoort|kyalami|honeydew|northcliff|walmer|newton park|summerstrand)\b", re.I)

# Marketing / legal footer lines that mention places but are not addresses.
MARKETING = re.compile(
    r"thank you|thanks for|welcome|shopping at|served by|proof of purchase|customer care|"
    r"care line|call us|visit us|www\.|http|follow us|keep your slip|"
    r"terms and conditions|t&c|\(pty\)|reg\.? ?no|registration|vat no|vat reg|"
    r"exchange|returns policy|refund", re.I)

# '0' or '+27' then nine more digits, with spaces/brackets/dashes/dots between.
# Metro cities: fine as address context, useless for identifying a *branch*.
METRO_CITIES = {"cape town", "johannesburg", "joburg", "pretoria", "durban", "gqeberha",
                "port elizabeth", "east london", "bloemfontein", "polokwane", "nelspruit",
                "mbombela", "kimberley", "pietermaritzburg", "sandton", "jhb", "south africa"}

SA_PHONE = re.compile(r"(?<![\d/])\(?\s*(?:\+?27|0)[\s\(\)\-\.]*(?:\d[\s\(\)\-\.]*){9}(?![\d/])")
# Share-call / toll-free lines are customer-care numbers, never a branch's own.
# (087 numbers are ordinary VoIP lines used by many retailers — keep them.)
TOLL_FREE_PREFIXES = ("0800", "0860", "0861")
PHONE_LINE_SKIP = re.compile(r"customer care|care line|call centre|helpline|hotline|\bfax\b|toll ?free|share ?call", re.I)

# OCR sometimes returns a transactional word as the "shop name" (e.g. a card slip
# whose first line is "Purchase"). These are never shops.
NON_SHOP_NAMES = {
    "purchase", "total", "subtotal", "tax invoice", "invoice", "receipt", "cash",
    "card", "eft", "change", "vat", "sale", "payment", "approved", "transaction",
    "customer copy", "merchant copy", "till slip", "unknown", "unknown shop",
    "customer receipt", "tax receipt", "slip", "thank you", "welcome", "logo",
}


# ── text normalisation ───────────────────────────────────────────────────────

def strip_markup(text: str) -> str:
    """Remove LandingAI markup (<::LOGO: ...::>), anchors and HTML tags."""
    text = re.sub(r"<::[^>]*?::>", " ", text or "", flags=re.S)
    text = re.sub(r"<::[A-Za-z_]+:\s*", "", text)
    text = re.sub(r"<a id=[^>]*></a>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text


def plain_lines(raw_text: str) -> List[str]:
    """
    Receipt as a list of visual lines. Table rows become one line with cells
    joined by ' | ' so column structure survives (header row above value row).
    """
    text = strip_markup(raw_text)
    text = re.sub(r"</tr>", "\n", text, flags=re.I)
    text = re.sub(r"</td>\s*<td[^>]*>", " | ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip(" |")
        if line:
            lines.append(line)
    return lines


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


# ── line classification ──────────────────────────────────────────────────────

def is_column_header(line: str) -> bool:
    """'Store Cash. Till Date Time' — words only, ≥2 transaction words, no long numbers."""
    if re.search(r"\d{3,}", line):
        return False
    words = re.findall(r"[A-Za-z]+", line)
    if len(words) < 2:
        return False
    hits = sum(1 for w in words if TRANSACTION_WORDS.fullmatch(w))
    return hits >= 2 and hits >= len(words) * 0.5


def is_transaction_context(lines: List[str], i: int) -> bool:
    """A value row of a transaction table, or a labelled transaction field."""
    line = lines[i]
    if is_column_header(line):
        return True
    if i > 0 and is_column_header(lines[i - 1]):
        return True  # value row beneath 'Store Cash. Till Date Time'
    # 'Store Cash.: 0348 50006064' / 'Batch: 1234' / 'Auth 0348'
    if re.search(r"\d", line) and TRANSACTION_WORDS.search(line) and not PLACE_WORDS.search(line):
        return True
    return False


ITEM_LINE = re.compile(r"(\d+[.,]\d{2}\s*#?\s*$)|(\|\s*R?\s*\d+[.,]\d{2})|(\d+\s*@\s*\d)")

def is_address_line(line: str) -> bool:
    if MARKETING.search(line):
        return False
    if ITEM_LINE.search(line):
        return False  # a priced line item, however street-like its abbreviations
    if len(_digits(line)) > max(8, len(line) * 0.6):
        return False  # mostly numbers: barcodes, references
    return bool(PLACE_WORDS.search(line))


def find_address_blocks(lines: List[str]) -> List[Dict]:
    """
    Runs of address-like lines. 95% of SA slips carry the address in the header;
    restaurant POS slips print a legal footer like '7848 Cape Town'. Both count.
    """
    n = len(lines)
    idx = [i for i, l in enumerate(lines) if is_address_line(l) and not is_transaction_context(lines, i)]
    # SA convention: the postcode may sit alone on the line under the suburb
    # ("Douglasdale JHB" / "2191"), sometimes with a province code ("7536 WC").
    for i in list(idx):
        j = i + 1
        if j < n and re.fullmatch(r"\d{4}(\s+[A-Z]{2})?", lines[j].strip()) and j not in idx:
            idx.append(j)
    idx.sort()
    blocks, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > 2:
            blocks.append(cur); cur = []
        cur.append(i)
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        # extend a header block upward to include a suburb/phone line just above it
        start, end = b[0], b[-1]
        # extend upward over at most two short, digit-free lines (a suburb or
        # branch-name line like "Fourways" printed above the street)
        steps = 0
        while start > 0 and steps < 2:
            prev = lines[start - 1]
            if is_transaction_context(lines, start - 1) or MARKETING.search(prev) \
                    or re.search(r"\d", prev) or len(prev.split()) > 4 \
                    or not re.search(r"[A-Za-z]{3,}", prev):
                break
            start -= 1; steps += 1
        out.append({
            "start": start, "end": end,
            "lines": lines[start:end + 1],
            "position": "header" if (start / max(n, 1)) < 0.34 else "footer",
        })
    return out


# ── field verifiers ──────────────────────────────────────────────────────────

def sanitize_shop_name(shop_name: Optional[str]) -> Optional[str]:
    """Drop non-shop 'names' (markup, transactional words, no letters)."""
    if not shop_name:
        return None
    shop_name = re.sub(r"\s*\*{2,}\s*", " ", strip_markup(shop_name)).strip(" >:*\"'#-_")
    if not shop_name:
        return None
    cleaned = re.sub(r"[^a-z0-9 ]", "", shop_name.lower()).strip()
    if not cleaned or cleaned in NON_SHOP_NAMES or not re.search(r"[a-z]", cleaned):
        return None
    # Logo/version strings ("Ver 2.1", "V2.0")
    if re.fullmatch(r"(ver|version|v)\s*\d+(\.\d+)*", cleaned):
        return None
    return shop_name


def verify_phone(candidate: Optional[str], lines: List[str]) -> Tuple[Optional[str], str]:
    """
    Return a normalised SA number (+27XXXXXXXXX) that is printed on the slip and
    is not a toll-free / customer-care line. The LLM's candidate is tried first,
    then the header lines are scanned (phones are printed with the address).
    """
    text_digits = _digits(" ".join(lines))

    def normalise(d: str) -> Optional[str]:
        if d.startswith("27") and len(d) == 11:
            d = "0" + d[2:]
        if len(d) != 10 or not d.startswith("0"):
            return None
        if d.startswith(TOLL_FREE_PREFIXES):
            return None
        if d[1] not in "12345678":  # SA area/mobile codes are 01x–08x
            return None
        return "+27" + d[1:]

    def printed(d: str) -> bool:
        local = d[1:] if d.startswith("0") else d
        return local in text_digits

    if candidate:
        d = _digits(re.sub(r"\(0\)", "", candidate))
        num = normalise(d)
        if num and printed(d):
            return num, "phone: proposal corroborated by text"
        reason = "phone: proposal rejected (" + ("toll-free/care line" if d.startswith(TOLL_FREE_PREFIXES) else "not printed / not an SA number") + ")"
    else:
        reason = "phone: none proposed"

    for i, line in enumerate(lines[: max(12, len(lines) // 3)]):
        if PHONE_LINE_SKIP.search(line):
            continue
        scan = re.sub(r"(?i)vat\s*(?:no\.?|reg\.?|number|:|#)*\s*:?\s*\d(?:\s?\d){8,9}", " ", line)  # drop the 10-digit VAT number only
        if TRANSACTION_WORDS.search(scan) and not re.search(r"(?i)\b(tel|phone|cell|telephone|contact)\b", scan):
            continue
        for m in SA_PHONE.finditer(scan):
            d = _digits(m.group(0))
            num = normalise(d if d.startswith("0") else "0" + d[-9:])
            if num:
                return num, f"phone: found on header line {i}"
    return None, reason


def verify_postal_code(candidate: Optional[str], source_line: Optional[str],
                       lines: List[str], blocks: List[Dict]) -> Tuple[Optional[str], str]:
    """
    A postcode is accepted only if the exact 4-digit token appears on a line that
    is inside an address block, is not a transaction row (or the row under a
    transaction header), carries fewer than 8 digits in total (phone guard), and
    sits next to a place word. Otherwise: None.
    """
    block_lines = {i for b in blocks for i in range(b["start"], b["end"] + 1)}

    def qualifies(i: int, code: str) -> Optional[str]:
        line = lines[i]
        if i not in block_lines:
            return "not on an address line"
        if is_transaction_context(lines, i):
            return "transaction row"
        if len(_digits(line)) >= 8:
            return "phone/reference line"
        if not re.search(rf"(?<!\d){code}(?!\d)", line):
            return "token not on line"
        if not re.search(r"[A-Za-z]{3,}", line) and line.strip() != code:
            return "no place word"
        if re.search(rf"{code}[.,]\d|R\s*{code}", line):
            return "looks like a price"
        return None

    if candidate:
        code = _digits(candidate)
        if not re.fullmatch(r"\d{4}", code) or code == "0000":
            return None, f"postal: proposal '{candidate}' is not a 4-digit code"
        # Prefer the LLM's cited line if it exists; otherwise any line with the token
        cands = []
        if source_line:
            ns = _norm(source_line)
            cands = [i for i, l in enumerate(lines) if ns and ns in _norm(l)]
        if not cands:
            cands = [i for i, l in enumerate(lines) if re.search(rf"(?<!\d){code}(?!\d)", l)]
        if not cands:
            return None, f"postal: proposal '{code}' not printed on the slip"
        reasons = []
        for i in cands:
            why = qualifies(i, code)
            if why is None:
                return code, f"postal: proposal '{code}' verified on line {i}: {lines[i][:50]!r}"
            reasons.append(f"line {i} ({why})")
        return None, f"postal: proposal '{code}' rejected — " + "; ".join(reasons)

    # No proposal: look only inside address blocks, next to a place/city word
    for b in blocks:
        for i in range(b["start"], b["end"] + 1):
            for m in re.finditer(r"(?<!\d)(\d{4})(?!\d)", lines[i]):
                code = m.group(1)
                if code != "0000" and qualifies(i, code) is None:
                    return code, f"postal: found in {b['position']} address block line {i}: {lines[i][:50]!r}"
    return None, "postal: none printed"


def verify_address(proposed_lines, proposed_address: Optional[str], blocks: List[Dict],
                   lines: List[str], shop_name: Optional[str]) -> Tuple[List[str], Optional[str], str]:
    """
    Address lines must be corroborated by an address block. If the LLM proposed
    nothing usable, the header block itself is the address.
    """
    def clean(line: str) -> str:
        line = SA_PHONE.sub("", line)
        line = re.sub(r"(?i)\b(tel|phone|cell|fax)\b[:\s]*", "", line)
        line = re.sub(r"\S+@\S+\.\S+", "", line)
        line = re.sub(r"(?i)vat\s*(?:no\.?|reg\.?|:)?\s*\d+", "", line)
        line = re.sub(r"(?i)\b(liquor lic\.?|lic\.?)\b.*$", "", line)
        if shop_name:
            line = re.sub(re.escape(shop_name), "", line, flags=re.I)
        line = re.sub(r"\s*\|\s*", ", ", line)
        return re.sub(r"^[\s,.\-:]+|[\s,.\-:]+$", "", re.sub(r"\s+", " ", line))

    block_text = _norm(" ".join(l for b in blocks for l in b["lines"]))
    proposals = list(proposed_lines or [])
    if proposed_address and not proposals:
        proposals = [p.strip() for p in re.split(r"[\n;]|,\s*(?=[A-Z])", proposed_address) if p.strip()]

    verified = []
    for p in proposals:
        np_ = _norm(clean(p))
        if len(np_) >= 4 and (np_ in block_text or any(_norm(clean(l)) and np_ in _norm(clean(l)) for b in blocks for l in b["lines"])):
            verified.append(clean(p))
    if verified:
        return verified, ", ".join(v for v in verified if v), "address: proposal corroborated by address block"

    # Fallback: the header block (or footer block if that's all we have)
    for pos in ("header", "footer"):
        for b in blocks:
            if b["position"] == pos:
                cleaned = [clean(l) for l in b["lines"]
                           if not (TRANSACTION_WORDS.search(l) and not PLACE_WORDS.search(l))]
                cleaned = [c for c in cleaned if len(c) >= 3 and re.search(r"[A-Za-z]{3,}", c)]
                if cleaned:
                    return cleaned, ", ".join(cleaned), f"address: taken from {pos} address block"
    return [], None, "address: none found"


def guess_suburb(address_lines: List[str]) -> Optional[str]:
    """A known SA *suburb* named in the address (never a metro city), for
    name+suburb shop searches."""
    generic = {"street", "shopping", "centre", "center", "corner", "estate", "village", "hotel",
               "lodge", "waterfront", "harbour", "farm", "club", "stadium", "airport", "station",
               "hospital", "university", "campus", "office park", "junction", "crossing",
               "gardens", "heights", "square", "plaza", "park", "mall", "arcade", "complex",
               "building", "precinct", "boulevard", "avenue", "crescent", "drive"}
    for line in address_lines:
        for cand in re.findall(r"[A-Za-z][A-Za-z ]{3,}", line):
            c = cand.strip()
            if PLACE_WORDS.fullmatch(c) and len(c) >= 5 and c.lower() not in generic \
                    and c.lower() not in METRO_CITIES:
                return c.title()
    return None


# ── entry point ──────────────────────────────────────────────────────────────

def verify_extraction(raw_text: str, proposal: Optional[Dict] = None) -> Dict:
    """
    proposal: the LLM schema output (any subset of shop_name, shop_address,
              address_lines, postal_code, postal_code_source_line, phone_number).
    Returns verified fields plus an evidence list explaining every decision.
    """
    proposal = proposal or {}
    lines = plain_lines(raw_text)
    blocks = find_address_blocks(lines)
    evidence = [f"lines={len(lines)} address_blocks=" + ", ".join(
        f"{b['position']}[{b['start']}-{b['end']}]" for b in blocks)]

    shop_name = sanitize_shop_name(proposal.get("shop_name"))
    if proposal.get("shop_name") and not shop_name:
        evidence.append(f"shop_name: proposal {proposal.get('shop_name')!r} rejected as non-shop")

    address_lines, address, why = verify_address(
        proposal.get("address_lines"), proposal.get("shop_address"), blocks, lines, shop_name)
    evidence.append(why)

    phone, why = verify_phone(proposal.get("phone_number"), lines)
    evidence.append(why)

    postal, why = verify_postal_code(proposal.get("postal_code"), proposal.get("postal_code_source_line"), lines, blocks)
    evidence.append(why)

    suburb = guess_suburb(address_lines)

    return {
        "shop_name": shop_name,
        "address_lines": address_lines,
        "address": address,
        "postal_code": postal,
        "phone_number": phone,
        "suburb": suburb,
        "evidence": evidence,
    }
