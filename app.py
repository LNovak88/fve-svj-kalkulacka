import streamlit as st
import requests
import numpy as np
import pandas as pd
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="FVE Kalkulačka pro SVJ", page_icon="☀️", layout="wide")

# ================================================================
# OTE TDD4 PROFILY — normalizované na průměr = 1.0/hodinu
# Zdroj: OTE ČR — Typové diagramy dodávek elektřiny, ERU vyhláška
# TDD4 = standardní domácnost (D01d, D02d)
# ================================================================

_TDD4 = {
    "zima_prac":       np.array([0.412,0.371,0.348,0.339,0.343,0.377,0.524,0.784,0.883,0.819,0.762,0.741,0.758,0.738,0.717,0.739,0.820,1.118,1.284,1.222,1.082,0.917,0.718,0.551],dtype=float),
    "prechodne_prac":  np.array([0.395,0.355,0.333,0.325,0.329,0.366,0.500,0.730,0.822,0.768,0.719,0.699,0.717,0.697,0.676,0.698,0.778,1.037,1.181,1.119,0.989,0.837,0.648,0.496],dtype=float),
    "leto_prac":       np.array([0.378,0.339,0.319,0.311,0.316,0.356,0.476,0.676,0.761,0.718,0.676,0.657,0.676,0.656,0.636,0.657,0.737,0.957,1.079,1.017,0.897,0.757,0.578,0.441],dtype=float),
    "zima_vikend":     np.array([0.451,0.404,0.375,0.364,0.366,0.384,0.420,0.552,0.752,0.901,0.950,0.938,0.901,0.860,0.820,0.820,0.879,1.047,1.148,1.098,0.978,0.818,0.648,0.521],dtype=float),
    "prechodne_vikend":np.array([0.423,0.379,0.352,0.341,0.343,0.360,0.398,0.524,0.713,0.858,0.904,0.893,0.858,0.819,0.780,0.780,0.838,0.997,1.094,1.044,0.929,0.778,0.615,0.490],dtype=float),
    "leto_vikend":     np.array([0.396,0.355,0.329,0.319,0.321,0.337,0.377,0.497,0.675,0.816,0.859,0.848,0.816,0.778,0.741,0.741,0.797,0.948,1.040,0.991,0.881,0.738,0.582,0.458],dtype=float),
}
# Normalizace na průměr = 1.0
for _k in _TDD4: _TDD4[_k] = _TDD4[_k] / _TDD4[_k].mean()

# TDD profil pro společné prostory (výtah, osvětlení chodeb, čerpadla)
_TDD_SP = {
    "zima_prac":       np.array([0.55,0.52,0.50,0.50,0.50,0.55,0.75,0.95,0.85,0.75,0.72,0.72,0.72,0.72,0.75,0.85,0.95,1.10,1.15,1.10,1.00,0.90,0.75,0.62],dtype=float),
    "prechodne_prac":  np.array([0.50,0.47,0.45,0.45,0.45,0.50,0.70,0.88,0.78,0.70,0.67,0.67,0.67,0.67,0.70,0.78,0.88,1.00,1.05,1.00,0.91,0.81,0.68,0.56],dtype=float),
    "leto_prac":       np.array([0.45,0.42,0.40,0.40,0.40,0.45,0.65,0.80,0.72,0.65,0.62,0.62,0.62,0.62,0.65,0.72,0.80,0.90,0.95,0.90,0.82,0.72,0.60,0.50],dtype=float),
    "zima_vikend":     np.array([0.58,0.54,0.52,0.51,0.51,0.54,0.62,0.78,0.90,0.95,0.95,0.93,0.90,0.88,0.85,0.88,0.92,1.05,1.10,1.05,0.95,0.85,0.72,0.63],dtype=float),
    "prechodne_vikend":np.array([0.53,0.49,0.47,0.46,0.46,0.49,0.57,0.72,0.82,0.88,0.88,0.86,0.82,0.80,0.78,0.80,0.84,0.97,1.01,0.97,0.88,0.78,0.66,0.58],dtype=float),
    "leto_vikend":     np.array([0.48,0.44,0.42,0.41,0.41,0.44,0.52,0.65,0.75,0.80,0.80,0.78,0.75,0.73,0.71,0.73,0.77,0.88,0.92,0.88,0.80,0.71,0.60,0.52],dtype=float),
}
for _k in _TDD_SP: _TDD_SP[_k] = _TDD_SP[_k] / _TDD_SP[_k].mean()

# Úpravy TDD dle profilu obyvatel
_UPRAVY = {
    "mix":        np.ones(24,dtype=float),
    "seniori":    np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.3,1.5,1.6,1.6,1.5,1.5,1.4,1.4,1.3,1.1,1.0,1.0,1.0,1.0,1.0,1.0],dtype=float),
    "pracujici":  np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.2,1.3,0.7,0.5,0.5,0.5,0.5,0.5,0.5,0.6,0.8,1.3,1.4,1.3,1.2,1.1,1.0,1.0],dtype=float),
    "rodiny":     np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.2,0.9,0.7,0.7,0.7,0.8,0.8,0.9,1.1,1.2,1.2,1.2,1.1,1.1,1.0,1.0,1.0],dtype=float),
    "provozovna": np.array([0.8,0.8,0.8,0.8,0.8,0.9,1.0,1.2,1.5,1.6,1.7,1.7,1.6,1.6,1.6,1.5,1.3,1.1,1.0,0.9,0.9,0.8,0.8,0.8],dtype=float),
}
for _k in _UPRAVY: _UPRAVY[_k] = _UPRAVY[_k] / _UPRAVY[_k].mean()

_CD = 365 * 96  # 35 040 intervalů/rok
_MESICE = ["Led","Úno","Bře","Dub","Kvě","Čvn","Čvc","Srp","Zář","Říj","Lis","Pro"]

# ================================================================
# SIMULAČNÍ ENGINE
# ================================================================

def _sezona(m):
    if m in [11,12,1,2]: return "zima"
    if m in [5,6,7,8]: return "leto"
    return "prechodne"


def _gen_profil(kwh, tdd, uprava=None):
    vals = []
    den = datetime.date(2026,1,1)
    for _ in range(365):
        sz = _sezona(den.month)
        tp = "vikend" if den.weekday()>=5 else "prac"
        p = tdd[f"{sz}_{tp}"].copy()
        if uprava is not None:
            p = p * uprava; p = p/p.mean()
        for h in range(24):
            v = float(p[h])/4.0
            vals.extend([v,v,v,v])
        den += datetime.timedelta(days=1)
    arr = np.array(vals,dtype=float)[:_CD]
    if arr.sum()>0: arr = arr*(float(kwh)/arr.sum())
    return arr


