import streamlit as st
import requests
import numpy as np
import pandas as pd
from simulation import (
    generuj_profil_spotreby_rocni,
    get_pvgis_hodinova_data,
    interpoluj_na_15min,
    simuluj_fve,
    simuluj_15let,
)

st.set_page_config(
    page_title="FVE Kalkulačka pro SVJ",
    page_icon="☀️",
    layout="wide"
)

# === CENÍKOVÉ TABULKY 2026 ===

CENY_VT = {
    "ČEZ Distribuce": {
        "D01d": 7493, "D02d": 7493,
        "D25d": 6945, "D26d": 6945, "D27d": 6945,
        "D35d": 5254, "D45d": 5254, "D56d": 5254, "D57d": 5254,
        "D61d": 8073,
    },
    "EG.D (E.ON)": {
        "D01d": 7053, "D02d": 7053,
        "D25d": 6550, "D26d": 6647, "D27d": 6647,
        "D35d": 6647, "D45d": 4865, "D56d": 4865, "D57d": 4865,
        "D61d": 8018,
    },
    "PREdistribuce": {
        "D01d": 6200, "D02d": 6200,
        "D25d": 5800, "D26d": 5800, "D27d": 5800,
        "D35d": 5200, "D45d": 4800, "D56d": 4800, "D57d": 4800,
        "D61d": 6800,
    },
}

CENY_NT = {
    "ČEZ Distribuce": {
        "D25d": 4190, "D26d": 4190, "D27d": 4140,
        "D35d": 4510, "D45d": 4510, "D56d": 4510, "D57d": 4510,
        "D61d": 4350,
    },
    "EG.D (E.ON)": {
        "D25d": 3833, "D26d": 3833, "D27d": 3833,
        "D35d": 3957, "D45d": 4027, "D56d": 4027, "D57d": 4027,
        "D61d": 3832,
    },
    "PREdistribuce": {
        "D25d": 3500, "D26d": 3500, "D27d": 3500,
        "D35d": 3700, "D45d": 3800, "D56d": 3800, "D57d": 3800,
        "D61d": 3500,
    },
}

STAY_PLAT = {"ČEZ Distribuce": 163, "EG.D (E.ON)": 144, "PREdistribuce": 150}

JISTIC_PLAT_3x25 = {
    "ČEZ Distribuce": {
        "D01d": 132, "D02d": 298, "D25d": 287, "D26d": 422,
        "D27d": 272, "D35d": 517, "D45d": 567, "D56d": 567,
        "D57d": 567, "D61d": 238,
    },
    "EG.D (E.ON)": {
        "D01d": 145, "D02d": 575, "D25d": 296, "D26d": 422,
        "D27d": 282, "D35d": 575, "D45d": 575, "D56d": 575,
        "D57d": 575, "D61d": 271,
    },
    "PREdistribuce": {
        "D01d": 100, "D02d": 280, "D25d": 250, "D26d": 350,
        "D27d": 230, "D35d": 420, "D45d": 480, "D56d": 480,
        "D57d": 480, "D61d": 200,
    },
}

SAZBY_S_NT = ["D25d", "D26d", "D27d", "D35d", "D45d", "D56d", "D57d", "D61d"]
PODIL_NT = {
    "D25d": 0.35, "D26d": 0.35, "D27d": 0.35,
    "D35d": 0.60, "D45d": 0.70, "D56d": 0.75, "D57d": 0.75,
    "D61d": 0.40,
}

POPIS_SAZEB = {
    "D01d": "Malý byt — jen svícení",
    "D02d": "Standardní domácnost",
    "D25d": "Ohřev vody bojlerem (8h NT)",
    "D26d": "Akumulační kamna (8h NT)",
    "D27d": "Elektromobil (8h NT)",
    "D35d": "Hybridní TČ (16h NT)",
    "D45d": "Přímotopy/elektrokotel (20h NT)",
    "D56d": "Vytápění TČ/přímotopy (22h NT)",
    "D57d": "TČ — hlavní zdroj tepla (20h NT)",
    "D61d": "Víkendový objekt",
}

