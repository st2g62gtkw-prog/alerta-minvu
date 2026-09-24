"""Alerta Minvu: avisa al celular (ntfy) cuando aparece un llamado nuevo DS1 / DS49.

Fuentes:
  1. Portada de minvu.gob.cl -> links nuevos a /postulacion/...llamado...
  2. Google News RSS -> noticias de apertura de postulaciones DS1 / DS49

Guarda lo ya visto en seen.json para avisar una sola vez por cosa.
"""
import json, os, re, sys, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

TOPIC = os.environ.get("NTFY_TOPIC", "minvu-nico-b9fca7ad")
SEEN_FILE = "seen.json"
UA = {"User-Agent": "Mozilla/5.0 (alerta-minvu)"}

SUBSIDIO = re.compile(r"d\.?\s?s\.?\s?(n[°º]?\s?)?(1|49)\b|sectores medios|fondo solidario", re.I)
APERTURA = re.compile(r"abre|abri[óo]|abiert|inicia|comienza|apertura|llamado|postulaci[óo]n|postular", re.I)


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def notify(title, body, url=None, priority="high"):
    headers = {"Title": title.encode("utf-8"), "Priority": priority, "Tags": "house"}
    if url:
        headers["Click"] = url
    req = urllib.request.Request(f"https://ntfy.sh/{TOPIC}", data=body.encode("utf-8"), headers=headers)
    urllib.request.urlopen(req, timeout=30)
    print("NOTIFICADO:", title)


def minvu_links():
    html = get("https://www.minvu.gob.cl/")
    out = {}
    for href, text in re.findall(r'<a[^>]+href="(https://www\.minvu\.gob\.cl/(?:postulacion|noticia)/[^"#?]+)"[^>]*>(.*?)</a>', html, re.S):
        text = re.sub(r"<[^>]+>|\s+", " ", text).strip()
        slug = href.lower()
        if "llamado" in slug or "postula" in slug:
            if SUBSIDIO.search(slug.replace("-", " ")) or SUBSIDIO.search(text) or "sectores-medios" in slug or "fondo-solidario" in slug:
                out[href] = text or href
    return out


def news():
    out = {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    for q in ['Minvu postulación DS1', 'Minvu postulación DS49', 'Minvu llamado "sectores medios"', 'Minvu llamado "fondo solidario"']:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:3d", "hl": "es-419", "gl": "CL", "ceid": "CL:es-419"})
        try:
            root = ET.fromstring(get(url))
        except Exception as e:
            print("news error", q, e)
            continue
        for it in root.iter("item"):
            title = it.findtext("title") or ""
            link = it.findtext("link") or ""
            try:
                if parsedate_to_datetime(it.findtext("pubDate")) < cutoff:
                    continue
            except Exception:
                pass
            if SUBSIDIO.search(title) and APERTURA.search(title):
                out[link] = title
    return out


def main():
    if os.environ.get("MODO") == "prueba":
        notify("🧪 Prueba Alerta Minvu", "Funciona. Cuando se abra un llamado DS1 o DS49 te llega un aviso así.")
        return

    first_run = not os.path.exists(SEEN_FILE)
    seen = {} if first_run else json.load(open(SEEN_FILE, encoding="utf-8"))

    found = {}
    try:
        found.update({k: ("Minvu", v) for k, v in minvu_links().items()})
    except Exception as e:
        print("minvu error", e)
    try:
        found.update({k: ("Noticia", v) for k, v in news().items()})
    except Exception as e:
        print("news error", e)

    new = {k: v for k, v in found.items() if k not in seen}
    for link, (src, title) in new.items():
        seen[link] = title
        if not first_run:
            notify(f"🏠 Minvu: posible llamado DS1/DS49 ({src})", title, link, "urgent" if src == "Minvu" else "high")

    if first_run:
        print(f"Primera ejecución: {len(new)} elementos marcados como vistos, sin avisar.")
    else:
        print(f"{len(new)} nuevos." if new else "Sin novedades.")

    json.dump(seen, open(SEEN_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
