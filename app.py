# app.py — UI Streamlit aplikace
# Spouštěj: streamlit run app.py

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from engine import *
from constants import *

st.set_page_config(page_title="FVE Kalkulačka pro SVJ", page_icon="☀️", layout="wide")

# ================================================================

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Přesná 15minutová simulace · OTE TDD profily · Ceny dle ceníků 2026")
st.divider()

# ── 1. ZÁKLADNÍ ÚDAJE ────────────────────────────────────────────
st.subheader("🏠 Základní údaje o domě")
c1,c2,c3=st.columns(3)
with c1:
    pocet_bytu=st.number_input("Počet bytů",2,200,12,1)
    sp_sp_mwh=st.number_input("Spotřeba společných prostor (MWh/rok)",0.1,50.0,3.5,0.1,format="%.1f",
                               help="Výtah, osvětlení chodeb, čerpadla")
    sp_by_vt_mwh=st.number_input("Spotřeba bytů VT (MWh/rok)",0.5,400.0,18.0,0.5,format="%.1f",
                                  help="Spotřeba v době vysokého tarifu (přes den)")
with c2:
    dist=st.selectbox("Distributor",list(CENY_VT.keys()),
                      help="ČEZ = většina ČR | EG.D = Morava/jih Čech | PRE = Praha")
    sazba=st.selectbox("Distribuční sazba",list(CENY_VT[dist].keys()),
                       format_func=lambda x:f"{x} — {POPIS_SAZEB[x]}",index=1)
with c3:
    st.selectbox("Hlavní jistič",["1×25A","3×16A","3×20A","3×25A","3×32A","3×40A","3×50A","3×63A"],index=3)
    profil=st.selectbox("Profil obyvatel",list(PROFILY.keys()),format_func=lambda x:PROFILY[x]["nazev"])
    st.caption(PROFILY[profil]["popis"])

# NT spotřeba — jen pro sazby s NT tarifem
ma_nt = sazba in SAZBY_NT
sp_by_nt_mwh = 0.0
if ma_nt:
    nt_h_count = len(NT_HODINY.get(sazba,set()))
    st.info(f"📌 Sazba **{sazba}** má NT tarif ({nt_h_count} hodin/den). "
            f"NT spotřeba (bojler, TČ) probíhá v noci — FVE ji nepokrývá přímo, "
            f"ale **baterie ji může pokrýt z denních přebytků**.")
    sp_by_nt_mwh = st.number_input(
        f"Spotřeba bytů NT (MWh/rok)",0.0,200.0,
        round(float(sp_by_vt_mwh)*PODIL_NT.get(sazba,0.3)/(1-PODIL_NT.get(sazba,0.3)),1),
        0.5,format="%.1f",
        help=f"Spotřeba v nízkém tarifu ({nt_h_count}h/den) — bojler, TČ, akumulační kamna")

sp_sp  = float(sp_sp_mwh)*1000
sp_by_vt = float(sp_by_vt_mwh)*1000
sp_by_nt = float(sp_by_nt_mwh)*1000
sp_cel = sp_sp + sp_by_vt + sp_by_nt
st.caption(f"Celková spotřeba domu: **{sp_cel/1000:.1f} MWh/rok** "
           f"(VT: {(sp_sp+sp_by_vt)/1000:.1f} MWh · NT: {sp_by_nt/1000:.1f} MWh)")

cena_vt  = float(CENY_VT[dist][sazba])/1000.0
cena_nt  = float(CENY_NT[dist].get(sazba, CENY_VT[dist][sazba]))/1000.0
stay     = float(STAY_PLAT[dist])
jistic   = float(JISTIC_3x25[dist][sazba])
naklad   = sp_cel*cena_vt + (stay+jistic)*12.0  # zjednodušení pro info
if ma_nt:
    naklad = sp_by_vt*cena_vt + sp_by_nt*cena_nt + sp_sp*cena_vt + (stay+jistic)*12.0

st.info(
    f"💡 **{dist}** · **{sazba}** · s DPH · POZE=0 Kč od 2026 | "
    f"VT: **{cena_vt:.2f} Kč/kWh**"
    + (f" · NT: **{cena_nt:.2f} Kč/kWh**" if ma_nt else "")
    + f" · Stálé platy: **{stay+jistic:.0f} Kč/měs** · Roční náklad: **{naklad:,.0f} Kč**"
)

with st.expander("✏️ Upravit ceny ručně"):
    u1,u2=st.columns(2)
    with u1: cena_vt=st.number_input("Cena VT (Kč/kWh)",1.0,15.0,round(cena_vt,2),0.01,format="%.2f")
    with u2:
        if ma_nt:
            cena_nt=st.number_input("Cena NT (Kč/kWh)",1.0,12.0,round(cena_nt,2),0.01,format="%.2f")

st.divider()

# ── 2. FVE A BATERIE ─────────────────────────────────────────────
st.subheader("⚡ Parametry FVE a baterie")
c1,c2=st.columns(2)
with c1:
    vykon=st.number_input("Výkon FVE (kWp)",1.0,200.0,20.0,0.5,format="%.1f")
    # Automatická cena dle výkonu (množstevní sleva)
    def _cena_kwp_auto(kw):
        if kw < 10:   return 38000
        elif kw < 20: return 33000
        elif kw < 40: return 28000
        elif kw < 80: return 24000
        else:         return 21000
    _cena_auto = _cena_kwp_auto(float(vykon))
    rucne = st.checkbox("Upravit cenu ručně", value=False)
    if rucne:
        cena_kwp = st.slider("Cena FVE (Kč/kWp)",20000,50000,_cena_auto,500)
    else:
        cena_kwp = _cena_auto
        st.caption(f"Cena dle výkonu: **{cena_kwp:,} Kč/kWp** (množstevní sleva)")
    cena_fve=int(float(vykon)*float(cena_kwp))
    st.caption(f"Odhadovaná cena FVE: **{cena_fve:,.0f} Kč**")
with c2:
    bat=st.number_input("Kapacita baterie (kWh)",0,200,0,5,
                         help="Nabíjí se z přetoků FVE přes den, vybíjí do NT spotřeby v noci" if ma_nt else "Nabíjí z přetoků FVE, vybíjí při nedostatku")
    if bat>0:
        cena_kwh_bat=st.slider("Cena baterie (Kč/kWh)",10000,20000,15000,500)
        cena_bat=int(float(bat)*float(cena_kwh_bat))
        st.caption(f"Odhadovaná cena baterie: **{cena_bat:,.0f} Kč**")
        if ma_nt and bat>0:
            st.success(f"🔋 Baterie přemostí denní přebytky FVE do noční NT spotřeby "
                       f"(úspora NT: {cena_nt:.2f} Kč/kWh místo ceny ze sítě).")
    else:
        cena_bat=0