def _gen_vyroba_fallback(kwp, sklon=35, azimut=0):
    """Záložní model kalibrovaný na průměr ČR (1050 kWh/kWp/rok)."""
    vh = np.zeros(8760,dtype=float)
    for h in range(8760):
        dr=h//24; hod=h%24
        uhel=2*np.pi*(dr-80)/365.0
        delka=12+4.5*np.sin(uhel)
        vychod=12-delka/2; zapad=12+delka/2
        if vychod<=hod<=zapad:
            t=(hod-vychod)/delka; elev=np.sin(np.pi*t)
            sezon=max(0.3,min(1.0,0.5+0.5*np.sin(uhel+np.pi/2)))
            koef=1.0+0.15*np.sin(np.pi*float(sklon)/90.0)
            vh[h]=float(kwp)*elev*sezon*koef*0.85
    if vh.sum()>0: vh=vh*(float(kwp)*1050.0/vh.sum())
    return vh


def _interpoluj(hod):
    h=np.array(hod,dtype=float); n=len(h)
    res=np.zeros(n*4,dtype=float)
    for i in range(n):
        ni=(i+1)%n
        for j in range(4):
            t=j/4.0; res[i*4+j]=(h[i]*(1.0-t)+h[ni]*t)/4.0
    return res[:_CD]


def _simuluj(vyroba_15, sp_sp15, sp_by15, bat=0.0, model="edc"):
    v=np.array(vyroba_15,dtype=float)
    ss=np.array(sp_sp15,dtype=float)
    sb=np.array(sp_by15,dtype=float)
    bat=float(bat)
    s = ss.copy() if model=="spolecne" else ss+sb
    n=int(min(len(v),len(s))); v,s=v[:n],s[:n]
    bmin,bmax,bkwh=bat*0.1,bat*0.9,bat*0.5; eta=0.92
    vl=np.zeros(n,dtype=float); pr=np.zeros(n,dtype=float); od=np.zeros(n,dtype=float)
    for i in range(n):
        vi,si=float(v[i]),float(s[i])
        prime=min(vi,si); vl[i]+=prime; zbv=vi-prime; zbs=si-prime
        if zbv>0.0 and bat>0.0:
            nab=min(zbv*eta,bmax-bkwh); bkwh+=nab; zbv-=nab/eta
        pr[i]=zbv
        if zbs>0.0 and bat>0.0:
            dos=(bkwh-bmin)*eta; vyb=min(zbs,dos)
            bkwh-=vyb/eta; zbs-=vyb; vl[i]+=vyb
        od[i]=zbs
    tv=float(v.sum()); tvl=float(vl.sum()); tpr=float(pr.sum()); tsp=float(s.sum())
    if model=="edc": tvl*=0.98; tpr=tv-tvl
    mv,ms,mvl,mpr=[],[],[],[]
    for m in range(12):
        a,b=m*30*96,min((m+1)*30*96,n)
        mv.append(float(v[a:b].sum())); ms.append(float(s[a:b].sum()))
        mvl.append(float(vl[a:b].sum())); mpr.append(float(pr[a:b].sum()))
    return {"vlastni_kwh":tvl,"pretoky_kwh":tpr,"odber_kwh":float(od.sum()),
            "vyroba_kwh":tv,"spotreba_kwh":tsp,
            "mira_vs":tvl/tv if tv>0 else 0.0,
            "mira_sob":tvl/tsp if tsp>0 else 0.0,
            "mesice_vyroba":mv,"mesice_spotreba":ms,
            "mesice_vlastni":mvl,"mesice_pretoky":mpr}


def _cashflow(vl, pr, cvt, cpr, vlast, uver, spl, splat,
              rust=3.0, deg=0.5, leta=25, jist=0.0, bonus=0.0):
    res=[]; kum=-(float(vlast)+float(uver)-float(bonus))
    for rok in range(1,int(leta)+1):
        d=(1.0-float(deg)/100.0)**(rok-1); c=(1.0+float(rust)/100.0)**(rok-1)
        u=float(vl)*d*float(cvt)*c+float(pr)*d*float(cpr)*c+float(jist)*c
        s=float(spl) if rok<=int(splat) else 0.0
        kum+=u-s
        res.append({"rok":rok,"vyroba_mwh":round((float(vl)+float(pr))*d/1000.0,2),
                    "vlastni_mwh":round(float(vl)*d/1000.0,2),"pretoky_mwh":round(float(pr)*d/1000.0,2),
                    "uspora_el":round(float(vl)*d*float(cvt)*c),
                    "uspora_pretoky":round(float(pr)*d*float(cpr)*c),
                    "uspora_celkem":round(u),"splatka":round(s),
                    "cisty_prinos":round(u-s),"kumulativni":round(kum),
                    "cena_vt":round(float(cvt)*c,3)})
    return res


def _gen_vyroba_den(kwp, sezona, pocasi):
    """Výroba v kWh/15min pro průměrný den dané sezóny a počasí."""
    koef = {"jasno":1.0,"polojasno":0.5,"zatazeno":0.15}[pocasi]
    intenzita = {"zima":0.220,"prechodne":0.408,"leto":0.647}[sezona]
    delka = {"zima":8.0,"prechodne":12.0,"leto":15.0}[sezona]
    vychod = 12-delka/2; zapad = 12+delka/2
    vyroba = np.zeros(96,dtype=float)
    for i in range(96):
        h = i/4.0
        if vychod<=h<=zapad:
            t=(h-vychod)/delka; elev=np.sin(np.pi*t)
            vyroba[i] = float(kwp)*elev*intenzita*koef*0.85*0.25  # kWh/15min
    return vyroba


def _gen_spotreba_den(kwh_rok, sezona, profil, vikend=False):
    """Průměrná denní spotřeba kWh/15min pro danou sezónu."""
    tp = "vikend" if vikend else "prac"
    p = _TDD4[f"{sezona}_{tp}"].copy() * _UPRAVY.get(profil, np.ones(24))
    p = p/p.mean()
    vals = np.zeros(96,dtype=float)
    for h in range(24):
        for j in range(4):
            vals[h*4+j] = float(p[h])/4.0
    # Denní spotřeba = roční / 365
    kwh_den = float(kwh_rok)/365.0
    if vals.sum()>0: vals = vals*(kwh_den/vals.sum())
    return vals


