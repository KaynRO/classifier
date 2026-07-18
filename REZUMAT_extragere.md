# Rezumat extragere prețuri live — 18 iulie 2026

Sursă: paginile-produs din `scrape_preturi.py` (49 URL-uri, 53 ținte item×magazin,
poz. 29 clonând ventilatoarele poz. 28).

## Rezultat

| Categorie | Nr. |
|---|---|
| **Prețuri confirmate LIVE** (exact, din JSON-LD / meta al paginii) | **27** |
| Preț „hint" Romstal (preț listat 19‑06‑2026, randat JS — **neconfirmat live**) | 12 |
| Neobtenabil (anti-bot / timeout / produs fără preț public) | 14 |
| **Total ținte** | **53** |

**Confirmate live pe magazin:** Dedeman 11 · eMAG 13 · Romstal 3.

## Ce s-a actualizat în `.docx`
- 22 celule de preț rescrise cu prețul live exact (hyperlink albastru + link-sursă păstrate).
- 5 prețuri live confirmate au picat pe celule care nu conțineau un preț simplu
  („—", „componente", „KIT complet") → nu am modificat celula, ci am notat prețul în „Observații".
- Fiecare rând (24 în total) are în „Observații" un audit: `Live 18 iulie 2026: Magazin X lei✓ … Neconfirmat: …`.
- Antet: linia „Prețuri verificate live: 18 iulie 2026".
- Lățimile de coloană / layout landscape A4 / coloana verde de estimare: neatinse.

## Neobtenabile (păstrat valoarea anterioară, marcat „neconf. live")
- **Leroy Merlin** (7 celule): Cloudflare 403 — blocare anti-bot consecventă.
- **Bricodepot** (4 celule): timeout consecvent (blocare la nivel de rețea).
- **Romstal poz. 18** (climasoft.ro) 403 Cloudflare; **poz. 19** (arhispec.ro) fără preț public.
- **eMAG poz. 27** (S&P TD‑350): rate‑limit 511 (celelalte 13 eMAG au ieșit live).
- **Romstal, 12 celule** cu preț randat prin JavaScript: în HTML există doar prețul din
  jurnalul de preț (`price_log`, datat 19‑06‑2026) — folosit ca reper, **nu** ca preț live.

## Note tehnice
- Scraperul original (SeleniumBase UC / Chrome) nu poate funcționa în acest mediu:
  browserul nu traversează proxy-ul de egress (toate site-urile `.ro` → `ERR_CONNECTION_RESET`).
  S-a folosit extragere prin HTTP (requests) prin proxy + parsare JSON-LD/meta — vezi `scrape_http.py`.
- Fișiere: `scrape_http.py` (extragere), `retry_http.py` (reîncercări cu spațiere),
  `update_docx.py` (actualizare tabel), `prices.csv` / `prices.json` (date brute),
  `Comparatie_preturi_deviz_actualizat.docx` (rezultat).
