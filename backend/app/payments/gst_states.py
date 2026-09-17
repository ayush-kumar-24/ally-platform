"""Indian states and union territories, with their GST state codes.

The codes are the first two digits of a GSTIN -- GoXL's own 24AALCG5562B1ZS
begins 24, which is Gujarat -- and they are what an invoice prints beside the
place of supply: "Gujarat (24)".

WHY THIS LIST EXISTS AT ALL. The choice between CGST+SGST and IGST is not a
preference, it is a fact about two states: the supplier's and the place of
supply. Same state, the tax splits into central and state halves; different
states, it is one integrated tax. Getting it wrong does not change what the
founder paid, but it does misstate which government is owed the money, on a
document their accountant will file. So the state has to be a value from a
known list, not free text a founder typed -- "Gujrat", "GJ" and "gujarat "
must all either resolve to Gujarat or be refused, never silently become a
state nobody can match.

The list is the statutory one as at the 2020 Ladakh/Daman-Diu reorganisation.
Codes 25 (Daman & Diu, merged into 26) and 34 are absent because they are.
"""

from __future__ import annotations

#: Canonical name -> GST state code. Ordered by code, which is how every
#: official listing of these is ordered.
GST_STATE_CODES: dict[str, str] = {
    "Jammu and Kashmir": "01",
    "Himachal Pradesh": "02",
    "Punjab": "03",
    "Chandigarh": "04",
    "Uttarakhand": "05",
    "Haryana": "06",
    "Delhi": "07",
    "Rajasthan": "08",
    "Uttar Pradesh": "09",
    "Bihar": "10",
    "Sikkim": "11",
    "Arunachal Pradesh": "12",
    "Nagaland": "13",
    "Manipur": "14",
    "Mizoram": "15",
    "Tripura": "16",
    "Meghalaya": "17",
    "Assam": "18",
    "West Bengal": "19",
    "Jharkhand": "20",
    "Odisha": "21",
    "Chhattisgarh": "22",
    "Madhya Pradesh": "23",
    "Gujarat": "24",
    "Dadra and Nagar Haveli and Daman and Diu": "26",
    "Maharashtra": "27",
    "Karnataka": "29",
    "Goa": "30",
    "Lakshadweep": "31",
    "Kerala": "32",
    "Tamil Nadu": "33",
    "Puducherry": "34",
    "Andaman and Nicobar Islands": "35",
    "Telangana": "36",
    "Andhra Pradesh": "37",
    "Ladakh": "38",
    "Other Territory": "97",
}

#: Spellings a founder or an older record may carry, mapped to the canonical
#: name. Two-letter codes are here because forms collect them; the renamed and
#: commonly-misspelt states are here because records outlive both.
_ALIASES: dict[str, str] = {
    "gujrat": "Gujarat",
    "gj": "Gujarat",
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "uttaranchal": "Uttarakhand",
    "new delhi": "Delhi",
    "nct of delhi": "Delhi",
    "delhi ncr": "Delhi",
    "j&k": "Jammu and Kashmir",
    "jammu & kashmir": "Jammu and Kashmir",
    "tamilnadu": "Tamil Nadu",
    "mh": "Maharashtra",
    "ka": "Karnataka",
    "tn": "Tamil Nadu",
    "up": "Uttar Pradesh",
    "wb": "West Bengal",
    "dl": "Delhi",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
}

#: Built once: lower-cased canonical names, plus the aliases above.
_LOOKUP: dict[str, str] = {name.lower(): name for name in GST_STATE_CODES}
_LOOKUP.update({alias: canonical for alias, canonical in _ALIASES.items()})
#: `and` vs `&` is the single commonest difference between two spellings of
#: the same state, so it is normalised rather than enumerated.
_LOOKUP.update({name.lower().replace(" and ", " & "): name for name in GST_STATE_CODES})


def normalise_state(raw: str | None) -> str | None:
    """A canonical state name, or None if this is not one of them.

    None is the honest answer for an unrecognised value and callers must treat
    it as "unknown", never as a default state. Guessing a place of supply is
    how an invoice ends up claiming the wrong government is owed the tax.
    """
    if not raw:
        return None
    key = " ".join(raw.split()).lower()
    return _LOOKUP.get(key)


def state_code(name: str | None) -> str | None:
    """The two-digit GST code for a canonical state name."""
    return GST_STATE_CODES.get(name or "")


def is_intra_state(*, seller_state: str | None, buyer_state: str | None) -> bool | None:
    """True for CGST+SGST, False for IGST, None when it cannot be decided.

    None is a THIRD ANSWER and not a synonym for False. It means one of the two
    states is unknown -- a payment taken before this product asked for the
    buyer's state, most of the time -- and the caller decides what to do with
    that. What it must not do is quietly pick a split: a document that says
    CGST+SGST because the buyer's state happened to be missing has named the
    wrong tax, and it looks exactly as authoritative as a correct one.
    """
    seller = normalise_state(seller_state)
    buyer = normalise_state(buyer_state)
    if seller is None or buyer is None:
        return None
    return seller == buyer
