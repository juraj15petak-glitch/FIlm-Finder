import os
from urllib.parse import quote_plus

import requests
import streamlit as st

def alternativne_odkazy(nazov: str) -> dict:
    q = quote_plus(nazov)
    return {
        "🔎 Hľadať dabing / kde pozrieť": f"https://www.google.com/search?q={q}+dabing+kde+pozrieť",
        "🎞️ ČSFD (dabing, tvorcovia, recenzie)": f"https://www.csfd.cz/hledat/?q={q}",
        "📺 JustWatch": f"https://www.justwatch.com/sk/vyhladavanie?q={q}",
    }

# ---------------------------------------------------------------------------
# Konfigurácia
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Kde pozrieť film", page_icon="🎬", layout="wide")

TMDB_BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w342"


def nacitaj_api_kluc() -> str:
    try:
        if "TMDB_API_KEY" in st.secrets:
            return st.secrets["TMDB_API_KEY"]
    except Exception:
        pass
    return os.getenv("TMDB_API_KEY", "")


API_KEY = nacitaj_api_kluc()

# Oficiálne platformy: názov -> (kľúčové slová v názve poskytovateľa z TMDB, šablóna odkazu)
PLATFORMY = {
    "Netflix": (["netflix"], "https://www.netflix.com/search?q={q}"),
    "Max": (["max", "hbo"], "https://www.google.com/search?q=site:max.com+{q}"),
    "Disney+": (["disney"], "https://www.google.com/search?q=site:disneyplus.com+{q}"),
    "SkyShowtime": (["skyshowtime"], "https://www.google.com/search?q=site:skyshowtime.com+{q}"),
    "Prime Video": (["amazon prime", "prime video"], "https://www.primevideo.com/search/?phrase={q}"),
    "Apple TV+": (["apple tv"], "https://www.google.com/search?q=site:tv.apple.com+{q}"),
}

# Legálne bezplatné / verejnoprávne zdroje
LEGALNE_ZDROJE = {
    "JOJ Play": ("Slovenské TV archívy, časť obsahu zadarmo s reklamou.", "https://www.google.com/search?q=site:play.joj.sk+{q}"),
    "RTVS / STVR": ("Verejnoprávny archív, slovenský dabing a tvorba.", "https://www.google.com/search?q=site:rtvs.sk+{q}"),
    "Prima+": ("České filmy a seriály, časť zadarmo s reklamou.", "https://www.google.com/search?q=site:iprima.cz+{q}"),
    "Voyo (Markíza)": ("Slovenský obsah, časť zdarma, väčšina v predplatnom.", "https://www.google.com/search?q=site:voyo.markiza.sk+{q}"),
    "Internet Archive": ("Voľné diela (public domain), legálne zadarmo.", "https://archive.org/search?query={q}&and[]=mediatype%3A%22movies%22"),
    "Knižničné služby (Kanopy)": ("Zadarmo cez členstvo vo vašej knižnici, ak ho ponúka.", "https://www.kanopy.com/en/search?query={q}"),
}

JAZYKY = {"sk": "slovenčina", "cs": "čeština", "en": "angličtina", "de": "nemčina", "fr": "francúzština",
          "es": "španielčina", "it": "taliančina", "ja": "japončina", "ko": "kórejčina", "pl": "poľština",
          "hu": "maďarčina", "ru": "ruština"}


# ---------------------------------------------------------------------------
# TMDB volania
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def hladaj(dotaz: str, api_key: str) -> list[dict]:
    r = requests.get(
        f"{TMDB_BASE}/search/multi",
        params={"api_key": api_key, "query": dotaz, "language": "sk-SK", "include_adult": "false"},
        timeout=10,
    )
    r.raise_for_status()
    return [x for x in r.json().get("results", []) if x.get("media_type") in ("movie", "tv")]


@st.cache_data(ttl=3600, show_spinner=False)
def detail(typ: str, tmdb_id: int, api_key: str) -> dict:
    r = requests.get(f"{TMDB_BASE}/{typ}/{tmdb_id}", params={"api_key": api_key, "language": "sk-SK"}, timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=3600, show_spinner=False)