st.divider()

# ── 3. MODEL SDÍLENÍ ─────────────────────────────────────────────
st.subheader("🔗 Model sdílení energie")
model=st.radio("Model",["spolecne","jom","edc"],horizontal=True,
               format_func=lambda x:{"spolecne":"🏢 Jen společné prostory",
                                     "jom":"⚡ Sjednocení odběrných míst",
                                     "edc":"🔗 EDC komunitní sdílení (iterační)"}[x])
# JOM: měřiče + paušál projekt/přepojení
_jom_merici = int(pocet_bytu)*10000
_jom_projekt = 75000  # paušál projekt elektro + přepojení
cena_mericu = (_jom_merici + _jom_projekt) if model=="jom" else 0
uspora_jist=jistic*(int(pocet_bytu)-1)*12.0 if model=="jom" else 0.0
if model=="spolecne":
    st.info(f"🏢 FVE pokrývá jen společnou spotřebu ({sp_sp_mwh:.1f} MWh/rok VT). Nejjednodušší realizace, žádné extra náklady.")
elif model=="jom":
    st.info(f"⚡ Jeden elektroměr pro celý dům. "
            f"Náklady navíc: měřiče **{_jom_merici:,} Kč** + projekt/přepojení **{_jom_projekt:,} Kč** = **{cena_mericu:,} Kč**. "
            f"Úspora distribuce: **{uspora_jist:,.0f} Kč/rok**.")
else:
    st.info("🔗 Každý byt si zachovává dodavatele. Chytré měřiče zdarma od distributora. Registrace na edc.cz.")

st.divider()

# ── 4. LOKALITA A STŘECHA ────────────────────────────────────────
st.subheader("🌍 Lokalita a střecha")
lc1,lc2=st.columns([2,1])

with lc1:
    lokace=st.text_input("Adresa nebo město",
                          placeholder="např. Náměstí Míru 5, Praha 2",
                          help="Zadejte přesnou adresu nebo název města pro přesnější výsledky")

    # Našeptávání adres
    if lokace and len(lokace) >= 4:
        with st.spinner("Hledám adresu..."):
            navrhys = _geocode_search(lokace)
        if navrhys:
            moznosti = []
            for n in navrhys[:5]:
                addr = n.get("address",{})
                parts = []
                if addr.get("road"): parts.append(addr["road"])
                if addr.get("house_number"): parts.append(addr["house_number"])
                if addr.get("city") or addr.get("town") or addr.get("village"):
                    parts.append(addr.get("city") or addr.get("town") or addr.get("village",""))
                if addr.get("postcode"): parts.append(addr["postcode"])
                label = ", ".join(parts) if parts else n.get("display_name","")[:60]
                moznosti.append(label)
            if moznosti:
                vyber = st.selectbox("Vyberte adresu ze seznamu:", ["— zadejte výše —"] + moznosti)
                if vyber != "— zadejte výše —":
                    lokace = vyber

with lc2:
    typ_str=st.radio("Typ střechy",["sikma","plocha"],
                     format_func=lambda x:"🏠 Šikmá" if x=="sikma" else "🏢 Plochá",
                     horizontal=True)

if typ_str=="sikma":
    sc1,sc2=st.columns(2)
    with sc1: sklon=st.slider("Sklon (°)",15,60,35)
    with sc2: azimut=st.select_slider("Orientace",[-90,-45,0,45,90],0,
                                       format_func=lambda x:{-90:"⬅️ Východ",-45:"↙️ JV",0:"⬆️ Jih",45:"↗️ JZ",90:"➡️ Západ"}[x])
    koef_str=1.0
else:
    pc1,pc2=st.columns(2)
    with pc1: sklon=st.slider("Sklon panelů (°)",5,20,10)
    with pc2: sys_pl=st.radio("Systém",["jih","jz_jv","vz"],format_func=lambda x:{"jih":"⬆️ Jih","jz_jv":"↗️ JZ+JV","vz":"↔️ V+Z"}[x])
    azimut=90 if sys_pl=="vz" else 0
    koef_str={"jih":1.0,"jz_jv":0.97,"vz":0.88}[sys_pl]

st.divider()

# ── 5. FINANCOVÁNÍ ───────────────────────────────────────────────
st.subheader("💰 Financování")
fc1,fc2=st.columns(2)
with fc1:
    scenar=st.radio("Scénář",["uver","vlastni","kombinace"],
                    format_func=lambda x:{"uver":"🏦 Bezúročný úvěr NZÚ (od září 2026)",
                                          "vlastni":"💵 Vlastní zdroje (fond oprav)",
                                          "kombinace":"🔀 Kombinace vlastní + úvěr"}[x])
with fc2:
    if scenar=="uver":
        splatnost=st.slider("Doba splácení (let)",5,25,15); vlastni_pct=0
        st.info("✅ Úroky hradí stát. SVJ splácí jen jistinu. Standardně 15 let — přesné podmínky NZÚ v září 2026.")
    elif scenar=="vlastni":
        splatnost=0; vlastni_pct=100; st.info("💡 SVJ hradí vše z fondu oprav.")
    else:
        vlastni_pct=st.slider("Vlastní zdroje (%)",10,90,30,10)
        splatnost=st.slider("Doba splácení (let)",5,25,15)

st.markdown("**Nízkopříjmové domácnosti**")
nb1,nb2=st.columns(2)
with nb1: pocet_nizko=st.number_input("Bytů s bonusem",0,int(pocet_bytu),0,1)
with nb2: bonus_byt=st.number_input("Bonus na byt (Kč)",0,150000,100000,5000,
                                     help="Přímý bonus NZÚ pro zranitelnou domácnost — snižuje její podíl splátky. Max avizováno 150 000 Kč/byt.")
bonus=int(pocet_nizko)*int(bonus_byt)  # celkový bonus pro SVJ

st.divider()

# ── 6. PARAMETRY SIMULACE ────────────────────────────────────────
st.subheader("⚙️ Parametry simulace")
sc1,sc2,sc3=st.columns(3)
with sc1: cena_pretoky=st.number_input("Výkupní cena přetoků (Kč/kWh)",0.30,2.50,0.95,0.05,format="%.2f")
with sc2: rust_cen=st.slider("Růst cen elektřiny (%/rok)",0.0,8.0,3.0,0.5)
with sc3: deg_pan=st.slider("Degradace panelů (%/rok)",0.2,1.0,0.5,0.1)

