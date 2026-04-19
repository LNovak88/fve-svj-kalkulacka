import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="FVE Kalkulačka pro SVJ",
    page_icon="☀️",
    layout="wide"
)

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Spočítejte návratnost fotovoltaické elektrárny pro váš bytový dům")

st.divider()

# === FUNKCE ===

@st.cache_data(ttl=3600)
def get_pvgis_data(lat, lon, vykon_kwp, sklon, azimut):
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
    params = {
        "lat": lat, "lon": lon, "peakpower": vykon_kwp,
        "loss": 14, "angle": sklon, "aspect": azimut,
        "outputformat": "json", "browser": 0
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data["outputs"]["totals"]["fixed"]["E_y"], None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=3600)
def geocode_lokace(dotaz):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": f"{dotaz}, Česká republika", "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "FVE-SVJ-Kalkulacka/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        results = r.json()
        if results:
            res = results[0]
            addr = res.get("address", {})
            mesto = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or dotaz
            return float(res["lat"]), float(res["lon"]), mesto, None
        return None, None, None, "Lokalita nenalezena"
    except Exception as e:
        return None, None, None, str(e)

# === ZÁKLADNÍ ÚDAJE ===

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏠 Základní údaje")
    spotreba_mwh = st.number_input(
        "Roční spotřeba elektřiny (MWh/rok)", min_value=1.0, max_value=500.0,
        value=25.0, step=1.0, format="%.1f",
        help="Celková spotřeba SVJ za rok včetně bytů"
    )
    spotreba = spotreba_mwh * 1000
    pocet_bytu = st.number_input("Počet bytů v domě", min_value=2, max_value=200, value=12, step=1)
    cena_elektriny = st.number_input(
        "Aktuální cena elektřiny (Kč/kWh)", min_value=1.0, max_value=10.0,
        value=5.5, step=0.1, format="%.1f"
    )
    cena_pretoky = st.number_input(
        "Výkupní cena přetoků (Kč/kWh)", min_value=0.30, max_value=2.50,
        value=0.95, step=0.05, format="%.2f",
        help="Typické rozmezí 2025: E.ON 0,70 Kč, TEDOM 0,75 Kč, spot ~1,50 Kč"
    )

with col2:
    st.subheader("⚡ Parametry FVE")
    vykon_fve = st.number_input(
        "Výkon FVE (kWp)", min_value=1.0, max_value=200.0,
        value=20.0, step=0.5, format="%.1f",
        help="Orientační pravidlo: 1 kWp na 1 MWh roční spotřeby"
    )
    cena_instalace_fve = st.number_input(
        "Cena instalace FVE (Kč bez DPH)", min_value=100000, max_value=10000000,
        value=700000, step=50000,
        help="Orientační cena: 30 000–40 000 Kč/kWp pro bytové domy"
    )

st.divider()

# === MODEL SDÍLENÍ ===

st.subheader("🔗 Model sdílení energie")

mod1, mod2 = st.columns([2, 1])

with mod1:
    model_sdileni = st.radio(
        "Zvolte model sdílení",
        options=["spolecne", "jom", "edc"],
        format_func=lambda x: {
            "spolecne": "🏢 Jen společné prostory — FVE napájí výtah, světla, čerpadla",
            "jom": "⚡ Sjednocení odběrných míst — jeden hlavní měřič, vlastní podružné měřiče na byty",
            "edc": "🔗 EDC komunitní sdílení — každý byt si zachovává svého dodavatele, alokační klíč"
        }[x],
        help="Výběr modelu zásadně ovlivňuje výši úspor i administrativní náročnost"
    )

with mod2:
    baterie_kapacita = st.number_input(
        "Kapacita baterie (kWh)",
        min_value=0, max_value=200, value=0, step=5,
        help="Baterie zvyšuje podíl vlastní spotřeby. 0 = bez baterie."
    )
    if baterie_kapacita > 0:
        cena_baterie = st.number_input(
            "Cena baterie (Kč bez DPH)",
            min_value=50000, max_value=2000000,
            value=int(baterie_kapacita * 8000),
            step=10000,
            help="Orientační cena: 7 000–10 000 Kč/kWh kapacity"
        )
    else:
        cena_baterie = 0

# Koeficient vlastní spotřeby dle modelu
koef_base = {
    "spolecne": 0.20,
    "jom": 0.60,
    "edc": 0.65
}[model_sdileni]

# Bonus za baterii (postupně klesající přínos)
if baterie_kapacita <= 0:
    koef_baterie = 0.0
elif baterie_kapacita <= 10:
    koef_baterie = 0.08
elif baterie_kapacita <= 20:
    koef_baterie = 0.13
elif baterie_kapacita <= 30:
    koef_baterie = 0.17
else:
    koef_baterie = 0.20

vlastni_spotreba_podil = min(koef_base + koef_baterie, 0.85)