PROFILY = {
    "mix":        {"nazev": "👨‍👩‍👧 Smíšený dům",        "popis": "Mix pracujících a seniorů"},
    "seniori":    {"nazev": "👴 Převaha seniorů",      "popis": "Většina doma přes den — vyšší denní spotřeba"},
    "pracujici":  {"nazev": "🏢 Převaha pracujících",  "popis": "Většina pryč přes den — nižší využití FVE"},
    "rodiny":     {"nazev": "👨‍👩‍👧‍👦 Rodiny s dětmi",     "popis": "Doma odpoledne a víkendy"},
    "provozovna": {"nazev": "🏪 S provozovnou",        "popis": "Kadeřnictví, ordinace — vysoká spotřeba přes den"},
}


@st.cache_data(ttl=3600)
def geocode(dotaz):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format": "json",
                    "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "FVE-SVJ-Kalkulacka/1.0"},
            timeout=5,
        )
        res = r.json()
        if res:
            addr = res[0].get("address", {})
            mesto = (addr.get("city") or addr.get("town") or
                     addr.get("village") or addr.get("municipality") or dotaz)
            return float(res[0]["lat"]), float(res[0]["lon"]), mesto, None
        return None, None, None, "Lokalita nenalezena"
    except Exception as e:
        return None, None, None, str(e)


# === UI ===

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Přesná 15minutová simulace návratnosti fotovoltaické elektrárny pro bytový dům")
st.divider()

# ── 1. ZÁKLADNÍ ÚDAJE ──────────────────────────────────────

st.subheader("🏠 Základní údaje o domě")
c1, c2, c3 = st.columns(3)

with c1:
    pocet_bytu = st.number_input("Počet bytů", 2, 200, 12, 1)
    spotreba_mwh = st.number_input(
        "Roční spotřeba (MWh/rok)", 1.0, 500.0, 25.0, 1.0, format="%.1f",
        help="Celková spotřeba SVJ za rok")
    spotreba = float(spotreba_mwh) * 1000.0

with c2:
    distributor = st.selectbox(
        "Distributor",
        list(CENY_VT.keys()),
        help="ČEZ = většina ČR | EG.D = Morava/jih Čech | PRE = Praha")
    sazba = st.selectbox(
        "Distribuční sazba",
        list(CENY_VT[distributor].keys()),
        format_func=lambda x: f"{x} — {POPIS_SAZEB[x]}",
        index=1)

with c3:
    st.selectbox("Hlavní jistič",
                 ["1×25A", "3×16A", "3×20A", "3×25A", "3×32A", "3×40A", "3×50A", "3×63A"],
                 index=3)
    profil_key = st.selectbox(
        "Profil obyvatel",
        list(PROFILY.keys()),
        format_func=lambda x: PROFILY[x]["nazev"])
    st.caption(PROFILY[profil_key]["popis"])

# Ceny z ceníku
cena_vt = float(CENY_VT[distributor][sazba]) / 1000.0
if sazba in SAZBY_S_NT:
    nt = float(CENY_NT[distributor].get(sazba, CENY_VT[distributor][sazba])) / 1000.0
    podil = PODIL_NT.get(sazba, 0.5)
    cena_prum = cena_vt * (1.0 - podil) + nt * podil
else:
    cena_prum = cena_vt

stay = float(STAY_PLAT[distributor])
jistic_m = float(JISTIC_PLAT_3x25[distributor][sazba])
naklad_rok = spotreba * cena_prum + (stay + jistic_m) * 12.0

st.info(
    f"💡 Ceník **{distributor}** · sazba **{sazba}** · s DPH · POZE = 0 Kč od 2026 | "
    f"Cena VT: **{cena_vt:.2f} Kč/kWh** · Průměr: **{cena_prum:.2f} Kč/kWh** · "
    f"Stálé platy: **{stay+jistic_m:.0f} Kč/měs** · "
    f"Roční náklad: **{naklad_rok:,.0f} Kč**"
)