with st.expander("⚙️ Pokročilé parametry"):
    ap1,ap2=st.columns(2)
    with ap1:
        deg_bat_val=st.slider("Degradace baterie (%/rok)",0.5,5.0,2.0,0.5,
                              help="Baterie ztrácí kapacitu ~2% ročně (výchozí)")
    with ap2:
        # EDC ztráta sdílení — výchozí z počtu bytů
        _edc_default=min(5.0,round(10.0/pocet_bytu**0.5,1))
        edc_ztrata_val=st.slider("Ztráta sdílení EDC (%)",0.0,10.0,_edc_default,0.5,
                                  help=f"Ztráta alokace pro {pocet_bytu} bytů. "
                                       f"Výchozí {_edc_default}% (menší dům = vyšší ztráta). "
                                       f"S chytrým řízením může být nižší.")

st.divider()

# Výchozí hodnoty pokročilých parametrů (pokud expander nebyl otevřen)
if 'deg_bat_val' not in dir(): deg_bat_val=2.0
if 'edc_ztrata_val' not in dir(): edc_ztrata_val=min(5.0,round(10.0/pocet_bytu**0.5,1))

# VÝPOČET INVESTICE
cena_invest = cena_fve + cena_bat + cena_mericu

# Správná logika NZÚ:
# SVJ si vezme bezúročný úvěr na celou investici (mínus vlastní zdroje)
# Bonus jde přímo konkrétnímu bytu — NESNIŽUJE celkový úvěr SVJ
vlastni_cast = float(cena_invest) * float(vlastni_pct) / 100.0
uver_cast = max(0.0, float(cena_invest) - vlastni_cast)  # bonus neodečítáme z úvěru
rocni_spl = uver_cast / float(splatnost) if (scenar!="vlastni" and splatnost>0) else 0.0

# Splátka na byt a efekt bonusu
podil_bytu_uver = uver_cast / float(pocet_bytu)  # podíl jednoho bytu na úvěru
splatka_byt_std = podil_bytu_uver / float(splatnost) / 12.0 if (scenar!="vlastni" and splatnost>0) else 0.0
# Bonus snižuje splátku konkrétního bytu (max do výše jeho podílu)
bonus_efekt_byt = min(float(bonus_byt), podil_bytu_uver)
zbytek_super = max(0.0, podil_bytu_uver - bonus_efekt_byt)
splatka_byt_super = zbytek_super / float(splatnost) / 12.0 if (scenar!="vlastni" and splatnost>0) else 0.0

bc1,bc2=st.columns([1,3])
with bc1: spustit=st.button("🔄 Spočítat simulaci",type="primary",use_container_width=True)
with bc2: st.caption("Stáhne hodinová solární data z PVGIS a provede přesný 15minutový výpočet. Trvá 5–20 s.")

if spustit:
    with st.spinner(f"Hledám {lokace}..."):
        lat,lon,mesto,geo_err=_geocode(lokace)
    if geo_err: st.error(f"Lokalita nenalezena: {geo_err}"); st.stop()

    kwp_eff=float(vykon)*float(koef_str)
    with st.spinner(f"Stahuji solární data pro {mesto} z PVGIS..."):
        vyroba_hod,pvgis_err=_pvgis(lat,lon,kwp_eff,sklon,azimut)
    if pvgis_err:
        st.warning("⚠️ PVGIS nedostupné — používám kalibrovaný záložní model.")
        vyroba_hod=_gen_vyroba_fallback(kwp_eff,sklon,azimut); pvgis_ok=False
    else: pvgis_ok=True

    with st.spinner("Simuluji v 15minutových intervalech..."):
        vyroba_15=_interpoluj(vyroba_hod)
        uprava = _UPRAVY.get(str(profil), np.ones(24,dtype=float))

        # Společné prostory — jen VT (žádný NT)
        sp_sp15 = _gen_profil_vt(sp_sp, _TDD_SP)

        # Byty VT + NT
        sp_by_vt15 = _gen_profil_vt(sp_by_vt, _TDD4, uprava)
        sp_by_nt15 = _gen_profil_nt(sp_by_nt, sazba)

        # Spotřeba pro vybraný model (hlavní simulace)
        if model == "spolecne":
            sp_vt15 = sp_sp15
            sp_nt15 = np.zeros(_CD, dtype=float)
        else:
            sp_vt15 = sp_sp15 + sp_by_vt15
            sp_nt15 = sp_by_nt15

        _edc_ztrata = float(edc_ztrata_val) if model=="edc" else 0.0
        sim=_simuluj(vyroba_15, sp_vt15, sp_nt15, float(bat), model, _edc_ztrata)
        # Cashflow SVJ: bonus nesnižuje úvěr — jde přímo konkrétnímu bytu
        cf=_cashflow(
            vl_vt=sim["vlastni_vt_kwh"], vl_nt=sim["vlastni_nt_kwh"],
            pr=sim["pretoky_kwh"],
            cvt=float(cena_vt), cnt=float(cena_nt), cpr=float(cena_pretoky),
            vlast=vlastni_cast, uver=uver_cast, spl=rocni_spl, splat=int(splatnost),
            rust=float(rust_cen), deg=float(deg_pan), leta=25,
            jist=float(uspora_jist), bonus=0.0, deg_bat=float(deg_bat_val))

        # Porovnání modelů — FIXNI vstupy, kazdy model ma sve vlastni naklady
        sp_vt_celkem = sp_sp15 + sp_by_vt15  # celý dům VT
        sp_nt_celkem = sp_by_nt15              # celý dům NT
        srovnani={}
        for mk in ["spolecne","jom","edc"]:
            # Každý model má své náklady na investici
            _mericu_mk = int(pocet_bytu)*10000 if mk=="jom" else 0
            _jist_mk   = jistic*(int(pocet_bytu)-1)*12.0 if mk=="jom" else 0.0
            _invest_mk = cena_fve + cena_bat + _mericu_mk
            _vlast_mk  = float(_invest_mk)*float(vlastni_pct)/100.0
            _uver_mk   = max(0.0, float(_invest_mk) - _vlast_mk - float(bonus))
            _spl_mk    = _uver_mk/float(splatnost) if (scenar!="vlastni" and splatnost>0) else 0.0

            if mk=="spolecne":
                svt=sp_sp15; snt=np.zeros(_CD,dtype=float)
            else:
                svt=sp_vt_celkem; snt=sp_nt_celkem
            _ez_mk = float(edc_ztrata_val) if mk=="edc" else 0.0
            sm=_simuluj(vyroba_15,svt,snt,float(bat),mk,_ez_mk)
            cfm=_cashflow(vl_vt=sm["vlastni_vt_kwh"],vl_nt=sm["vlastni_nt_kwh"],
                          pr=sm["pretoky_kwh"],cvt=float(cena_vt),cnt=float(cena_nt),
                          cpr=float(cena_pretoky),vlast=_vlast_mk,uver=_uver_mk,
                          spl=_spl_mk,splat=int(splatnost),rust=float(rust_cen),
                          deg=float(deg_pan),leta=25,
                          jist=_jist_mk,bonus=float(bonus),deg_bat=float(deg_bat_val))
            nav_m=next((r["rok"] for r in cfm if r["kumulativni"]>=0),None)
            stat_m=float(_invest_mk)/cfm[0]["uspora_celkem"] if cfm[0]["uspora_celkem"]>0 else 999
            splatka_mk=_spl_mk/float(pocet_bytu)/12.0
            cisty_byt_mk=cfm[0]["uspora_celkem"]/float(pocet_bytu)/12.0-splatka_mk
            srovnani[mk]={"sim":sm,"cf":cfm,"nav":nav_m,"stat":stat_m,"rok1":cfm[0],
                          "invest":_invest_mk,"splatka_byt":splatka_mk,
                          "cisty_byt":cisty_byt_mk}

    st.session_state["res"]={
        "sim":sim,"cf":cf,"vyroba_15":vyroba_15,
        "sp_vt15":sp_vt15,"sp_nt15":sp_nt15,
        "pvgis_ok":pvgis_ok,"mesto":mesto,"lat":lat,"lon":lon,
        "srovnani":srovnani}
    st.success(f"✅ Hotovo — {mesto} ({lat:.2f}°N, {lon:.2f}°E) {'· PVGIS data' if pvgis_ok else '· záložní model'}")

