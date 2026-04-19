import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="FVE Kalkulačka pro SVJ",
    page_icon="☀️",
    layout="wide"
)

# === DATOVÉ TABULKY CEN 2026 ===

# Celková cena VT s DPH v Kč/MWh (komodita + distribuce + systémové služby + daň)
# Zdroj: ceníky ČEZ, E.ON, PRE platné od 1.1.2026, POZE = 0 od 2026
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

# Celková cena NT s DPH v Kč/MWh
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

# Měsíční stálý plat dodavatele s DPH
STAY_PLAT = {
    "ČEZ Distribuce": 163, "EG.D (E.ON)": 144, "PREdistribuce": 150,
}

# Měsíční plat za jistič 3×25A s DPH (distribuce)
JISTIC_PLAT_3x25 = {
    "ČEZ Distribuce": {"D01d": 132, "D02d": 298, "D25d": 287, "D26d": 422,
                       "D27d": 272, "D35d": 517, "D45d": 567, "D56d": 567,
                       "D57d": 567, "D61d": 238},
    "EG.D (E.ON)":    {"D01d": 145, "D02d": 575, "D25d": 296, "D26d": 422,
                       "D27d": 282, "D35d": 575, "D45d": 575, "D56d": 575,
                       "D57d": 575, "D61d": 271},
    "PREdistribuce":  {"D01d": 100, "D02d": 280, "D25d": 250, "D26d": 350,
                       "D27d": 230, "D35d": 420, "D45d": 480, "D56d": 480,
                       "D57d": 480, "D61d": 200},
}

# Sazby s NT tarifem
SAZBY_S_NT = ["D25d", "D26d", "D27d", "D35d", "D45d", "D56d", "D57d", "D61d"]

# Podíl NT spotřeby dle sazby (kolik % spotřeby je v NT)
PODIL_NT = {
    "D25d": 0.35, "D26d": 0.35, "D27d": 0.35,
    "D35d": 0.60, "D45d": 0.70, "D56d": 0.75, "D57d": 0.75,
    "D61d": 0.40,
}

# Popis sazeb
POPIS_SAZEB = {
    "D01d": "Malý byt — jen svícení, minimum spotřebičů",
    "D02d": "Standardní domácnost — běžné spotřebiče",
    "D25d": "Ohřev vody bojlerem (8h NT)",
    "D26d": "Akumulační kamna (8h NT)",
    "D27d": "Elektromobil (8h NT)",
    "D35d": "Hybridní vytápění — tepelné čerpadlo (16h NT)",
    "D45d": "Přímotopy nebo elektrokotel (20h NT)",
    "D56d": "Vytápění TČ nebo přímotopy (22h NT)",
    "D57d": "Tepelné čerpadlo — hlavní zdroj tepla (20h NT)",
    "D61d": "Víkendový objekt — rekreace",
}

# Profily spotřeby — vliv na koeficient vlastní spotřeby
PROFILY = {
    "mix": {"nazev": "👨‍👩‍👧 Smíšený dům", "koef": 0.0,
            "popis": "Mix pracujících a seniorů — průměrná denní spotřeba"},
    "seniori": {"nazev": "👴 Převaha seniorů", "koef": +0.10,
                "popis": "Většina obyvatel doma přes den — vysoká denní spotřeba"},
    "pracujici": {"nazev": "🏢 Převaha pracujících", "koef": -0.10,
                  "popis": "Většina pryč přes den — nižší využití výroby FVE"},
    "rodiny": {"nazev": "👨‍👩‍👧‍👦 Rodiny s dětmi", "koef": +0.05,
               "popis": "Doma odpoledne a víkendy — nadprůměrná denní spotřeba"},
    "provozovna": {"nazev": "🏪 S provozovnou", "koef": +0.15,
                   "popis": "Kadeřnictví, ordinace v přízemí — vysoká spotřeba přes den"},
}

# === POMOCNÉ FUNKCE ===

