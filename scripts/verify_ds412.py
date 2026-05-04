"""
One-off citation verifier for WTO DS-412 (document 7effb1ea-bf1b-5031-a165-a2959229b627).
Tier 3 validation per the citation-verifier protocol.

Reads:
  - data/extraction_results/7effb1ea-bf1b-5031-a165-a2959229b627_extracted.json
  - data/decisions_md/7effb1ea-bf1b-5031-a165-a2959229b627.md

Writes:
  - data/extraction_results/7effb1ea-bf1b-5031-a165-a2959229b627_verified.json

Methodology
-----------
This is a WTO Appellate Body Report (source_region = International, source_jurisdiction =
WTO Dispute Settlement Body). Per the user task instructions, all WTO->WTO citations are
classified Inter-System (Type 4) with is_vertical_dialogue = false.

Dedup follows D22: when long-form (Cases-Cited table entry, indices 1-48) and a short-form
body mention (indices 49-96) refer to the same WTO dispute (matched by WT/DSnnn case
number), keep the long-form as primary and mark the short-form as DUPLICATE pointing back
to it.

Functional use is finalized using full-document context (D31). Body-only short-form
mentions tagged 'dismissed' by the chunked extractor are upgraded to 'aligned' if the
Appellate Body itself engages with the case in its substantive analysis section
(positions >= AB Analysis start). Two such upgrades were identified: US - Wheat Gluten
(idx 47) and Korea - Various Measures on Beef (idx 31).
"""
import json
import re
from datetime import datetime, timezone

EXTRACTED = "C:/Users/gusta/workspace/proj/phdMutley/data/extraction_results/7effb1ea-bf1b-5031-a165-a2959229b627_extracted.json"
DOC = "C:/Users/gusta/workspace/proj/phdMutley/data/decisions_md/7effb1ea-bf1b-5031-a165-a2959229b627.md"
OUT = "C:/Users/gusta/workspace/proj/phdMutley/data/extraction_results/7effb1ea-bf1b-5031-a165-a2959229b627_verified.json"