if "res" not in st.session_state:
    st.info("👆 Vyplňte parametry a klikněte na **Spočítat simulaci**.")
    st.stop()

# ================================================================
# VÝSLEDKY
# ================================================================

d=st.session_state["res"]
sim=d["sim"]; cf=d["cf"]; srovnani=d["srovnani"]
rok1=cf[0]
nav=next((r["rok"] for r in cf if r["kumulativni"]>=0),None)

stat_nav=float(cena_invest)/rok1["uspora_celkem"] if rok1["uspora_celkem"]>0 else 999
# Splátky — správná logika NZÚ
splatka_vsichni = splatka_byt_std  # předpočítáno výše
uspora_byt_mesic = rok1["uspora_celkem"] / float(pocet_bytu) / 12.0
# Byt se superdávkou má nižší splátku díky bonusu
cista_splatka_super = splatka_byt_super  # předpočítáno výše
uspora_diky_bonusu = splatka_byt_std - splatka_byt_super  # kolik ušetří díky bonusu

st.divider()
st.subheader("📊 Výsledky simulace")

# Killer metrika nahoře — kolik % výroby se využije
util_pct = sim["mira_vs"]*100
if util_pct >= 70:
    util_delta = "výborné využití ✅"
elif util_pct >= 50:
    util_delta = "dobré využití"
else:
    util_delta = "zvažte baterii"

# Soběstačnost — vždy vůči celkové spotřebě domu (i pro model "spolecne")
mira_sob_real = sim["vlastni_kwh"] / float(sp_cel) if sp_cel > 0 else 0.0

r1,r2,r3,r4,r5,r6=st.columns(6)
with r1: st.metric("Roční výroba FVE",f"{sim['vyroba_kwh']/1000:.1f} MWh")
with r2: st.metric("Využití výroby v domě",f"{util_pct:.1f} %",
                   delta=util_delta,
                   help="Klíčová metrika: kolik % výroby FVE se spotřebuje přímo v domě nebo přes baterii. Zbytek jde za nízkou výkupní cenu.")
with r3: st.metric("Soběstačnost",f"{mira_sob_real*100:.1f} %",help="% celkové spotřeby domu (vč. bytů) pokryté FVE")
with r4: st.metric("Roční úspora (rok 1)",f"{rok1['uspora_celkem']:,.0f} Kč")
with r5: st.metric("Orientační návratnost",f"{stat_nav:.1f} let",
                   help="Investice ÷ roční úspora — pouze orientačně, bez vlivu růstu cen")
with r6: st.metric("Cashflow návratnost",f"{nav} let" if nav else ">25 let",
                   help="Realistická návratnost: kdy kumulativní cashflow přejde do kladných čísel")

# EDC efektivita
# Míra časového překryvu — zobrazit vždy (pro všechny modely)
prekryv = sim.get("edc_efektivita", 1.0) * 100
if prekryv >= 70:
    prekryv_hod = "výborné — výroba a spotřeba jsou dobře sladěny"
elif prekryv >= 50:
    prekryv_hod = "dobré — baterie může pomoci s nesouladem"
else:
    prekryv_hod = "nízké — velká část výroby jde mimo dobu spotřeby, baterie velmi doporučena"
st.info(f"⏱️ **Míra časového sladění výroby a spotřeby: {prekryv:.1f} %** — "
        f"{prekryv_hod}. "
        f"Závisí na profilu: senioři = vyšší, pracující = nižší.")

# VT/NT rozpad úspory
if ma_nt and sim["vlastni_nt_kwh"]>0:
    st.info(
        f"🔋 **Rozpad úspory:** "
        f"VT přímá spotřeba: **{rok1['uspora_vt']:,.0f} Kč** · "
        f"NT z baterie: **{rok1['uspora_nt']:,.0f} Kč** · "
        f"Přetoky: **{rok1['uspora_pretoky']:,.0f} Kč**"
    )

st.divider()

# ── POROVNÁNÍ MODELŮ ──────────────────────────────────────────────
st.subheader("📊 Porovnání modelů sdílení")
st.caption("Stejná FVE a investice pro všechny modely — mění se jen co FVE pokrývá.")
nazvy={"spolecne":"🏢 Jen společné","jom":"⚡ JOM","edc":"🔗 EDC"}
# Najdi nejlepší model dle cashflow návratnosti
best_mk = min(["spolecne","jom","edc"],
              key=lambda x: srovnani[x]["nav"] if srovnani[x]["nav"] else 999)