@st.cache_data(ttl=3600)
def get_pvgis_data(lat, lon, vykon_kwp, sklon, azimut):
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
    params = {"lat": lat, "lon": lon, "peakpower": vykon_kwp,
              "loss": 14, "angle": sklon, "aspect": azimut,
              "outputformat": "json", "browser": 0}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()["outputs"]["totals"]["fixed"]["E_y"], None
    except Exception as e:
        return None, str(e)

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

def vypocet_ceny_kwh(distributor, sazba, spotreba_mwh):
    """Vypočte průměrnou cenu elektřiny v Kč/kWh včetně stálých platů."""
    cena_vt = CENY_VT[distributor][sazba] / 1000
    if sazba in SAZBY_S_NT:
        podil_nt = PODIL_NT.get(sazba, 0.5)
        cena_nt = CENY_NT[distributor].get(sazba, cena_vt * 0.7) / 1000
        cena_kwh = cena_vt * (1 - podil_nt) + cena_nt * podil_nt
    else:
        cena_kwh = cena_vt
    return cena_vt, cena_kwh

# === HLAVNÍ UI ===

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Orientační výpočet návratnosti fotovoltaické elektrárny pro bytový dům")

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
        help="Celková spotřeba SVJ za rok včetně bytů")
    spotreba = spotreba_mwh * 1000

with col2:
    distributor = st.selectbox(
        "Distributor elektřiny",
        options=list(CENY_VT.keys()),
        help="Závisí na lokalitě: ČEZ = většina ČR, EG.D = Morava/jih Čech, PRE = Praha")

    sazba = st.selectbox(
        "Distribuční sazba",
        options=list(CENY_VT[distributor].keys()),
        format_func=lambda x: f"{x} — {POPIS_SAZEB[x]}",
        index=1)

with col3:
    jistic = st.selectbox(
        "Hlavní jistič",
        options=["1×25A", "3×16A", "3×20A", "3×25A", "3×32A", "3×40A", "3×50A", "3×63A"],
        index=3,
        help="Velikost hlavního jističe před elektroměrem")

    profil_key = st.selectbox(
        "Profil obyvatel domu",
        options=list(PROFILY.keys()),
        format_func=lambda x: PROFILY[x]["nazev"])
    st.caption(PROFILY[profil_key]["popis"])

# Výpočet ceny elektřiny
cena_vt_kwh, cena_prumerna_kwh = vypocet_ceny_kwh(distributor, sazba, spotreba_mwh)
stay_plat = STAY_PLAT[distributor]
jistic_plat = JISTIC_PLAT_3x25[distributor][sazba]

# Roční náklad na elektřinu
rocni_naklad_elektrina = (spotreba * cena_prumerna_kwh) + (stay_plat + jistic_plat) * 12

st.info(
    f"💡 Ceny dle ceníku **{distributor}**, sazba **{sazba}**, platné od 1.1.2026 (s DPH 21 %, POZE = 0 Kč)\n\n"
    f"• Cena VT: **{cena_vt_kwh:.2f} Kč/kWh** | "
    f"Průměrná cena (vč. NT): **{cena_prumerna_kwh:.2f} Kč/kWh** | "
    f"Stálé platy: **{stay_plat + jistic_plat:.0f} Kč/měsíc**\n\n"
    f"• Odhadovaný roční náklad na elektřinu: **{rocni_naklad_elektrina:,.0f} Kč/rok**"
)

with st.expander("✏️ Upravit ceny ručně (pokud máte vlastní smlouvu nebo fixaci)"):
    up1, up2, up3 = st.columns(3)
    with up1:
        cena_prumerna_kwh = st.number_input(
            "Průměrná cena elektřiny (Kč/kWh)",
            min_value=1.0, max_value=15.0,
            value=round(cena_prumerna_kwh, 2),
            step=0.01, format="%.2f",
            help="Celková průměrná cena včetně distribuce a daní s DPH")
    with up2:
        stay_plat_upraveny = st.number_input(
            "Stálý plat celkem (Kč/měsíc)",
            min_value=0, max_value=5000,
            value=int(stay_plat + jistic_plat),
            step=10,
            help="Součet stálého platu dodavatele + měsíční plat za jistič")
    with up3:
        st.metric("Roční náklad (upravený)",
                  f"{(spotreba * cena_prumerna_kwh + stay_plat_upraveny * 12):,.0f} Kč")
    # Přepočet ročního nákladu s upravenými hodnotami
    rocni_naklad_elektrina = spotreba * cena_prumerna_kwh + stay_plat_upraveny * 12

