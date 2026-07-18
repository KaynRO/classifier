#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP scraper (through the agent proxy) — pages are server-rendered with
JSON-LD / meta price data, so no browser is needed. Reuses TARGETS from
scrape_preturi.py. Writes prices.csv / prices.json with a `confirmed` flag."""
import sys, csv, json, re, os, time
sys.path.insert(0, "/home/user/classifier")
import scrape_preturi as SP
import requests

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
OUT = "/home/user/classifier"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
HDR = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
}

PRICE_LEI = re.compile(r'(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\s*(?:lei|ron)', re.I)


def norm_price(s):
    """Format-aware: handle both '3.550,00' (RO display) and '3550.00' (JSON)."""
    if s is None:
        return None
    s = str(s).strip().replace('\xa0', ' ').replace('&nbsp;', ' ')
    s = re.sub(r'(lei|ron)', '', s, flags=re.I).strip()
    if not s:
        return None
    has_comma, has_dot = ',' in s, '.' in s
    if has_comma and has_dot:                 # 3.550,00 -> 3550.00
        s = s.replace('.', '').replace(' ', '').replace(',', '.')
    elif has_comma:                           # 3550,00 -> 3550.00
        s = s.replace(' ', '').replace(',', '.')
    else:                                     # 3550 / 3550.00 / 3 550 -> keep dot as decimal
        s = s.replace(' ', '')
        # a lone dot with !=2 or ==3 trailing digits used as thousands sep -> strip
        m = re.match(r'^\d{1,3}(\.\d{3})+$', s)
        if m:
            s = s.replace('.', '')
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _walk_jsonld(data):
    """Yield price candidates from a parsed JSON-LD object."""
    stack = [data]
    prices = []
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            offers = node.get("offers")
            for o in ([offers] if isinstance(offers, dict) else offers if isinstance(offers, list) else []):
                if isinstance(o, dict):
                    for k in ("price", "lowPrice", "highPrice"):
                        if o.get(k):
                            prices.append(str(o[k]))
                    stack.append(o)
            if node.get("price"):
                prices.append(str(node["price"]))
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return prices


def from_jsonld(html):
    for raw in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                          html, re.S | re.I):
        raw = raw.strip()
        if not raw or 'price' not in raw.lower():
            continue
        cands = []
        try:                                   # strict=False tolerates raw newlines in strings
            data = json.loads(raw, strict=False)
            cands = [norm_price(p) for p in _walk_jsonld(data)]
        except Exception:
            # block is malformed JSON (trailing commas etc.) -> regex the price fields
            for v in re.findall(r'"(?:price|lowPrice)"\s*:\s*"?([0-9][0-9.,]*)"?', raw):
                cands.append(norm_price(v))
        cands = [c for c in cands if c and c > 0]
        if cands:
            return str(min(cands)), "json-ld"   # min positive = current/sale price
    return None, None


def from_meta(html):
    for pat in [r'<meta[^>]*itemprop=["\']price["\'][^>]*content=["\']([^"\']+)["\']',
                r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*itemprop=["\']price["\']',
                r'<meta[^>]*property=["\']product:price:amount["\'][^>]*content=["\']([^"\']+)["\']',
                r'<meta[^>]*property=["\']og:price:amount["\'][^>]*content=["\']([^"\']+)["\']']:
        m = re.search(pat, html, re.I)
        if m:
            v = norm_price(m.group(1))
            if v:
                return str(m.group(1)), "meta"
    return None, None


def from_dataattr(html):
    for pat in [r'data-price=["\']([\d.,\s]+)["\']',
                r'"price"\s*:\s*"?([\d.,]+)"?',
                r'"finalPrice"\s*:\s*"?([\d.,]+)"?',
                r'"gross_price"\s*:\s*"?([\d.,]+)"?']:
        m = re.search(pat, html, re.I)
        if m:
            v = norm_price(m.group(1))
            if v and v > 1:
                return str(m.group(1)), "data-attr"
    return None, None


def from_regex(html):
    text = re.sub(r'<script.*?</script>', ' ', html, flags=re.S | re.I)
    text = re.sub(r'<style.*?</style>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    m = PRICE_LEI.search(text)
    if m:
        v = norm_price(m.group(1))
        if v:
            return m.group(1), "regex-lei"
    return None, None


def from_embedded_hint(html):
    """Non-authoritative price hints from embedded JS state (e.g. Romstal
    price_log). Returned only as a hint, never as a confirmed live price."""
    m = re.search(r'"price_log"\s*:\s*\{\s*"price"\s*:\s*"([0-9.]+)"[^}]*"created_at"\s*:\s*"([0-9-]+)"', html)
    if m:
        v = norm_price(m.group(1))
        if v:
            return v, f"price_log {m.group(2)}"
    return None, None


def blocked(html, status):
    low = html.lower()
    if status in (403, 429, 503, 511):
        return True
    return ('just a moment' in low or 'checking your browser' in low
            or 'emag captcha' in low or 'cf-challenge' in low
            or 'captcha' in low[:3000] or 'enable javascript and cookies' in low)


def fetch(url, tries=2):
    last = None
    with requests.Session() as s:
        s.headers.update(HDR)
        for i in range(tries):
            try:
                r = s.get(url, timeout=30, allow_redirects=True)
                return r.status_code, r.text
            except Exception as e:
                last = f"{e.__class__.__name__}"
                time.sleep(1.5 * (i + 1))
    return None, last or "error"


def scrape(t):
    status, html = fetch(t["url"])
    if status is None:
        return {"price": None, "confirmed": False, "method": f"eroare:{html}",
                "raw": None, "http": None}
    if not isinstance(html, str) or blocked(html, status):
        return {"price": None, "confirmed": False,
                "method": f"blocat(http {status})", "raw": None, "http": status}
    for fn in (from_jsonld, from_meta, from_dataattr):
        raw, method = fn(html)
        if raw:
            p = norm_price(raw)
            if p:
                return {"price": p, "confirmed": True, "method": method,
                        "raw": str(raw)[:60], "http": status}
    # non-authoritative hint (dated embedded price) — reported but NOT confirmed
    hv, hm = from_embedded_hint(html)
    if hv:
        return {"price": hv, "confirmed": False, "method": hm,
                "raw": None, "http": status}
    return {"price": None, "confirmed": False, "method": "negăsit",
            "raw": None, "http": status}


def main():
    rows = []
    for i, t in enumerate(SP.TARGETS, 1):
        r = scrape(t)
        row = {**t, **r}
        ps = f"{r['price']:.2f} lei" if r["price"] else "—"
        print(f"[{i:>2}/{len(SP.TARGETS)}] item {t['item']:>2} {t['store']:<12} "
              f"-> {ps:>14}  ({r['method']})  raw={r['raw']}", flush=True)
        rows.append(row)
        time.sleep(1.3)
    with open(f"{OUT}/prices.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with open(f"{OUT}/prices.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item", "store", "name", "price",
                                          "confirmed", "method", "http", "raw", "url"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    ok = sum(1 for r in rows if r["price"])
    print(f"\nGata: {ok}/{len(rows)} prețuri confirmate live.", flush=True)


if __name__ == "__main__":
    main()