@st.cache_data(ttl=3600)
def _geocode(dotaz):
    _FALLBACK = {
        "praha":(50.08,14.44),"brno":(49.19,16.61),"ostrava":(49.83,18.29),
        "plzeň":(49.74,13.37),"třinec":(49.68,18.67),"liberec":(50.77,15.06),
        "olomouc":(49.59,17.25),"zlín":(49.22,17.66),"znojmo":(48.86,16.05),
        "hradec králové":(50.21,15.83),"pardubice":(50.04,15.78),
        "české budějovice":(48.97,14.47),"ústí nad labem":(50.66,14.03),
        "havířov":(49.78,18.43),"karviná":(49.85,18.54),"opava":(49.94,17.90),
        "frýdek-místek":(49.68,18.35),"jihlava":(49.40,15.59),
    }
    try:
        r=requests.get("https://nominatim.openstreetmap.org/search",
                       params={"q":f"{dotaz}, Česká republika","format":"json","limit":1,"addressdetails":1},
                       headers={"User-Agent":"FVE-SVJ-Kalkulacka/1.0"},timeout=10)
        if r.status_code==200 and r.text.strip():
            res=r.json()
            if res:
                addr=res[0].get("address",{})
                m=addr.get("city") or addr.get("town") or addr.get("village") or dotaz
                return float(res[0]["lat"]),float(res[0]["lon"]),m,None
    except: pass
    klic=dotaz.lower().strip()
    if klic in _FALLBACK:
        lat,lon=_FALLBACK[klic]
        return lat,lon,dotaz,None
    return None,None,None,"Nenalezeno"


@st.cache_data(ttl=86400)
def _pvgis(lat,lon,kwp,sklon,azimut):
    try:
        r=requests.get("https://re.jrc.ec.europa.eu/api/v5_2/seriescalc",
                       params={"lat":float(lat),"lon":float(lon),"peakpower":float(kwp),
                               "loss":14,"angle":int(sklon),"aspect":int(azimut),
                               "outputformat":"json","browser":0,
                               "startyear":2020,"endyear":2020,
                               "pvcalculation":1,"pvtechchoice":"crystSi",
                               "mountingplace":"building","trackingtype":0},
                       timeout=30)
        r.raise_for_status()
        arr=np.array([float(h["P"])/1000.0 for h in r.json()["outputs"]["hourly"]],dtype=float)
        return arr[:8760],None
    except Exception as e:
        return None,str(e)


# Plotly config — zakáže zoom kolečkem
_PLOTLY_CFG = {"scrollZoom":False,"displayModeBar":False,"staticPlot":False}
_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10,r=10,t=30,b=10),
    legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
    font=dict(size=12),
    xaxis=dict(fixedrange=True),
    yaxis=dict(fixedrange=True),
)

# ================================================================
# CENÍKOVÉ TABULKY 2026
# ================================================================

CENY_VT = {
    "ČEZ Distribuce": {"D01d":7493,"D02d":7493,"D25d":6945,"D26d":6945,"D27d":6945,"D35d":5254,"D45d":5254,"D56d":5254,"D57d":5254,"D61d":8073},
    "EG.D (E.ON)":    {"D01d":7053,"D02d":7053,"D25d":6550,"D26d":6647,"D27d":6647,"D35d":6647,"D45d":4865,"D56d":4865,"D57d":4865,"D61d":8018},
    "PREdistribuce":  {"D01d":6200,"D02d":6200,"D25d":5800,"D26d":5800,"D27d":5800,"D35d":5200,"D45d":4800,"D56d":4800,"D57d":4800,"D61d":6800},
}
CENY_NT = {
    "ČEZ Distribuce": {"D25d":4190,"D26d":4190,"D27d":4140,"D35d":4510,"D45d":4510,"D56d":4510,"D57d":4510,"D61d":4350},
    "EG.D (E.ON)":    {"D25d":3833,"D26d":3833,"D27d":3833,"D35d":3957,"D45d":4027,"D56d":4027,"D57d":4027,"D61d":3832},
    "PREdistribuce":  {"D25d":3500,"D26d":3500,"D27d":3500,"D35d":3700,"D45d":3800,"D56d":3800,"D57d":3800,"D61d":3500},
}
STAY_PLAT={"ČEZ Distribuce":163,"EG.D (E.ON)":144,"PREdistribuce":150}
JISTIC_3x25={"ČEZ Distribuce":{"D01d":132,"D02d":298,"D25d":287,"D26d":422,"D27d":272,"D35d":517,"D45d":567,"D56d":567,"D57d":567,"D61d":238},"EG.D (E.ON)":{"D01d":145,"D02d":575,"D25d":296,"D26d":422,"D27d":282,"D35d":575,"D45d":575,"D56d":575,"D57d":575,"D61d":271},"PREdistribuce":{"D01d":100,"D02d":280,"D25d":250,"D26d":350,"D27d":230,"D35d":420,"D45d":480,"D56d":480,"D57d":480,"D61d":200}}
SAZBY_NT=["D25d","D26d","D27d","D35d","D45d","D56d","D57d","D61d"]
PODIL_NT={"D25d":0.35,"D26d":0.35,"D27d":0.35,"D35d":0.60,"D45d":0.70,"D56d":0.75,"D57d":0.75,"D61d":0.40}
POPIS_SAZEB={"D01d":"Malý byt — jen svícení","D02d":"Standardní domácnost","D25d":"Ohřev vody bojlerem (8h NT)","D26d":"Akumulační kamna (8h NT)","D27d":"Elektromobil (8h NT)","D35d":"Hybridní TČ (16h NT)","D45d":"Přímotopy/elektrokotel (20h NT)","D56d":"Vytápění TČ/přímotopy (22h NT)","D57d":"TČ — hlavní zdroj tepla (20h NT)","D61d":"Víkendový objekt"}
PROFILY={"mix":{"nazev":"👨‍👩‍👧 Smíšený dům","popis":"Mix pracujících a seniorů"},"seniori":{"nazev":"👴 Převaha seniorů","popis":"Více doma přes den — vyšší využití FVE"},"pracujici":{"nazev":"🏢 Převaha pracujících","popis":"Většina pryč přes den — nižší přímé využití FVE"},"rodiny":{"nazev":"👨‍👩‍👧‍👦 Rodiny s dětmi","popis":"Doma odpoledne a víkendy"},"provozovna":{"nazev":"🏪 S provozovnou","popis":"Kadeřnictví, ordinace — vysoká spotřeba přes den"}}

# ================================================================
# UI
# ================================================================

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Přesná 15minutová simulace návratnosti FVE · OTE TDD profily · Ceny dle ceníků 2026")
st.divider()

