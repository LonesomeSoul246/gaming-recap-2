"""Gaming Recap – Benachrichtigungen ohne PC (läuft als GitHub Action alle 3 Std).
Prüft Epic-Gratisspiele und Angebote auf der Steam-Wunschliste und schickt sie über ntfy aufs Handy.
Braucht nur zwei Geheimnisse im Repository: NTFY_TOPIC und STEAM_ID. Keine Passwörter, keine Zugangs-Codes.
Einstellungen (welche Themen, Nachtruhe) kommen aus notify.json, die dein PC hier ablegt."""
import json, os, sys, time, urllib.parse, urllib.request, datetime as dt
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

UA = {"User-Agent": "GamingRecap-CloudNotify"}


def get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def hdr(t):
    try:
        t.encode("latin-1"); return t
    except UnicodeEncodeError:
        import base64
        return "=?UTF-8?B?" + base64.b64encode(t.encode()).decode() + "?="


def push(topic, title, body, url=None, delay=None):
    h = {"Title": hdr(title), "Tags": "video_game,cloud"}
    if url:
        h["Click"] = url
    if delay:
        h["Delay"] = str(int(delay))
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), headers=h, method="POST"), timeout=20).read()


def norm(t):
    return "".join(c for c in (t or "").lower() if c.isalnum())


def epic_now():
    j = get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=de&country=DE&allowCountries=DE")
    out = []
    for el in (((j.get("data") or {}).get("Catalog") or {}).get("searchStore") or {}).get("elements") or []:
        for block in ((el.get("promotions") or {}).get("promotionalOffers")) or []:
            for o in block.get("promotionalOffers") or []:
                if int((o.get("discountSetting") or {}).get("discountPercentage", 100)) == 0:
                    slug = el.get("productSlug") or next((m.get("pageSlug") for m in (el.get("catalogNs") or {}).get("mappings") or [] if m.get("pageSlug")), None)
                    out.append((norm(el.get("title")), el.get("title"), f"https://store.epicgames.com/de/p/{slug}" if slug else "https://store.epicgames.com/de/free-games"))
    return list({k: (k, t, u) for k, t, u in out}.values())


def resolve_steamid(v):
    """Steam-ID (Zahl), Profil-Link oder eigener Profilname → SteamID64 (über das öffentliche Profil, ohne Schlüssel)."""
    import re
    v = v.strip().rstrip("/")
    m = re.search(r"(7656119\d{10})", v)
    if m:
        return m.group(1)
    name = v.split("/id/")[-1].split("/")[0]
    with urllib.request.urlopen(urllib.request.Request(f"https://steamcommunity.com/id/{urllib.parse.quote(name)}/?xml=1", headers=UA), timeout=30) as r:
        xml = r.read().decode("utf-8", "ignore")
    m = re.search(r"<steamID64>(\d+)</steamID64>", xml)
    if not m:
        raise RuntimeError(f"Steam-Profil „{name}“ nicht gefunden (Profil öffentlich?)")
    return m.group(1)


def wishlist_sales(steamid):
    steamid = resolve_steamid(steamid)
    wl = get("https://api.steampowered.com/IWishlistService/GetWishlist/v1/?" + urllib.parse.urlencode({"steamid": steamid}))
    ids = [str(x["appid"]) for x in ((wl.get("response") or {}).get("items") or [])]
    out = {}
    for i in range(0, len(ids), 50):
        part = ids[i:i + 50]
        j = get("https://store.steampowered.com/api/appdetails?" + urllib.parse.urlencode({"appids": ",".join(part), "filters": "price_overview", "cc": "de"}))
        for a in part:
            po = ((j.get(a) or {}).get("data") or {})
            po = po.get("price_overview") if isinstance(po, dict) else None
            if po and int(po.get("discount_percent") or 0) > 0:
                out[a] = (int(po["discount_percent"]), po.get("final_formatted"))
        time.sleep(1.5)
    names = {}
    if out:   # Namen nur für Angebote holen
        for a in list(out)[:15]:
            try:
                d = (get(f"https://store.steampowered.com/api/appdetails?appids={a}&filters=basic&cc=de").get(a) or {}).get("data") or {}
                names[a] = d.get("name")
            except Exception:
                pass
            time.sleep(1.2)
    return out, names


def main():
    topic, steamid = os.environ.get("NTFY_TOPIC", "").strip(), os.environ.get("STEAM_ID", "").strip()
    cfg = json.load(open("notify.json", encoding="utf-8")) if os.path.exists("notify.json") else {}
    st = json.load(open("notify-state.json", encoding="utf-8")) if os.path.exists("notify-state.json") else {}
    st.setdefault("free_seen", []); st.setdefault("sale_seen", {})
    first = not st.get("init")
    status = []
    if not topic:
        status.append("NTFY_TOPIC fehlt")
    cats, on = cfg.get("cats") or {}, bool(topic) and cfg.get("phone", True) and cfg.get("enabled", True)
    tz = ZoneInfo(cfg.get("tz") or "Europe/Berlin") if ZoneInfo else None
    now = dt.datetime.now(tz) if tz else dt.datetime.now()
    delay = None
    q = cfg.get("quiet")
    if q and (q[0] <= now.hour < q[1] if q[0] < q[1] else (now.hour >= q[0] or now.hour < q[1])):
        end = now.replace(hour=q[1], minute=0, second=0, microsecond=0)
        if end <= now:
            end += dt.timedelta(days=1)
        delay = int(end.timestamp()) + 60
    sent = 0
    try:
        free = epic_now()
        new = [x for x in free if x[0] not in st["free_seen"]]
        if new and on and cats.get("free", True) and not first:
            push(topic, "Gratis bei Epic", ", ".join(t for _, t, _ in new[:3]) + " – jetzt kostenlos holen.", new[0][2], delay); sent += 1
        st["free_seen"] = sorted(set(st["free_seen"]) | {k for k, _, _ in free})[-200:]
    except Exception as e:
        status.append(f"Epic: {e}")
    if steamid:
        try:
            sales, names = wishlist_sales(steamid)
            fresh = [a for a, (pct, _) in sales.items() if st["sale_seen"].get(a) != pct]
            if fresh and on and cats.get("sales", True) and not first:
                if len(fresh) <= 3:
                    for a in fresh:
                        pct, price = sales[a]
                        push(topic, "Wunschliste im Angebot", f"{names.get(a) or 'Ein Spiel'}: -{pct} % für {price}", f"https://store.steampowered.com/app/{a}", delay); sent += 1
                else:
                    top = sorted(fresh, key=lambda a: -sales[a][0])[:4]
                    push(topic, f"{len(fresh)} Spiele deiner Wunschliste im Angebot",
                         " · ".join(f"{names.get(a) or a} -{sales[a][0]} %" for a in top), "https://store.steampowered.com/wishlist/", delay); sent += 1
            st["sale_seen"] = {a: pct for a, (pct, _) in sales.items()}
        except Exception as e:
            status.append(f"Steam: {e}")
    else:
        status.append("STEAM_ID fehlt")
    st["init"] = True
    st["last_day"] = now.strftime("%Y-%m-%d")
    st["status"] = status
    old = open("notify-state.json", encoding="utf-8").read() if os.path.exists("notify-state.json") else ""
    new_txt = json.dumps(st, ensure_ascii=False, sort_keys=True, indent=1)
    if new_txt != old:
        open("notify-state.json", "w", encoding="utf-8").write(new_txt)
    print(f"{sent} Nachrichten gesendet", "; ".join(status))


if __name__ == "__main__":
    main()