sc1,sc2,sc3=st.columns(3)
for col,mk in zip([sc1,sc2,sc3],["spolecne","jom","edc"]):
    sv=srovnani[mk]
    cisty_byt=sv["cisty_byt"]        # počítáno s vlastní investicí modelu
    splatka_byt_mk=sv["splatka_byt"] # splátka pro tento konkrétní model
    je_vybran = mk == model
    je_nejlepsi = mk == best_mk
    with col:
        hlavicka = nazvy[mk]
        if je_nejlepsi: hlavicka += " ⭐"
        if je_vybran:   hlavicka += " ✓"
        st.markdown(f"**{hlavicka}**")
        if mk=="jom":
            st.caption(f"Investice: {sv['invest']:,.0f} Kč (vč. měřičů)")
        else:
            st.caption(f"Investice: {sv['invest']:,.0f} Kč")
        st.metric("Roční úspora",f"{sv['rok1']['uspora_celkem']:,.0f} Kč")
        st.metric("Vlastní spotřeba",f"{sv['sim']['mira_vs']*100:.1f} %")
        # Pro "spolecne" počítáme soběstačnost vůči celé spotřebě domu
        _sob = sv["sim"]["vlastni_kwh"] / float(sp_cel) if sp_cel>0 else 0.0
        st.metric("Soběstačnost",f"{_sob*100:.1f} %",
                  help="% celkové spotřeby domu pokryté FVE" if mk!="spolecne" else "% celkové spotřeby domu — FVE kryje jen společné prostory")
        st.metric("Statická návratnost",f"{sv['stat']:.1f} let")
        st.metric("Cashflow návratnost",f"{sv['nav']} let" if sv['nav'] else ">25 let")
        st.metric("Splátka/byt",f"{splatka_byt_mk:.0f} Kč/měs")
        if cisty_byt>=0:
            st.metric("Čistý přínos/byt",f"+{cisty_byt:.0f} Kč/měs",delta="kladný")
        else:
            st.metric("Čistý náklad/byt",f"{cisty_byt:.0f} Kč/měs",delta_color="inverse")
        if je_vybran:
            st.info("✓ Váš výběr")

st.divider()

# ── PŘEHLED NA BYT ────────────────────────────────────────────────
st.subheader("🏠 Přehled na jednotlivý byt (měsíčně)")
ba1,ba2=st.columns(2)
with ba1:
    st.markdown("**Standardní byt**")
    cisty_std=uspora_byt_mesic-splatka_vsichni
    st.metric("Úspora z FVE",f"{uspora_byt_mesic:.0f} Kč/měs")
    st.metric("Splátka úvěru",f"{splatka_vsichni:.0f} Kč/měs")
    if cisty_std>=0:
        st.metric("Čistý měsíční přínos",f"+{cisty_std:.0f} Kč/měs",delta="kladný od roku 1")
    else:
        st.metric("Čistý měsíční náklad",f"{cisty_std:.0f} Kč/měs")
    if bonus>0 and uspora_diky_bonusu>0:
        st.info(f"💡 Díky bonusu ušetří každý byt **{uspora_diky_bonusu:.0f} Kč/měs** na splátce.")
with ba2:
    if pocet_nizko>0:
        st.markdown(f"**Byt se superdávkou** ({pocet_nizko}× v domě)")
        cisty_super=uspora_byt_mesic-cista_splatka_super
        st.metric("Úspora z FVE",f"{uspora_byt_mesic:.0f} Kč/měs")
        st.metric("Podíl na úvěru (celkem)",f"{podil_bytu_uver:,.0f} Kč",
                  help="Podíl tohoto bytu na celkovém úvěru SVJ")
        st.metric("Přímý bonus NZÚ",f"{bonus_efekt_byt:,.0f} Kč",
                  delta=f"pokryje {bonus_efekt_byt/podil_bytu_uver*100:.0f}% podílu" if podil_bytu_uver>0 else "",
                  help="Přímá platba státu na konkrétní byt — snižuje jeho zbývající dluh na úvěru")
        st.metric("Zbývající splátka",f"{cista_splatka_super:.0f} Kč/měs",
                  help=f"Splátka po odečtení bonusu. Std byt: {splatka_vsichni:.0f} Kč/měs")
        if cisty_super>=0:
            st.metric("Čistý měsíční přínos",f"+{cisty_super:.0f} Kč/měs",
                      delta=f"+{cisty_super-cisty_std:.0f} Kč vs std. byt")
        else:
            st.metric("Čistý měsíční náklad",f"{cisty_super:.0f} Kč/měs")
        st.divider()
        st.markdown("**🤝 Přínos bonusu NZÚ**")
        st.write(f"• Přímý bonus od státu: **{bonus_efekt_byt:,.0f} Kč** (na byt se superdávkou)")
        st.write(f"• Bonus pokryje: **{bonus_efekt_byt/podil_bytu_uver*100:.0f}%** podílu na úvěru")
        st.write(f"• Zbývající splátka super bytu: **{cista_splatka_super:.0f} Kč/měs** (vs {splatka_vsichni:.0f} Kč std)")
        st.write(f"• Ostatní byty: splátka **{splatka_vsichni:.0f} Kč/měs** — beze změny")
    else:
        st.markdown("**Žádné byty se superdávkou**")
        st.caption("Zadejte počet bytů s bonusem výše.")

st.divider()

# ── MILNÍKY ───────────────────────────────────────────────────────
st.markdown("**📍 Klíčové milníky**")
m1,m2,m3=st.columns(3)
with m1:
    lines=["**Rok 1**",
           f"Vlastní spotřeba VT: **{sim['vlastni_vt_kwh']:,.0f} kWh**",
           f"Vlastní spotřeba NT (bat): **{sim['vlastni_nt_kwh']:,.0f} kWh**",
           f"Přetoky do sítě: **{sim['pretoky_kwh']:,.0f} kWh**",
           f"**Celková úspora: {rok1['uspora_celkem']:,.0f} Kč/rok**",
           f"Na byt: **{uspora_byt_mesic*12:,.0f} Kč/rok** · **{uspora_byt_mesic:.0f} Kč/měs**",
           f"Splátka na byt: **{splatka_vsichni:.0f} Kč/měs**"]
    st.info("  \n".join(lines))
with m2:
    if scenar!="vlastni" and splatnost>0 and splatnost<=25:
        rs=cf[min(splatnost-1,len(cf)-1)]
        lines=[f"**Rok {splatnost} — úvěr splacen ✅**",
               f"Úspora v tom roce: **{rs['uspora_celkem']:,.0f} Kč**",
               f"(vč. růstu cen +{rust_cen}%/rok)",
               f"Poté plný přínos bez splátky:",
               f"**{rs['uspora_celkem']:,.0f} Kč/rok**"]
        st.info("  \n".join(lines))
    else:
        st.info("  \n".join(["**Vlastní financování**","Žádné splátky",
                              f"Plný přínos od roku 1:",f"**{rok1['uspora_celkem']:,.0f} Kč/rok**"]))
