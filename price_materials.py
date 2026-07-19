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


NUM_RE = re.compile(r'\d+(?:[.,]\d+)?(?:/\d+)?')


def tokenize(text):
    """Return (alpha_tokens, num_tokens) from a material name / title."""
    t = re.sub(r'[\-_/\\.,;:()]+', ' ', str(text).lower())
    alpha, nums = set(), set()
    for w in t.split():
        if STOP.match(w):
            continue
        m = NUM_RE.fullmatch(w) or (NUM_RE.search(w))
        if any(c.isdigit() for c in w):
            for nm in NUM_RE.findall(w):
                nums.add(nm.replace(',', '.'))
        wa = re.sub(r'[^a-zăâîșț]', '', w)
        if len(wa) >= 3:
            alpha.add(wa)
    return alpha, nums


def score_title(name_alpha, name_nums, title):
    ta, tn = tokenize(title)
    a_ov = len(name_alpha & ta)
    n_ov = len(name_nums & tn)
    ratio = difflib.SequenceMatcher(None, " ".join(sorted(name_alpha)),
                                    " ".join(sorted(ta))).ratio()
    return a_ov + 2 * n_ov + ratio, a_ov, n_ov


def best_match(name, results):
    """Score candidate titles against the FULL name (incl. dimensions)."""
    if not results:
        return None
    na, nn = tokenize(name)
    best, bscore, binfo = None, -1, (0, 0)
    for title, url in results:
        s, a_ov, n_ov = score_title(na, nn, title)
        if s > bscore:
            best, bscore, binfo = (title, url), s, (a_ov, n_ov)
    a_ov, n_ov = binfo
    return best[0], best[1], a_ov, n_ov, len(nn)


def confidence(a_ov, n_ov, n_nums):
    """Ridicată/Medie/Scăzută. Penalise when the item has dimensions but the
    matched product shares none (wrong size = classic false match)."""
    if n_nums > 0 and n_ov == 0:
        return "Scăzută"
    if a_ov >= 2 and (n_ov >= 1 or n_nums == 0):
        return "Ridicată"
    if a_ov >= 1:
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
    m = best_match(name, results)
    if not m:
        return {"query": q, "price": None, "match_name": "", "match_url": "",
                "conf": "-", "note": "fără potrivire"}
    title, url, a_ov, n_ov, n_nums = m
    conf = confidence(a_ov, n_ov, n_nums)
    # fetch product page once: price + authoritative product name for the audit trail
    st, html = S.fetch(url)
    price, pname = None, title
    if isinstance(html, str) and not S.blocked(html, st):
        for fn in (S.from_jsonld, S.from_meta, S.from_dataattr):
            raw, _ = fn(html)
            if raw and S.norm_price(raw):
                price = S.norm_price(raw)
                break
        mt = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)', html) \
            or re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
        if mt:
            pname = re.sub(r'\s+', ' ', mt.group(1)).replace(' - Dedeman', '').strip()[:120]
    return {"query": q, "price": price, "match_name": pname, "match_url": url,
            "conf": conf if price else "-",
            "note": ("Dedeman live" if price else "preț negăsit pe pagină")}
