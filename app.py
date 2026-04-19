import streamlit as st
import requests

st.set_page_config(
    page_title="FVE Kalkulačka pro SVJ",
    page_icon="☀️",
    layout="wide"
)

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Spočítejte návratnost fotovoltaické elektrárny pro váš bytový dům")

st.divider()

# === PVGIS FUNKCE ===

@st.cache_data(ttl=3600)
def get_pvgis_data(lat, lon, vykon_kwp, sklon, azimut):
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
    params = {
        "lat": lat,
        "lon": lon,
        "peakpower": vykon_kwp,
        "loss": 14,
        "angle": sklon,
        "aspect": azimut,
        "outputformat": "json",
        "browser": 0
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        vyroba = data["outputs"]["totals"]["fixed"]["E_y"]
        return vyroba, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=3600)
def geocode_mesto(mesto):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{mesto}, Česká republika",
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "FVE-SVJ-Kalkulacka/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"]), None
        return None, None, "Město nenalezeno"
    except Exception as e:
        return None, None, str(e)

# === VSTUPY ===

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏠 Základní údaje")

    spotreba_mwh = st.number_input(
        "Roční spotřeba elektřiny (MWh/rok)",
        min_value=1.0,
        max_value=500.0,
        value=25.0,
        step=1.0,
        format="%.1f",
        help="Celková spotřeba SVJ za rok"
    )
    spotreba = spotreba_mwh * 1000

    pocet_bytu = st.number_input(
        "Počet bytů v domě",
        min_value=2,
        max_value=200,
        value=12,
        step=1
    )

    cena_elektriny = st.number_input(
        "Aktuální cena elektřiny (Kč/kWh)",
        min_value=1.0,
        max_value=10.0,
        value=5.5,
        step=0.1,
        format="%.1f"
    )

with col2:
    st.subheader("⚡ Parametry FVE")

    vykon_fve = st.number_input(
        "Výkon FVE (kWp)",
        min_value=1.0,
        max_value=200.0,
        value=20.0,
        step=0.5,
        format="%.1f",
        help="Orientační pravidlo: 1 kWp na 1 MWh roční spotřeby"
    )

    cena_instalace = st.number_input(
        "Cena instalace (Kč bez DPH)",
        min_value=100000,
        max_value=10000000,
        value=700000,
        step=50000,
        help="Orientační cena: 30 000–40 000 Kč/kWp pro bytové domy"
    )

    dotace_procento = st.slider(
        "Dotace NZÚ (%)",
        min_value=0,
        max_value=70,
        value=50,
        help="Aktuální dotační programy NZÚ pro SVJ pokrývají typicky 40–50 % nákladů"
    )

st.divider()

# === LOKALITA A PVGIS ===

st.subheader("🌍 Lokalita a oslunění")

lok1, lok2, lok3 = st.columns(3)

with lok1:
    mesto = st.text_input(
        "Město nebo obec",
        value="Praha",
        help="Zadejte název města pro načtení reálných dat oslunění"
    )

with lok2:
    sklon = st.slider(
        "Sklon střechy (°)",
        min_value=0,
        max_value=60,
        value=35,
        help="Typická šikmá střecha: 30–45°. Plochá střecha: 10–15°"
    )

with lok3:
    azimut = st.select_slider(
        "Orientace střechy",
        options=[-90, -45, 0, 45, 90],
        value=0,
        format_func=lambda x: {
            -90: "⬅️ Východ",
            -45: "↖️ Severovýchod",
            0: "⬆️ Jih (ideální)",
            45: "↗️ Jihozápad",
            90: "➡️ Západ"
        }[x]
    )