with st.expander("✏️ Upravit ceny ručně"):
    u1, u2, u3 = st.columns(3)
    with u1:
        cena_vt = st.number_input("Cena VT (Kč/kWh)", 1.0, 15.0,
                                   round(cena_vt, 2), 0.01, format="%.2f",
                                   help="Použita pro výpočet úspory z FVE")
    with u2:
        cena_prum = st.number_input("Průměrná cena (Kč/kWh)", 1.0, 15.0,
                                     round(cena_prum, 2), 0.01, format="%.2f")
    with u3:
        stay_celkem = st.number_input("Stálé platy (Kč/měs)", 0, 5000,
                                       int(stay + jistic_m), 10)
    naklad_rok = spotreba * cena_prum + float(stay_celkem) * 12.0
    st.metric("Roční náklad (upravený)", f"{naklad_rok:,.0f} Kč")

st.divider()

# ── 2. FVE A BATERIE ────────────────────────────────────────

st.subheader("⚡ Parametry FVE a baterie")
c1, c2 = st.columns(2)

with c1:
    vykon_fve = st.number_input("Výkon FVE (kWp)", 1.0, 200.0, 20.0, 0.5, format="%.1f")
    cena_kwp = st.slider("Cena FVE (Kč/kWp)", 25000, 50000, 37000, 1000,
                          help="Včetně montáže, střídače, kabeláže. Typicky 30–45 tis. Kč/kWp")
    cena_fve = int(float(vykon_fve) * float(cena_kwp))
    st.caption(f"Odhadovaná cena FVE: **{cena_fve:,.0f} Kč** "
               f"({vykon_fve} kWp × {cena_kwp:,} Kč/kWp)")

with c2:
    bat_kap = st.number_input("Kapacita baterie (kWh)", 0, 200, 0, 5,
                               help="0 = bez baterie. Simulace přesně počítá nabíjení/vybíjení.")
    if bat_kap > 0:
        cena_kwh_bat = st.slider("Cena baterie (Kč/kWh)", 10000, 20000, 15000, 500,
                                  help="Včetně střídače a BMS. Typicky 12–18 tis. Kč/kWh")
        cena_bat = int(float(bat_kap) * float(cena_kwh_bat))
        st.caption(f"Odhadovaná cena baterie: **{cena_bat:,.0f} Kč** "
                   f"({bat_kap} kWh × {cena_kwh_bat:,} Kč/kWh)")
    else:
        cena_bat = 0

st.divider()

# ── 3. MODEL SDÍLENÍ ────────────────────────────────────────

st.subheader("🔗 Model sdílení energie")
model = st.radio(
    "Model",
    ["spolecne", "jom", "edc"],
    format_func=lambda x: {
        "spolecne": "🏢 Jen společné prostory",
        "jom": "⚡ Sjednocení odběrných míst",
        "edc": "🔗 EDC komunitní sdílení",
    }[x],
    horizontal=True,
)

cena_mericu = int(pocet_bytu) * 10000 if model == "jom" else 0
uspora_jistic = jistic_m * (int(pocet_bytu) - 1) * 12.0 if model == "jom" else 0.0

# Koeficient spotřeby pro model "jen společné prostory"
koef_model = 0.20 if model == "spolecne" else 1.0

if model == "spolecne":
    st.info("🏢 FVE pokrývá jen společnou spotřebu. Nejjednodušší, nejnižší úspora.")
elif model == "jom":
    st.info(f"⚡ Jeden hlavní elektroměr + podružné měřiče. "
            f"Náklady na měřiče: **{cena_mericu:,} Kč**. "
            f"Úspora distribuce: **{uspora_jistic:,.0f} Kč/rok**.")
else:
    st.info("🔗 Každý byt si zachovává dodavatele. Chytré měřiče zdarma od distributora. "
            "Registrace na edc.cz.")