# Informační box dle modelu
if model_sdileni == "spolecne":
    st.info("🏢 Nejjednodušší model. FVE pokrývá společnou spotřebu (výtah, osvětlení, čerpadla). Nevyžaduje souhlas nájemníků ani změnu smluv. Úspora je nejnižší.")
elif model_sdileni == "jom":
    st.info(f"⚡ Jeden hlavní elektroměr pro celý dům. SVJ nakupuje elektřinu hromadně a interně ji rozpočítává přes podružné měřiče. Cena podružných měřičů: **{pocet_bytu} bytů × 10 000 Kč = {pocet_bytu * 10000:,} Kč** (zahrnuto v celkových nákladech).")
elif model_sdileni == "edc":
    st.info("🔗 Každý byt si zachovává vlastního dodavatele elektřiny. Chytré elektroměry instaluje distributor zdarma. Výroba se rozděluje podle alokačního klíče přes EDC. Vyžaduje registraci u EDC.")

st.divider()

# === LOKALITA A STŘECHA ===

st.subheader("🌍 Lokalita a střecha")

lok1, lok2 = st.columns([1, 2])

with lok1:
    lokace_input = st.text_input(
        "Město nebo PSČ", value="Praha",
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
            "Orientace", options=[-90, -45, 0, 45, 90], value=0,
            format_func=lambda x: {
                -90: "⬅️ Východ", -45: "↙️ Jihovýchod",
                0: "⬆️ Jih (ideální)", 45: "↗️ Jihozápad", 90: "➡️ Západ"
            }[x]
        )
    azimut = azimut_volba
    koeficient_vyroba = 1.0
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
        azimut, koeficient_vyroba = 0, 1.0
        st.info("☀️ Maximální výkon, výroba soustředěná kolem poledne.")
    elif system_plocha == "jz_jv":
        azimut, koeficient_vyroba = 0, 0.97
        st.info("☀️ Mírně nižší špičkový výkon, výroba rozložená na delší část dne.")
    else:
        azimut, koeficient_vyroba = 90, 0.88
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

# === FINANCOVÁNÍ ===

st.subheader("💰 Model financování")

fin_col1, fin_col2 = st.columns(2)

with fin_col1:
    scenar = st.radio(
        "Scénář financování",
        options=["uver", "vlastni", "kombinace"],
        format_func=lambda x: {
            "uver": "🏦 Bezúročný úvěr NZÚ (od září 2026)",
            "vlastni": "💵 Vlastní zdroje (fond oprav)",
            "kombinace": "🔀 Kombinace vlastní + úvěr"
        }[x],
        help="Od roku 2026 NZÚ poskytuje bezúročné úvěry místo přímých dotací"
    )

with fin_col2:
    if scenar == "uver":
        splatnost = st.slider("Doba splácení úvěru (let)", min_value=5, max_value=25, value=15)
        vlastni_podil_pct = 0
        st.info("✅ Úroky hradí stát (SFŽP). SVJ splácí pouze jistinu.")
    elif scenar == "vlastni":
        splatnost = 0
        vlastni_podil_pct = 100
        st.info("💡 SVJ hradí vše z fondu oprav nebo jednorázovým příspěvkem.")
    else:
        vlastni_podil_pct = st.slider("Vlastní zdroje (%)", min_value=10, max_value=90, value=30, step=10)
        splatnost = st.slider("Doba splácení úvěru (let)", min_value=5, max_value=25, value=15)

# Nízkopříjmové domácnosti
st.markdown("**Nízkopříjmové domácnosti (superdávka)**")
nizko_col1, nizko_col2 = st.columns(2)
with nizko_col1:
    pocet_nizko = st.number_input(
        "Počet bytů s nárokem na superdávku",
        min_value=0, max_value=int(pocet_bytu), value=0, step=1,
        help="Tyto domácnosti mají nárok na přímý bonus od státu"
    )
with nizko_col2:
    bonus_na_byt = st.number_input(
        "Bonus na nízkopříjmový byt (Kč)",
        min_value=0, max_value=150000, value=50000, step=5000
    )

bonus_celkem = pocet_nizko * bonus_na_byt

st.divider()

# === VÝPOČTY ===

# Celková cena investice
cena_mericu = pocet_bytu * 10000 if model_sdileni == "jom" else 0
cena_instalace = cena_instalace_fve + cena_baterie + cena_mericu

# Výroba a spotřeba
vlastni_spotreba = min(vyroba_rocni * vlastni_spotreba_podil, spotreba)
pretoky = vyroba_rocni - vlastni_spotreba
uspora_rocni = (vlastni_spotreba * cena_elektriny) + (pretoky * cena_pretoky)

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
uspora_na_byt = uspora_rocni / pocet_bytu
splatka_na_byt = rocni_splatka / pocet_bytu / 12

# === VÝSLEDKY ===

st.subheader("📊 Výsledky")

res1, res2, res3, res4 = st.columns(4)