with m3:
    kum25=cf[-1]["kumulativni"]
    if nav:
        lines=[f"**Rok {nav} — investice se vrátí ✅**",
               f"Statická: **{stat_nav:.1f} let** · Cashflow: **{nav} let**",
               f"Za 25 let celková úspora:",
               f"**{kum25:,.0f} Kč** ({kum25/float(pocet_bytu):,.0f} Kč/byt)",
               f"→ dalších {max(0,25-nav)} let čistý zisk!"]
        st.success("  \n".join(lines))
    else:
        st.warning("  \n".join([f"**Za 25 let investice se nevrátí**",
                                f"Cashflow: **{kum25:,.0f} Kč**",
                                "Zvyšte výkon FVE nebo zvolte jiný model."]))

st.divider()

# ── GRAFY ─────────────────────────────────────────────────────────
tab1,tab2,tab3=st.tabs(["📅 Denní graf","📈 Roční přehled","💰 Cashflow 25 let"])

with tab1:
    st.markdown("**Průměrný den — výroba vs spotřeba**")
    gc1,gc2=st.columns(2)
    with gc1: sezona_g=st.radio("Sezóna",["zima","prechodne","leto"],horizontal=True,
                                 format_func=lambda x:{"zima":"❄️ Zima","prechodne":"🌤️ Jaro/Podzim","leto":"☀️ Léto"}[x])
    with gc2: pocasi_g=st.radio("Počasí",["jasno","polojasno","zatazeno"],horizontal=True,
                                 format_func=lambda x:{"jasno":"☀️ Jasno","polojasno":"⛅ Polojasno","zatazeno":"☁️ Zataženo"}[x])

    kwp_eff=float(vykon)*float(koef_str)
    vyr_den=_gen_vyroba_den(kwp_eff,sezona_g,pocasi_g)
    sp_total_vt=(sp_sp+sp_by_vt) if model!="spolecne" else sp_sp
    sp_total_nt=sp_by_nt if model!="spolecne" else 0.0
    sp_den_vt=_gen_spotreba_den(sp_total_vt,sezona_g,profil,False)
    # NT profil pro den
    nt_h=NT_HODINY.get(sazba,set())
    sp_den_nt=np.zeros(96,dtype=float)
    if sp_total_nt>0 and nt_h:
        nt_den=sp_total_nt/365.0
        for i in range(96):
            if (i//4) in nt_h: sp_den_nt[i]=nt_den/len(nt_h)/4.0 if len(nt_h)>0 else 0

    hodiny=[i/4.0 for i in range(96)]
    sp_den_total=sp_den_vt+sp_den_nt

    fig=go.Figure()
    fig.add_trace(go.Scatter(x=hodiny,y=vyr_den*4,name="⚡ Výroba FVE (kW)",
                              fill="tozeroy",fillcolor="rgba(255,193,7,0.2)",
                              line=dict(color="#FFC107",width=2)))
    fig.add_trace(go.Scatter(x=hodiny,y=sp_den_vt*4,name="🏠 Spotřeba VT (kW)",
                              line=dict(color="#2196F3",width=2)))
    if ma_nt and sp_total_nt>0:
        fig.add_trace(go.Scatter(x=hodiny,y=sp_den_nt*4,name="🌙 Spotřeba NT (kW)",
                                  fill="tozeroy",fillcolor="rgba(156,39,176,0.15)",
                                  line=dict(color="#9C27B0",width=1,dash="dot")))
    # Baterie SOC — stejná logika jako hlavní simulace
    # VT spotřeba má prioritu před NT (dražší tarif)
    bat_soc=np.zeros(96)
    if bat>0:
        _bmin=float(bat)*0.10
        _bmax=float(bat)*0.90
        _eta=0.92
        # Začínáme s vybitou baterií — realisticky po noční spotřebě
        bkwh=float(bat)*0.20
        for i in range(96):
            vi   = float(vyr_den[i])
            svti = float(sp_den_vt[i])
            snti = float(sp_den_nt[i])

            # 1. FVE → VT spotřeba přímo
            prime = min(vi, svti)
            zbv   = vi - prime
            zbsvt = svti - prime

            # 2. Přebytek výroby → nabít baterii
            if zbv > 0:
                nab = min(zbv*_eta, _bmax-bkwh)
                bkwh += nab
                zbv  -= nab/_eta

            # 3. Zbylá VT spotřeba → vybít baterii (VT = dražší, priorita!)
            if zbsvt > 0:
                dos = (bkwh-_bmin)*_eta
                vyb = min(zbsvt, dos)
                bkwh -= vyb/_eta
                zbsvt -= vyb

            # 4. NT spotřeba → vybít zbylou baterii
            if snti > 0:
                dos = (bkwh-_bmin)*_eta
                vyb = min(snti, dos)
                bkwh -= vyb/_eta

            bat_soc[i] = bkwh/float(bat)*100

        fig.add_trace(go.Scatter(x=hodiny,y=bat_soc,name="🔋 Baterie SOC (%)",
                                  yaxis="y2",line=dict(color="#4CAF50",width=2,dash="dash")))

    lay=dict(_LAY); lay.update(dict(
        xaxis=dict(title="Hodina",tickmode="linear",tick0=0,dtick=2,
                   range=[0,24],fixedrange=True),
        yaxis=dict(title="kW",fixedrange=True),height=350))
    if bat>0: lay["yaxis2"]=dict(title="SOC %",overlaying="y",side="right",range=[0,100],fixedrange=True)
    fig.update_layout(**lay)
    st.plotly_chart(fig,use_container_width=True,config=_CFG)

with tab2:
    fig2=go.Figure()
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in sim["mesice_vyroba"]],
                           name="Výroba FVE (MWh)",marker_color="#FFC107",opacity=0.8))
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in sim["mesice_vlastni"]],
                           name="Vlastní spotřeba (MWh)",marker_color="#4CAF50",opacity=0.9))
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in sim["mesice_pretoky"]],
                           name="Přetoky (MWh)",marker_color="#9E9E9E",opacity=0.7))
    lay2=dict(_LAY); lay2.update(dict(barmode="overlay",
        yaxis=dict(title="MWh",fixedrange=True),height=350))
    fig2.update_layout(**lay2)
    st.plotly_chart(fig2,use_container_width=True,config=_CFG)