st.divider()

# ── 4. LOKALITA A STŘECHA ───────────────────────────────────

st.subheader("🌍 Lokalita a střecha")
lc1, lc2 = st.columns([1, 2])

with lc1:
    lokace = st.text_input("Město nebo PSČ", "Praha")

with lc2:
    typ_str = st.radio("Typ střechy", ["sikma", "plocha"],
                        format_func=lambda x: "🏠 Šikmá" if x == "sikma" else "🏢 Plochá",
                        horizontal=True)

if typ_str == "sikma":
    sc1, sc2 = st.columns(2)
    with sc1:
        sklon = st.slider("Sklon (°)", 15, 60, 35)
    with sc2:
        azimut = st.select_slider(
            "Orientace", [-90, -45, 0, 45, 90], 0,
            format_func=lambda x: {
                -90: "⬅️ Východ", -45: "↙️ Jihovýchod",
                0: "⬆️ Jih", 45: "↗️ Jihozápad", 90: "➡️ Západ"}[x])
    koef_str = 1.0
else:
    pc1, pc2 = st.columns(2)
    with pc1:
        sklon = st.slider("Sklon panelů (°)", 5, 20, 10)
    with pc2:
        sys_pl = st.radio("Systém", ["jih", "jz_jv", "vz"],
                           format_func=lambda x: {"jih": "⬆️ Jih",
                                                   "jz_jv": "↗️ JZ+JV",
                                                   "vz": "↔️ V+Z"}[x])
    azimut = 90 if sys_pl == "vz" else 0
    koef_str = {"jih": 1.0, "jz_jv": 0.97, "vz": 0.88}[sys_pl]
    popis_str = {"jih": "Maximum výkonu, špička kolem poledne.",
                 "jz_jv": "Mírně nižší výkon, rovnoměrnější výroba.",
                 "vz": "Nejrovnoměrnější výroba, ideální pro vlastní spotřebu."}[sys_pl]
    st.info(f"☀️ {popis_str}")

st.divider()

# ── 5. FINANCOVÁNÍ ──────────────────────────────────────────

st.subheader("💰 Financování")
fc1, fc2 = st.columns(2)

with fc1:
    scenar = st.radio(
        "Scénář",
        ["uver", "vlastni", "kombinace"],
        format_func=lambda x: {
            "uver": "🏦 Bezúročný úvěr NZÚ (od září 2026)",
            "vlastni": "💵 Vlastní zdroje (fond oprav)",
            "kombinace": "🔀 Kombinace vlastní + úvěr",
        }[x])

with fc2:
    if scenar == "uver":
        splatnost = st.slider("Doba splácení (let)", 5, 25, 15)
        vlastni_pct = 0
        st.info("✅ Úroky hradí stát. SVJ splácí pouze jistinu.")
    elif scenar == "vlastni":
        splatnost = 0
        vlastni_pct = 100
        st.info("💡 SVJ hradí vše z fondu oprav.")
    else:
        vlastni_pct = st.slider("Vlastní zdroje (%)", 10, 90, 30, 10)
        splatnost = st.slider("Doba splácení úvěru (let)", 5, 25, 15)

st.markdown("**Nízkopříjmové domácnosti**")
nb1, nb2 = st.columns(2)
with nb1:
    pocet_nizko = st.number_input("Bytů s bonusem", 0, int(pocet_bytu), 0, 1)
with nb2:
    bonus_byt = st.number_input("Bonus na byt (Kč)", 0, 150000, 50000, 5000)
bonus = int(pocet_nizko) * int(bonus_byt)

st.divider()

# ── 6. PARAMETRY SIMULACE ───────────────────────────────────

st.subheader("⚙️ Parametry simulace")
sc1, sc2, sc3 = st.columns(3)
with sc1:
    cena_pretoky = st.number_input("Výkupní cena přetoků (Kč/kWh)",
                                    0.30, 2.50, 0.95, 0.05, format="%.2f",
                                    help="E.ON 0,70 · TEDOM 0,75 · spot ~1,50 Kč/kWh")