# 1. ZÁKLADNÍ ÚDAJE
st.subheader("🏠 Základní údaje o domě")
c1,c2,c3=st.columns(3)
with c1:
    pocet_bytu=st.number_input("Počet bytů",2,200,12,1)
    sp_sp_mwh=st.number_input("Spotřeba společných prostor (MWh/rok)",0.1,50.0,3.5,0.1,format="%.1f",help="Výtah, osvětlení chodeb, čerpadla")
    sp_by_mwh=st.number_input("Spotřeba bytů celkem (MWh/rok)",1.0,500.0,21.5,0.5,format="%.1f")
    sp_sp=float(sp_sp_mwh)*1000; sp_by=float(sp_by_mwh)*1000; sp_cel=sp_sp+sp_by
    st.caption(f"Celková spotřeba domu: **{sp_cel/1000:.1f} MWh/rok**")
with c2:
    dist=st.selectbox("Distributor",list(CENY_VT.keys()))
    sazba=st.selectbox("Distribuční sazba",list(CENY_VT[dist].keys()),
                       format_func=lambda x:f"{x} — {POPIS_SAZEB[x]}",index=1)
with c3:
    st.selectbox("Hlavní jistič",["1×25A","3×16A","3×20A","3×25A","3×32A","3×40A","3×50A","3×63A"],index=3)
    profil=st.selectbox("Profil obyvatel",list(PROFILY.keys()),format_func=lambda x:PROFILY[x]["nazev"])
    st.caption(PROFILY[profil]["popis"])

cena_vt=float(CENY_VT[dist][sazba])/1000.0
cena_prum=(cena_vt*(1-PODIL_NT.get(sazba,0))+float(CENY_NT[dist].get(sazba,CENY_VT[dist][sazba]))/1000.0*PODIL_NT.get(sazba,0)) if sazba in SAZBY_NT else cena_vt
stay=float(STAY_PLAT[dist]); jistic=float(JISTIC_3x25[dist][sazba])
naklad=sp_cel*cena_prum+(stay+jistic)*12.0
st.info(f"💡 **{dist}** · **{sazba}** · s DPH · POZE=0 Kč od 2026 | VT: **{cena_vt:.2f} Kč/kWh** · Průměr: **{cena_prum:.2f} Kč/kWh** · Stálé platy: **{stay+jistic:.0f} Kč/měs** · Roční náklad: **{naklad:,.0f} Kč**")
with st.expander("✏️ Upravit ceny ručně"):
    u1,u2=st.columns(2)
    with u1: cena_vt=st.number_input("Cena VT (Kč/kWh)",1.0,15.0,round(cena_vt,2),0.01,format="%.2f")
    with u2: cena_prum=st.number_input("Průměrná cena (Kč/kWh)",1.0,15.0,round(cena_prum,2),0.01,format="%.2f")

st.divider()

# 2. FVE A BATERIE
st.subheader("⚡ Parametry FVE a baterie")
c1,c2=st.columns(2)
with c1:
    vykon=st.number_input("Výkon FVE (kWp)",1.0,200.0,20.0,0.5,format="%.1f")
    cena_kwp=st.slider("Cena FVE (Kč/kWp)",25000,50000,37000,1000)
    cena_fve=int(float(vykon)*float(cena_kwp))
    st.caption(f"Odhadovaná cena FVE: **{cena_fve:,.0f} Kč**")
with c2:
    bat=st.number_input("Kapacita baterie (kWh)",0,200,0,5,help="0 = bez baterie")
    if bat>0:
        cena_kwh_bat=st.slider("Cena baterie (Kč/kWh)",10000,20000,15000,500)
        cena_bat=int(float(bat)*float(cena_kwh_bat))
        st.caption(f"Odhadovaná cena baterie: **{cena_bat:,.0f} Kč**")
    else:
        cena_bat=0

st.divider()

# 3. MODEL SDÍLENÍ
st.subheader("🔗 Model sdílení energie")
model=st.radio("Model",["spolecne","jom","edc"],horizontal=True,
               format_func=lambda x:{"spolecne":"🏢 Jen společné prostory","jom":"⚡ Sjednocení odběrných míst","edc":"🔗 EDC komunitní sdílení (iterační)"}[x])
cena_mericu=int(pocet_bytu)*10000 if model=="jom" else 0
uspora_jist=jistic*(int(pocet_bytu)-1)*12.0 if model=="jom" else 0.0
if model=="spolecne":
    st.info(f"🏢 FVE pokrývá jen společnou spotřebu ({sp_sp_mwh:.1f} MWh/rok). Nejjednodušší realizace.")
elif model=="jom":
    st.info(f"⚡ Jeden elektroměr pro celý dům. Náklady na měřiče: **{cena_mericu:,} Kč**. Úspora distribuce: **{uspora_jist:,.0f} Kč/rok**.")
else:
    st.info("🔗 Každý byt si zachovává dodavatele. Chytré měřiče zdarma od distributora. EDC iterační alokace (−2 % vs JOM). Registrace na edc.cz.")

st.divider()

# 4. LOKALITA A STŘECHA
st.subheader("🌍 Lokalita a střecha")
lc1,lc2=st.columns([1,2])
with lc1: lokace=st.text_input("Město nebo PSČ","Praha")
with lc2: typ_str=st.radio("Typ střechy",["sikma","plocha"],format_func=lambda x:"🏠 Šikmá" if x=="sikma" else "🏢 Plochá",horizontal=True)
if typ_str=="sikma":
    sc1,sc2=st.columns(2)
    with sc1: sklon=st.slider("Sklon (°)",15,60,35)
    with sc2: azimut=st.select_slider("Orientace",[-90,-45,0,45,90],0,format_func=lambda x:{-90:"⬅️ Východ",-45:"↙️ JV",0:"⬆️ Jih",45:"↗️ JZ",90:"➡️ Západ"}[x])
    koef_str=1.0
else:
    pc1,pc2=st.columns(2)
    with pc1: sklon=st.slider("Sklon panelů (°)",5,20,10)
    with pc2: sys_pl=st.radio("Systém",["jih","jz_jv","vz"],format_func=lambda x:{"jih":"⬆️ Jih","jz_jv":"↗️ JZ+JV","vz":"↔️ V+Z"}[x])
    azimut=90 if sys_pl=="vz" else 0
    koef_str={"jih":1.0,"jz_jv":0.97,"vz":0.88}[sys_pl]

st.divider()