with tab3:
    roky=[r["rok"] for r in cf]
    kum=[r["kumulativni"] for r in cf]
    fig3=go.Figure()
    fig3.add_trace(go.Scatter(x=roky,y=kum,name="Kumulativní cashflow",
                               fill="tozeroy",fillcolor="rgba(33,150,243,0.15)",
                               line=dict(color="#2196F3",width=3)))
    fig3.add_hline(y=0,line_dash="dash",line_color="#666",line_width=1)
    if nav:
        fig3.add_vline(x=nav,line_dash="dot",line_color="#4CAF50",line_width=2,
                       annotation_text=f"Rok {nav}",annotation_position="top right")
    if scenar!="vlastni":
        fig3.add_trace(go.Bar(x=roky,y=[-r["splatka"] for r in cf],
                               name="Splátka úvěru",marker_color="rgba(244,67,54,0.4)"))
    lay3=dict(_LAY); lay3.update(dict(
        xaxis=dict(title="Rok",fixedrange=True,dtick=2),
        yaxis=dict(title="Kč",fixedrange=True,tickformat=","),
        height=380,barmode="overlay"))
    fig3.update_layout(**lay3)
    st.plotly_chart(fig3,use_container_width=True,config=_CFG)

st.divider()

# ── VERDIKT ───────────────────────────────────────────────────────
st.subheader("🎯 Verdikt a scénáře")

# Verdikt
kum25=cf[-1]["kumulativni"]
if nav and nav <= 12:
    verdikt_text = "✅ PROJEKT SE JEDNOZNAČNĚ VYPLATÍ"
    verdikt_color = "success"
    verdikt_popis = f"Cashflow návratnost {nav} let je výborná. Investice je bezpečná i při konzervativním scénáři (+1%/rok)."
elif nav and nav <= 20:
    verdikt_text = "⚠️ PROJEKT JE HRANIČNÍ"
    verdikt_color = "warning"
    verdikt_popis = f"Cashflow návratnost {nav} let závisí na vývoji cen elektřiny. Při realistickém scénáři (+{rust_cen:.0f}%/rok) se vyplatí. Bezúročný úvěr NZÚ výrazně snižuje riziko."
elif nav:
    verdikt_text = "⚠️ PROJEKT JE RIZIKOVÝ"
    verdikt_color = "warning"
    verdikt_popis = f"Cashflow návratnost {nav} let je dlouhá. Zvažte vyšší výkon FVE, baterii nebo model JOM/EDC pro lepší využití výroby."
else:
    verdikt_text = "❌ PROJEKT SE NEVRÁTÍ ZA 25 LET"
    verdikt_color = "error"
    verdikt_popis = "Při současných parametrech se investice nevrátí za životnost panelů. Zásadně přehodnoťte výkon FVE a model sdílení."

if verdikt_color == "success":
    st.success(f"**{verdikt_text}**  \n{verdikt_popis}")
elif verdikt_color == "warning":
    st.warning(f"**{verdikt_text}**  \n{verdikt_popis}")
else:
    st.error(f"**{verdikt_text}**  \n{verdikt_popis}")

# Bez FVE vs s FVE
st.markdown("**💡 Bez FVE vs s FVE — celkové náklady za 25 let**")
bv1,bv2,bv3=st.columns(3)

for col,rust_sc,nazev in zip(
    [bv1,bv2,bv3],
    [1.0, float(rust_cen), 6.0],
    ["😐 Pesimistický (+1%/rok)","📊 Realistický (+{}%/rok)".format(rust_cen),"🔥 Krizový (+6%/rok)"]
):
    # Náklady bez FVE
    naklad_bez=sum(sp_cel*cena_vt*(1+rust_sc/100)**(r-1) for r in range(1,26))
    # Úspory s FVE (degradace + růst cen)
    uspora_sc=sum(
        rok1["uspora_celkem"]*(1+rust_sc/100)**(r-1)*(1-float(deg_pan)/100)**(r-1)
        for r in range(1,26))
    naklad_s=naklad_bez-uspora_sc
    # Cashflow návratnost pro tento scénář
    kum_sc=-(vlastni_cast+uver_cast-float(bonus))
    nav_sc=None
    for r in range(1,26):
        u_sc=rok1["uspora_celkem"]*(1+rust_sc/100)**(r-1)*(1-float(deg_pan)/100)**(r-1)
        s_sc=rocni_spl if r<=int(splatnost) else 0.0
        kum_sc+=u_sc-s_sc
        if kum_sc>=0 and nav_sc is None: nav_sc=r
    with col:
        st.markdown(f"**{nazev}**")
        st.metric("Bez FVE (25 let)",f"{naklad_bez/1e6:.2f} mil. Kč")
        st.metric("S FVE (25 let)",f"{naklad_s/1e6:.2f} mil. Kč",
                  delta=f"−{uspora_sc/1e6:.2f} mil. Kč úspora",delta_color="normal")
        st.metric("Cashflow návratnost",f"{nav_sc} let" if nav_sc else ">25 let")

st.caption(f"💡 Bez FVE zaplatíte za 25 let více na elektřině — i při pesimistickém scénáři. "
           f"Bezúročný úvěr znamená že úspory FVE začínají okamžitě pokrývat splátky.")

st.divider()

# ── CASHFLOW TABULKA ──────────────────────────────────────────────
st.subheader("📋 Cashflow rok po roku (25 let)")
df=pd.DataFrame([{"Rok":r["rok"],"Výroba MWh":r["vyroba_mwh"],"Vlastní MWh":r["vlastni_mwh"],
                   "Přetoky MWh":r["pretoky_mwh"],"Úspora VT Kč":r["uspora_vt"],
                   "Úspora NT Kč":r["uspora_nt"],"Příjem přetoky Kč":r["uspora_pretoky"],
                   "Úspora celkem Kč":r["uspora_celkem"],"Splátka Kč":r["splatka"],
                   "Čistý přínos Kč":r["cisty_prinos"],"Kumulativní Kč":r["kumulativni"],
                   "Cena VT Kč/kWh":r["cena_vt"]} for r in cf])

def hl(row):
    if nav and row["Rok"]==nav: return ["background-color:#d4edda"]*len(row)
    if row["Kumulativní Kč"]<0: return ["background-color:#fff3cd"]*len(row)
    return [""]*len(row)

# Skryjeme NT sloupec pokud není NT sazba
cols_show=["Rok","Výroba MWh","Vlastní MWh","Přetoky MWh","Úspora VT Kč"]
if ma_nt: cols_show.append("Úspora NT Kč")
cols_show+=["Příjem přetoky Kč","Úspora celkem Kč","Splátka Kč","Čistý přínos Kč","Kumulativní Kč","Cena VT Kč/kWh"]