with sc2:
    rust_cen = st.slider("Růst cen elektřiny (%/rok)", 0.0, 8.0, 3.0, 0.5,
                          help="Historický průměr ČR ~3–4 %/rok")
with sc3:
    degradace = st.slider("Degradace panelů (%/rok)", 0.2, 1.0, 0.5, 0.1,
                           help="Standardní křemíkové panely ~0,5 %/rok")

st.divider()

# ── SPUŠTĚNÍ ────────────────────────────────────────────────

# Výpočet investice a splátek
cena_invest = cena_fve + cena_bat + cena_mericu
vlastni_castka = float(cena_invest) * float(vlastni_pct) / 100.0
uver_castka = max(0.0, float(cena_invest) - vlastni_castka - float(bonus))
rocni_splatka = uver_castka / float(splatnost) if (scenar != "vlastni" and splatnost > 0) else 0.0

bc1, bc2 = st.columns([1, 3])
with bc1:
    spustit = st.button("🔄 Spočítat simulaci", type="primary", use_container_width=True)
with bc2:
    st.caption("Stáhne hodinová solární data z PVGIS a provede přesný výpočet "
               "v 15minutových intervalech. Trvá 5–20 sekund.")

if spustit:
    # Geocoding
    with st.spinner(f"Hledám {lokace}..."):
        lat, lon, mesto, geo_err = geocode(lokace)
    if geo_err:
        st.error(f"Lokalita nenalezena: {geo_err}")
        st.stop()

    # PVGIS
    effective_kwp = float(vykon_fve) * float(koef_str)
    with st.spinner(f"Stahuji solární data pro {mesto} z PVGIS..."):
        vyroba_hod, pvgis_err = get_pvgis_hodinova_data(lat, lon, effective_kwp, sklon, azimut)
    if pvgis_err:
        st.error(f"PVGIS chyba: {pvgis_err}")
        st.stop()

    with st.spinner("Zpracovávám data..."):
        vyroba_15 = interpoluj_na_15min(vyroba_hod)
        spotreba_15 = generuj_profil_spotreby_rocni(
            spotreba * koef_model, profil_key, sazba)
        sim = simuluj_fve(vyroba_15, spotreba_15, float(bat_kap))
        cf = simuluj_15let(
            vlastni_spotreba_1rok=sim["vlastni_spotreba_kwh"],
            pretoky_1rok=sim["pretoky_kwh"],
            cena_vt_kwh=float(cena_vt),
            cena_pretoky_kwh=float(cena_pretoky),
            cena_instalace=float(cena_invest),
            vlastni_castka=vlastni_castka,
            uver_castka=uver_castka,
            rocni_splatka=rocni_splatka,
            splatnost=int(splatnost),
            rust_cen_pct=float(rust_cen),
            degradace_pct=float(degradace),
            leta=15,
            uspora_jistic_rocni=float(uspora_jistic),
            bonus_celkem=float(bonus),
        )

    st.session_state["data"] = {
        "sim": sim, "cf": cf,
        "vyroba_15": vyroba_15,
        "spotreba_15": spotreba_15,
        "mesto": mesto, "lat": lat, "lon": lon,
    }
    st.success(f"✅ Simulace dokončena — {mesto} ({lat:.2f}°N, {lon:.2f}°E)")

# ── VÝSLEDKY ────────────────────────────────────────────────

if "data" not in st.session_state:
    st.info("👆 Vyplňte parametry a klikněte na **Spočítat simulaci**.")
    st.stop()

d = st.session_state["data"]
sim = d["sim"]
cf = d["cf"]
rok1 = cf[0]
nav = next((r["rok"] for r in cf if r["kumulativni_cashflow"] >= 0), None)

st.divider()
st.subheader("📊 Výsledky simulace")

