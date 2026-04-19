import streamlit as st
import math

st.set_page_config(
    page_title="FVE Kalkulačka pro SVJ",
    page_icon="☀️",
    layout="wide"
)

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Spočítejte návratnost fotovoltaické elektrárny pro váš bytový dům")

st.divider()

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
    help="Celková spotřeba SVJ za rok – najdete ji na faktuře nebo ve smlouvě s dodavatelem"
)
spotreba = spotreba_mwh * 1000  # převod na kWh pro výpočty
    
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
    
    vvykon_fve = st.number_input(
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

# === VÝPOČTY ===

# Výroba FVE (průměr ČR ~1000 kWh/kWp/rok)
vyroba_rocni = vykon_fve * 1000

# Vlastní spotřeba (předpoklad 60 % z výroby)
vlastni_spotreba_podil = 0.60
vlastni_spotreba = min(vyroba_rocni * vlastni_spotreba_podil, spotreba)

# Přetoky do sítě
pretoky = vyroba_rocni - vlastni_spotreba
cena_pretoky = 1.8  # Kč/kWh výkupní cena

# Roční úspora
uspora_rocni = (vlastni_spotreba * cena_elektriny) + (pretoky * cena_pretoky)

# Financování
dotace_castka = cena_instalace * (dotace_procento / 100)
vlastni_naklady = cena_instalace - dotace_castka

# Návratnost
navratnost = vlastni_naklady / uspora_rocni if uspora_rocni > 0 else 999

# Úspora na byt
uspora_na_byt = uspora_rocni / pocet_bytu

# === VÝSLEDKY ===

st.subheader("📊 Výsledky")

res1, res2, res3, res4 = st.columns(4)

with res1:
    st.metric(
    label="Roční výroba FVE",
    value=f"{vyroba_rocni/1000:,.1f} MWh",
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
    st.write(f"• Náklady na byt: **{vlastni_naklady/pocet_bytu:,.0f} Kč**")

with fin2:
    st.markdown("**Výnosy**")
    st.write(f"• Vlastní spotřeba z FVE: **{vlastni_spotreba:,.0f} kWh/rok**")
    st.write(f"• Úspora na faktuře: **{vlastni_spotreba * cena_elektriny:,.0f} Kč/rok**")
    st.write(f"• Přetoky do sítě: **{pretoky:,.0f} kWh/rok**")
    st.write(f"• Příjem z přetoků: **{pretoky * cena_pretoky:,.0f} Kč/rok**")

st.divider()
st.caption("⚠️ Kalkulačka poskytuje orientační výpočty. Přesné hodnoty závisí na lokalitě, orientaci střechy a aktuálních cenách energií. Výkupní cena přetoků: 1,80 Kč/kWh. Výroba FVE: 1 000 kWh/kWp/rok (průměr ČR).")