# 5. FINANCOVÁNÍ
st.subheader("💰 Financování")
fc1,fc2=st.columns(2)
with fc1:
    scenar=st.radio("Scénář",["uver","vlastni","kombinace"],format_func=lambda x:{"uver":"🏦 Bezúročný úvěr NZÚ (od září 2026)","vlastni":"💵 Vlastní zdroje (fond oprav)","kombinace":"🔀 Kombinace vlastní + úvěr"}[x])
with fc2:
    if scenar=="uver": splatnost=st.slider("Doba splácení (let)",5,25,15); vlastni_pct=0; st.info("✅ Úroky hradí stát. SVJ splácí jen jistinu.")
    elif scenar=="vlastni": splatnost=0; vlastni_pct=100; st.info("💡 SVJ hradí vše z fondu oprav.")
    else: vlastni_pct=st.slider("Vlastní zdroje (%)",10,90,30,10); splatnost=st.slider("Doba splácení (let)",5,25,15)

st.markdown("**Nízkopříjmové domácnosti**")
nb1,nb2=st.columns(2)
with nb1: pocet_nizko=st.number_input("Bytů s bonusem",0,int(pocet_bytu),0,1)
with nb2: bonus_byt=st.number_input("Bonus na byt (Kč)",0,150000,50000,5000)
bonus=int(pocet_nizko)*int(bonus_byt)

st.divider()

# 6. PARAMETRY SIMULACE
st.subheader("⚙️ Parametry simulace")
sc1,sc2,sc3=st.columns(3)
with sc1: cena_pretoky=st.number_input("Výkupní cena přetoků (Kč/kWh)",0.30,2.50,0.95,0.05,format="%.2f")
with sc2: rust_cen=st.slider("Růst cen elektřiny (%/rok)",0.0,8.0,3.0,0.5)
with sc3: deg_pan=st.slider("Degradace panelů (%/rok)",0.2,1.0,0.5,0.1)

st.divider()

# VÝPOČET INVESTICE
cena_invest=cena_fve+cena_bat+cena_mericu
vlastni_cast=float(cena_invest)*float(vlastni_pct)/100.0
uver_cast=max(0.0,float(cena_invest)-vlastni_cast-float(bonus))
rocni_spl=uver_cast/float(splatnost) if (scenar!="vlastni" and splatnost>0) else 0.0

bc1,bc2=st.columns([1,3])
with bc1: spustit=st.button("🔄 Spočítat simulaci",type="primary",use_container_width=True)
with bc2: st.caption("Stáhne hodinová solární data z PVGIS a provede přesný 15minutový výpočet. Trvá 5–20 s.")

if spustit:
    with st.spinner(f"Hledám lokalitu {lokace}..."):
        lat,lon,mesto,geo_err=_geocode(lokace)
    if geo_err: st.error(f"Lokalita nenalezena: {geo_err}"); st.stop()

    kwp_eff=float(vykon)*float(koef_str)
    with st.spinner(f"Stahuji solární data pro {mesto} z PVGIS..."):
        vyroba_hod,pvgis_err=_pvgis(lat,lon,kwp_eff,sklon,azimut)
    if pvgis_err:
        st.warning("⚠️ PVGIS nedostupné — používám kalibrovaný záložní model.")
        vyroba_hod=_gen_vyroba_fallback(kwp_eff,sklon,azimut); pvgis_ok=False
    else: pvgis_ok=True

    with st.spinner("Simuluji v 15minutových intervalech (OTE TDD profily)..."):
        vyroba_15=_interpoluj(vyroba_hod)
        sp_sp15=_gen_profil(sp_sp,_TDD_SP)
        sp_by15=_gen_profil(sp_by,_TDD4,_UPRAVY.get(profil))
        sim=_simuluj(vyroba_15,sp_sp15,sp_by15,float(bat),model)
        cf=_cashflow(vl=sim["vlastni_kwh"],pr=sim["pretoky_kwh"],
                     cvt=float(cena_vt),cpr=float(cena_pretoky),
                     vlast=vlastni_cast,uver=uver_cast,spl=rocni_spl,splat=int(splatnost),
                     rust=float(rust_cen),deg=float(deg_pan),leta=25,
                     jist=float(uspora_jist),bonus=float(bonus))
        # Porovnání modelů
        srovnani={}
        for mk in ["spolecne","jom","edc"]:
            sm=_simuluj(vyroba_15,sp_sp15,sp_by15,float(bat),mk)
            cfm=_cashflow(vl=sm["vlastni_kwh"],pr=sm["pretoky_kwh"],
                          cvt=float(cena_vt),cpr=float(cena_pretoky),
                          vlast=vlastni_cast,uver=uver_cast,spl=rocni_spl,splat=int(splatnost),
                          rust=float(rust_cen),deg=float(deg_pan),leta=25,
                          jist=float(uspora_jist) if mk=="jom" else 0.0,bonus=float(bonus))
            nav_m=next((r["rok"] for r in cfm if r["kumulativni"]>=0),None)
            stat_m=float(cena_invest)/cfm[0]["uspora_celkem"] if cfm[0]["uspora_celkem"]>0 else 999
            srovnani[mk]={"sim":sm,"cf":cfm,"nav":nav_m,"stat":stat_m,"rok1":cfm[0]}

    st.session_state["res"]={"sim":sim,"cf":cf,"vyroba_15":vyroba_15,
                              "vyroba_hod":vyroba_hod,"pvgis_ok":pvgis_ok,
                              "sp_sp15":sp_sp15,"sp_by15":sp_by15,
                              "mesto":mesto,"lat":lat,"lon":lon,"srovnani":srovnani}
    st.success(f"✅ Hotovo — {mesto} ({lat:.2f}°N, {lon:.2f}°E) {'· PVGIS data' if pvgis_ok else '· záložní model'}")

if "res" not in st.session_state:
    st.info("👆 Vyplňte parametry a klikněte na **Spočítat simulaci**.")
    st.stop()

# ================================================================
# VÝSLEDKY
# ================================================================

d=st.session_state["res"]
sim=d["sim"]; cf=d["cf"]; srovnani=d["srovnani"]
sp_sp15=d["sp_sp15"]; sp_by15=d["sp_by15"]
rok1=cf[0]
nav=next((r["rok"] for r in cf if r["kumulativni"]>=0),None)