r1, r2, r3, r4, r5 = st.columns(5)
with r1:
    st.metric("Roční výroba FVE",
              f"{sim['vyroba_kwh']/1000:.1f} MWh",
              help="PVGIS hodinová data pro vaši lokalitu")
with r2:
    st.metric("Míra vlastní spotřeby",
              f"{sim['mira_vlastni_spotreby']*100:.1f} %",
              help="Kolik % výroby FVE se spotřebuje přímo v domě")
with r3:
    st.metric("Míra soběstačnosti",
              f"{sim['mira_sobestacnosti']*100:.1f} %",
              help="Kolik % celkové spotřeby pokryje FVE")
with r4:
    st.metric("Roční úspora (rok 1)", f"{rok1['uspora_celkem']:,.0f} Kč")
with r5:
    st.metric("Návratnost", f"{nav} let" if nav else ">15 let")

# Milníky
st.markdown("**📍 Klíčové milníky**")
m1, m2, m3 = st.columns(3)
uspora_byt = rok1["uspora_celkem"] / float(pocet_bytu)
splatka_byt = rocni_splatka / float(pocet_bytu) / 12.0

with m1:
    st.info(
        f"**Rok 1**\n\n"
        f"Vlastní spotřeba: **{sim['vlastni_spotreba_kwh']:,.0f} kWh**\n\n"
        f"Přetoky do sítě: **{sim['pretoky_kwh']:,.0f} kWh**\n\n"
        f"Roční úspora: **{rok1['uspora_celkem']:,.0f} Kč**\n\n"
        f"Na byt: **{uspora_byt:,.0f} Kč/rok** · **{uspora_byt/12:.0f} Kč/měs**\n\n"
        f"Splátka na byt: **{splatka_byt:,.0f} Kč/měs**"
    )

with m2:
    if splatnost > 0 and splatnost <= 15:
        rs = cf[splatnost - 1]
        st.info(
            f"**Rok {splatnost} — úvěr splacen ✅**\n\n"
            f"Úspora v tom roce: **{rs['uspora_celkem']:,.0f} Kč**\n\n"
            f"(Vč. růstu cen {rust_cen} %/rok)\n\n"
            f"Poté plný přínos bez splátky:\n\n"
            f"**{rs['uspora_celkem']:,.0f} Kč/rok**"
        )
    else:
        st.info(
            f"**Vlastní financování**\n\n"
            f"Žádné splátky\n\n"
            f"Plný přínos od roku 1:\n\n"
            f"**{rok1['uspora_celkem']:,.0f} Kč/rok**"
        )

with m3:
    cf_konec = cf[-1]["kumulativni_cashflow"]
    if nav:
        st.success(
            f"**Rok {nav} — investice se vrátí ✅**\n\n"
            f"Za 15 let celková úspora:\n\n"
            f"**{cf_konec:,.0f} Kč**\n\n"
            f"Na byt: **{cf_konec/float(pocet_bytu):,.0f} Kč**"
        )
    else:
        st.warning(
            f"**Za 15 let**\n\n"
            f"Investice se nevrátí\n\n"
            f"Cashflow: **{cf_konec:,.0f} Kč**\n\n"
            "Zkuste zvýšit výkon FVE nebo model sdílení."
        )

st.divider()

# Tabulka rok po roku
st.subheader("📋 Přehled rok po roku")

df = pd.DataFrame(cf)[[
    "rok", "vyroba_mwh", "vlastni_spotreba_mwh", "pretoky_mwh",
    "uspora_elektrina", "uspora_pretoky", "uspora_celkem",
    "splatka", "cisty_prinos", "kumulativni_cashflow", "cena_vt_rok",
]]
df.columns = [
    "Rok", "Výroba MWh", "Vlastní MWh", "Přetoky MWh",
    "Úspora el. Kč", "Příjem přetoky Kč", "Úspora celkem Kč",
    "Splátka Kč", "Čistý přínos Kč", "Kumulativní Kč", "Cena VT Kč/kWh",
]