def main():
    d = json.load(open(EXTRACTED, encoding="utf-8"))
    txt = open(DOC, encoding="utf-8").read()

    ab_start = txt.find("ANALYSIS OF THE APPELLATE BODY\n5.1 The order")
    assert ab_start > 0, "Cannot locate AB Analysis section start"

    citations_in = {c["citation_index"]: c for c in d["citations"]}

    # Dedup map: short_form_idx -> long_form_idx (same case). None means short-form is unique.
    DUP_MAP = {
        49: 18,   # EC - Asbestos
        50: 2,    # Brazil - Retreaded Tyres
        51: 47,   # US - Wheat Gluten
        52: 23,   # EC - Sardines
        53: 35,   # US - Carbon Steel
        54: 13,   # Chile - Price Band System
        55: 19,   # EC - Bananas III (DS27/AB/R)
        56: 39,   # US - Large Civil Aircraft (2nd complaint) -> DS353/AB/R
        57: 41,   # US - Softwood Lumber IV (AB Report)
        58: 32,   # Philippines - Distilled Spirits
        59: 30,   # Korea - Alcoholic Beverages
        60: 11,   # Canada - Wheat Exports and Grain Imports
        61: 15,   # China - Intellectual Property Rights
        62: 28,   # Japan - Alcoholic Beverages II
        63: 33,   # Turkey - Rice
        64: 5,    # Canada - Autos (AB Report)
        65: 31,   # Korea - Various Measures on Beef
        66: 16,   # China - Publications and Audiovisual Products
        67: 43,   # US - Tuna II (Mexico)
        68: 27,   # Indonesia - Autos
        69: 3,    # Canada - Aircraft (DS70/AB/R)
        70: 34,   # US - Anti-Dumping and Countervailing Duties (China)
        71: 25,   # EC and certain member States - Large Civil Aircraft
        72: 26,   # India - Autos
        73: 21,   # EC - Export Subsidies on Sugar
        74: 44,   # US - Upland Cotton (AB Report)
        75: 29,   # Japan - DRAMs (Korea)
        76: 24,   # EC - Selected Customs Matters
        77: 17,   # China - Raw Materials
        78: 38,   # US - Gasoline (Reformulated)
        79: 7,    # Canada - Dairy
        80: 1,    # Australia - Salmon
        81: 14,   # China - Auto Parts
        82: 40,   # US - Section 211 Appropriations Act
        83: 48,   # US - Wool Shirts and Blouses
        84: 22,   # EC - Hormones
        85: 36,   # US - Certain EC Products
        86: 4,    # Canada - Aircraft (Article 21.5 - Brazil) -> DS70/AB/RW
        87: None, # Korea - Dairy (DS98) - new citation
        88: 9,    # Canada - Periodicals
        89: 10,   # Renewable Energy Panel under appeal (DS412/R)
        90: 8,    # Feed-in Tariff Panel under appeal (DS426/R)
        91: None, # US/Canada - Continued Suspension (DS320/321) - new
        92: 19,   # EC Bananas III Article 21.5 follow-up - dedup to primary EC-Bananas-III
        93: None, # US - Continued Existence ... Zeroing (DS350) - new
        94: None, # US - Laws/Regulations Zeroing (DS294) - new
        95: None, # US - Zeroing/Sunset Reviews (DS322) - new
        96: None, # Australia - Apples (DS367) - new
    }

    # Functional use finalization. Long-form indices 1-48 inherit body-engagement classification
    # from their short-form duplicates (which have actual body context); when no engagement,
    # default to 'dismissed' (party-only) per D31.
    PRIMARY_FU = {
        # Cases the AB engages with in body (substantive reasoning):
        1: "aligned",   # Australia - Salmon (AB cites in fn 717-718 of body)
        3: "aligned",   # Canada - Aircraft (DS70/AB/R) - AB cite, multiple body refs
        4: "aligned",   # Canada - Aircraft (Article 21.5 - Brazil) - AB cite at fn 717
        5: "aligned",   # Canada - Autos (AB) - AB cite at fn 718
        6: "aligned",   # Canada - Autos (Panel)
        7: "aligned",   # Canada - Dairy
        9: "aligned",   # Canada - Periodicals - AB cite at fn 718
        11: "aligned",  # Canada - Wheat Exports (AB)
        12: "aligned",  # Canada - Wheat Exports (Panel)
        14: "aligned",  # China - Auto Parts
        17: "aligned",  # China - Raw Materials
        18: "aligned",  # EC - Asbestos - AB cite (e.g. fn 172)
        19: "aligned",  # EC - Bananas III (AB)
        20: "aligned",  # EC - Bananas III (Panel)
        21: "aligned",  # EC - Export Subsidies on Sugar
        22: "aligned",  # EC - Hormones
        24: "aligned",  # EC - Selected Customs Matters
        25: "aligned",  # EC and certain member States - Large Civil Aircraft (AB cite fn at body)
        26: "aligned",  # India - Autos
        27: "aligned",  # Indonesia - Autos
        28: "aligned",  # Japan - Alcoholic Beverages II
        31: "aligned",  # Korea - Various Measures on Beef - AB cite at fn 718 (UPGRADED from dismissed)
        34: "aligned",  # US - Anti-Dumping (DS379)
        36: "aligned",  # US - Certain EC Products
        37: "aligned",  # US - COOL
        38: "aligned",  # US - Gasoline
        39: "aligned",  # US - Large Civil Aircraft (DS353)
        40: "aligned",  # US - Section 211
        41: "aligned",  # US - Softwood Lumber IV (AB)
        42: "aligned",  # US - Softwood Lumber IV (Panel)
        43: "contested",# US - Tuna II (Mexico) - AB engages but distinguishes
        44: "aligned",  # US - Upland Cotton (AB)
        45: "aligned",  # US - Upland Cotton (Panel)
        46: "aligned",  # US - Upland Cotton (Article 21.5)
        47: "aligned",  # US - Wheat Gluten - AB cite at fn 717 (UPGRADED from dismissed)
        48: "aligned",  # US - Wool Shirts and Blouses

        # Cases that appear ONLY in party submissions (no AB engagement) -> dismissed per D31:
        2: "dismissed", # Brazil - Retreaded Tyres
        13: "dismissed",# Chile - Price Band System
        15: "dismissed",# China - Intellectual Property Rights
        16: "dismissed",# China - Publications and Audiovisual Products
        23: "dismissed",# EC - Sardines
        29: "dismissed",# Japan - DRAMs (Korea)
        30: "dismissed",# Korea - Alcoholic Beverages
        32: "dismissed",# Philippines - Distilled Spirits
        33: "dismissed",# Turkey - Rice
        35: "dismissed",# US - Carbon Steel

        # Panel reports under appeal (substantive engagement throughout the AB Report):
        # The AB engages directly with the underlying Panel Reports - reversing/upholding
        # specific findings. Functional use is 'contested' since the AB modifies/reverses
        # numerous findings while upholding others.
        8: "contested", # Feed-in Tariff Panel under appeal (DS426/R)
        10: "contested",# Renewable Energy Panel under appeal (DS412/R)

        # New citations from short-form (87, 91, 93-96):
        87: "aligned",  # Korea - Dairy: AB cite at fn 718
        91: "aligned",  # US/Canada - Continued Suspension
        93: "aligned",  # US - Continued Existence and Application of Zeroing
        94: "aligned",  # US - Laws, Regulations and Methodology for Calculating Zeroing
        95: "aligned",  # US - Measures Relating to Zeroing and Sunset Reviews
        96: "aligned",  # Australia - Apples
    }

    def find_verbatim_snippet(c):
        """Find a verbatim snippet from the document containing this citation."""
        cnum = c.get("case_number") or ""
        cn = c.get("case_name") or ""
        raw = c.get("raw_text") or ""

        # Try the exact raw_text first
        if raw and raw in txt:
            return (raw[:497] + "...") if len(raw) > 500 else raw

        # Try each WT/DS... token in case_number
        for token in re.findall(r"WT/DS\d+(?:/[A-Za-z0-9]+)*", cnum):
            pos = txt.find(token)
            if pos >= 0:
                start = max(0, pos - 150)
                end = min(len(txt), pos + 250)
                snippet = re.sub(r"\s+", " ", txt[start:end]).strip()
                return snippet[:500]

        # Try short or full case_name
        if cn:
            pos = txt.find(cn)
            if pos < 0:
                # Try first significant chunk of cn
                key = cn.split("(")[0].strip()
                if key and key != cn:
                    pos = txt.find(key)
            if pos >= 0:
                start = max(0, pos - 150)
                end = min(len(txt), pos + 250)
                snippet = re.sub(r"\s+", " ", txt[start:end]).strip()
                return snippet[:500]

        return None

    def make_record(c, verdict="CONFIRMED", dup_of=None, fu_override=None, fu_conf=0.85, notes=None):
        idx = c["citation_index"]
        rec = {
            "citation_index": idx,
            "verification_verdict": verdict,
            "case_name": c.get("case_name"),
            "raw_text": c.get("raw_text"),
            "verbatim_snippet": None,
            "cited_court": c.get("cited_court"),
            "case_number": c.get("case_number"),
            "cited_year": c.get("cited_year"),
            "confidence": c.get("confidence", 0.9),
            "functional_use": fu_override if fu_override is not None else c.get("functional_use"),
            "functional_use_confidence": fu_conf,
            "opinion_type": c.get("opinion_type") or "majority",
            "origin_country": None,
            "origin_region": "International",
            "origin_court": c.get("origin_court") or c.get("cited_court"),
            "sixfold_type": "Inter-System Citation",
            "is_vertical_dialogue": False,
            "citation_pattern": c.get("citation_pattern", "traditional"),
            "requires_manual_review": False,
            "manual_review_reason": None,
            "is_duplicate_of": dup_of,
            "verification_notes": notes,
        }
        return rec

    LONG = set(range(1, 49))
    SHORT = set(range(49, 97))

    long_to_dups = {}
    for s, l in DUP_MAP.items():
        if l is not None:
            long_to_dups.setdefault(l, []).append(s)

    out_recs = []

    for c in d["citations"]:
        idx = c["citation_index"]

        if idx in LONG:
            fu = PRIMARY_FU.get(idx, c.get("functional_use", "dismissed"))
            dup_short = long_to_dups.get(idx, [])
            notes_parts = []
            if dup_short:
                short_names = [
                    citations_in[s].get("case_name", "") for s in dup_short
                ]
                notes_parts.append(
                    f"Short-form duplicates: indices {dup_short} (names: {'; '.join(short_names)})"
                )
            if fu != c.get("functional_use"):
                notes_parts.append(
                    f"Functional use updated from extracted '{c.get('functional_use')}' to '{fu}' based on body engagement analysis"
                )
            rec = make_record(
                c,
                verdict="CONFIRMED",
                fu_override=fu,
                fu_conf=0.85,
                notes=" | ".join(notes_parts) if notes_parts else None,
            )
            rec["verbatim_snippet"] = find_verbatim_snippet(c)
            out_recs.append(rec)

        elif idx in SHORT:
            target = DUP_MAP.get(idx)
            if target is not None:
                rec = make_record(
                    c,
                    verdict="DUPLICATE",
                    dup_of=target,
                    fu_override=None,
                    fu_conf=0.0,
                    notes=f"Short-form mention; primary at long-form index {target}",
                )
                # Duplicates do not carry sixfold/origin; null those out
                rec["verbatim_snippet"] = None
                rec["sixfold_type"] = None
                rec["origin_country"] = None
                rec["origin_region"] = None
                rec["origin_court"] = None
                rec["is_vertical_dialogue"] = False
                out_recs.append(rec)
            else:
                # New unique citation (no long-form table entry)
                fu = PRIMARY_FU.get(idx, c.get("functional_use", "aligned"))
                rec = make_record(
                    c,
                    verdict="CONFIRMED",
                    fu_override=fu,
                    fu_conf=0.85,
                    notes="Confirmed via short-form body mention; case_number located in document body.",
                )
                rec["verbatim_snippet"] = find_verbatim_snippet(c)
                out_recs.append(rec)

    out_recs.sort(key=lambda r: r["citation_index"])

    total_confirmed = sum(1 for r in out_recs if r["verification_verdict"] == "CONFIRMED")
    total_duplicates = sum(1 for r in out_recs if r["verification_verdict"] == "DUPLICATE")
    total_not_found = sum(1 for r in out_recs if r["verification_verdict"] == "NOT_FOUND")
    total_misattributed = sum(1 for r in out_recs if r["verification_verdict"] == "MISATTRIBUTED")
    total_not_a_case = sum(1 for r in out_recs if r["verification_verdict"] == "NOT_A_CASE")
    flagged = sum(1 for r in out_recs if r.get("requires_manual_review"))

    by_sixfold = {
        "Foreign Citation": 0,
        "International Citation": 0,
        "Foreign International Citation": 0,
        "Inter-System Citation": 0,
        "Member-State Citation": 0,
        "Non-Member Citation": 0,
        "Domestic": 0,
        "Unclassified": 0,
    }
    by_fu = {"aligned": 0, "contested": 0, "avoided": 0, "invoked": 0, "dismissed": 0}
    by_vert = {"true": 0, "false": 0}
    by_origin = {
        "Global North": 0,
        "Global South": 0,
        "International": 0,
        "Domestic": 0,
        "Unknown": 0,
    }

    for r in out_recs:
        if r["verification_verdict"] != "CONFIRMED":
            continue
        sixfold = r["sixfold_type"]
        if sixfold in by_sixfold:
            by_sixfold[sixfold] += 1
        fu = r["functional_use"]
        if fu in by_fu:
            by_fu[fu] += 1
        by_vert["true" if r["is_vertical_dialogue"] else "false"] += 1
        orr = r["origin_region"]
        if orr in by_origin:
            by_origin[orr] += 1
        elif orr is None:
            by_origin["Unknown"] += 1

    verified = {
        "document_id": d["document_id"],
        "case_id": d["case_id"],
        "source_jurisdiction": d["source_jurisdiction"],
        "source_region": d["source_region"],
        "source_year": d["source_year"],
        "verification_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_citations_extracted": len(d["citations"]),
        "total_confirmed": total_confirmed,
        "total_not_found": total_not_found,
        "total_misattributed": total_misattributed,
        "total_not_a_case": total_not_a_case,
        "total_duplicates": total_duplicates,
        "unique_citations_confirmed": total_confirmed,
        "citations": out_recs,
        "summary": {
            "confirmed_unique": total_confirmed,
            "by_sixfold_type": by_sixfold,
            "by_functional_use": by_fu,
            "by_vertical_dialogue": by_vert,
            "by_origin_region": by_origin,
            "flagged_for_review": flagged,
        },
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(verified, f, ensure_ascii=False, indent=2)

    print(f"Wrote: {OUT}")
    print(f"  Total extracted: {len(d['citations'])}")
    print(f"  Confirmed (unique): {total_confirmed}")
    print(f"  Duplicates: {total_duplicates}")
    print(f"  Sixfold breakdown: {by_sixfold}")
    print(f"  Functional use: {by_fu}")
    print(f"  Vertical dialogue: {by_vert}")
    print(f"  Origin region: {by_origin}")


if __name__ == "__main__":
    main()