# Předpočítané hodnoty
stat_nav=float(cena_invest)/rok1["uspora_celkem"] if rok1["uspora_celkem"]>0 else 999
splatka_vsichni=rocni_spl/float(pocet_bytu)/12.0
solidarni_refund=float(bonus_byt)/(float(splatnost)*12.0) if splatnost>0 else 0.0
cista_splatka_super=max(0.0,splatka_vsichni-solidarni_refund)
splatka_bez_bonusu=float(cena_invest)/float(splatnost)/float(pocet_bytu)/12.0 if splatnost>0 else 0.0
uspora_diky_bonusu=splatka_bez_bonusu-splatka_vsichni
uspora_byt_mesic=rok1["uspora_celkem"]/float(pocet_bytu)/12.0

st.divider()
st.subheader("📊 Výsledky simulace")

r1,r2,r3,r4,r5,r6=st.columns(6)
with r1: st.metric("Roční výroba FVE",f"{sim['vyroba_kwh']/1000:.1f} MWh")
with r2: st.metric("Vlastní spotřeba",f"{sim['mira_vs']*100:.1f} %",help="% výroby FVE spotřebované v domě nebo přes baterii")
with r3: st.metric("Soběstačnost",f"{sim['mira_sob']*100:.1f} %",help="% celkové spotřeby pokryté FVE")
with r4: st.metric("Roční úspora (rok 1)",f"{rok1['uspora_celkem']:,.0f} Kč")
with r5: st.metric("Statická návratnost",f"{stat_nav:.1f} let",help="Investice ÷ roční úspora (bez splátek a inflace)")
with r6: st.metric("Cashflow návratnost",f"{nav} let" if nav else ">25 let",help="Kdy kumulativní cashflow přejde do kladných čísel")

st.divider()

# ── POROVNÁNÍ MODELŮ ──────────────────────────────────────────────
st.subheader("📊 Porovnání modelů sdílení")
st.caption("Stejná FVE a investice — rozdíl je v tom co FVE pokrývá.")
nazvy={"spolecne":"🏢 Jen společné","jom":"⚡ JOM","edc":"🔗 EDC"}
sc1,sc2,sc3=st.columns(3)
for col,mk in zip([sc1,sc2,sc3],["spolecne","jom","edc"]):
    sv=srovnani[mk]
    cisty_byt=sv["rok1"]["uspora_celkem"]/float(pocet_bytu)/12.0-splatka_vsichni
    with col:
        st.markdown(f"**{nazvy[mk]}**")
        st.metric("Roční úspora",f"{sv['rok1']['uspora_celkem']:,.0f} Kč")
        st.metric("Vlastní spotřeba",f"{sv['sim']['mira_vs']*100:.1f} %")
        st.metric("Soběstačnost",f"{sv['sim']['mira_sob']*100:.1f} %")
        st.metric("Statická návratnost",f"{sv['stat']:.1f} let")
        st.metric("Cashflow návratnost",f"{sv['nav']} let" if sv['nav'] else ">25 let")
        if cisty_byt>=0:
            st.metric("Čistý přínos/byt",f"+{cisty_byt:.0f} Kč/měs",delta="kladný")
        else:
            st.metric("Čistý náklad/byt",f"{cisty_byt:.0f} Kč/měs",delta=f"{cisty_byt:.0f} Kč",delta_color="inverse")

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
        st.metric("Splátka úvěru",f"{splatka_vsichni:.0f} Kč/měs")
        st.metric("Solidární refundace",f"−{solidarni_refund:.0f} Kč/měs",help=f"Bonus {bonus_byt:,} Kč ÷ {splatnost*12} měsíců")
        st.metric("Čistá splátka",f"{cista_splatka_super:.0f} Kč/měs")
        st.metric("Čistý měsíční přínos",f"+{cisty_super:.0f} Kč/měs",delta=f"+{cisty_super-cisty_std:.0f} Kč vs std. byt")
        st.divider()
        st.markdown("**🤝 Přínos bonusu pro dům**")
        st.write(f"• Státní bonus: **{bonus:,.0f} Kč** ({pocet_nizko}× {bonus_byt:,} Kč)")
        st.write(f"• Každý byt ušetří: **{uspora_diky_bonusu:.0f} Kč/měs** na splátce")
        rez=float(bonus); ref_mes=solidarni_refund*pocet_nizko
        if ref_mes>0:
            st.write(f"• Rezerva vydrží: **{rez/ref_mes:.0f} měsíců** ({'✅' if rez/ref_mes>=splatnost*12 else '⚠️'})")
    else:
        st.markdown("**Žádné byty se superdávkou**")
        st.caption("Zadejte počet bytů s bonusem výše.")

st.divider()

# ── KLÍČOVÉ MILNÍKY ───────────────────────────────────────────────
st.markdown("**📍 Klíčové milníky**")
m1,m2,m3=st.columns(3)
with m1:
    lines=["**Rok 1**",
           f"Vlastní spotřeba: **{sim['vlastni_kwh']:,.0f} kWh** ({sim['mira_vs']*100:.0f} % výroby)",
           f"Přetoky do sítě: **{sim['pretoky_kwh']:,.0f} kWh**",
           f"Úspora elektřina: **{rok1['uspora_el']:,.0f} Kč**",
           f"Příjem přetoky: **{rok1['uspora_pretoky']:,.0f} Kč**",
           f"**Celková úspora: {rok1['uspora_celkem']:,.0f} Kč/rok**",
           f"Na byt: **{uspora_byt_mesic*12:,.0f} Kč/rok** · **{uspora_byt_mesic:.0f} Kč/měs**",
           f"Splátka na byt: **{splatka_vsichni:.0f} Kč/měs**"]
    st.info("  \n".join(lines))
with m2:
    if scenar!="vlastni" and splatnost>0 and splatnost<=25:
        rs=cf[min(splatnost-1,len(cf)-1)]
        lines=[f"**Rok {splatnost} — úvěr splacen ✅**",
               f"Úspora v tom roce: **{rs['uspora_celkem']:,.0f} Kč**",
               f"(vč. růstu cen +{rust_cen}%/rok, degradace -{deg_pan}%/rok)",
               f"Poté plný přínos bez splátky:",
               f"**{rs['uspora_celkem']:,.0f} Kč/rok**"]
        st.info("  \n".join(lines))
    else:
        st.info("  \n".join(["**Vlastní financování**","Žádné splátky",f"Plný přínos od roku 1:",f"**{rok1['uspora_celkem']:,.0f} Kč/rok**"]))