def highlight(row):
    if nav and row["Rok"] == nav:
        return ["background-color: #d4edda"] * len(row)
    if row["Kumulativní Kč"] < 0:
        return ["background-color: #fff3cd"] * len(row)
    return [""] * len(row)

st.dataframe(
    df.style.apply(highlight, axis=1).format({
        "Výroba MWh": "{:.2f}", "Vlastní MWh": "{:.2f}", "Přetoky MWh": "{:.2f}",
        "Úspora el. Kč": "{:,.0f}", "Příjem přetoky Kč": "{:,.0f}",
        "Úspora celkem Kč": "{:,.0f}", "Splátka Kč": "{:,.0f}",
        "Čistý přínos Kč": "{:,.0f}", "Kumulativní Kč": "{:,.0f}",
        "Cena VT Kč/kWh": "{:.3f}",
    }),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# Detail investice
st.subheader("💰 Detail investice a výnosů")
di1, di2 = st.columns(2)

with di1:
    st.markdown("**Investice**")
    st.write(f"• FVE {vykon_fve} kWp × {cena_kwp:,} Kč/kWp: **{cena_fve:,.0f} Kč**")
    if cena_bat > 0:
        st.write(f"• Baterie {bat_kap} kWh: **{cena_bat:,.0f} Kč**")
    if cena_mericu > 0:
        st.write(f"• Podružné měřiče ({pocet_bytu} ks): **{cena_mericu:,.0f} Kč**")
    st.write(f"• **Celková investice: {cena_invest:,.0f} Kč**")
    if bonus > 0:
        st.write(f"• Bonus nízkopříjmové: **− {bonus:,.0f} Kč**")
    if scenar != "vlastni":
        st.write(f"• Vlastní zdroje: **{vlastni_castka:,.0f} Kč**")
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_castka:,.0f} Kč**")
        st.write(f"• Roční splátka: **{rocni_splatka:,.0f} Kč** ({splatnost} let)")
    st.write(f"• Náklady na byt: **{vlastni_castka/float(pocet_bytu):,.0f} Kč**")

with di2:
    st.markdown("**Výnosy rok 1**")
    nazev_mod = {"spolecne": "Jen společné prostory",
                 "jom": "Sjednocení odběrných míst",
                 "edc": "EDC komunitní sdílení"}[model]
    st.write(f"• Model: **{nazev_mod}**")
    st.write(f"• Profil: **{PROFILY[profil_key]['nazev']}**")
    st.write(f"• Vlastní spotřeba: **{sim['vlastni_spotreba_kwh']:,.0f} kWh/rok**")
    st.write(f"• Úspora elektřina (VT {cena_vt:.2f} Kč/kWh): **{rok1['uspora_elektrina']:,.0f} Kč/rok**")
    st.write(f"• Přetoky: **{sim['pretoky_kwh']:,.0f} kWh** → **{rok1['uspora_pretoky']:,.0f} Kč/rok**")
    if uspora_jistic > 0:
        st.write(f"• Úspora distribuce (JOM): **{uspora_jistic:,.0f} Kč/rok**")
    st.write(f"• **Celkem: {rok1['uspora_celkem']:,.0f} Kč/rok**")
    st.write(f"• Na byt/rok: **{uspora_byt:,.0f} Kč** · na byt/měsíc: **{uspora_byt/12:.0f} Kč**")

st.divider()
st.caption(
    "⚠️ Orientační výpočty — 15minutová simulace. "
    "Solární data: PVGIS TMY © Evropská komise, JRC. "
    "Profily spotřeby: OTE ČR normalizované TDD. "
    "Ceny dle ceníků ČEZ, E.ON, PRE od 1.1.2026 (s DPH 21 %, POZE = 0 Kč). "
    "Bezúročný úvěr NZÚ — žádosti od září 2026. "
    "EDC sdílení — registrace na edc.cz."
)