def poskytovatelia(typ: str, tmdb_id: int, api_key: str) -> dict:
    r = requests.get(f"{TMDB_BASE}/{typ}/{tmdb_id}/watch/providers", params={"api_key": api_key}, timeout=10)
    r.raise_for_status()
    return r.json().get("results", {})


# ---------------------------------------------------------------------------
# Pomocné funkcie
# ---------------------------------------------------------------------------
def najdi_platformu(nazov_poskytovatela: str) -> str | None:
    n = nazov_poskytovatela.lower()
    for platforma, (slova, _) in PLATFORMY.items():
        if any(s in n for s in slova):
            return platforma
    return None


def dostupnost(prov: dict, krajiny: list[str]) -> dict:
    """Vráti {platforma: {'typy': set(...), 'krajiny': set(...)}} pre zvolené krajiny."""
    vysledok = {}
    for krajina in krajiny:
        data = prov.get(krajina, {})
        for kluc, popis in (("flatrate", "predplatné"), ("free", "zadarmo"), ("ads", "zadarmo s reklamou"),
                            ("rent", "požičanie"), ("buy", "kúpa")):
            for p in data.get(kluc, []):
                plat = najdi_platformu(p.get("provider_name", ""))
                if plat:
                    zaznam = vysledok.setdefault(plat, {"typy": set(), "krajiny": set()})
                    zaznam["typy"].add(popis)
                    zaznam["krajiny"].add(krajina)
    return vysledok


def odkaz(sablona: str, dotaz: str) -> str:
    return sablona.format(q=quote_plus(dotaz))


def justwatch_odkaz(dotaz: str, krajina: str) -> str:
    return f"https://www.justwatch.com/{krajina.lower()}/vyhladavanie?q={quote_plus(dotaz)}"


# ---------------------------------------------------------------------------
# Bočný panel – filtre
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🎛️ Filtre")

    typ_filter = st.radio("Typ obsahu", ["Všetko", "Filmy", "Seriály"])
    krajiny_vyber = st.multiselect("Krajina dostupnosti", ["SK", "CZ"], default=["SK", "CZ"])
    vybrane_platformy = st.multiselect("Oficiálne platformy", list(PLATFORMY), default=list(PLATFORMY))
    iba_dostupne = st.checkbox("Iba tituly dostupné na vybraných platformách", value=False)
    zobraz_legalne = st.checkbox("Zobraziť legálne bezplatné zdroje", value=True)
    max_vysledkov = st.slider("Počet výsledkov", 1, 10, 5)

    st.divider()
    st.subheader("📡 Stav pripojenia")
    if API_KEY:
        st.success("TMDB API kľúč je nastavený.")
    else:
        st.warning("Chýba `TMDB_API_KEY`.")
        st.code('# .streamlit/secrets.toml\nTMDB_API_KEY = "váš_kľúč"', language="toml")

    st.caption("Dostupnosť pochádza z TMDB (dáta JustWatch). Dostupnosť slovenského/českého dabingu si "
               "overte priamo na platforme, TMDB ju po jednotlivých platformách neeviduje.")

# ---------------------------------------------------------------------------
# Hlavná časť
# ---------------------------------------------------------------------------
st.title("🎬 Kde pozrieť film alebo seriál")
dotaz = st.text_input("Názov filmu alebo seriálu", placeholder="napr. Pán prsteňov, Wednesday, Kolja…")

if not API_KEY:
    st.info("Pre fungovanie vyhľadávania doplňte TMDB API kľúč (pozri bočný panel).")
    st.stop()

if not dotaz.strip():
    st.write("Zadajte názov a ukážem vám, kde sa dá legálne pozrieť.")
    st.stop()

try:
    with st.spinner("Hľadám…"):
        vysledky = hladaj(dotaz.strip(), API_KEY)
except requests.exceptions.RequestException as e:
    st.error(f"Nepodarilo sa kontaktovať TMDB: {e}")
    st.stop()

if typ_filter == "Filmy":
    vysledky = [v for v in vysledky if v["media_type"] == "movie"]
elif typ_filter == "Seriály":
    vysledky = [v for v in vysledky if v["media_type"] == "tv"]