with m3:
    kum25=cf[-1]["kumulativni"]
    if nav:
        lines=[f"**Rok {nav} — investice se vrátí ✅**",
               f"Statická návratnost: **{stat_nav:.1f} let**",
               f"Cashflow návratnost: **{nav} let**",
               f"Za 25 let celková úspora:",
               f"**{kum25:,.0f} Kč** ({kum25/float(pocet_bytu):,.0f} Kč/byt)",
               f"→ dalších {max(0,25-nav)} let čistý zisk!"]
        st.success("  \n".join(lines))
    else:
        st.warning("  \n".join([f"**Za 25 let investice se nevrátí**",
                                f"Statická návratnost: **{stat_nav:.1f} let**",
                                f"Cashflow: **{kum25:,.0f} Kč**",
                                "Zvyšte výkon FVE nebo zvolte jiný model."]))

st.divider()

# ── GRAFY ─────────────────────────────────────────────────────────
tab1,tab2,tab3=st.tabs(["📅 Denní graf","📈 Roční přehled","💰 Cashflow 25 let"])

with tab1:
    st.markdown("**Průměrný den — výroba vs spotřeba**")
    gc1,gc2=st.columns(2)
    with gc1: sezona_g=st.radio("Sezóna",["zima","prechodne","leto"],horizontal=True,format_func=lambda x:{"zima":"❄️ Zima","prechodne":"🌤️ Jaro/Podzim","leto":"☀️ Léto"}[x])
    with gc2: pocasi_g=st.radio("Počasí",["jasno","polojasno","zatazeno"],horizontal=True,format_func=lambda x:{"jasno":"☀️ Jasno","polojasno":"⛅ Polojasno","zatazeno":"☁️ Zataženo"}[x])

    kwp_eff=float(vykon)*float(koef_str)
    vyr_den=_gen_vyroba_den(kwp_eff,sezona_g,pocasi_g)  # kWh/15min
    sp_total=sp_sp+sp_by if model!="spolecne" else sp_sp
    sp_den=_gen_spotreba_den(sp_total,profil,sezona_g,False)  # kWh/15min

    hodiny=[i/4.0 for i in range(96)]
    vlastni_den=np.minimum(vyr_den,sp_den)
    pretoky_den=np.maximum(vyr_den-sp_den,0)
    odber_den=np.maximum(sp_den-vyr_den,0)

    # Baterie SOC simulace pro den
    bat_soc=np.zeros(96)
    if bat>0:
        bkwh=float(bat)*0.5
        for i in range(96):
            vi,si=float(vyr_den[i]),float(sp_den[i])
            if vi>=si:
                ex=vi-si; nab=min(ex*0.92,float(bat)*0.9-bkwh); bkwh+=nab
            else:
                nd=si-vi; vyb=min(nd,(bkwh-float(bat)*0.1)*0.92); bkwh-=vyb/0.92
            bat_soc[i]=bkwh/float(bat)*100

    fig=go.Figure()
    fig.add_trace(go.Scatter(x=hodiny,y=vyr_den*4,name="⚡ Výroba FVE (kW)",fill="tozeroy",
                              fillcolor="rgba(255,193,7,0.2)",line=dict(color="#FFC107",width=2)))
    fig.add_trace(go.Scatter(x=hodiny,y=sp_den*4,name="🏠 Spotřeba (kW)",
                              line=dict(color="#2196F3",width=2)))
    fig.add_trace(go.Scatter(x=hodiny,y=vlastni_den*4,name="✅ Vlastní spotřeba (kW)",fill="tozeroy",
                              fillcolor="rgba(76,175,80,0.2)",line=dict(color="#4CAF50",width=1,dash="dot")))
    if bat>0:
        fig.add_trace(go.Scatter(x=hodiny,y=bat_soc,name="🔋 Baterie SOC (%)",
                                  yaxis="y2",line=dict(color="#9C27B0",width=1,dash="dash")))

    layout=dict(_PLOTLY_LAYOUT)
    layout.update(dict(
        xaxis=dict(title="Hodina",tickmode="linear",tick0=0,dtick=2,fixedrange=True),
        yaxis=dict(title="kW",fixedrange=True),
        height=350,
    ))
    if bat>0:
        layout["yaxis2"]=dict(title="SOC %",overlaying="y",side="right",range=[0,100],fixedrange=True)
    fig.update_layout(**layout)
    st.plotly_chart(fig,use_container_width=True,config=_PLOTLY_CFG)
    st.caption(f"Průměrný den · {sezona_g} · {pocasi_g} · {kwp_eff:.0f} kWp FVE")

with tab2:
    st.markdown("**Měsíční přehled výroby a spotřeby**")
    mesice_v=sim["mesice_vyroba"]
    mesice_vl=sim["mesice_vlastni"]
    mesice_pr=sim["mesice_pretoky"]

    fig2=go.Figure()
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in mesice_v],name="Výroba FVE (MWh)",
                           marker_color="#FFC107",opacity=0.8))
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in mesice_vl],name="Vlastní spotřeba (MWh)",
                           marker_color="#4CAF50",opacity=0.9))
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in mesice_pr],name="Přetoky (MWh)",
                           marker_color="#9E9E9E",opacity=0.7))

    layout2=dict(_PLOTLY_LAYOUT)
    layout2.update(dict(barmode="overlay",
                        xaxis=dict(fixedrange=True),
                        yaxis=dict(title="MWh",fixedrange=True),
                        height=350))
    fig2.update_layout(**layout2)
    st.plotly_chart(fig2,use_container_width=True,config=_PLOTLY_CFG)

with tab3:
    st.markdown("**Kumulativní cashflow — 25 let životnosti panelů**")
    roky=[r["rok"] for r in cf]
    kum=[r["kumulativni"] for r in cf]
    uspora_cum=[sum(r["uspora_celkem"] for r in cf[:i+1]) for i in range(len(cf))]

    fig3=go.Figure()
    fig3.add_hrect(y0=0,y1=max(kum)*1.1,fillcolor="rgba(76,175,80,0.05)",line_width=0)
    fig3.add_trace(go.Scatter(x=roky,y=kum,name="Kumulativní cashflow",fill="tozeroy",
                               fillcolor="rgba(33,150,243,0.15)",line=dict(color="#2196F3",width=3)))
    fig3.add_hline(y=0,line_dash="dash",line_color="#666",line_width=1)
    if nav:
        fig3.add_vline(x=nav,line_dash="dot",line_color="#4CAF50",line_width=2,
                       annotation_text=f"Rok {nav} — návratnost",annotation_position="top right")
    # Splátky jako ztráta
    splatky=[-r["splatka"] for r in cf]
    if scenar!="vlastni":
        fig3.add_trace(go.Bar(x=roky,y=splatky,name="Splátka úvěru",
                               marker_color="rgba(244,67,54,0.4)",yaxis="y"))

    layout3=dict(_PLOTLY_LAYOUT)
    layout3.update(dict(
        xaxis=dict(title="Rok",fixedrange=True,dtick=2),
        yaxis=dict(title="Kč",fixedrange=True,tickformat=","),
        height=380,barmode="overlay",
    ))
    fig3.update_layout(**layout3)
    st.plotly_chart(fig3,use_container_width=True,config=_PLOTLY_CFG)
    st.caption(f"🟦 Kumulativní cashflow · 🔴 Splátky úvěru · Zelená linie = návratnost rok {nav if nav else '—'}")