st.divider()

# --- SEKCE 2: PARAMETRY FVE ---
st.subheader("⚡ Parametry FVE a baterie")

col1, col2 = st.columns(2)

with col1:
    vykon_fve = st.number_input(
        "Výkon FVE (kWp)", min_value=1.0, max_value=200.0,
        value=20.0, step=0.5, format="%.1f",
        help="Orientační pravidlo: 1 kWp na 1 MWh roční spotřeby")

    cena_kwp = st.slider(
        "Cena FVE (Kč/kWp)", min_value=25000, max_value=50000,
        value=37000, step=1000,
        help="Včetně montáže, střídače a kabeláže. Typicky 30 000–45 000 Kč/kWp")
    cena_instalace_fve = int(vykon_fve * cena_kwp)
    st.caption(f"Odhadovaná cena FVE: **{cena_instalace_fve:,.0f} Kč** "
               f"({vykon_fve} kWp × {cena_kwp:,} Kč/kWp)")

with col2:
    baterie_kapacita = st.number_input(
        "Kapacita baterie (kWh)", min_value=0, max_value=200, value=0, step=5,
        help="0 = bez baterie. Baterie výrazně zvyšuje vlastní spotřebu.")

    if baterie_kapacita > 0:
        cena_kwh_bat = st.slider(
            "Cena baterie (Kč/kWh)", min_value=10000, max_value=20000,
            value=15000, step=500,
            help="Včetně střídače a BMS. Typicky 12 000–18 000 Kč/kWh")
        cena_baterie = int(baterie_kapacita * cena_kwh_bat)
        st.caption(f"Odhadovaná cena baterie: **{cena_baterie:,.0f} Kč** "
                   f"({baterie_kapacita} kWh × {cena_kwh_bat:,} Kč/kWh)")
    else:
        cena_baterie = 0

st.divider()

# --- SEKCE 3: MODEL SDÍLENÍ ---
st.subheader("🔗 Model sdílení energie")

model_sdileni = st.radio(
    "Zvolte model sdílení",
    options=["spolecne", "jom", "edc"],
    format_func=lambda x: {
        "spolecne": "🏢 Jen společné prostory — FVE napájí výtah, světla, čerpadla",
        "jom": "⚡ Sjednocení odběrných míst — jeden hlavní měřič + podružné měřiče na byty",
        "edc": "🔗 EDC komunitní sdílení — každý byt si zachovává svého dodavatele"
    }[x],
    horizontal=True)

# Koeficient vlastní spotřeby
koef_base = {"spolecne": 0.20, "jom": 0.60, "edc": 0.65}[model_sdileni]

# Bonus za baterii
if baterie_kapacita <= 0:
    koef_bat = 0.0
elif baterie_kapacita <= 10:
    koef_bat = 0.08
elif baterie_kapacita <= 20:
    koef_bat = 0.13
elif baterie_kapacita <= 30:
    koef_bat = 0.17
else:
    koef_bat = 0.20

# Bonus za profil
koef_profil = PROFILY[profil_key]["koef"]

vlastni_spotreba_podil = min(koef_base + koef_bat + koef_profil, 0.85)

if model_sdileni == "spolecne":
    st.info("🏢 Nejjednodušší. FVE pokrývá jen společnou spotřebu. Nevyžaduje souhlas nájemníků.")
elif model_sdileni == "jom":
    cena_mericu = pocet_bytu * 10000
    st.info(f"⚡ Jeden hlavní elektroměr, interní rozpočítávání přes podružné měřiče. "
            f"Náklady na měřiče: {pocet_bytu} × 10 000 Kč = **{cena_mericu:,} Kč**. "
            f"Úspora na distribuci: platíte jen jeden jistič místo {pocet_bytu}.")