# Načtení PVGIS dat
if mesto:
    with st.spinner(f"Načítám data pro {mesto}..."):
        lat, lon, geo_err = geocode_mesto(mesto)

    if geo_err:
        st.warning(f"⚠️ Nepodařilo se najít město: {geo_err}. Používám průměr ČR (1 000 kWh/kWp).")
        vyroba_rocni = vykon_fve * 1000
        pvgis_ok = False
    else:
        with st.spinner("Načítám solární data z PVGIS (EU databáze)..."):
            vyroba_pvgis, pvgis_err = get_pvgis_data(lat, lon, vykon_fve, sklon, azimut)

        if pvgis_err:
            st.warning(f"⚠️ PVGIS nedostupné: {pvgis_err}. Používám průměr ČR.")
            vyroba_rocni = vykon_fve * 1000
            pvgis_ok = False
        else:
            vyroba_rocni = vyroba_pvgis
            pvgis_ok = True
            st.success(f"✅ Data načtena pro {mesto} ({lat:.2f}°N, {lon:.2f}°E) — výroba {vyroba_rocni:,.0f} kWh/rok")
else:
    vyroba_rocni = vykon_fve * 1000
    pvgis_ok = False

st.divider()

# === VÝPOČTY ===

vlastni_spotreba_podil = 0.60
vlastni_spotreba = min(vyroba_rocni * vlastni_spotreba_podil, spotreba)

pretoky = vyroba_rocni - vlastni_spotreba
cena_pretoky = 1.8

uspora_rocni = (vlastni_spotreba * cena_elektriny) + (pretoky * cena_pretoky)

dotace_castka = cena_instalace * (dotace_procento / 100)
vlastni_naklady = cena_instalace - dotace_castka

navratnost = vlastni_naklady / uspora_rocni if uspora_rocni > 0 else 999

uspora_na_byt = uspora_rocni / pocet_bytu

# === VÝSLEDKY ===

st.subheader("📊 Výsledky")

res1, res2, res3, res4 = st.columns(4)

with res1:
    st.metric(
        label="Roční výroba FVE",
        value=f"{vyroba_rocni / 1000:,.1f} MWh",
        help="Dle reálných dat PVGIS pro vaši lokalitu" if pvgis_ok else "Odhad dle průměru ČR"
    )

with res2:
    st.metric(
        label="Roční úspora",
        value=f"{uspora_rocni:,.0f} Kč",
        help="Součet úspory na faktuře + příjem z přetoků"
    )

with res3:
    st.metric(
        label="Návratnost investice",
        value=f"{navratnost:.1f} let",
        delta=f"Po dotaci {dotace_procento} %",
        delta_color="normal"
    )

with res4:
    st.metric(
        label="Úspora na byt/rok",
        value=f"{uspora_na_byt:,.0f} Kč",
        help="Průměrná roční úspora na jeden byt"
    )

st.divider()

# === DETAIL FINANCOVÁNÍ ===

st.subheader("💰 Financování")

fin1, fin2 = st.columns(2)

with fin1:
    st.markdown("**Náklady**")
    st.write(f"• Celková cena instalace: **{cena_instalace:,.0f} Kč**")
    st.write(f"• Dotace NZÚ ({dotace_procento} %): **− {dotace_castka:,.0f} Kč**")
    st.write(f"• Vlastní náklady SVJ: **{vlastni_naklady:,.0f} Kč**")
    st.write(f"• Náklady na byt: **{vlastni_naklady / pocet_bytu:,.0f} Kč**")

with fin2:
    st.markdown("**Výnosy**")
    st.write(f"• Vlastní spotřeba z FVE: **{vlastni_spotreba / 1000:,.1f} MWh/rok**")
    st.write(f"• Úspora na faktuře: **{vlastni_spotreba * cena_elektriny:,.0f} Kč/rok**")
    st.write(f"• Přetoky do sítě: **{pretoky / 1000:,.1f} MWh/rok**")
    st.write(f"• Příjem z přetoků: **{pretoky * cena_pretoky:,.0f} Kč/rok**")

st.divider()
st.caption("⚠️ Kalkulačka poskytuje orientační výpočty. Solární data: PVGIS © Evropská komise, JRC. Výkupní cena přetoků: 1,80 Kč/kWh.")
