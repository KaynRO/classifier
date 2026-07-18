#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Retry pass: re-attempt every NOT-confirmed target with polite spacing and
per-host delays (defeats eMAG/rate-limit captchas). Only upgrades a row when a
confirmed live price is found; otherwise keeps the existing value/hint."""
import sys, csv, json, time
sys.path.insert(0, "/home/user/classifier")
import scrape_http as S

IN = "/home/user/classifier/prices.json"


def save(rows):
    with open("/home/user/classifier/prices.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with open("/home/user/classifier/prices.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item", "store", "name", "price",
                                          "confirmed", "method", "http", "raw", "url"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})


def main():
    rows = json.load(open(IN, encoding="utf-8"))
    # price_log hints are JS-rendered values that static HTTP cannot upgrade -> skip
    todo = [i for i, r in enumerate(rows)
            if not r.get("confirmed") and not str(r.get("method", "")).startswith("price_log")]
    print(f"Retrying {len(todo)} transient-failure targets (of {len(rows)})", flush=True)
    for n, i in enumerate(todo, 1):
        r = rows[i]
        best = None
        for attempt in range(3):
            res = S.scrape(r)
            if res.get("confirmed"):
                best = res
                break
            # keep a hint (e.g. price_log) if we didn't already have one
            if res.get("price") and not best:
                best = res
            time.sleep(2.5 + attempt * 2.0)
        if best and best.get("confirmed"):
            rows[i] = {**r, **best}
            tag = "✔ LIVE"
        elif best and best.get("price") and not r.get("price"):
            rows[i] = {**r, **best}
            tag = "~ hint"
        else:
            tag = "· still blocked/negăsit"
        p = rows[i].get("price")
        ps = f"{p:.2f} lei" if p else "—"
        print(f"[{n:>2}/{len(todo)}] item {r['item']:>2} {r['store']:<12} "
              f"-> {ps:>12} ({rows[i].get('method')}) {tag}", flush=True)
        save(rows)
        time.sleep(3.0)          # polite spacing between hosts
    ok = sum(1 for r in rows if r.get("confirmed"))
    print(f"\nRetry done. Confirmed live now: {ok}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