else:
    st.info("🔗 Každý byt si zachovává dodavatele. Chytré měřiče instaluje distributor zdarma. "
            "Registrace u EDC. Sdílení přes alokační klíč.")

cena_mericu = pocet_bytu * 10000 if model_sdileni == "jom" else 0

# Úspora na distribuci u JOM
if model_sdileni == "jom":
    # Místo N jističů platí SVJ pouze jeden velký
    uspora_jistic_mesic = jistic_plat * (pocet_bytu - 1)
    uspora_jistic_rocni = uspora_jistic_mesic * 12
else:
    uspora_jistic_rocni = 0

st.divider()

# --- SEKCE 4: LOKALITA A STŘECHA ---
st.subheader("🌍 Lokalita a střecha")

col1, col2 = st.columns([1, 2])

with col1:
    lokace_input = st.text_input("Město nebo PSČ", value="Praha",
                                 help="Zadejte název města nebo PSČ")

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
        azimut = st.select_slider("Orientace", options=[-90, -45, 0, 45, 90], value=0,
                                  format_func=lambda x: {
                                      -90: "⬅️ Východ", -45: "↙️ Jihovýchod",
                                      0: "⬆️ Jih", 45: "↗️ Jihozápad", 90: "➡️ Západ"}[x])
    koef_vyroba = 1.0
else:
    p1, p2 = st.columns(2)
    with p1:
        sklon = st.slider("Sklon panelů (°)", 5, 20, 10)
    with p2:
        system_plocha = st.radio("Systém",
                                 options=["jih", "jz_jv", "vz"],
                                 format_func=lambda x: {"jih": "⬆️ Jih",
                                                        "jz_jv": "↗️ JZ+JV",
                                                        "vz": "↔️ V+Z"}[x])
    if system_plocha == "jih":
        azimut, koef_vyroba = 0, 1.0
        st.info("☀️ Maximum výkonu, výroba kolem poledne.")
    elif system_plocha == "jz_jv":
        azimut, koef_vyroba = 0, 0.97
        st.info("☀️ Mírně nižší výkon, rovnoměrnější výroba.")
    else:
        azimut, koef_vyroba = 90, 0.88
        st.info("☀️ Nejrovnoměrnější výroba, ideální pro vlastní spotřebu.")

# PVGIS
if lokace_input:
    with st.spinner(f"Hledám {lokace_input}..."):
        lat, lon, nazev_mesta, geo_err = geocode_lokace(lokace_input)
    if geo_err:
        st.warning("⚠️ Lokalita nenalezena. Používám průměr ČR.")
        vyroba_rocni = vykon_fve * 1000
        pvgis_ok = False
    else:
        with st.spinner(f"Načítám solární data pro {nazev_mesta}..."):
            vyroba_pvgis, pvgis_err = get_pvgis_data(lat, lon, vykon_fve, sklon, azimut)
        if pvgis_err:
            st.warning("⚠️ PVGIS nedostupné. Používám průměr ČR.")
            vyroba_rocni = vykon_fve * 1000
            pvgis_ok = False
        else:
            vyroba_rocni = vyroba_pvgis * koef_vyroba
            pvgis_ok = True
            st.success(f"✅ {nazev_mesta} ({lat:.2f}°N, {lon:.2f}°E) — "
                       f"výroba {vyroba_rocni:,.0f} kWh/rok")
else:
    vyroba_rocni = vykon_fve * 1000
    pvgis_ok = False

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
        st.info("✅ Úroky hradí stát. SVJ splácí pouze jistinu.")
    elif scenar == "vlastni":
        splatnost = 0
        vlastni_podil_pct = 100
        st.info("💡 SVJ hradí vše z fondu oprav.")
    else:
        vlastni_podil_pct = st.slider("Vlastní zdroje (%)", 10, 90, 30, step=10)
        splatnost = st.slider("Doba splácení úvěru (let)", 5, 25, 15)