zobrazene = 0
for v in vysledky:
    if zobrazene >= max_vysledkov:
        break

    typ, tmdb_id = v["media_type"], v["id"]
    nazov = v.get("title") or v.get("name") or "Bez názvu"
    rok = (v.get("release_date") or v.get("first_air_date") or "")[:4]

    try:
        prov = poskytovatelia(typ, tmdb_id, API_KEY)
        det = detail(typ, tmdb_id, API_KEY)
    except requests.exceptions.RequestException:
        prov, det = {}, {}

    dost = {k: x for k, x in dostupnost(prov, krajiny_vyber).items() if k in vybrane_platformy}
    if iba_dostupne and not dost:
        continue
    zobrazene += 1

    with st.container(border=True):
        c1, c2 = st.columns([1, 3])

        with c1:
            if v.get("poster_path"):
                st.image(IMG_BASE + v["poster_path"], use_container_width=True)
            else:
                st.write("🖼️ bez plagátu")

        with c2:
            st.subheader(f"{nazov} ({rok})" if rok else nazov)
            st.caption(("🎞️ Film" if typ == "movie" else "📺 Seriál")
                       + (f" · ⭐ {v['vote_average']:.1f}/10" if v.get("vote_average") else ""))
            if v.get("overview"):
                st.write(v["overview"])

st.markdown("**Hľadať ďalej:**")
for popis, url in alternativne_odkazy(nazov).items():
    st.link_button(popis, url)

            # Jazyky
            povodny = JAZYKY.get(v.get("original_language", ""), v.get("original_language", "neznámy"))
            hovorene = [JAZYKY.get(j.get("iso_639_1"), j.get("english_name", "")) for j in det.get("spoken_languages", [])]
            st.markdown(f"**Pôvodný jazyk:** {povodny}" + (f" · **Zvuk vo filme:** {', '.join(hovorene)}" if hovorene else ""))

            tab1, tab2 = st.tabs(["✅ Oficiálne platformy", "🆓 Legálne bezplatné zdroje"])

            with tab1:
                if not vybrane_platformy:
                    st.write("Vyberte aspoň jednu platformu v bočnom paneli.")
                for platforma in vybrane_platformy:
                    sablona = PLATFORMY[platforma][1]
                    p1, p2 = st.columns([2, 3])
                    if platforma in dost:
                        info = dost[platforma]
                        p1.markdown(f"**{platforma}** ✅")
                        p2.markdown(
                            f"{', '.join(sorted(info['typy']))} ({', '.join(sorted(info['krajiny']))}) · "
                            f"[Otvoriť]({odkaz(sablona, nazov)})"
                        )
                        st.caption("🗣️ Dabing a titulky: overte v detaile titulu na platforme.") if False else None
                    else:
                        p1.markdown(f"**{platforma}** ➖")
                        p2.markdown(f"Nenájdené v zvolených krajinách · [Hľadať ručne]({odkaz(sablona, nazov)})")

                kr = krajiny_vyber[0] if krajiny_vyber else "SK"
                st.markdown(f"🔎 [Všetky možnosti na JustWatch]({justwatch_odkaz(nazov, kr)}) – "
                            "tam nájdete aj filter na jazyk zvuku a titulkov.")
                st.caption("🗣️ Slovenský/český dabing a titulky sa líšia podľa titulu a platformy. "
                           "Na platforme ich uvidíte v detaile titulu (ikona Zvuk a titulky).")

            with tab2:
                if not zobraz_legalne:
                    st.write("Zapnite zobrazenie v bočnom paneli.")
                else:
                    for zdroj, (popis, sablona) in LEGALNE_ZDROJE.items():
                        z1, z2 = st.columns([2, 3])
                        z1.markdown(f"**{zdroj}**")
                        z2.markdown(f"{popis} [Hľadať]({odkaz(sablona, nazov)})")

if zobrazene == 0:
    st.warning("Nič sa nenašlo. Skúste iný názov alebo upravte filtre.")

st.caption("Údaje poskytuje TMDB. Táto aplikácia nie je podporovaná ani certifikovaná TMDB.")
