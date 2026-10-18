"""Session 5 entity-resolution code adapted to genuine Foundation/SR records. See sources.json for gold-label scope."""

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEIGHTS = {
    "code exact": (0.60, 0.001),
    "code close": (0.35, 0.02),
    "code different": (0.05, 0.979),
    "plant same": (0.95, 0.80),
    "plant different": (0.05, 0.20),
    "service same": (0.90, 0.40),
    "service different": (0.10, 0.60),
}
THRESHOLDS = (4, 8)


def clean_code(s):
    # The domain-specific normalization changes; Jaro-Winkler and scoring remain course code.
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def clean_plant(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def jaro_winkler(a, b):
    if a == b:
        return 1.0
    reach = max(len(a), len(b)) // 2 - 1
    ma, mb = [False] * len(a), [False] * len(b)
    m = 0
    for i, ca in enumerate(a):
        for j in range(max(0, i - reach), min(len(b), i + reach + 1)):
            if not mb[j] and b[j] == ca:
                ma[i] = mb[j] = True
                m += 1
                break
    if not m:
        return 0.0
    sa = [c for c, f in zip(a, ma) if f]
    sb = [c for c, f in zip(b, mb) if f]
    t = sum(x != y for x, y in zip(sa, sb)) / 2
    jaro = (m / len(a) + m / len(b) + (m - t) / m) / 3
    prefix = next(
        (k for k in range(min(4, len(a), len(b))) if a[k] != b[k]),
        min(4, len(a), len(b)),
    )
    return jaro + prefix * 0.1 * (1 - jaro)


def score(t, b):
    code = (
        "code exact"
        if t["code"] == b["code"]
        else (
            "code close"
            if jaro_winkler(t["code"], b["code"]) >= 0.93
            else "code different"
        )
    )
    outcomes = [code, "plant same" if t["plant"] == b["plant"] else "plant different"]
    if t["service"]:
        outcomes.append(
            "service same" if t["service"] == b["service"] else "service different"
        )
    return sum(math.log2(WEIGHTS[o][0] / WEIGHTS[o][1]) for o in outcomes), outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, action="append")
    thresholds = parser.parse_args().threshold or THRESHOLDS

    def records(filename):
        with (HERE / filename).open(encoding="utf-8", newline="") as stream:
            return [
                {
                    "id": r["id"],
                    "raw": r["description"],
                    "code": clean_code(r["description"]),
                    "plant": clean_plant(r["category"]),
                    "service": "",
                }
                for r in csv.DictReader(stream)
            ]

    targets, sources = records("foundation-foods.csv"), records("sr-foods.csv")
    pairs = [(t, b) for t in sources for b in targets if t["plant"] == b["plant"]]
    best = {}
    for t, b in pairs:
        value, why = score(t, b)
        if t["id"] not in best or value > best[t["id"]][0]:
            best[t["id"]] = (value, b["id"], why)
    # Truth is opened only after matching, as in the demo.
    with (HERE / "truth.csv").open(encoding="utf-8", newline="") as stream:
        truth = {r["source_id"]: r["target_id"] for r in csv.DictReader(stream)}
    runs = []
    print(
        f"{len(sources)} SR records, {len(targets)} Foundation candidates; {len(pairs)} candidate pairs after category blocking"
    )
    for threshold in thresholds:
        found = {
            tid: code for tid, (value, code, why) in best.items() if value >= threshold
        }
        tp = sum(truth[tid] == code for tid, code in found.items())
        fp = [tid for tid, code in found.items() if truth[tid] != code]
        fn = [tid for tid, code in truth.items() if code and found.get(tid) != code]
        precision = tp / max(len(found), 1)
        recall = tp / sum(bool(code) for code in truth.values())
        runs.append(
            {
                "threshold": threshold,
                "tp": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": precision,
                "recall": recall,
                "matches": found,
            }
        )
        print(
            f"threshold {threshold}: {len(found)} matches, {tp} correct; precision {precision:.3f}, recall {recall:.3f}"
        )
    (HERE / "results.json").write_text(
        json.dumps(
            {
                "utc": datetime.now(timezone.utc).isoformat(),
                "method": "Course Fellegi-Sunter weights and Jaro-Winkler; description replaces code, category replaces plant, service omitted",
                "weights_note": "Course stated weights, not estimated or calibrated for food records",
                "runs": runs,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