# Nízkopříjmové domácnosti
st.markdown("**Nízkopříjmové domácnosti (superdávka)**")
n1, n2 = st.columns(2)
with n1:
    pocet_nizko = st.number_input("Bytů s nárokem na bonus", 0, int(pocet_bytu), 0, step=1)
with n2:
    bonus_na_byt = st.number_input("Bonus na byt (Kč)", 0, 150000, 50000, step=5000)
bonus_celkem = pocet_nizko * bonus_na_byt

st.divider()

# === VÝPOČTY ===

# Celková investice
cena_instalace = cena_instalace_fve + cena_baterie + cena_mericu

# Výroba a spotřeba
vlastni_spotreba = min(vyroba_rocni * vlastni_spotreba_podil, spotreba)
pretoky = vyroba_rocni - vlastni_spotreba

# Výkupní cena přetoků
cena_pretoky = st.sidebar.number_input(
    "Výkupní cena přetoků (Kč/kWh)",
    min_value=0.30, max_value=2.50, value=0.95, step=0.05, format="%.2f",
    help="E.ON 0,70 Kč, TEDOM 0,75 Kč, spot průměr ~1,50 Kč")

# Roční úspora
uspora_elektrina = vlastni_spotreba * cena_prumerna_kwh
uspora_pretoky = pretoky * cena_pretoky
uspora_jistic = uspora_jistic_rocni
uspora_rocni = uspora_elektrina + uspora_pretoky + uspora_jistic

# Financování
vlastni_castka = cena_instalace * (vlastni_podil_pct / 100)
uver_castka = max(0, cena_instalace - vlastni_castka - bonus_celkem)

if scenar == "vlastni":
    rocni_splatka = 0
elif splatnost > 0:
    rocni_splatka = uver_castka / splatnost
else:
    rocni_splatka = 0

rocni_prinos_cisty = uspora_rocni - rocni_splatka
uspora_na_byt_rok = uspora_rocni / pocet_bytu
splatka_na_byt_mesic = rocni_splatka / pocet_bytu / 12

# Horizont: délka úvěru + 5 let, max 20
horizont = min(max(splatnost + 5, 10), 20) if splatnost > 0 else 15

# Cashflow
cashflow_data = []
for rok in range(0, horizont + 1):
    uspora_k = uspora_rocni * rok
    splatky_k = rocni_splatka * min(rok, splatnost)
    investice = vlastni_castka + uver_castka
    cf = uspora_k - splatky_k - investice
    cashflow_data.append({"Rok": rok, "Kumulativní úspora": uspora_k, "Cashflow": cf})

navratnost_rok = next((d["Rok"] for d in cashflow_data if d["Cashflow"] >= 0), None)

# === VÝSLEDKY ===

st.subheader("📊 Výsledky")

r1, r2, r3, r4, r5 = st.columns(5)

with r1:
    st.metric("Roční výroba FVE",
              f"{vyroba_rocni / 1000:,.1f} MWh",
              help="PVGIS data" if pvgis_ok else "Průměr ČR")
with r2:
    st.metric("Roční úspora celkem",
              f"{uspora_rocni:,.0f} Kč",
              help="Elektřina + přetoky + distribuce")
with r3:
    st.metric("Čistý roční přínos",
              f"{rocni_prinos_cisty:,.0f} Kč",
              delta="po splátce úvěru" if rocni_splatka > 0 else None)
with r4:
    st.metric("Splátka na byt/měsíc",
              f"{splatka_na_byt_mesic:,.0f} Kč" if rocni_splatka > 0 else "0 Kč")
with r5:
    if navratnost_rok:
        st.metric("Návratnost", f"{navratnost_rok} let")
    else:
        st.metric("Návratnost", f">{horizont} let")

# Milníky
st.markdown("**📍 Klíčové milníky**")

m1, m2, m3 = st.columns(3)
with m1:
    st.info(f"**Rok 1**\nRoční úspora: **{uspora_rocni:,.0f} Kč**\n"
            f"Na byt: **{uspora_na_byt_rok:,.0f} Kč/rok**")
