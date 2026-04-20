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

# === DATOVÉ TABULKY CEN 2026 ===

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

STAY_PLAT = {
    "ČEZ Distribuce": 163, "EG.D (E.ON)": 144, "PREdistribuce": 150,
}

JISTIC_PLAT_3x25 = {
    "ČEZ Distribuce": {
        "D01d": 132, "D02d": 298, "D25d": 287, "D26d": 422,
        "D27d": 272, "D35d": 517, "D45d": 567, "D56d": 567,
        "D57d": 567, "D61d": 238
    },
    "EG.D (E.ON)": {
        "D01d": 145, "D02d": 575, "D25d": 296, "D26d": 422,
        "D27d": 282, "D35d": 575, "D45d": 575, "D56d": 575,
        "D57d": 575, "D61d": 271
    },
    "PREdistribuce": {
        "D01d": 100, "D02d": 280, "D25d": 250, "D26d": 350,
        "D27d": 230, "D35d": 420, "D45d": 480, "D56d": 480,
        "D57d": 480, "D61d": 200
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
    "mix": {"nazev": "👨‍👩‍👧 Smíšený dům", "popis": "Mix pracujících a seniorů"},
    "seniori": {"nazev": "👴 Převaha seniorů", "popis": "Většina doma přes den — vysoká denní spotřeba"},
    "pracujici": {"nazev": "🏢 Převaha pracujících", "popis": "Většina pryč přes den — nižší využití FVE"},
    "rodiny": {"nazev": "👨‍👩‍👧‍👦 Rodiny s dětmi", "popis": "Doma odpoledne a víkendy"},
    "provozovna": {"nazev": "🏪 S provozovnou", "popis": "Kadeřnictví, ordinace — vysoká spotřeba přes den"},
}

MODELY_SDILENI = {
    "spolecne": "🏢 Jen společné prostory",
    "jom": "⚡ Sjednocení odběrných míst",
    "edc": "🔗 EDC komunitní sdílení",
}

# === GEOCODING ===

@st.cache_data(ttl=3600)
def geocode_lokace(dotaz):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": f"{dotaz}, Česká republika", "format": "json",
              "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "FVE-SVJ-Kalkulacka/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        results = r.json()
        if results:
            res = results[0]
            addr = res.get("address", {})
            mesto = (addr.get("city") or addr.get("town") or
                     addr.get("village") or addr.get("municipality") or dotaz)
            return float(res["lat"]), float(res["lon"]), mesto, None
        return None, None, None, "Lokalita nenalezena"
    except Exception as e:
        return None, None, None, str(e)

# === HLAVNÍ UI ===

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Přesná 15minutová simulace návratnosti fotovoltaické elektrárny pro bytový dům")

st.divider()

# --- SEKCE 1: ZÁKLADNÍ ÚDAJE ---
st.subheader("🏠 Základní údaje o domě")

col1, col2, col3 = st.columns(3)

with col1:
    pocet_bytu = st.number_input(
        "Počet bytů v domě", min_value=2, max_value=200, value=12, step=1)
    spotreba_mwh = st.number_input(
        "Roční spotřeba elektřiny (MWh/rok)",
        min_value=1.0, max_value=500.0, value=25.0, step=1.0, format="%.1f",
        help="Celková spotřeba SVJ za rok včetně bytů a společných prostor")
    spotreba = spotreba_mwh * 1000

with col2:
    distributor = st.selectbox(
        "Distributor elektřiny",
        options=list(CENY_VT.keys()),
        help="ČEZ = většina ČR, EG.D = Morava/jih Čech, PRE = Praha")
    sazba = st.selectbox(
        "Distribuční sazba",
        options=list(CENY_VT[distributor].keys()),
        format_func=lambda x: f"{x} — {POPIS_SAZEB[x]}",
        index=1)

with col3:
    jistic = st.selectbox(
        "Hlavní jistič",
        options=["1×25A", "3×16A", "3×20A", "3×25A", "3×32A", "3×40A", "3×50A", "3×63A"],
        index=3)
    profil_key = st.selectbox(
        "Profil obyvatel domu",
        options=list(PROFILY.keys()),
        format_func=lambda x: PROFILY[x]["nazev"])
    st.caption(PROFILY[profil_key]["popis"])

# Ceny z ceníku
cena_vt_kwh = CENY_VT[distributor][sazba] / 1000
if sazba in SAZBY_S_NT:
    podil_nt = PODIL_NT.get(sazba, 0.5)
    cena_nt_kwh = CENY_NT[distributor].get(sazba, cena_vt_kwh * 0.7) / 1000
    cena_prumerna_kwh = cena_vt_kwh * (1 - podil_nt) + cena_nt_kwh * podil_nt
else:
    cena_prumerna_kwh = cena_vt_kwh

stay_plat = STAY_PLAT[distributor]
jistic_plat = JISTIC_PLAT_3x25[distributor][sazba]
rocni_naklad_elektrina = spotreba * cena_prumerna_kwh + (stay_plat + jistic_plat) * 12

st.info(
    f"💡 Ceník **{distributor}**, sazba **{sazba}** (s DPH 21 %, POZE = 0 Kč od 2026) | "
    f"Cena VT: **{cena_vt_kwh:.2f} Kč/kWh** | "
    f"Průměrná cena: **{cena_prumerna_kwh:.2f} Kč/kWh** | "
    f"Stálé platy: **{stay_plat + jistic_plat:.0f} Kč/měsíc** | "
    f"Roční náklad: **{rocni_naklad_elektrina:,.0f} Kč**"
)

with st.expander("✏️ Upravit ceny ručně"):
    up1, up2, up3 = st.columns(3)
    with up1:
        cena_vt_kwh = st.number_input(
            "Cena VT (Kč/kWh)",
            min_value=1.0, max_value=15.0,
            value=round(cena_vt_kwh, 2), step=0.01, format="%.2f",
            help="Použita pro výpočet úspory z FVE (FVE vyrábí přes den = VT)")
    with up2:
        cena_prumerna_kwh = st.number_input(
            "Průměrná cena (Kč/kWh)",
            min_value=1.0, max_value=15.0,
            value=round(cena_prumerna_kwh, 2), step=0.01, format="%.2f")
    with up3:
        stay_plat_celkem = st.number_input(
            "Stálé platy (Kč/měsíc)",
            min_value=0, max_value=5000,
            value=int(stay_plat + jistic_plat), step=10)
    rocni_naklad_elektrina = spotreba * cena_prumerna_kwh + stay_plat_celkem * 12
    st.metric("Roční náklad (upravený)", f"{rocni_naklad_elektrina:,.0f} Kč")

st.divider()

# --- SEKCE 2: FVE A BATERIE ---
st.subheader("⚡ Parametry FVE a baterie")

col1, col2 = st.columns(2)

with col1:
    vykon_fve = st.number_input(
        "Výkon FVE (kWp)", min_value=1.0, max_value=200.0,
        value=20.0, step=0.5, format="%.1f")
    cena_kwp = st.slider(
        "Cena FVE (Kč/kWp)", min_value=25000, max_value=50000,
        value=37000, step=1000,
        help="Včetně montáže, střídače a kabeláže. Typicky 30 000–45 000 Kč/kWp")
    cena_instalace_fve = int(vykon_fve * cena_kwp)
    st.caption(f"Odhadovaná cena FVE: **{cena_instalace_fve:,.0f} Kč**")

with col2:
    baterie_kapacita = st.number_input(
        "Kapacita baterie (kWh)", min_value=0, max_value=200, value=0, step=5,
        help="0 = bez baterie. Baterie zvyšuje vlastní spotřebu — simulace to přesně počítá.")
    if baterie_kapacita > 0:
        cena_kwh_bat = st.slider(
            "Cena baterie (Kč/kWh)", min_value=10000, max_value=20000,
            value=15000, step=500,
            help="Včetně střídače a BMS. Typicky 12 000–18 000 Kč/kWh")
        cena_baterie = int(baterie_kapacita * cena_kwh_bat)
        st.caption(f"Odhadovaná cena baterie: **{cena_baterie:,.0f} Kč**")
    else:
        cena_baterie = 0

st.divider()

# --- SEKCE 3: MODEL SDÍLENÍ ---
st.subheader("🔗 Model sdílení energie")

model_sdileni = st.radio(
    "Zvolte model sdílení",
    options=list(MODELY_SDILENI.keys()),
    format_func=lambda x: MODELY_SDILENI[x],
    horizontal=True)

cena_mericu = pocet_bytu * 10000 if model_sdileni == "jom" else 0
uspora_jistic_rocni = jistic_plat * (pocet_bytu - 1) * 12 if model_sdileni == "jom" else 0

if model_sdileni == "spolecne":
    st.info("🏢 FVE pokrývá jen společnou spotřebu (výtah, světla, čerpadla). "
            "Nevyžaduje souhlas nájemníků. Nejnižší úspora.")
elif model_sdileni == "jom":
    st.info(f"⚡ Jeden hlavní elektroměr + podružné měřiče na byty. "
            f"Náklady na měřiče: **{cena_mericu:,} Kč**. "
            f"Úspora na distribuci: **{uspora_jistic_rocni:,.0f} Kč/rok** "
            f"(jeden jistič místo {pocet_bytu}).")
else:
    st.info("🔗 Každý byt si zachovává dodavatele. Chytré měřiče instaluje distributor zdarma. "
            "Sdílení přes alokační klíč v EDC (edc.cz).")

st.divider()

# --- SEKCE 4: LOKALITA A STŘECHA ---
st.subheader("🌍 Lokalita a střecha")

col1, col2 = st.columns([1, 2])
with col1:
    lokace_input = st.text_input("Město nebo PSČ", value="Praha")
with col2:
    typ_strechy = st.radio("Typ střechy",
                           options=["sikma", "plocha"],
                           format_func=lambda x: "🏠 Šikmá" if x == "sikma" else "🏢 Plochá",
                           horizontal=True)

if typ_strechy == "sikma":
    s1, s2 = st.columns(2)
    with s1:
        sklon = st.slider("Sklon střechy (°)", 15, 60, 35)
    with s2:
        azimut = st.select_slider(
            "Orientace", options=[-90, -45, 0, 45, 90], value=0,
            format_func=lambda x: {
                -90: "⬅️ Východ", -45: "↙️ Jihovýchod",
                0: "⬆️ Jih", 45: "↗️ Jihozápad", 90: "➡️ Západ"}[x])
    koef_vyroba = 1.0
else:
    p1, p2 = st.columns(2)
    with p1:
        sklon = st.slider("Sklon panelů (°)", 5, 20, 10)
    with p2:
        system_plocha = st.radio(
            "Systém", options=["jih", "jz_jv", "vz"],
            format_func=lambda x: {"jih": "⬆️ Jih",
                                   "jz_jv": "↗️ JZ+JV", "vz": "↔️ V+Z"}[x])
    if system_plocha == "jih":
        azimut, koef_vyroba = 0, 1.0
        st.info("☀️ Maximum výkonu, výroba kolem poledne.")
    elif system_plocha == "jz_jv":
        azimut, koef_vyroba = 0, 0.97
        st.info("☀️ Mírně nižší výkon, rovnoměrnější výroba.")
    else:
        azimut, koef_vyroba = 90, 0.88
        st.info("☀️ Nejrovnoměrnější výroba, ideální pro vlastní spotřebu.")

st.divider()

# --- SEKCE 5: FINANCOVÁNÍ ---
st.subheader("💰 Financování")

fin1, fin2 = st.columns(2)
with fin1:
    scenar = st.radio(
        "Scénář financování",
        options=["uver", "vlastni", "kombinace"],
        format_func=lambda x: {
            "uver": "🏦 Bezúročný úvěr NZÚ (od září 2026)",
            "vlastni": "💵 Vlastní zdroje (fond oprav)",
            "kombinace": "🔀 Kombinace vlastní + úvěr"
        }[x])

with fin2:
    if scenar == "uver":
        splatnost = st.slider("Doba splácení (let)", 5, 25, 15)
        vlastni_podil_pct = 0
        st.info("✅ Úroky hradí stát (SFŽP). SVJ splácí pouze jistinu.")
    elif scenar == "vlastni":
        splatnost = 0
        vlastni_podil_pct = 100
        st.info("💡 SVJ hradí vše z fondu oprav.")
    else:
        vlastni_podil_pct = st.slider("Vlastní zdroje (%)", 10, 90, 30, step=10)
        splatnost = st.slider("Doba splácení úvěru (let)", 5, 25, 15)

st.markdown("**Nízkopříjmové domácnosti (superdávka)**")
n1, n2 = st.columns(2)
with n1:
    pocet_nizko = st.number_input("Bytů s nárokem na bonus", 0, int(pocet_bytu), 0, step=1)
with n2:
    bonus_na_byt = st.number_input("Bonus na byt (Kč)", 0, 150000, 50000, step=5000)
bonus_celkem = pocet_nizko * bonus_na_byt

st.divider()

# --- SEKCE 6: PARAMETRY SIMULACE ---
st.subheader("⚙️ Parametry simulace")

sim1, sim2, sim3 = st.columns(3)
with sim1:
    cena_pretoky = st.number_input(
        "Výkupní cena přetoků (Kč/kWh)",
        min_value=0.30, max_value=2.50, value=0.95, step=0.05, format="%.2f",
        help="E.ON 0,70 Kč, TEDOM 0,75 Kč, spot průměr ~1,50 Kč")
with sim2:
    rust_cen = st.slider(
        "Předpokládaný růst cen elektřiny (%/rok)",
        min_value=0.0, max_value=8.0, value=3.0, step=0.5,
        help="Historický průměr ČR ~3-4 % ročně")
with sim3:
    degradace = st.slider(
        "Degradace panelů (%/rok)",
        min_value=0.2, max_value=1.0, value=0.5, step=0.1,
        help="Standardní degradace krystalického křemíku ~0,5 %/rok")

st.divider()

# === SPUŠTĚNÍ SIMULACE ===

cena_instalace = cena_instalace_fve + cena_baterie + cena_mericu
vlastni_castka = cena_instalace * (vlastni_podil_pct / 100)
uver_castka = max(0, cena_instalace - vlastni_castka - bonus_celkem)
rocni_splatka = uver_castka / splatnost if (scenar != "vlastni" and splatnost > 0) else 0

col_btn, col_info = st.columns([1, 3])
with col_btn:
    spustit = st.button("🔄 Spočítat simulaci", type="primary", use_container_width=True)
with col_info:
    st.caption("Simulace stáhne hodinová solární data z PVGIS a provede přesný výpočet "
               "v 15minutových intervalech pro celý rok. Může trvat 5–15 sekund.")

if spustit or "sim_vysledky" in st.session_state:

    if spustit:
        # Geocoding
        with st.spinner(f"Hledám lokalitu {lokace_input}..."):
            lat, lon, nazev_mesta, geo_err = geocode_lokace(lokace_input)

        if geo_err:
            st.error(f"⚠️ Lokalita nenalezena: {geo_err}")
            st.stop()

        # PVGIS hodinová data
        with st.spinner(f"Stahuji hodinová solární data pro {nazev_mesta} z PVGIS..."):
            vyroba_hod, pvgis_err = get_pvgis_hodinova_data(
                lat, lon, vykon_fve * koef_vyroba, sklon, azimut)

        if pvgis_err:
            st.error(f"⚠️ PVGIS nedostupné: {pvgis_err}")
            st.stop()

        # Interpolace na 15min
        with st.spinner("Interpoluji výrobu na 15minutové intervaly..."):
            vyroba_15min = interpoluj_na_15min(vyroba_hod)

        # Profil spotřeby
        with st.spinner("Generuji profil spotřeby dle typu obyvatel..."):
            spotreba_15min = generuj_profil_spotreby_rocni(
                spotreba, profil_key, sazba)

            # Úprava pro model sdílení
            if model_sdileni == "spolecne":
                # Pouze ~20% spotřeby je přes den ve společných prostorách
                spotreba_15min_sim = spotreba_15min * 0.20
            else:
                spotreba_15min_sim = spotreba_15min

        # Simulace FVE
        with st.spinner("Simuluji provoz FVE v 15minutových intervalech..."):
            sim = simuluj_fve(
                vyroba_15min,
                spotreba_15min_sim,
                baterie_kapacita_kwh=baterie_kapacita,
            )

        # 15letý cashflow
        with st.spinner("Počítám 15letý cashflow..."):
            cashflow = simuluj_15let(
                vyroba_rocni_kwh=vyroba_15min.sum(),
                vlastni_spotreba_1rok=sim["vlastni_spotreba_kwh"],
                pretoky_1rok=sim["pretoky_kwh"],
                odber_1rok=sim["odber_kwh"],
                spotreba_rocni_kwh=spotreba,
                cena_vt_kwh=cena_vt_kwh,
                cena_prumerna_kwh=cena_prumerna_kwh,
                cena_pretoky_kwh=cena_pretoky,
                stay_plat_mesic=stay_plat + jistic_plat,
                cena_instalace=cena_instalace,
                vlastni_castka=vlastni_castka,
                uver_castka=uver_castka,
                rocni_splatka=rocni_splatka,
                splatnost=splatnost,
                rust_cen_pct=rust_cen,
                degradace_pct=degradace,
                leta=15,
                uspora_jistic_rocni=uspora_jistic_rocni,
                bonus_celkem=bonus_celkem,
            )

        st.session_state["sim_vysledky"] = {
            "sim": sim,
            "cashflow": cashflow,
            "vyroba_15min": vyroba_15min,
            "nazev_mesta": nazev_mesta,
            "lat": lat, "lon": lon,
        }
        st.success(f"✅ Simulace dokončena pro {nazev_mesta} "
                   f"({lat:.2f}°N, {lon:.2f}°E)")

    # === ZOBRAZENÍ VÝSLEDKŮ ===

    data = st.session_state["sim_vysledky"]
    sim = data["sim"]
    cashflow = data["cashflow"]
    nazev_mesta = data["nazev_mesta"]

    rok1 = cashflow[0]
    navratnost_rok = next(
        (r["rok"] for r in cashflow if r["kumulativni_cashflow"] >= 0), None)

    st.divider()
    st.subheader("📊 Výsledky simulace")

    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        st.metric("Roční výroba FVE",
                  f"{data['vyroba_15min'].sum() / 1000:,.1f} MWh",
                  help="PVGIS TMY hodinová data pro danou lokalitu")
    with r2:
        st.metric("Míra vlastní spotřeby",
                  f"{sim['mira_vlastni_spotreby']*100:.1f} %",
                  help="Kolik % výroby FVE se spotřebuje přímo v domě")
    with r3:
        st.metric("Míra soběstačnosti",
                  f"{sim['mira_sobestacnosti']*100:.1f} %",
                  help="Kolik % celkové spotřeby domu pokryje FVE")
    with r4:
        st.metric("Roční úspora (rok 1)",
                  f"{rok1['uspora_celkem']:,.0f} Kč")
    with r5:
        if navratnost_rok:
            st.metric("Návratnost", f"{navratnost_rok} let")
        else:
            st.metric("Návratnost", ">15 let")

    # Milníky
    st.markdown("**📍 Klíčové milníky**")
    m1, m2, m3 = st.columns(3)

    uspora_na_byt = rok1["uspora_celkem"] / pocet_bytu
    splatka_na_byt = rocni_splatka / pocet_bytu / 12

    with m1:
        st.info(
            f"**Rok 1**\n\n"
            f"Vlastní spotřeba: **{sim['vlastni_spotreba_kwh']:,.0f} kWh**\n\n"
            f"Přetoky: **{sim['pretoky_kwh']:,.0f} kWh**\n\n"
            f"Roční úspora: **{rok1['uspora_celkem']:,.0f} Kč**\n\n"
            f"Na byt: **{uspora_na_byt:,.0f} Kč/rok** "
            f"({uspora_na_byt/12:,.0f} Kč/měsíc)\n\n"
            f"Splátka na byt: **{splatka_na_byt:,.0f} Kč/měsíc**"
        )

    with m2:
        if splatnost > 0 and splatnost <= 15:
            rok_splaceni = cashflow[splatnost - 1]
            st.info(
                f"**Rok {splatnost} — úvěr splacen ✅**\n\n"
                f"Úspora v tom roce: **{rok_splaceni['uspora_celkem']:,.0f} Kč**\n\n"
                f"(Vč. růstu cen {rust_cen}%/rok)\n\n"
                f"Poté čistý přínos bez splátky:\n\n"
                f"**{rok_splaceni['uspora_celkem']:,.0f} Kč/rok**"
            )
        else:
            st.info(
                f"**Vlastní financování**\n\n"
                f"Žádné splátky\n\n"
                f"Plný přínos hned: **{rok1['uspora_celkem']:,.0f} Kč/rok**"
            )

    with m3:
        cf_konec = cashflow[-1]["kumulativni_cashflow"]
        if navratnost_rok:
            st.success(
                f"**Rok {navratnost_rok} — investice se vrátí ✅**\n\n"
                f"Za 15 let celková úspora:\n\n"
                f"**{cf_konec:,.0f} Kč**\n\n"
                f"Na byt: **{cf_konec/pocet_bytu:,.0f} Kč**"
            )
        else:
            st.warning(
                f"**Za 15 let**\n\n"
                f"Investice se nevrátí\n\n"
                f"Kumulativní cashflow: **{cf_konec:,.0f} Kč**\n\n"
                "Zkuste zvýšit výkon FVE nebo zvolit jiný model sdílení."
            )

    st.divider()

    # Tabulka rok po roku
    st.subheader("📋 Přehled rok po roku")

    df = pd.DataFrame(cashflow)
    df_zobrazeni = df[[
        "rok", "vyroba_mwh", "vlastni_spotreba_mwh", "pretoky_mwh",
        "uspora_elektrina", "uspora_pretoky", "uspora_celkem",
        "splatka", "cisty_prinos", "kumulativni_cashflow", "cena_vt_rok"
    ]].copy()

    df_zobrazeni.columns = [
        "Rok", "Výroba (MWh)", "Vlastní spořeba (MWh)", "Přetoky (MWh)",
        "Úspora elektřina (Kč)", "Příjem přetoky (Kč)", "Úspora celkem (Kč)",
        "Splátka (Kč)", "Čistý přínos (Kč)", "Kumulativní (Kč)", "Cena VT (Kč/kWh)"
    ]

    # Zvýrazni rok návratnosti
    def highlight_navratnost(row):
        if navratnost_rok and row["Rok"] == navratnost_rok:
            return ["background-color: #d4edda"] * len(row)
        elif row["Kumulativní (Kč)"] < 0:
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_zobrazeni.style
        .apply(highlight_navratnost, axis=1)
        .format({
            "Výroba (MWh)": "{:.2f}",
            "Vlastní spořeba (MWh)": "{:.2f}",
            "Přetoky (MWh)": "{:.2f}",
            "Úspora elektřina (Kč)": "{:,.0f}",
            "Příjem přetoky (Kč)": "{:,.0f}",
            "Úspora celkem (Kč)": "{:,.0f}",
            "Splátka (Kč)": "{:,.0f}",
            "Čistý přínos (Kč)": "{:,.0f}",
            "Kumulativní (Kč)": "{:,.0f}",
            "Cena VT (Kč/kWh)": "{:.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # Detail nákladů
    st.subheader("💰 Detail investice a nákladů")
    d1, d2 = st.columns(2)

    with d1:
        st.markdown("**Investice**")
        st.write(f"• FVE {vykon_fve} kWp × {cena_kwp:,} Kč/kWp: **{cena_instalace_fve:,.0f} Kč**")
        if cena_baterie > 0:
            st.write(f"• Baterie {baterie_kapacita} kWh: **{cena_baterie:,.0f} Kč**")
        if cena_mericu > 0:
            st.write(f"• Podružné měřiče ({pocet_bytu} ks × 10 000 Kč): **{cena_mericu:,.0f} Kč**")
        st.write(f"• **Celková investice: {cena_instalace:,.0f} Kč**")
        if bonus_celkem > 0:
            st.write(f"• Bonus nízkopříjmové domácnosti: **− {bonus_celkem:,.0f} Kč**")
        if scenar != "vlastni":
            st.write(f"• Vlastní zdroje SVJ: **{vlastni_castka:,.0f} Kč**")
            st.write(f"• Bezúročný úvěr NZÚ: **{uver_castka:,.0f} Kč**")
            st.write(f"• Roční splátka: **{rocni_splatka:,.0f} Kč** ({splatnost} let)")
        st.write(f"• Náklady na byt (vlastní část): **{vlastni_castka/pocet_bytu:,.0f} Kč**")

    with d2:
        st.markdown("**Výnosy rok 1**")
        nazev_mod = {
            "spolecne": "Jen společné prostory",
            "jom": "Sjednocení odběrných míst",
            "edc": "EDC komunitní sdílení"
        }[model_sdileni]
        st.write(f"• Model sdílení: **{nazev_mod}**")
        st.write(f"• Profil obyvatel: **{PROFILY[profil_key]['nazev']}**")
        st.write(f"• Vlastní spotřeba z FVE: **{sim['vlastni_spotreba_kwh']:,.0f} kWh/rok**")
        st.write(f"• Úspora na elektřině (VT {cena_vt_kwh:.2f} Kč/kWh): **{rok1['uspora_elektrina']:,.0f} Kč/rok**")
        st.write(f"• Přetoky do sítě: **{sim['pretoky_kwh']:,.0f} kWh/rok** → **{rok1['uspora_pretoky']:,.0f} Kč/rok**")
        if uspora_jistic_rocni > 0:
            st.write(f"• Úspora distribuce (JOM): **{uspora_jistic_rocni:,.0f} Kč/rok**")
        st.write(f"• **Celková roční úspora: {rok1['uspora_celkem']:,.0f} Kč**")
        st.write(f"• Úspora na byt/rok: **{rok1['uspora_celkem']/pocet_bytu:,.0f} Kč**")
        st.write(f"• Úspora na byt/měsíc: **{rok1['uspora_celkem']/pocet_bytu/12:,.0f} Kč**")

st.divider()
st.caption(
    "⚠️ Orientační výpočty na základě 15minutové simulace. "
    "Solární data: PVGIS TMY © Evropská komise, JRC. "
    "Profily spotřeby: OTE ČR normalizované TDD. "
    "Ceny elektřiny dle ceníků ČEZ, E.ON, PRE platných od 1.1.2026 (s DPH 21 %). "
    "POZE = 0 Kč od roku 2026. "
    "Bezúročný úvěr NZÚ — žádosti od září 2026. "
    "EDC komunitní sdílení — registrace na edc.cz."
)