fmt={"Výroba MWh":"{:.2f}","Vlastní MWh":"{:.2f}","Přetoky MWh":"{:.2f}",
     "Úspora VT Kč":"{:,.0f}","Úspora NT Kč":"{:,.0f}","Příjem přetoky Kč":"{:,.0f}",
     "Úspora celkem Kč":"{:,.0f}","Splátka Kč":"{:,.0f}",
     "Čistý přínos Kč":"{:,.0f}","Kumulativní Kč":"{:,.0f}","Cena VT Kč/kWh":"{:.3f}"}

st.dataframe(df[cols_show].style.apply(hl,axis=1).format({k:v for k,v in fmt.items() if k in cols_show}),
             use_container_width=True,hide_index=True)

st.divider()

# ── DETAIL INVESTICE ──────────────────────────────────────────────
st.subheader("💰 Detail investice a výnosů")
di1,di2=st.columns(2)
with di1:
    st.markdown("**Investice**")
    st.write(f"• FVE {vykon} kWp × {cena_kwp:,} Kč/kWp: **{cena_fve:,.0f} Kč**")
    if cena_bat>0: st.write(f"• Baterie {bat} kWh × {cena_kwh_bat:,} Kč/kWh: **{cena_bat:,.0f} Kč**")
    if cena_mericu>0: st.write(f"• Podružné měřiče: **{cena_mericu:,.0f} Kč**")
    st.write(f"• **Celková investice: {cena_invest:,.0f} Kč**")
    if bonus>0: st.write(f"• Bonus NZÚ: **− {bonus:,.0f} Kč**")
    if scenar!="vlastni":
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_cast:,.0f} Kč**")
        st.write(f"• Roční splátka: **{rocni_spl:,.0f} Kč** ({splatnost} let)")
with di2:
    st.markdown("**Výnosy rok 1**")
    _nm={"spolecne":"Jen společné prostory","jom":"Sjednocení odběrných míst","edc":"EDC komunitní sdílení"}
    st.write(f"• Model: **{_nm[model]}** · Profil: **{PROFILY[profil]['nazev']}**")
    st.write(f"• Vlastní spotřeba VT (FVE): **{sim['vlastni_vt_kwh']:,.0f} kWh** → **{rok1['uspora_vt']:,.0f} Kč**")
    if ma_nt: st.write(f"• Vlastní spotřeba NT (baterie): **{sim['vlastni_nt_kwh']:,.0f} kWh** → **{rok1['uspora_nt']:,.0f} Kč**")
    st.write(f"• Přetoky: **{sim['pretoky_kwh']:,.0f} kWh** @ {cena_pretoky:.2f} Kč → **{rok1['uspora_pretoky']:,.0f} Kč**")
    if uspora_jist>0: st.write(f"• Úspora distribuce (JOM): **{uspora_jist:,.0f} Kč**")
    st.write(f"• **Celkem: {rok1['uspora_celkem']:,.0f} Kč/rok**")
    st.write(f"• Na byt: **{uspora_byt_mesic*12:,.0f} Kč/rok** · **{uspora_byt_mesic:.0f} Kč/měs**")

st.divider()

# ── JEDNOVĚTÝ ZÁVĚR ───────────────────────────────────────────────
kum25_final = cf[-1]["kumulativni"]
uspora_25_total = sum(r["uspora_celkem"] for r in cf)
rust_real = float(rust_cen)

# Závěr dle scénáře
if nav and nav <= 12:
    zaver = (f"✅ **Projekt se jednoznačně vyplatí** — i při konzervativním scénáři "
             f"se investice vrátí za {nav} let a za 25 let ušetříte "
             f"**{kum25_final/1000:.0f} tis. Kč** ({kum25_final/float(pocet_bytu)/1000:.0f} tis. Kč/byt).")
elif nav and nav <= 18:
    uspora_pess = sum(
        rok1["uspora_celkem"]*(1+1.0/100)**(r-1)*(1-float(deg_pan)/100)**(r-1)
        for r in range(1,26))
    zaver = (f"⚠️ **Projekt se vyplatí při realistickém vývoji cen** (+{rust_real}%/rok) — "
             f"návratnost {nav} let. Při pesimistickém scénáři (+1%/rok) "
             f"{'se také vrátí' if uspora_pess > float(cena_invest) else 'se nemusí vrátit'}. "
             f"Bezúročný úvěr NZÚ výrazně snižuje riziko.")
elif nav:
    zaver = (f"⚠️ **Projekt je ekonomicky hraniční** — návratnost {nav} let je dlouhá. "
             f"Doporučujeme zvýšit výkon FVE, přidat baterii nebo zvolit model JOM/EDC "
             f"pro lepší využití výroby.")
else:
    zaver = (f"❌ **Projekt se za 25 let nevrátí** při současných parametrech. "
             f"Zásadně přehodnoťte výkon FVE a model sdílení.")

st.info(zaver)

# Klíčový insight o baterii
if bat > 0 and ma_nt:
    st.caption(
        f"💡 **Baterie nepřidává výrobu — jen posouvá hodnotu z dne do noci.** "
        f"Přes den zachytí přebytky FVE, v noci pokryje NT spotřebu (bojler, TČ) "
        f"za cenu VT místo NT ze sítě."
    )

st.divider()

# ── NZÚ INFO ──────────────────────────────────────────────────────
st.subheader("🏛️ Státní podpora NZÚ 2026")
ni1,ni2=st.columns(2)
with ni1:
    st.markdown("**Co existuje pro SVJ (dle sfzp.gov.cz):**")
    st.write("✅ **Bezúročný úvěr NZÚ** — od září 2026, splácení standardně 15 let (max. 25 let)")
    st.write("✅ **Bonus za zranitelné domácnosti** — za byty se superdávkou")
    st.write("✅ **NZÚ Light** — přímá dotace jen pro nízkopříjmové")
with ni2:
    st.markdown("**Další technologie (bezúročný úvěr):**")
    st.write("• Zateplení fasády a střechy · Výměna oken")
    st.write("• Tepelné čerpadlo · Rekuperace")
    st.info("📋 Vždy ověřte na **[novazelenausporam.cz](https://novazelenausporam.cz)**")

st.divider()
st.caption(
    "⚠️ Orientační výpočty — 15minutová simulace. "
    "Profily spotřeby: OTE ČR — Typové diagramy dodávek elektřiny (TDD4). "
    "Solární data: PVGIS TMY © Evropská komise, JRC. "
    "Ceny dle ceníků ČEZ, E.ON, PRE od 1.1.2026 (s DPH 21 %, POZE=0 Kč). "
    "NZÚ: sfzp.gov.cz · EDC: edc.cz"
)