with m2:
    if splatnost > 0:
        st.info(f"**Rok {splatnost}**\nÚvěr splacen ✅\n"
                f"Poté čistý přínos: **{uspora_rocni:,.0f} Kč/rok**")
    else:
        st.info(f"**Vlastní financování**\nŽádné splátky\n"
                f"Plný přínos hned: **{uspora_rocni:,.0f} Kč/rok**")
with m3:
    cf_konec = cashflow_data[-1]["Cashflow"]
    if navratnost_rok:
        st.success(f"**Rok {navratnost_rok}**\nInvestice se vrátí ✅\n"
                   f"Za {horizont} let: **{cf_konec:,.0f} Kč** čistý zisk")
    else:
        st.warning(f"**Za {horizont} let**\nInvestice se nevrátí\n"
                   f"Cashflow: **{cf_konec:,.0f} Kč**")

st.divider()

# Detail nákladů a výnosů
st.subheader("💰 Detail nákladů a výnosů")

d1, d2 = st.columns(2)

with d1:
    st.markdown("**Náklady**")
    st.write(f"• FVE {vykon_fve} kWp: **{cena_instalace_fve:,.0f} Kč**")
    if cena_baterie > 0:
        st.write(f"• Baterie {baterie_kapacita} kWh: **{cena_baterie:,.0f} Kč**")
    if cena_mericu > 0:
        st.write(f"• Podružné měřiče ({pocet_bytu} ks): **{cena_mericu:,.0f} Kč**")
    st.write(f"• **Celková investice: {cena_instalace:,.0f} Kč**")
    if bonus_celkem > 0:
        st.write(f"• Bonus nízkopříjmové: **− {bonus_celkem:,.0f} Kč**")
    if scenar != "vlastni":
        st.write(f"• Vlastní zdroje: **{vlastni_castka:,.0f} Kč**")
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_castka:,.0f} Kč**")
        st.write(f"• Roční splátka: **{rocni_splatka:,.0f} Kč** ({splatnost} let)")
    st.write(f"• Náklady na byt: **{vlastni_castka / pocet_bytu:,.0f} Kč**")

with d2:
    st.markdown("**Výnosy**")
    nazev_modelu = {"spolecne": "Jen společné prostory",
                    "jom": "Sjednocení odběrných míst",
                    "edc": "EDC komunitní sdílení"}[model_sdileni]
    st.write(f"• Model: **{nazev_modelu}**")
    st.write(f"• Vlastní spotřeba: **{vlastni_spotreba/1000:,.1f} MWh/rok** "
             f"({vlastni_spotreba_podil*100:.0f} %)")
    st.write(f"• Úspora na elektřině: **{uspora_elektrina:,.0f} Kč/rok**")
    st.write(f"• Přetoky: **{pretoky/1000:,.1f} MWh/rok** → "
             f"**{uspora_pretoky:,.0f} Kč/rok**")
    if uspora_jistic > 0:
        st.write(f"• Úspora na distribuci (JOM): **{uspora_jistic:,.0f} Kč/rok**")
    st.write(f"• **Celková roční úspora: {uspora_rocni:,.0f} Kč**")
    st.write(f"• Úspora na byt/rok: **{uspora_na_byt_rok:,.0f} Kč**")
    st.write(f"• Úspora na byt/měsíc: **{uspora_na_byt_rok/12:,.0f} Kč**")

st.divider()
st.caption(
    "⚠️ Orientační výpočty. Solární data: PVGIS © Evropská komise, JRC. "
    "Ceny elektřiny dle ceníků ČEZ, E.ON, PRE platných od 1.1.2026. "
    "POZE = 0 Kč od roku 2026. "
    "Bezúročný úvěr NZÚ — žádosti od září 2026. "
    "EDC komunitní sdílení — registrace na edc.cz. "
    "Výkupní cena přetoků závisí na smlouvě s dodavatelem."
)
