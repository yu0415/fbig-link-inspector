import argparse, os, time, csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.inspect import inspect_url

def run_once(url: str, mode: str) -> dict:
    os.environ["FBIG_FORCE_PLAYWRIGHT"] = "1"
    if mode == "login":
        os.environ["FBIG_STORAGE_STATE"] = "state.json"
    else:
        os.environ.pop("FBIG_STORAGE_STATE", None)

    start = time.time()
    result = inspect_url(url)
    elapsed = int((time.time() - start) * 1000)

    ok = result.get("status") == "ok"
    title = (result.get("data") or {}).get("og:title")
    got_title = bool(title)
    fetched_with = (result.get("meta") or {}).get("fetched_with", "")

    return {
        "url": url,
        "mode": mode,
        "duration_ms": elapsed,
        "status": "ok" if ok else "error",
        "fetched_with": fetched_with,
        "got_title": got_title
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["anon","login"], required=True)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--urls", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    urls = [u.strip() for u in Path(args.urls).read_text().splitlines() if u.strip()]
    results = []
    for url in urls:
        for i in range(args.trials):
            r = run_once(url, args.mode)
            r["trial"] = i + 1
            print(f"[{args.mode}] ({i+1}) {url} → {r['duration_ms']}ms, {r['status']}")
            results.append(r)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"✅ 已輸出：{out_path}")

if __name__ == "__main__":
    main()