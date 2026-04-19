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
def geocode_lokace(dotaz):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{dotaz}, Česká republika",
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }
    headers = {"User-Agent": "FVE-SVJ-Kalkulacka/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        results = r.json()
        if results:
            res = results[0]
            addr = res.get("address", {})
            mesto = (
                addr.get("city") or
                addr.get("town") or
                addr.get("village") or
                addr.get("municipality") or
                dotaz
            )
            return float(res["lat"]), float(res["lon"]), mesto, None
        return None, None, None, "Lokalita nenalezena"
    except Exception as e:
        return None, None, None, str(e)

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

    cena_pretoky = st.number_input(
        "Výkupní cena přetoků (Kč/kWh)",
        min_value=0.30,
        max_value=2.50,
        value=0.95,
        step=0.05,
        format="%.2f",
        help="Typické rozmezí 2025: E.ON 0,70 Kč, TEDOM 0,75 Kč, spotový trh průměr ~1,50 Kč"
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

st.divider()

# === FINANCOVÁNÍ ===

st.subheader("💰 Model financování")

fin_col1, fin_col2 = st.columns(2)

with fin_col1:
    scenar = st.radio(
        "Scénář financování",
        options=["uvěr", "vlastni", "kombinace"],
        format_func=lambda x: {
            "uvěr": "🏦 Bezúročný úvěr NZÚ (od září 2026)",
            "vlastni": "💵 Vlastní zdroje (fond oprav)",
            "kombinace": "🔀 Kombinace vlastní + úvěr"
        }[x],
        help="Od roku 2026 NZÚ poskytuje bezúročné úvěry místo přímých dotací"
    )

with fin_col2:
    if scenar == "uvěr":
        splatnost = st.slider(
            "Doba splácení úvěru (let)",
            min_value=5,
            max_value=25,
            value=15,
            help="NZÚ bezúročný úvěr — max. 25 let, 0 % úrok"
        )
        vlastni_podil_pct = 0
        st.info("✅ Úroky hradí stát (SFŽP). SVJ splácí pouze jistinu.")

    elif scenar == "vlastni":
        splatnost = 0
        vlastni_podil_pct = 100
        st.info("💡 SVJ hradí vše z fondu oprav nebo jednorázovým příspěvkem.")

    else:
        vlastni_podil_pct = st.slider(
            "Vlastní zdroje (%)",
            min_value=10,
            max_value=90,
            value=30,
            step=10,
            help="Zbytek pokryje bezúročný úvěr NZÚ"
        )
        splatnost = st.slider(
            "Doba splácení úvěru (let)",
            min_value=5,
            max_value=25,
            value=15,
            help="NZÚ bezúročný úvěr — max. 25 let, 0 % úrok"
        )

# Nízkopříjmové domácnosti — bonus
st.markdown("**Nízkopříjmové domácnosti (superdávka)**")
nizko_col1, nizko_col2 = st.columns(2)
with nizko_col1:
    pocet_nizko = st.number_input(
        "Počet bytů s nárokem na superdávku",
        min_value=0,
        max_value=int(pocet_bytu),
        value=0,
        step=1,
        help="Tyto domácnosti mají nárok na přímý bonus od státu (až 150 000 Kč/byt při komplexní renovaci)"
    )
with nizko_col2:
    bonus_na_byt = st.number_input(
        "Bonus na nízkopříjmový byt (Kč)",
        min_value=0,
        max_value=150000,
        value=50000,
        step=5000,
        help="Přímý státní bonus pro nízkopříjmové domácnosti v SVJ"
    )

bonus_celkem = pocet_nizko * bonus_na_byt

st.divider()

# === LOKALITA A STŘECHA ===

st.subheader("🌍 Lokalita a střecha")

lok1, lok2 = st.columns([1, 2])

with lok1:
    lokace_input = st.text_input(
        "Město nebo PSČ",
        value="Praha",
        help="Zadejte název města nebo PSČ (např. 739 61 nebo Třinec)"
    )

with lok2:
    typ_strechy = st.radio(
        "Typ střechy",
        options=["sikma", "plocha"],
        format_func=lambda x: "🏠 Šikmá střecha" if x == "sikma" else "🏢 Plochá střecha",
        horizontal=True
    )

if typ_strechy == "sikma":
    s1, s2 = st.columns(2)
    with s1:
        sklon = st.slider("Sklon střechy (°)", min_value=15, max_value=60, value=35)
    with s2:
        azimut_volba = st.select_slider(
            "Orientace",
            options=[-90, -45, 0, 45, 90],
            value=0,
            format_func=lambda x: {
                -90: "⬅️ Východ",
                -45: "↙️ Jihovýchod",
                0: "⬆️ Jih (ideální)",
                45: "↗️ Jihozápad",
                90: "➡️ Západ"
            }[x]
        )
    azimut = azimut_volba
    koeficient_vyroba = 1.0
    vlastni_spotreba_podil = 0.60

else:
    p1, p2 = st.columns(2)
    with p1:
        sklon = st.slider("Sklon panelů (°)", min_value=5, max_value=20, value=10)
    with p2:
        system_plocha = st.radio(
            "Systém rozmístění",
            options=["jih", "jz_jv", "vychod_zapad"],
            format_func=lambda x: {
                "jih": "⬆️ Jih",
                "jz_jv": "↗️ JZ + JV",
                "vychod_zapad": "↔️ Východ + Západ"
            }[x]
        )
    if system_plocha == "jih":
        azimut = 0
        koeficient_vyroba = 1.0
        vlastni_spotreba_podil = 0.60
        st.info("☀️ Maximální výkon, výroba soustředěná kolem poledne.")
    elif system_plocha == "jz_jv":
        azimut = 0
        koeficient_vyroba = 0.97
        vlastni_spotreba_podil = 0.65
        st.info("☀️ Mírně nižší špičkový výkon, výroba rozložená na delší část dne.")
    else:
        azimut = 90
        koeficient_vyroba = 0.88
        vlastni_spotreba_podil = 0.70
        st.info("☀️ Nejrovnoměrnější výroba, ideální pro vlastní spotřebu SVJ.")

# === PVGIS ===

if lokace_input:
    with st.spinner(f"Hledám lokalitu: {lokace_input}..."):
        lat, lon, nazev_mesta, geo_err = geocode_lokace(lokace_input)

    if geo_err:
        st.warning("⚠️ Nepodařilo se najít lokalitu. Používám průměr ČR.")
        vyroba_rocni = vykon_fve * 1000
        pvgis_ok = False
    else:
        with st.spinner(f"Načítám solární data pro {nazev_mesta} z PVGIS..."):
            vyroba_pvgis, pvgis_err = get_pvgis_data(lat, lon, vykon_fve, sklon, azimut)

        if pvgis_err:
            st.warning("⚠️ PVGIS nedostupné. Používám průměr ČR.")
            vyroba_rocni = vykon_fve * 1000
            pvgis_ok = False
        else:
            vyroba_rocni = vyroba_pvgis * koeficient_vyroba
            pvgis_ok = True
            st.success(f"✅ {nazev_mesta} ({lat:.2f}°N, {lon:.2f}°E) — výroba {vyroba_rocni:,.0f} kWh/rok")
else:
    vyroba_rocni = vykon_fve * 1000
    pvgis_ok = False

st.divider()

# === VÝPOČTY ===

vlastni_spotreba = min(vyroba_rocni * vlastni_spotreba_podil, spotreba)
pretoky = vyroba_rocni - vlastni_spotreba
uspora_rocni = (vlastni_spotreba * cena_elektriny) + (pretoky * cena_pretoky)

# Financování
vlastni_castka = cena_instalace * (vlastni_podil_pct / 100)
uver_castka = cena_instalace - vlastni_castka - bonus_celkem
uver_castka = max(0, uver_castka)

if scenar == "vlastni":
    rocni_splatka = 0
    celkove_naklady_svj = cena_instalace - bonus_celkem
elif splatnost > 0:
    rocni_splatka = uver_castka / splatnost
    celkove_naklady_svj = vlastni_castka + uver_castka - bonus_celkem
else:
    rocni_splatka = 0
    celkove_naklady_svj = cena_instalace - bonus_celkem

celkove_naklady_svj = max(0, celkove_naklady_svj)

# Čistý roční přínos (úspora mínus splátka)
rocni_prinos_cisty = uspora_rocni - rocni_splatka

# Návratnost vlastní části
if rocni_prinos_cisty > 0 and vlastni_castka > 0:
    navratnost = vlastni_castka / rocni_prinos_cisty
elif scenar == "uvěr" and rocni_prinos_cisty > 0:
    navratnost = 0
else:
    navratnost = celkove_naklady_svj / uspora_rocni if uspora_rocni > 0 else 999

uspora_na_byt = uspora_rocni / pocet_bytu
splatka_na_byt = rocni_splatka / pocet_bytu / 12

# === VÝSLEDKY ===

st.subheader("📊 Výsledky")

res1, res2, res3, res4 = st.columns(4)

with res1:
    st.metric(
        label="Roční výroba FVE",
        value=f"{vyroba_rocni / 1000:,.1f} MWh",
        help="Dle PVGIS pro vaši lokalitu" if pvgis_ok else "Odhad průměr ČR"
    )

with res2:
    st.metric(
        label="Roční úspora",
        value=f"{uspora_rocni:,.0f} Kč",
        help="Úspora na faktuře + příjem z přetoků"
    )

with res3:
    st.metric(
        label="Čistý roční přínos",
        value=f"{rocni_prinos_cisty:,.0f} Kč",
        help="Roční úspora mínus splátka úvěru"
    )

with res4:
    st.metric(
        label="Splátka na byt/měsíc",
        value=f"{splatka_na_byt:,.0f} Kč" if rocni_splatka > 0 else "0 Kč",
        help="Měsíční splátka úvěru na jeden byt"
    )

st.divider()

# === DETAIL FINANCOVÁNÍ ===

st.subheader("💰 Přehled financování")

fin1, fin2 = st.columns(2)

with fin1:
    st.markdown("**Náklady**")
    st.write(f"• Cena instalace: **{cena_instalace:,.0f} Kč**")
    if bonus_celkem > 0:
        st.write(f"• Bonus nízkopříjmové domácnosti: **− {bonus_celkem:,.0f} Kč**")
    if scenar != "vlastni":
        st.write(f"• Vlastní zdroje SVJ: **{vlastni_castka:,.0f} Kč**")
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_castka:,.0f} Kč**")
        st.write(f"• Splátka úvěru: **{rocni_splatka:,.0f} Kč/rok** ({splatnost} let)")
    st.write(f"• Náklady na byt (vlastní): **{vlastni_castka / pocet_bytu:,.0f} Kč**")

with fin2:
    st.markdown("**Výnosy**")
    st.write(f"• Vlastní spotřeba z FVE: **{vlastni_spotreba / 1000:,.1f} MWh/rok**")
    st.write(f"• Úspora na faktuře: **{vlastni_spotreba * cena_elektriny:,.0f} Kč/rok**")
    st.write(f"• Přetoky do sítě: **{pretoky / 1000:,.1f} MWh/rok**")
    st.write(f"• Příjem z přetoků: **{pretoky * cena_pretoky:,.0f} Kč/rok**")
    st.write(f"• Úspora na byt/rok: **{uspora_na_byt:,.0f} Kč**")

st.divider()

# === GRAF NÁVRATNOSTI ===

st.subheader("📈 Graf návratnosti investice (25 let)")

roky = list(range(0, 26))
kumulativni_uspora = []
kumulativni_splatky = []
cashflow = []

for rok in roky:
    uspora_k = uspora_rocni * rok
    splatky_k = rocni_splatka * min(rok, splatnost)
    # Počáteční investice = vlastní část + celý úvěr (jistina)
    pocatecni_investice = vlastni_castka + uver_castka
    cf = uspora_k - splatky_k - pocatecni_investice
    kumulativni_uspora.append(uspora_k)
    kumulativni_splatky.append(splatky_k)
    cashflow.append(cf)

# Najdi bod návratnosti
navratnost_rok = None
for i, cf in enumerate(cashflow):
    if cf >= 0:
        navratnost_rok = i
        break

# Streamlit nativní graf
import pandas as pd

df_graf = pd.DataFrame({
    "Rok": roky,
    "Kumulativní úspora (Kč)": kumulativni_uspora,
    "Kumulativní splátky (Kč)": kumulativni_splatky,
    "Čistý cashflow (Kč)": cashflow
})

st.line_chart(
    df_graf.set_index("Rok")[["Kumulativní úspora (Kč)", "Čistý cashflow (Kč)"]],
    color=["#f5a623", "#2ecc71"]
)

if navratnost_rok:
    st.success(f"✅ Investice se vrátí přibližně v roce **{navratnost_rok}** od spuštění FVE.")
    uspora_25 = cashflow[25]
    st.info(f"💡 Za 25 let bude čistý přínos pro SVJ **{uspora_25:,.0f} Kč** (tj. {uspora_25/pocet_bytu:,.0f} Kč na byt).")
else:
    st.warning("⚠️ Při zadaných parametrech se investice do 25 let nevrátí. Zkuste upravit výkon FVE nebo model financování.")

st.divider()
st.caption("⚠️ Kalkulačka poskytuje orientační výpočty. Solární data: PVGIS © Evropská komise, JRC. Bezúročný úvěr NZÚ — žádosti od září 2026 přes zapojené banky a stavební spořitelny. Výkupní cena přetoků závisí na smlouvě s dodavatelem (typicky 0,70–1,50 Kč/kWh v roce 2025).")
