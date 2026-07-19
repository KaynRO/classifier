#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live unit-price finder for the Materiale resource list.

For each material: clean the name into a search query, query Dedeman's search
(the only shop with an open, parseable search that returns real prices via
product-page meta), take the best-matching product, and read its live price.

Dedeman is used as the live source because Romstal's search endpoint 404s and
eMAG/Leroy/Bricodepot block automated search. Output columns record the matched
product name + URL + price so every figure is auditable.
"""
import sys, os, re, json, time, urllib.parse, difflib
sys.path.insert(0, "/home/user/classifier")
import scrape_http as S
import requests

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept-Language": "ro-RO,ro;q=0.9", "Accept-Encoding": "gzip, deflate"}

# tokens that hurt search matching (standards, abbreviations, noise)
STOP = re.compile(r'^(stas|s|sr|sr-en|en|iso|tip|d|dn|nr|buc|kg|mp|mc|ml|profil|cu|din|pentru|si|de|la|x)$', re.I)
CODE = re.compile(r'^[a-z]{0,3}\.?\d')   # things like "438", "d8-12", "ob37"...


def clean_query(name):
    name = re.sub(r'[\-_/\\.,;:()]+', ' ', str(name).lower())
    name = re.sub(r'\bstas\b.*', '', name)          # drop everything after 'stas'
    name = re.sub(r'\bs\s*\d[\d\s-]*', ' ', name)    # drop 's 438 ...' std refs
    words = []
    for w in name.split():
        if STOP.match(w):
            continue
        words.append(w)
        if len(words) >= 5:
            break
    return ' '.join(words).strip()


def ded_search(q):
    """Return list of (title, url) product results from Dedeman search."""
    try:
        url = "https://www.dedeman.ro/ro/catalogsearch/result/v2?q=" + urllib.parse.quote(q)
        h = requests.get(url, headers=H, timeout=25).text
    except Exception:
        return []
    # product links
    urls = []
    for l in re.findall(r'href="(https://www\.dedeman\.ro/ro/[a-z0-9\-]+/p/[\w\-]+)"', h):
        if l not in urls:
            urls.append(l)
    # titles from dataLayer impressions (in result order)
    titles = re.findall(r'"name":\s*"([^"]{4,90})"', h)
    titles = [bytes(t, "utf-8").decode("unicode_escape") if '\\u' in t else t for t in titles]
    out = []
    for i, u in enumerate(urls[:6]):
        out.append((titles[i] if i < len(titles) else "", u))
    return out


ALLOW_RE = re.compile(r'material\s+(marunt|mediu|nespecificat)|transport|manoper|\bora\b|cheltuieli', re.I)


def is_allowance(name, um):
    """Rows that are % allowances / labour / transport — not a purchasable item."""
    um = str(um or "").strip().lower()
    if um in ("%", "lei", "ora"):
        return True
    return bool(ALLOW_RE.search(str(name or "")))


def best_match(query, results):
    """Pick the best result; return (title, url, overlap, ratio)."""
    if not results:
        return None
    qwords = [w for w in query.lower().split() if len(w) > 1]
    best, bscore = None, -1
    for title, url in results:
        tl = title.lower()
        overlap = sum(1 for w in qwords if w in tl)
        ratio = difflib.SequenceMatcher(None, query.lower(), tl).ratio()
        score = overlap + ratio
        if score > bscore:
            best, bscore = (title, url, overlap, ratio), score
    return best


def confidence(qwords, overlap, ratio):
    """High/Medie/Scăzută based on how much of the query the match covers."""
    n = max(1, len(qwords))
    cov = overlap / n
    if overlap >= 3 and cov >= 0.6:
        return "Ridicată"
    if overlap >= 2 and cov >= 0.4:
        return "Medie"
    return "Scăzută"


def price_for(name, um=None):
    if is_allowance(name, um):
        return {"query": "", "price": None, "match_name": "", "match_url": "",
                "conf": "-", "note": "poziție de tip alocație/manoperă (%/lei) — nepreţuit"}
    q = clean_query(name)
    if not q:
        return {"query": q, "price": None, "match_name": "", "match_url": "",
                "conf": "-", "note": "query gol"}
    results = ded_search(q)
    if not results:
        return {"query": q, "price": None, "match_name": "", "match_url": "",
                "conf": "-", "note": "fără rezultate Dedeman"}
    m = best_match(q, results)
    if not m:
        return {"query": q, "price": None, "match_name": "", "match_url": "",
                "conf": "-", "note": "fără potrivire"}
    title, url, overlap, ratio = m
    conf = confidence([w for w in q.split() if len(w) > 1], overlap, ratio)
    res = S.scrape({"url": url})
    price = res.get("price")
    return {"query": q, "price": price, "match_name": title, "match_url": url,
            "conf": conf if price else "-",
            "note": ("Dedeman live" if price else "preț negăsit pe pagină")}
