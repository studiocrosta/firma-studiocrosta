"""
Firma email dinamica di Studio Crosta.

Dal link di una scheda corso genera:
  docs/firma.png   -> l'immagine della firma (foto del corso + titolo, date, ore)
  docs/corso.html  -> la pagina ponte che porta alla scheda del corso

Uso:
  python genera_firma.py https://studiocrosta.com/it/corso/10/3171
  python genera_firma.py LINK --titolo "Addetti antincendio – livello 2"
  python genera_firma.py LINK --info "Lunedì 23 novembre · 8 ore · in aula a Fermo"

Titolo e info sono facoltativi: se mancano li legge dalla pagina.
"""

import argparse
import base64
import html
import io
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date

LARGHEZZA, ALTEZZA = 520, 140
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
UA = {"User-Agent": "Mozilla/5.0 (firma Studio Crosta)"}

# Duotono blu: ombre, toni medi, luci. Per un blu più leggero schiarisci i tre colori.
DUOTONO = ("#1d2466", "#6470c0", "#f0f2fb")


def scarica(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def foto_duotono(sorgente):
    """Scarica la foto, la porta in bianco e nero, ne normalizza la luminosità
    (così foto chiare e scure rendono uguale) e la colora con i tre toni di DUOTONO."""
    from PIL import Image, ImageOps
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=)([\w-]+)", sorgente)
    if m:
        sorgente = f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    if re.match(r"https?://", sorgente):
        req = urllib.request.Request(sorgente, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            dati = r.read()
    else:
        dati = open(sorgente, "rb").read()
    im = Image.open(io.BytesIO(dati)).convert("L")
    im = ImageOps.autocontrast(im, cutoff=2)
    ombre, medi, luci = DUOTONO
    im = ImageOps.colorize(im, black=ombre, mid=medi, white=luci)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def testo(frammento):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", frammento))).strip()


def leggi_scheda(link, pagina):
    """Estrae i dati del corso principale (non quelli delle card in fondo alla pagina)."""
    principale = pagina.split("Calendario Lezioni", 1)
    blocco = pagina[: pagina.find("</section>", pagina.find("<h1")) + 1]

    m = re.search(r"<h1[^>]*>(.*?)</h1>", blocco, re.S | re.I)
    titolo = testo(m.group(1)) if m else ""

    m = re.search(r"Durata Corso:</b>\s*<br>\s*([\d,\.]+)\s*ore", blocco, re.I)
    ore = m.group(1) if m else ""

    m = re.search(r"Sede:</b>\s*<br>(.*?)<b>", blocco, re.S | re.I)
    sede = testo(m.group(1)) if m else ""

    date_lezioni = []
    if len(principale) > 1:
        cal = principale[1].split("Costo", 1)[0]
        for g, mth, a in re.findall(r"(\d{2})/(\d{2})/(\d{4})", cal):
            d = date(int(a), int(mth), int(g))
            if d not in date_lezioni:
                date_lezioni.append(d)

    m = re.search(r'thumb\.php\?src=([\w-]+\.(?:jpg|jpeg|png))', blocco, re.I)
    foto = urllib.parse.urljoin(link, f"/corsi/thumb.php?src={m.group(1)}&w=800&h=530") if m else ""

    return {"titolo": titolo, "ore": ore, "sede": sede, "date": date_lezioni, "foto": foto}


def titolo_breve(t, massimo=62):
    t = re.sub(r"^Corso\s+(di\s+)?(formazione\s+)?(teorico-pratico\s+)?(per\s+)?", "", t, flags=re.I).strip()
    t = t[:1].upper() + t[1:]
    if len(t) <= massimo:
        return t
    return t[:massimo].rsplit(" ", 1)[0].rstrip(" ,-–") + "…"


def etichetta_date(giorni):
    if not giorni:
        return ""
    a, b = giorni[0], giorni[-1]
    ga = GIORNI[a.weekday()].capitalize()
    if a == b:
        return f"{ga} {a.day} {MESI[a.month - 1]}"
    if len(giorni) == 2 and a.month == b.month:
        return f"{ga} {a.day} e {GIORNI[b.weekday()]} {b.day} {MESI[b.month - 1]}"
    if a.month == b.month:
        return f"Dal {a.day} al {b.day} {MESI[b.month - 1]}"
    return f"Dal {a.day} {MESI[a.month - 1]} al {b.day} {MESI[b.month - 1]}"


def componi_info(dati):
    pezzi = [etichetta_date(dati["date"])]
    if dati["ore"]:
        pezzi.append(f"{dati['ore']} ore")
    if "fermo" in dati["sede"].lower():
        pezzi.append("in aula a Fermo")
    elif dati["sede"]:
        pezzi.append(dati["sede"])
    return " · ".join(p for p in pezzi if p)


def banner_html(titolo, info, foto, etichetta="Corso in evidenza", cta="Scheda e iscrizione"):
    e = html.escape
    img = f'<img src="{e(foto)}" alt="">' if foto else ""
    size = 19 if len(titolo) <= 24 else 17
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#fff}}
.b{{width:{LARGHEZZA}px;height:{ALTEZZA}px;display:flex;overflow:hidden;font-family:'Segoe UI','Open Sans',Arial,sans-serif}}
.foto{{width:190px;flex-shrink:0;background:#2e3a96;overflow:hidden;position:relative}}
.foto img{{width:100%;height:100%;object-fit:cover;display:block}}
.foto:after{{content:"";position:absolute;right:0;top:0;bottom:0;width:4px;background:#d4a843}}
.m{{flex:1;background:#f6ecd2;padding:0 20px;display:flex;flex-direction:column;justify-content:center;gap:4px}}
.k{{font-size:10px;font-weight:700;letter-spacing:2.4px;text-transform:uppercase;color:#6f6136}}
.t{{font-size:{size}px;font-weight:800;line-height:1.2;color:#1a1a1a;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.d{{font-size:13px;color:#4a4a4a}}
.l{{font-size:13px;font-weight:700;color:#2e3a96;margin-top:3px}}
</style></head><body><div class="b">
<div class="foto">{img}</div>
<div class="m"><div class="k">{e(etichetta)}</div><div class="t">{e(titolo)}</div>
<div class="d">{e(info)}</div><div class="l">{e(cta)} &rsaquo;</div></div>
</div></body></html>"""


def redirect_html(link):
    l = html.escape(link, quote=True)
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={l}"><title>Studio Crosta</title>
<script>location.replace({link!r});</script></head>
<body><a href="{l}">Vai alla scheda del corso</a></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("link", help="link della scheda corso")
    ap.add_argument("--titolo", default="", help="titolo breve (facoltativo)")
    ap.add_argument("--info", default="", help="riga date/ore (facoltativa)")
    ap.add_argument("--foto", default="", help="link di un'altra foto (facoltativo)")
    ap.add_argument("--etichetta", default="", help="scritta in alto, es. Formazione finanziata")
    ap.add_argument("--cta", default="", help="testo del link in basso, es. Scopri di più")
    ap.add_argument("--manuale", action="store_true", help="non legge la pagina: usa solo i campi indicati")
    ap.add_argument("--pagina", default="", help=argparse.SUPPRESS)  # file HTML locale, per le prove
    a = ap.parse_args()

    if a.manuale:
        dati = {"titolo": "", "ore": "", "sede": "", "date": [], "foto": ""}
    else:
        pagina = open(a.pagina, encoding="utf-8").read() if a.pagina else scarica(a.link)
        dati = leggi_scheda(a.link, pagina)
    titolo = a.titolo.strip() or titolo_breve(dati["titolo"])
    info = a.info.strip() or componi_info(dati)
    etichetta = a.etichetta.strip() or ("In evidenza" if a.manuale else "Corso in evidenza")
    cta = a.cta.strip().rstrip("›> ").strip() or ("Scopri di più" if a.manuale else "Scheda e iscrizione")
    foto = a.foto.strip() or dati["foto"]
    if not titolo:
        sys.exit("Non ho trovato il titolo nella pagina: indicalo con --titolo")

    print(f"Titolo: {titolo}\nInfo:   {info}\nFoto:   {foto or '(nessuna)'}")
    foto_img = foto_duotono(foto) if foto else ""

    os.makedirs("docs", exist_ok=True)
    with open("docs/banner.html", "w", encoding="utf-8") as f:
        f.write(banner_html(titolo, info, foto_img, etichetta, cta))
    with open("docs/corso.html", "w", encoding="utf-8") as f:
        f.write(redirect_html(a.link))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        exe = os.environ.get("CHROMIUM_PATH")
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": LARGHEZZA, "height": ALTEZZA}, device_scale_factor=2)
        pg.goto("file://" + os.path.abspath("docs/banner.html"), wait_until="networkidle")
        pg.locator(".b").screenshot(path="docs/firma.png")
        b.close()
    os.remove("docs/banner.html")
    print("Fatto: docs/firma.png e docs/corso.html")


if __name__ == "__main__":
    main()