with res1:
    st.metric(
        "Roční výroba FVE",
        f"{vyroba_rocni / 1000:,.1f} MWh",
        help="Dle PVGIS pro vaši lokalitu" if pvgis_ok else "Odhad průměr ČR"
    )
with res2:
    st.metric("Roční úspora", f"{uspora_rocni:,.0f} Kč",
              help="Úspora na faktuře + příjem z přetoků")
with res3:
    st.metric("Čistý roční přínos", f"{rocni_prinos_cisty:,.0f} Kč",
              help="Roční úspora mínus splátka úvěru")
with res4:
    st.metric(
        "Splátka na byt/měsíc",
        f"{splatka_na_byt:,.0f} Kč" if rocni_splatka > 0 else "0 Kč",
        help="Měsíční splátka úvěru na jeden byt"
    )

st.divider()

# === PŘEHLED NÁKLADŮ ===

st.subheader("💰 Přehled nákladů a výnosů")

fin1, fin2 = st.columns(2)

with fin1:
    st.markdown("**Náklady**")
    st.write(f"• FVE instalace: **{cena_instalace_fve:,.0f} Kč**")
    if cena_baterie > 0:
        st.write(f"• Baterie {baterie_kapacita} kWh: **{cena_baterie:,.0f} Kč**")
    if cena_mericu > 0:
        st.write(f"• Podružné měřiče ({pocet_bytu} bytů): **{cena_mericu:,.0f} Kč**")
    st.write(f"• **Celková investice: {cena_instalace:,.0f} Kč**")
    if bonus_celkem > 0:
        st.write(f"• Bonus nízkopříjmové domácnosti: **− {bonus_celkem:,.0f} Kč**")
    if scenar != "vlastni":
        st.write(f"• Vlastní zdroje SVJ: **{vlastni_castka:,.0f} Kč**")
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_castka:,.0f} Kč**")
        st.write(f"• Splátka úvěru: **{rocni_splatka:,.0f} Kč/rok** ({splatnost} let)")
    st.write(f"• Náklady na byt (vlastní část): **{vlastni_castka / pocet_bytu:,.0f} Kč**")

with fin2:
    st.markdown("**Výnosy**")
    nazev_modelu = {'spolecne': 'Jen společné prostory', 'jom': 'Sjednocení odběrných míst', 'edc': 'EDC komunitní sdílení'}[model_sdileni]
st.write(f"• Model sdílení: **{nazev_modelu}**")
    st.write(f"• Vlastní spotřeba z FVE: **{vlastni_spotreba / 1000:,.1f} MWh/rok** ({vlastni_spotreba_podil*100:.0f} %)")
    st.write(f"• Úspora na faktuře: **{vlastni_spotreba * cena_elektriny:,.0f} Kč/rok**")
    st.write(f"• Přetoky do sítě: **{pretoky / 1000:,.1f} MWh/rok**")
    st.write(f"• Příjem z přetoků: **{pretoky * cena_pretoky:,.0f} Kč/rok**")
    st.write(f"• Úspora na byt/rok: **{uspora_na_byt:,.0f} Kč**")

st.divider()

# === GRAF NÁVRATNOSTI ===

st.subheader("📈 Graf návratnosti investice (25 let)")

roky = list(range(0, 26))
cashflow = []
kumulativni_uspora = []

for rok in roky:
    uspora_k = uspora_rocni * rok
    splatky_k = rocni_splatka * min(rok, splatnost)
    pocatecni_investice = vlastni_castka + uver_castka
    cf = uspora_k - splatky_k - pocatecni_investice
    kumulativni_uspora.append(uspora_k)
    cashflow.append(cf)

navratnost_rok = next((i for i, cf in enumerate(cashflow) if cf >= 0), None)

df_graf = pd.DataFrame({
    "Rok": roky,
    "Kumulativní úspora (Kč)": kumulativni_uspora,
    "Čistý cashflow (Kč)": cashflow
})

st.line_chart(
    df_graf.set_index("Rok")[["Kumulativní úspora (Kč)", "Čistý cashflow (Kč)"]],
    color=["#f5a623", "#2ecc71"]
)

if navratnost_rok:
    st.success(f"✅ Investice se vrátí přibližně v roce **{navratnost_rok}** od spuštění FVE.")
    uspora_25 = cashflow[25]
    st.info(f"💡 Za 25 let bude čistý přínos pro SVJ **{uspora_25:,.0f} Kč** ({uspora_25/pocet_bytu:,.0f} Kč na byt).")
else:
    st.warning("⚠️ Při zadaných parametrech se investice do 25 let nevrátí. Zkuste upravit výkon FVE nebo model financování.")

st.divider()
st.caption("⚠️ Kalkulačka poskytuje orientační výpočty. Solární data: PVGIS © Evropská komise, JRC. Bezúročný úvěr NZÚ — žádosti od září 2026. Výkupní cena přetoků závisí na smlouvě s dodavatelem (typicky 0,70–1,50 Kč/kWh). EDC komunitní sdílení — registrace na edc.cz.")
