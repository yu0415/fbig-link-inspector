import argparse, csv, statistics
from pathlib import Path
from collections import defaultdict

def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    k = (len(values)-1) * p
    f = int(k)
    c = min(f+1, len(values)-1)
    return values[f] + (values[c]-values[f])*(k-f)

def summarize(files):
    data = []
    for f in files:
        with open(f, newline='', encoding='utf-8') as csvf:
            reader = csv.DictReader(csvf)
            for row in reader:
                row["duration_ms"] = int(row["duration_ms"])
                data.append(row)
    grouped = defaultdict(list)
    for r in data:
        grouped[r["mode"]].append(r["duration_ms"])

    lines = ["# Benchmark Summary"]
    for mode, vals in grouped.items():
        avg = sum(vals)/len(vals)
        p50 = percentile(vals, 0.5)
        p90 = percentile(vals, 0.9)
        lines.append(f"{mode}: avg {avg/1000:.2f}s / p50 {p50/1000:.2f}s / p90 {p90/1000:.2f}s (n={len(vals)})")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    summary = summarize(args.files)
    Path(args.out).write_text(summary, encoding="utf-8")
    print(summary)

if __name__ == "__main__":
    main()