st.divider()

# ── CASHFLOW TABULKA ──────────────────────────────────────────────
st.subheader("📋 Cashflow rok po roku (25 let)")
df=pd.DataFrame([{"Rok":r["rok"],"Výroba MWh":r["vyroba_mwh"],"Vlastní MWh":r["vlastni_mwh"],
                   "Přetoky MWh":r["pretoky_mwh"],"Úspora el. Kč":r["uspora_el"],
                   "Příjem přetoky Kč":r["uspora_pretoky"],"Úspora celkem Kč":r["uspora_celkem"],
                   "Splátka Kč":r["splatka"],"Čistý přínos Kč":r["cisty_prinos"],
                   "Kumulativní Kč":r["kumulativni"],"Cena VT Kč/kWh":r["cena_vt"]} for r in cf])

def hl(row):
    if nav and row["Rok"]==nav: return ["background-color:#d4edda"]*len(row)
    if row["Kumulativní Kč"]<0: return ["background-color:#fff3cd"]*len(row)
    return [""]*len(row)

st.dataframe(df.style.apply(hl,axis=1).format({"Výroba MWh":"{:.2f}","Vlastní MWh":"{:.2f}","Přetoky MWh":"{:.2f}","Úspora el. Kč":"{:,.0f}","Příjem přetoky Kč":"{:,.0f}","Úspora celkem Kč":"{:,.0f}","Splátka Kč":"{:,.0f}","Čistý přínos Kč":"{:,.0f}","Kumulativní Kč":"{:,.0f}","Cena VT Kč/kWh":"{:.3f}"}),use_container_width=True,hide_index=True)

st.divider()

# ── DETAIL INVESTICE ──────────────────────────────────────────────
st.subheader("💰 Detail investice a výnosů")
di1,di2=st.columns(2)
with di1:
    st.markdown("**Investice**")
    st.write(f"• FVE {vykon} kWp × {cena_kwp:,} Kč/kWp: **{cena_fve:,.0f} Kč**")
    if cena_bat>0: st.write(f"• Baterie {bat} kWh × {cena_kwh_bat:,} Kč/kWh: **{cena_bat:,.0f} Kč**")
    if cena_mericu>0: st.write(f"• Podružné měřiče ({pocet_bytu}×10 000 Kč): **{cena_mericu:,.0f} Kč**")
    st.write(f"• **Celková investice: {cena_invest:,.0f} Kč**")
    if bonus>0: st.write(f"• Bonus NZÚ (nízkopříjmové): **− {bonus:,.0f} Kč**")
    if scenar!="vlastni":
        st.write(f"• Vlastní zdroje: **{vlastni_cast:,.0f} Kč**")
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_cast:,.0f} Kč**")
        st.write(f"• Roční splátka: **{rocni_spl:,.0f} Kč** ({splatnost} let)")
with di2:
    st.markdown("**Výnosy rok 1**")
    _nazev_mod = {'spolecne':'Jen společné prostory','jom':'Sjednocení odběrných míst','edc':'EDC komunitní sdílení'}[model]
    st.write(f"• Model: **{_nazev_mod}**")
    st.write(f"• Profil: **{PROFILY[profil]['nazev']}**")
    st.write(f"• Vlastní spotřeba FVE+bat: **{sim['vlastni_kwh']:,.0f} kWh** ({sim['mira_vs']*100:.0f} % výroby)")
    st.write(f"• Soběstačnost: **{sim['mira_sob']*100:.0f} %** spotřeby pokryto z FVE")
    st.write(f"• Úspora elektřina: **{rok1['uspora_el']:,.0f} Kč/rok**")
    st.write(f"• Přetoky: **{sim['pretoky_kwh']:,.0f} kWh** @ {cena_pretoky:.2f} Kč → **{rok1['uspora_pretoky']:,.0f} Kč/rok**")
    if uspora_jist>0: st.write(f"• Úspora distribuce (JOM): **{uspora_jist:,.0f} Kč/rok**")
    st.write(f"• **Celkem: {rok1['uspora_celkem']:,.0f} Kč/rok**")
    st.write(f"• Na byt: **{uspora_byt_mesic*12:,.0f} Kč/rok** · **{uspora_byt_mesic:.0f} Kč/měs**")

# ── NZÚ INFO ──────────────────────────────────────────────────────
st.divider()
st.subheader("🏛️ Státní podpora NZÚ 2026")
ni1,ni2=st.columns(2)
with ni1:
    st.markdown("**Co existuje pro SVJ (dle sfzp.gov.cz):**")
    st.write("✅ **Bezúročný úvěr NZÚ** — od září 2026, splácení až 25 let, úroky hradí stát")
    st.write("✅ **Bonus za zranitelné domácnosti** — finanční příspěvek za byty se superdávkou")
    st.write("✅ **NZÚ Light** — přímá dotace jen pro nízkopříjmové domácnosti")
with ni2:
    st.markdown("**Další technologie (bezúročný úvěr):**")
    st.write("• Zateplení fasády a střechy")
    st.write("• Výměna oken a dveří")
    st.write("• Tepelné čerpadlo")
    st.write("• Rekuperace")
    st.info("📋 Přesné podmínky a výše podpory vždy ověřte na **[novazelenausporam.cz](https://novazelenausporam.cz)** nebo u energetického poradce NZÚ.")

st.divider()
st.caption(
    "⚠️ Orientační výpočty — 15minutová simulace. "
    "Profily spotřeby: OTE ČR — Typové diagramy dodávek elektřiny (TDD4). "
    "Solární data: PVGIS TMY © Evropská komise, JRC. "
    "Ceny dle ceníků ČEZ, E.ON, PRE od 1.1.2026 (s DPH 21 %, POZE=0 Kč). "
    "Bezúročný úvěr NZÚ — žádosti od září 2026. "
    "EDC iterační sdílení — registrace na edc.cz. "
    "Zdroj NZÚ: sfzp.gov.cz"
)
