#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_preturi.py  —  extrage prețurile EXACTE de pe paginile-produs RO
folosind SeleniumBase în UC-mode (bypass Cloudflare / anti-bot).

Se rulează într-un mediu cu acces la internet (fără proxy care blochează
domeniile .ro). Scoate:  prices.csv  și  prices.json

INSTALARE (o singură dată):
    pip install seleniumbase
    # Chromium/Chrome trebuie să existe; SeleniumBase îl descarcă automat la nevoie.

RULARE:
    python scrape_preturi.py
    # opțional, vizibil (util pt. debug):  python scrape_preturi.py --head

STRATEGIE DE EXTRAGERE (în ordine, prima care reușește câștigă):
    1) JSON-LD  <script type="application/ld+json">  ->  offers.price      (cel mai fiabil)
    2) <meta itemprop="price"> / og:price:amount
    3) selectori CSS specifici fiecărui magazin
    4) regex pe textul paginii, lângă "lei" / "RON"
Fiecare rezultat notează și metoda folosită, ca să știi cât de sigur e.
"""
import sys, csv, json, re, time

# ---------------------------------------------------------------- ținte
# item = nr. poziției din tabel; store = coloana; name = produsul potrivit; url = pagina-produs
TARGETS = [
 {"item":2,  "store":"Dedeman",     "name":"Puffer Ferroli FB 500 izolat",              "url":"https://www.dedeman.ro/ro/puffer-500-litri-rezervor-de-acumulare-ferroli-fb-500-din-otel-cu-izolatie/p/2022960-2022690"},
 {"item":2,  "store":"Leroy Merlin","name":"Puffer Ferroli 500L izolat (37163)",         "url":"https://www.leroymerlin.ro/produse/rezistente-supape-si-alte-accesorii/958/puffer-rezervor-ferroli-izolat-pentru-cazane-max-3-bar-1-12-500-l/37163"},
 {"item":2,  "store":"Romstal",     "name":"Acumulator Romstal Vision 500L",             "url":"https://www.romstal.ro/acumulator-incalzire-romstal-vision-500-l-montaj-vertical.html"},
 {"item":2,  "store":"eMAG",        "name":"Puffer Cordivari Fit 500L",                  "url":"https://www.emag.ro/puffer-500l-cordivari-fit-acumulator-energie-termica-fara-serpentina-izolat-pentru-centrale-pe-lemne-peleti-si-pompe-de-caldura-3251162310302/pd/DGW1M4MBM/"},

 {"item":3,  "store":"Romstal",     "name":"Vas expansiune Varem vertical 60L 10 bar",   "url":"https://www.romstal.ro/vas-expansiune-universal-vertical-varem-10-bar-60l.html"},
 {"item":3,  "store":"eMAG",        "name":"Vas expansiune Reflex DE 60 (echiv.)",       "url":"https://www.quickshop.ro/vas-expansiune-acm-reflex-de-60-10-bar-60-litri-p12768"},

 {"item":4,  "store":"Dedeman",     "name":"Vas expansiune VRV100 100L",                 "url":"https://www.dedeman.ro/ro/vas-expansiune-pentru-sisteme-incalzire-vrv100-100-l/p/2002185"},
 {"item":4,  "store":"Romstal",     "name":"Vas expansiune Varem 100L 6 bar",            "url":"https://www.romstal.ro/vas-expansiune-pt-incalzire-vertical-varem-6-bar-100l.html"},
 {"item":4,  "store":"eMAG",        "name":"Vas expansiune Reflex N100 (echiv.)",        "url":"https://www.quickshop.ro/vas-expansiune-incalzire-reflex-n-100-6-1-5-bar-100-litri-p10148"},

 {"item":5,  "store":"Romstal",     "name":"Schimbător SWEP B10T 70 plăci (ref.)",       "url":"https://www.romstal.ro/schimbator-de-caldura-brazat-otel-inox-swep-b10t-25-bari-70-placi.html"},

 {"item":6,  "store":"Leroy Merlin","name":"Dedurizator AquaPUR Soft 10 Simplex",        "url":"https://www.leroymerlin.ro/produse/dedurizatoare/684/statie-de-dedurizare-aquapur-soft-10-simplex-cu-by-pass-q0.8-mch-rezervor-sare-28-kg/162202"},
 {"item":6,  "store":"Romstal",     "name":"Dedurizator Romstal Aquaone 10 Cab",         "url":"https://www.romstal.ro/statie-dedurizare-romstal-vision-aquaone-10-cab-q-0-8mc-h-bypass.html"},
 {"item":6,  "store":"eMAG",        "name":"Dedurizator AquaPUR Soft 10",                "url":"https://www.emag.ro/statie-de-dedurizare-dedurizator-aquapur-soft-10-48aq0111-2-6-bari-10-l-5945768012740/pd/DYJBQ0MBM/"},

 {"item":7,  "store":"Dedeman",     "name":"Pompă Wilo Yonos Pico 25/1-8 (echiv.)",      "url":"https://www.dedeman.ro/ro/pompa-de-circulatie-wilo-yonos-pico-1-0-25/1-8-75-w-q-max-4-3-mc/h-pn-10-230-v/p/2027883"},
 {"item":7,  "store":"Leroy Merlin","name":"Pompă Ferro 25-80 (echiv.)",                 "url":"https://www.leroymerlin.ro/produse/rezistente-supape-si-alte-accesorii/958/pompa-de-circulatie-ferro-25-80-h-max-8-m-l-180-mm-debit-maxim-3.3-mch/29186"},
 {"item":7,  "store":"eMAG",        "name":"Pompă Grundfos UPS 25-60/180 (echiv.)",      "url":"https://www.emag.ro/pompa-recirculare-ups-grundfos-25-60-180-1-x-230-v-5-mc-h-inaltime-6-m-63394/pd/DF9ZRWBBM/"},

 {"item":8,  "store":"Dedeman",     "name":"Pompă Wilo Yonos Pico 25/1-6 (echiv.)",      "url":"https://www.dedeman.ro/ro/pompa-de-circulatie-wilo-yonos-pico-1-0-25/1-6-41-w-q-max-3-5-mc/h-pn-10-230-v/p/2027882"},

 {"item":9,  "store":"Romstal",     "name":"DAB EVOPLUS B 150/280.50 M",                 "url":"https://www.romstal.ro/pompa-electronica-dab-evoplus-b-150-280-50-m.html"},
 {"item":10, "store":"Romstal",     "name":"DAB EVOPLUS B 150/280.50 M (idem 9)",        "url":"https://www.romstal.ro/pompa-electronica-dab-evoplus-b-150-280-50-m.html"},

 {"item":11, "store":"Dedeman",     "name":"Pompă Blautechnik 25-80-180 (echiv.)",       "url":"https://www.dedeman.ro/ro/pompa-de-circulatie-blautechnik-25-80-180-h-max-8-m-q-max-10-5-mc/h-pn10-230v/p/2020903"},
 {"item":11, "store":"Romstal",     "name":"DAB EVOPLUS 110/180 XM",                     "url":"https://www.romstal.ro/pompa-circulatie-dab-evoplus-110-180xm-p50127.html"},
 {"item":11, "store":"eMAG",        "name":"DAB EVOPLUS 110/180 XM (60150945)",          "url":"https://www.emag.ro/pompa-recirculare-electronica-dab-evoplus-110-180-xm-60150945/pd/D24NCFBBM/"},
 {"item":12, "store":"Romstal",     "name":"DAB EVOPLUS 110/180 XM (idem 11)",           "url":"https://www.romstal.ro/pompa-circulatie-dab-evoplus-110-180xm-p50127.html"},
 {"item":12, "store":"eMAG",        "name":"DAB EVOPLUS 110/180 XM (idem 11)",           "url":"https://www.emag.ro/pompa-recirculare-electronica-dab-evoplus-110-180-xm-60150945/pd/D24NCFBBM/"},

 {"item":13, "store":"Romstal",     "name":"Vană 3 căi Danfoss HFE 3 DN65",              "url":"https://www.romstal.ro/vana-3-cai-danfoss-hfe-3-dn-65.html"},
 {"item":14, "store":"Romstal",     "name":"Servomotor Danfoss AMB 162",                 "url":"https://www.romstal.ro/servomotor-danfoss-amb-162-230v-60-secunde.html"},

 {"item":15, "store":"Dedeman",     "name":"Filtru PUR 3 UF AquaPur",                    "url":"https://www.dedeman.ro/ro/filtru-apa-potabila-cu-ultrafiltrare-pur-3-uf-aquapur-10/p/2021327"},
 {"item":15, "store":"Romstal",     "name":"Filtru Valrom PUR 3UF 10",                   "url":"https://www.romstal.ro/sistem-ultra-filtrare-apa-in-3-trepte-valrom-pur-3uf-10.html"},
 {"item":15, "store":"eMAG",        "name":"Filtru PUR 3 UF AquaPur",                    "url":"https://www.emag.ro/filtru-apa-potabila-cu-ultrafiltrare-pur-3-uf-aquapur-10-n165/pd/DWHNGLYBM/"},
 {"item":15, "store":"Bricodepot",  "name":"Filtru Aquaphor Crystal (echiv.)",           "url":"https://www.bricodepot.ro/filtru-apa-crystal-trei-trepte-filtrare-aquaphor/cpd/101080896/"},

 {"item":18, "store":"Romstal",     "name":"Panou Atrea CP Touch (echiv., climasoft)",   "url":"https://www.climasoft.ro/panou-de-control-digital-atrea-cp-touch"},
 {"item":19, "store":"Romstal",     "name":"Ascensor MP GO (arhispec)",                  "url":"https://arhispec.ro/produs/ascensor-gearless-mp-go-evolution"},

 {"item":20, "store":"Dedeman",     "name":"Panou solar Sontec 30 tuburi",               "url":"https://www.dedeman.ro/ro/panou-solar-presurizat-sontec-spa-s58/1800a-inox-30-tuburi-montaj-pe-sarpanta-kit-montaj-inclus-apa-calda-5-persoane/p/2029978"},
 {"item":20, "store":"Romstal",     "name":"Panou solar Romstal 1800/30 tuburi",         "url":"https://www.romstal.ro/panou-solar-cu-tuburi-vidate-romstal-500-presurizat-1800-30-tuburi-1-8-kw.html"},

 {"item":21, "store":"Dedeman",     "name":"Cablu solar H1Z2Z2-K 6mmp",                  "url":"https://www.dedeman.ro/ro/cablu-solar-h1z2z2-k-1-x-6-mmp-pentru-sisteme-fotovoltaice-negru/p/1064036"},
 {"item":21, "store":"Leroy Merlin","name":"Cofret Schneider IP65 (echiv.)",             "url":"https://www.leroymerlin.ro/produse/tablouri-electrice/620/cofret-aparent-schneider-8-module-montaj-aparent-ip65/6785"},
 {"item":21, "store":"Romstal",     "name":"Power meter Huawei DTSU666-H",               "url":"https://www.romstal.ro/power-meter-trifazat-dtsu666-h-huawei.html"},
 {"item":21, "store":"eMAG",        "name":"Kit fotovoltaic 20kW Huawei+Jinko",          "url":"https://www.emag.ro/kit-panouri-fotovoltaice-20-kw-trifazat-complet-si-cu-montaj-inclus-huawei-jinko-20kw-t-j475/pd/DC6LKXYBM/"},

 {"item":23, "store":"Romstal",     "name":"Pompă submersibilă DAB S4 1/13 KIT",         "url":"https://www.romstal.ro/pompa-submersibila-s4-1-13-0-5hp-kit-4ol.html"},
 {"item":24, "store":"eMAG",        "name":"Rezervor subteran GRP 3000L (Fibromar)",     "url":"https://fibromar.ro/produs/rezervor-apa-pluviala-fibra-de-sticla-subteran-3000-l/"},
 {"item":25, "store":"eMAG",        "name":"Grup electrogen NPR-50 50kVA (echiv.)",      "url":"https://www.emag.ro/grup-electrogen-generator-electric-50-kva-cu-carcasa-si-aar-ats-npr-50/pd/DM29T4BBM/"},

 {"item":27, "store":"Dedeman",     "name":"Ventilator Vortice Lineo 125",               "url":"https://www.dedeman.ro/ro/ventilator-industrial-axial-pentru-tubulatura-vortice-lineo-125-plastic-ipx5-33-w-2140-rpm-365-mc/h-d-125-mm-220-240-v/p/2029562"},
 {"item":27, "store":"Leroy Merlin","name":"Ventilator Vents In-Line 125",               "url":"https://www.leroymerlin.ro/produse/ventilatie-baie/703/ventilator-in-line-125-mm-280-m3h-vents/22192"},
 {"item":27, "store":"eMAG",        "name":"Ventilator S&P TD-350/125 Silent",           "url":"https://www.emag.ro/ventilator-de-tubulatura-in-line-soler-palau-td-350-125-silent-5211360400/pd/DJHSKDMBM/"},
 {"item":27, "store":"Bricodepot",  "name":"Ventilator Vents 125 axial",                 "url":"https://www.bricodepot.ro/ventilator-axial-pentru-tubulatura-vents-23-37-w-125-mm-alb/cpd/100857765/"},

 {"item":28, "store":"Dedeman",     "name":"Ventilator baie Vents D 120 (174 mc/h)",     "url":"https://www.dedeman.ro/ro/ventilator-baie-axial-vents-d-cu-plasa-insecte-plastic-ip34-17-w-174-mc/h-d-120-mm/p/2034125"},
 {"item":28, "store":"Leroy Merlin","name":"Ventilator Vents D125 185 m³/h",             "url":"https://www.leroymerlin.ro/produse/ventilatoare-baie/703/ventilator-vents-d-125-mm-185-m3h-cu-jaluzele-automate/22187"},
 {"item":28, "store":"eMAG",        "name":"Ventilator Dospel Polo 5 150 mc/h",          "url":"https://www.emag.ro/ventilator-cu-senzor-de-umiditate-si-timer-diametru-120-mm-cu-debit-150-mc-h-dospel-polo-5-alb-20-007-0114/pd/D2M803BBM/"},
 {"item":28, "store":"Bricodepot",  "name":"Ventilator Vents 125 + timer",               "url":"https://www.bricodepot.ro/incalzire-si-climatizare/sisteme-de-ventilatie/fan-vents-switch-timer-125mat.html"},
]
# item 29 folosește aceleași ventilatoare ca item 28 (le clonăm)
for t in [x for x in TARGETS if x["item"]==28]:
    TARGETS.append({**t, "item":29})

# ---------------------------------------------------------------- selectori per magazin
CSS_SELECTORS = {
 "dedeman.ro":     ["[data-testid='product-price']", ".product-price .price", ".price-box .price", "span.price"],
 "emag.ro":        ["p.product-new-price", ".product-new-price", "[data-testid='product-price']"],
 "romstal.ro":     [".product-new-price", ".price .amount", "[itemprop='price']", ".product-price"],
 "leroymerlin.ro": ["[data-testid='price']", ".price__amount", ".m-price__amount", "span.price"],
 "bricodepot.ro":  [".product-price__value", ".price__value", "[itemprop='price']", ".product-price"],
 "quickshop.ro":   [".price", "[itemprop='price']", ".product-price"],
 "climasoft.ro":   [".price", "[itemprop='price']", ".product-price"],
 "fibromar.ro":    [".price", "ins .amount", ".woocommerce-Price-amount"],
 "arhispec.ro":    [".price", ".woocommerce-Price-amount", "[itemprop='price']"],
}

PRICE_RE = re.compile(r'(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\s*(?:lei|ron)', re.IGNORECASE)

def host_of(url):
    m = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return m.group(1) if m else ""

def norm_price(s):
    s = s.strip().replace('\xa0',' ')
    # 3.550,00 -> 3550.00 ; 3 550 -> 3550
    s = s.replace('.', '').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None

def from_jsonld(sb):
    try:
        blocks = sb.find_elements("script[type='application/ld+json']")
    except Exception:
        return None
    for b in blocks:
        raw = (b.get_attribute("innerHTML") or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                offers = node.get("offers")
                if isinstance(offers, dict) and offers.get("price"):
                    return str(offers["price"])
                if isinstance(offers, list):
                    for o in offers:
                        if isinstance(o, dict) and o.get("price"):
                            return str(o["price"])
                if node.get("price"):
                    return str(node["price"])
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    return None

def from_meta(sb):
    for sel in ["meta[itemprop='price']", "meta[property='product:price:amount']", "meta[property='og:price:amount']"]:
        try:
            el = sb.find_element(sel, timeout=1)
            v = el.get_attribute("content")
            if v:
                return v
        except Exception:
            pass
    return None

def from_css(sb, host):
    for sel in CSS_SELECTORS.get(host, []):
        try:
            el = sb.find_element(sel, timeout=1)
            txt = (el.text or el.get_attribute("content") or "").strip()
            if txt:
                return txt
        except Exception:
            pass
    return None

def from_regex(sb):
    try:
        body = sb.get_text("body")
    except Exception:
        return None
    m = PRICE_RE.search(body)
    return m.group(1) if m else None

def accept_cookies(sb):
    for sel in ["#onetrust-accept-btn-handler", "button#acceptCookies",
                "button[aria-label*='Accept']", "button:contains('Accept')",
                "button:contains('Sunt de acord')", ".cookie-accept"]:
        try:
            sb.click(sel, timeout=2)
            return
        except Exception:
            continue

def scrape_one(sb, t):
    host = host_of(t["url"])
    sb.uc_open_with_reconnect(t["url"], reconnect_time=6)
    try:
        sb.uc_gui_click_captcha()   # rezolvă Cloudflare Turnstile dacă apare
    except Exception:
        pass
    time.sleep(2.5)
    accept_cookies(sb)
    time.sleep(1.0)

    raw, method = None, None
    for fn, name in [(from_jsonld,"json-ld"), (from_meta,"meta"),
                     (lambda s: from_css(s,host),"css"), (from_regex,"regex")]:
        try:
            raw = fn(sb)
        except Exception:
            raw = None
        if raw:
            method = name
            break

    price = None
    if raw:
        m = PRICE_RE.search(raw) or re.search(r'\d[\d.\s,]*', raw)
        if m:
            price = norm_price(m.group(1) if m.re is PRICE_RE else m.group(0))
    return {"raw": raw, "price": price, "method": method or "negăsit", "host": host}

def main():
    headless = "--head" not in sys.argv
    from seleniumbase import SB
    rows = []
    with SB(uc=True, headless=headless, locale_code="ro") as sb:
        for i, t in enumerate(TARGETS, 1):
            print(f"[{i}/{len(TARGETS)}] item {t['item']:>2} · {t['store']:<12} · {t['name'][:40]}")
            try:
                r = scrape_one(sb, t)
            except Exception as e:
                r = {"raw":None,"price":None,"method":f"eroare: {e.__class__.__name__}","host":host_of(t['url'])}
            row = {**t, **r}
            price_str = f"{r['price']:.2f} lei" if r["price"] else "—"
            print(f"        -> {price_str}   ({r['method']})   raw={str(r['raw'])[:50]}")
            rows.append(row)
            time.sleep(1.5)   # politicos între cereri

    with open("prices.json","w",encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with open("prices.csv","w",encoding="utf-8",newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item","store","name","price","method","raw","url"])
        w.writeheader()
        for r in rows:
            w.writerow({k:r.get(k,"") for k in w.fieldnames})
    ok = sum(1 for r in rows if r["price"])
    print(f"\nGata: {ok}/{len(rows)} prețuri extrase.  ->  prices.csv / prices.json")

if __name__ == "__main__":
    main()
