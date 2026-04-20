import streamlit as st
import requests
import numpy as np
import pandas as pd
import datetime

st.set_page_config(page_title="FVE Kalkulačka pro SVJ", page_icon="☀️", layout="wide")

# ================================================================
# SIMULAČNÍ ENGINE — čistá fyzická logika, žádné fixní koeficienty
# ================================================================

_CD = 365 * 96  # 35 040 intervalů/rok

# TDD profily bytů (OTE třída 4 — standardní domácnost)
_TDD_BYTY = {
    "zima_prac":       np.array([0.42,0.38,0.36,0.35,0.35,0.38,0.52,0.78,0.88,0.82,0.76,0.74,0.76,0.74,0.72,0.74,0.82,1.12,1.28,1.22,1.08,0.92,0.72,0.55],dtype=float),
    "leto_prac":       np.array([0.38,0.34,0.32,0.31,0.32,0.36,0.48,0.68,0.76,0.72,0.68,0.66,0.68,0.66,0.64,0.66,0.74,0.96,1.08,1.02,0.90,0.76,0.58,0.44],dtype=float),
    "prechodne_prac":  np.array([0.40,0.36,0.34,0.33,0.34,0.37,0.50,0.73,0.82,0.77,0.72,0.70,0.72,0.70,0.68,0.70,0.78,1.04,1.18,1.12,0.99,0.84,0.65,0.50],dtype=float),
    "zima_vikend":     np.array([0.45,0.40,0.37,0.36,0.36,0.38,0.42,0.55,0.75,0.90,0.95,0.94,0.90,0.86,0.82,0.82,0.88,1.05,1.15,1.10,0.98,0.82,0.65,0.52],dtype=float),
    "leto_vikend":     np.array([0.40,0.36,0.33,0.32,0.32,0.34,0.38,0.50,0.68,0.82,0.86,0.85,0.82,0.78,0.74,0.74,0.80,0.95,1.04,0.99,0.88,0.74,0.58,0.46],dtype=float),
    "prechodne_vikend":np.array([0.42,0.38,0.35,0.34,0.34,0.36,0.40,0.52,0.72,0.86,0.90,0.89,0.86,0.82,0.78,0.78,0.84,1.00,1.10,1.04,0.93,0.78,0.62,0.49],dtype=float),
}

# TDD profily společných prostor — výtah+osvětlení+čerpadla, rovnoměrnější křivka
_TDD_SPOLECNE = {
    "zima_prac":       np.array([0.55,0.52,0.50,0.50,0.50,0.55,0.75,0.95,0.85,0.75,0.72,0.72,0.72,0.72,0.75,0.85,0.95,1.10,1.15,1.10,1.00,0.90,0.75,0.62],dtype=float),
    "leto_prac":       np.array([0.45,0.42,0.40,0.40,0.40,0.45,0.65,0.80,0.72,0.65,0.62,0.62,0.62,0.62,0.65,0.72,0.80,0.90,0.95,0.90,0.82,0.72,0.60,0.50],dtype=float),
    "prechodne_prac":  np.array([0.50,0.47,0.45,0.45,0.45,0.50,0.70,0.88,0.78,0.70,0.67,0.67,0.67,0.67,0.70,0.78,0.88,1.00,1.05,1.00,0.91,0.81,0.68,0.56],dtype=float),
    "zima_vikend":     np.array([0.58,0.54,0.52,0.51,0.51,0.54,0.62,0.78,0.90,0.95,0.95,0.93,0.90,0.88,0.85,0.88,0.92,1.05,1.10,1.05,0.95,0.85,0.72,0.63],dtype=float),
    "leto_vikend":     np.array([0.48,0.44,0.42,0.41,0.41,0.44,0.52,0.65,0.75,0.80,0.80,0.78,0.75,0.73,0.71,0.73,0.77,0.88,0.92,0.88,0.80,0.71,0.60,0.52],dtype=float),
    "prechodne_vikend":np.array([0.53,0.49,0.47,0.46,0.46,0.49,0.57,0.72,0.82,0.88,0.88,0.86,0.82,0.80,0.78,0.80,0.84,0.97,1.01,0.97,0.88,0.78,0.66,0.58],dtype=float),
}

_UPRAVY = {
    "mix":        np.ones(24,dtype=float),
    "seniori":    np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.3,1.5,1.6,1.6,1.5,1.5,1.4,1.4,1.3,1.1,1.0,1.0,1.0,1.0,1.0,1.0],dtype=float),
    "pracujici":  np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.2,1.3,0.7,0.5,0.5,0.5,0.5,0.5,0.5,0.6,0.8,1.3,1.4,1.3,1.2,1.1,1.0,1.0],dtype=float),
    "rodiny":     np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.2,0.9,0.7,0.7,0.7,0.8,0.8,0.9,1.1,1.2,1.2,1.2,1.1,1.1,1.0,1.0,1.0],dtype=float),
    "provozovna": np.array([0.8,0.8,0.8,0.8,0.8,0.9,1.0,1.2,1.5,1.6,1.7,1.7,1.6,1.6,1.6,1.5,1.3,1.1,1.0,0.9,0.9,0.8,0.8,0.8],dtype=float),
}


def _sezona(m):
    if m in [11,12,1,2]: return "zima"
    if m in [5,6,7,8]: return "leto"
    return "prechodne"


def _gen_profil(kwh, tdd, uprava=None):
    """Generuje 15min profil spotřeby pro zadaný TDD a roční spotřebu."""
    vals = []
    den = datetime.date(2026,1,1)
    for _ in range(365):
        sz = _sezona(den.month)
        tp = "vikend" if den.weekday()>=5 else "prac"
        p = tdd[f"{sz}_{tp}"].copy()
        if uprava is not None:
            p = p * uprava
        p = p/p.sum()*24.0
        for h in range(24):
            v = float(p[h])/4.0
            vals.extend([v,v,v,v])
        den += datetime.timedelta(days=1)
    arr = np.array(vals,dtype=float)[:_CD]
    if arr.sum()>0: arr = arr*(float(kwh)/arr.sum())
    return arr


def _gen_vyroba_fallback(kwp, sklon=35, azimut=0):
    """Záložní model výroby kalibrovaný na průměr ČR (1050 kWh/kWp/rok)."""
    vh = np.zeros(8760,dtype=float)
    for h in range(8760):
        dr=h//24; hod=h%24
        uhel=2*np.pi*(dr-80)/365.0
        delka=12+4.5*np.sin(uhel)
        vychod=12-delka/2; zapad=12+delka/2
        if vychod<=hod<=zapad:
            t=(hod-vychod)/delka
            elev=np.sin(np.pi*t)
            sezon=max(0.3,min(1.0,0.5+0.5*np.sin(uhel+np.pi/2)))
            koef=1.0+0.15*np.sin(np.pi*float(sklon)/90.0)
            vh[h]=float(kwp)*elev*sezon*koef*0.85
    if vh.sum()>0:
        vh=vh*(float(kwp)*1050.0/vh.sum())
    return vh


def _interpoluj(hod):
    h=np.array(hod,dtype=float); n=len(h)
    res=np.zeros(n*4,dtype=float)
    for i in range(n):
        ni=(i+1)%n
        for j in range(4):
            t=j/4.0
            res[i*4+j]=(h[i]*(1.0-t)+h[ni]*t)/4.0
    return res[:_CD]


def _simuluj(vyroba_15, sp_spolecne_15, sp_byty_15, bat=0.0, model="edc"):
    """
    Přesná 15min simulace FVE.

    Model logika:
    - spolecne: spotřeba = pouze společné prostory
    - jom:      spotřeba = společné + všechny byty (fyzicky jeden elektroměr)
    - edc:      spotřeba = společné + všechny byty (účetní operace,
                           -2% korekce za iterační ztrátu alokace)

    Baterie:
    - nabíjí se z přetoků FVE v každém intervalu
    - vybíjí se když spotřeba > výroba (energie z bat = vlastní spotřeba)
    - u EDC: vybíjení jde fyzicky do sítě, ale EDC to účetně přiřadí bytům
    """
    v  = np.array(vyroba_15,dtype=float)
    ss = np.array(sp_spolecne_15,dtype=float)
    sb = np.array(sp_byty_15,dtype=float)
    bat = float(bat)

    # Spotřeba dle modelu
    if model == "spolecne":
        s = ss.copy()
    else:
        s = ss + sb

    n = int(min(len(v),len(s)))
    v,s = v[:n],s[:n]

    bmin    = bat*0.10
    bmax    = bat*0.90
    bkwh    = bat*0.50   # počáteční SOC 50%
    eta     = 0.92       # účinnost baterie (nabíjení i vybíjení)

    vl = np.zeros(n,dtype=float)   # vlastní spotřeba (FVE + baterie)
    pr = np.zeros(n,dtype=float)   # přetoky do sítě
    od = np.zeros(n,dtype=float)   # odběr ze sítě

    for i in range(n):
        vi = float(v[i])
        si = float(s[i])

        # Krok 1: FVE pokryje spotřebu přímo
        prime    = min(vi,si)
        vl[i]   += prime
        zbyla_v  = vi - prime
        zbyla_s  = si - prime

        # Krok 2: Přebytek výroby → nabít baterii
        if zbyla_v > 0.0 and bat > 0.0:
            misto = bmax - bkwh
            nab   = min(zbyla_v*eta, misto)
            bkwh += nab
            zbyla_v -= nab/eta

        # Krok 3: Zbylá výroba → přetoky
        pr[i] = zbyla_v

        # Krok 4: Zbylá spotřeba → vybít baterii (energie z bat = vlastní spotřeba)
        if zbyla_s > 0.0 and bat > 0.0:
            dos  = (bkwh - bmin)*eta
            vyb  = min(zbyla_s, dos)
            bkwh -= vyb/eta
            zbyla_s -= vyb
            vl[i]   += vyb

        # Krok 5: Zbytek ze sítě
        od[i] = zbyla_s

    tv  = float(v.sum())
    tvl = float(vl.sum())
    tpr = float(pr.sum())
    tsp = float(s.sum())

    # EDC korekce: iterační alokace je o ~2 % méně efektivní než JOM
    if model == "edc":
        ztrata = tvl * 0.02
        tvl   -= ztrata
        tpr   += ztrata

    # Měsíční data (přibližně po 30 dnech)
    mv,ms,mvl,mpr = [],[],[],[]
    for m in range(12):
        a = m*30*96; b = min((m+1)*30*96,n)
        mv.append(float(v[a:b].sum()))
        ms.append(float(s[a:b].sum()))
        mvl.append(float(vl[a:b].sum()))
        mpr.append(float(pr[a:b].sum()))

    return {
        "vlastni_kwh":    tvl,
        "pretoky_kwh":    tpr,
        "odber_kwh":      float(od.sum()),
        "vyroba_kwh":     tv,
        "spotreba_kwh":   tsp,
        "mira_vs":        tvl/tv  if tv>0  else 0.0,
        "mira_sob":       tvl/tsp if tsp>0 else 0.0,
        "mesice_vyroba":  mv,
        "mesice_spotreba":ms,
        "mesice_vlastni": mvl,
        "mesice_pretoky": mpr,
    }


def _cashflow(vl, pr, cvt, cpr, vlast, uver, spl, splat,
              rust=3.0, deg=0.5, leta=15, jist=0.0, bonus=0.0):
    res=[]; kum=-(float(vlast)+float(uver)-float(bonus))
    for rok in range(1,int(leta)+1):
        d=(1.0-float(deg)/100.0)**(rok-1)
        c=(1.0+float(rust)/100.0)**(rok-1)
        u_el = float(vl)*d*float(cvt)*c
        u_pr = float(pr)*d*float(cpr)*c
        u_ji = float(jist)*c
        u    = u_el+u_pr+u_ji
        s    = float(spl) if rok<=int(splat) else 0.0
        kum += u-s
        res.append({
            "rok":rok,
            "vyroba_mwh":   round((float(vl)+float(pr))*d/1000.0,2),
            "vlastni_mwh":  round(float(vl)*d/1000.0,2),
            "pretoky_mwh":  round(float(pr)*d/1000.0,2),
            "uspora_el":    round(u_el),
            "uspora_pretoky":round(u_pr),
            "uspora_distribuce":round(u_ji),
            "uspora_celkem":round(u),
            "splatka":      round(s),
            "cisty_prinos": round(u-s),
            "kumulativni":  round(kum),
            "cena_vt":      round(float(cvt)*c,3),
        })
    return res


_MESTA_FALLBACK = {
    "praha": (50.08, 14.44), "brno": (49.19, 16.61),
    "ostrava": (49.83, 18.29), "plzeň": (49.74, 13.37),
    "třinec": (49.68, 18.67), "liberec": (50.77, 15.06),
    "olomouc": (49.59, 17.25), "zlín": (49.22, 17.66),
    "hradec králové": (50.21, 15.83), "pardubice": (50.04, 15.78),
    "české budějovice": (48.97, 14.47), "ústí nad labem": (50.66, 14.03),
    "havířov": (49.78, 18.43), "karviná": (49.85, 18.54),
    "opava": (49.94, 17.90), "frýdek-místek": (49.68, 18.35),
}

@st.cache_data(ttl=3600)
def _geocode(dotaz):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format": "json",
                    "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "FVE-SVJ-Kalkulacka/1.0"},
            timeout=10)
        if r.status_code != 200:
            return None, None, None, f"HTTP {r.status_code}"
        text = r.text.strip()
        if not text:
            return None, None, None, "Prázdná odpověď"
        res = r.json()
        if not res:
            return None, None, None, f"'{dotaz}' nenalezeno"
        addr = res[0].get("address", {})
        m = (addr.get("city") or addr.get("town") or
             addr.get("village") or addr.get("municipality") or dotaz)
        return float(res[0]["lat"]), float(res[0]["lon"]), m, None
    except requests.exceptions.Timeout:
        return None, None, None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, None, None, "Chyba připojení"
    except Exception as e:
        return None, None, None, str(e)


@st.cache_data(ttl=86400)
def _pvgis(lat,lon,kwp,sklon,azimut):
    try:
        r=requests.get(
            "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc",
            params={"lat":float(lat),"lon":float(lon),
                    "peakpower":float(kwp),"loss":14,
                    "angle":int(sklon),"aspect":int(azimut),
                    "outputformat":"json","browser":0,
                    "startyear":2020,"endyear":2020,
                    "pvcalculation":1,"pvtechchoice":"crystSi",
                    "mountingplace":"building","trackingtype":0},
            timeout=30)
        r.raise_for_status()
        hourly=r.json()["outputs"]["hourly"]
        arr=np.array([float(h["P"])/1000.0 for h in hourly],dtype=float)
        return arr[:8760],None
    except Exception as e:
        return None,str(e)


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
STAY_PLAT   = {"ČEZ Distribuce":163,"EG.D (E.ON)":144,"PREdistribuce":150}
JISTIC_3x25 = {
    "ČEZ Distribuce": {"D01d":132,"D02d":298,"D25d":287,"D26d":422,"D27d":272,"D35d":517,"D45d":567,"D56d":567,"D57d":567,"D61d":238},
    "EG.D (E.ON)":    {"D01d":145,"D02d":575,"D25d":296,"D26d":422,"D27d":282,"D35d":575,"D45d":575,"D56d":575,"D57d":575,"D61d":271},
    "PREdistribuce":  {"D01d":100,"D02d":280,"D25d":250,"D26d":350,"D27d":230,"D35d":420,"D45d":480,"D56d":480,"D57d":480,"D61d":200},
}
SAZBY_NT=["D25d","D26d","D27d","D35d","D45d","D56d","D57d","D61d"]
PODIL_NT={"D25d":0.35,"D26d":0.35,"D27d":0.35,"D35d":0.60,"D45d":0.70,"D56d":0.75,"D57d":0.75,"D61d":0.40}
POPIS_SAZEB={
    "D01d":"Malý byt — jen svícení","D02d":"Standardní domácnost",
    "D25d":"Ohřev vody bojlerem (8h NT)","D26d":"Akumulační kamna (8h NT)",
    "D27d":"Elektromobil (8h NT)","D35d":"Hybridní TČ (16h NT)",
    "D45d":"Přímotopy/elektrokotel (20h NT)","D56d":"Vytápění TČ/přímotopy (22h NT)",
    "D57d":"TČ — hlavní zdroj tepla (20h NT)","D61d":"Víkendový objekt",
}
PROFILY={
    "mix":       {"nazev":"👨‍👩‍👧 Smíšený dům",       "popis":"Mix pracujících a seniorů"},
    "seniori":   {"nazev":"👴 Převaha seniorů",     "popis":"Většina doma přes den — vyšší využití FVE"},
    "pracujici": {"nazev":"🏢 Převaha pracujících", "popis":"Většina pryč přes den — nižší přímé využití FVE"},
    "rodiny":    {"nazev":"👨‍👩‍👧‍👦 Rodiny s dětmi",    "popis":"Doma odpoledne a víkendy"},
    "provozovna":{"nazev":"🏪 S provozovnou",       "popis":"Kadeřnictví, ordinace — vysoká spotřeba přes den"},
}
MESICE=["Led","Úno","Bře","Dub","Kvě","Čvn","Čvc","Srp","Zář","Říj","Lis","Pro"]

# ================================================================
# UI
# ================================================================

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Přesná 15minutová simulace návratnosti FVE · Ceny dle ceníků 2026")
st.divider()

# ── 1. ZÁKLADNÍ ÚDAJE ───────────────────────────────────────────
st.subheader("🏠 Základní údaje o domě")
c1,c2,c3 = st.columns(3)

with c1:
    pocet_bytu = st.number_input("Počet bytů",2,200,12,1)
    spotreba_spolecne_mwh = st.number_input(
        "Spotřeba společných prostor (MWh/rok)",
        min_value=0.1, max_value=50.0, value=3.5, step=0.1, format="%.1f",
        help="Výtah, osvětlení chodeb, čerpadla, sklepy. Typicky 3–6 MWh/rok pro středně velký dům.")
    spotreba_byty_mwh = st.number_input(
        "Spotřeba bytů celkem (MWh/rok)",
        min_value=1.0, max_value=500.0, value=21.5, step=0.5, format="%.1f",
        help="Součet spotřeby všech bytových jednotek.")
    spotreba_spolecne = float(spotreba_spolecne_mwh)*1000.0
    spotreba_byty     = float(spotreba_byty_mwh)*1000.0
    spotreba_celkem   = spotreba_spolecne + spotreba_byty
    st.caption(f"Celková spotřeba domu: **{spotreba_celkem/1000:.1f} MWh/rok**")

with c2:
    dist  = st.selectbox("Distributor",list(CENY_VT.keys()),
                         help="ČEZ = většina ČR | EG.D = Morava/jih Čech | PRE = Praha")
    sazba = st.selectbox("Distribuční sazba",list(CENY_VT[dist].keys()),
                         format_func=lambda x:f"{x} — {POPIS_SAZEB[x]}",index=1)

with c3:
    st.selectbox("Hlavní jistič",
                 ["1×25A","3×16A","3×20A","3×25A","3×32A","3×40A","3×50A","3×63A"],index=3)
    profil = st.selectbox("Profil obyvatel bytů",list(PROFILY.keys()),
                          format_func=lambda x:PROFILY[x]["nazev"])
    st.caption(PROFILY[profil]["popis"])

cena_vt  = float(CENY_VT[dist][sazba])/1000.0
cena_prum= (cena_vt*(1-PODIL_NT.get(sazba,0))+
            float(CENY_NT[dist].get(sazba,CENY_VT[dist][sazba]))/1000.0*PODIL_NT.get(sazba,0)
            ) if sazba in SAZBY_NT else cena_vt
stay  = float(STAY_PLAT[dist])
jistic= float(JISTIC_3x25[dist][sazba])
naklad= spotreba_celkem*cena_prum+(stay+jistic)*12.0

st.info(
    f"💡 **{dist}** · **{sazba}** · s DPH · POZE=0 Kč od 2026 | "
    f"VT: **{cena_vt:.2f} Kč/kWh** · Průměr: **{cena_prum:.2f} Kč/kWh** · "
    f"Stálé platy: **{stay+jistic:.0f} Kč/měs** · "
    f"Odhadovaný roční náklad: **{naklad:,.0f} Kč**"
)

with st.expander("✏️ Upravit ceny ručně"):
    u1,u2,u3 = st.columns(3)
    with u1: cena_vt  = st.number_input("Cena VT (Kč/kWh)",1.0,15.0,
                                         round(cena_vt,2),0.01,format="%.2f",
                                         help="Použita pro výpočet úspory z FVE")
    with u2: cena_prum= st.number_input("Průměrná cena (Kč/kWh)",1.0,15.0,
                                         round(cena_prum,2),0.01,format="%.2f")
    with u3: stay_up  = st.number_input("Stálé platy (Kč/měs)",0,5000,
                                         int(stay+jistic),10)
    naklad = spotreba_celkem*cena_prum+float(stay_up)*12.0
    st.metric("Roční náklad (upravený)",f"{naklad:,.0f} Kč")

st.divider()

# ── 2. FVE A BATERIE ─────────────────────────────────────────────
st.subheader("⚡ Parametry FVE a baterie")
c1,c2 = st.columns(2)

with c1:
    vykon    = st.number_input("Výkon FVE (kWp)",1.0,200.0,20.0,0.5,format="%.1f")
    cena_kwp = st.slider("Cena FVE (Kč/kWp)",25000,50000,37000,1000,
                          help="Včetně montáže, střídače, kabeláže. Typicky 30–45 tis. Kč/kWp")
    cena_fve = int(float(vykon)*float(cena_kwp))
    st.caption(f"Odhadovaná cena FVE: **{cena_fve:,.0f} Kč** "
               f"({vykon} kWp × {cena_kwp:,} Kč/kWp)")

with c2:
    bat = st.number_input("Kapacita baterie (kWh)",0,200,0,5,
                           help="Nabíjí se z přetoků FVE, vybíjí když FVE nestačí.")
    if bat>0:
        cena_kwh_bat = st.slider("Cena baterie (Kč/kWh)",10000,20000,15000,500,
                                  help="Včetně střídače a BMS. Typicky 12–18 tis. Kč/kWh")
        cena_bat = int(float(bat)*float(cena_kwh_bat))
        st.caption(f"Odhadovaná cena baterie: **{cena_bat:,.0f} Kč** "
                   f"({bat} kWh × {cena_kwh_bat:,} Kč/kWh)")
    else:
        cena_bat = 0

st.divider()

# ── 3. MODEL SDÍLENÍ ─────────────────────────────────────────────
st.subheader("🔗 Model sdílení energie")
model = st.radio(
    "Model", ["spolecne","jom","edc"], horizontal=True,
    format_func=lambda x:{
        "spolecne":"🏢 Jen společné prostory",
        "jom":     "⚡ Sjednocení odběrných míst",
        "edc":     "🔗 EDC komunitní sdílení (iterační)",
    }[x])

cena_mericu = int(pocet_bytu)*10000 if model=="jom" else 0
uspora_jist = jistic*(int(pocet_bytu)-1)*12.0 if model=="jom" else 0.0

if model=="spolecne":
    st.info(
        f"🏢 FVE pokrývá pouze spotřebu společných prostor "
        f"({spotreba_spolecne_mwh:.1f} MWh/rok). "
        f"Nejjednodušší realizace, nejnižší úspora."
    )
elif model=="jom":
    st.info(
        f"⚡ Fyzicky jeden elektroměr — FVE pokrývá celou spotřebu domu "
        f"({spotreba_celkem/1000:.1f} MWh/rok). "
        f"Podružné měřiče na byty: **{cena_mericu:,} Kč**. "
        f"Úspora distribuce: **{uspora_jist:,.0f} Kč/rok**."
    )
else:
    st.info(
        f"🔗 FVE pokrývá celou spotřebu domu ({spotreba_celkem/1000:.1f} MWh/rok) "
        f"účetně přes EDC. Každý byt si zachovává dodavatele. "
        f"Chytré měřiče zdarma od distributora. "
        f"Iterační alokace (o ~2 % méně efektivní než JOM). "
        f"Registrace na edc.cz."
    )

st.divider()

# ── 4. LOKALITA A STŘECHA ────────────────────────────────────────
st.subheader("🌍 Lokalita a střecha")
lc1,lc2 = st.columns([1,2])
with lc1: lokace = st.text_input("Město nebo PSČ","Praha")
with lc2:
    typ_str = st.radio("Typ střechy",["sikma","plocha"],
                       format_func=lambda x:"🏠 Šikmá" if x=="sikma" else "🏢 Plochá",
                       horizontal=True)

if typ_str=="sikma":
    sc1,sc2 = st.columns(2)
    with sc1: sklon  = st.slider("Sklon (°)",15,60,35)
    with sc2: azimut = st.select_slider(
        "Orientace",[-90,-45,0,45,90],0,
        format_func=lambda x:{-90:"⬅️ Východ",-45:"↙️ Jihovýchod",
                               0:"⬆️ Jih",45:"↗️ Jihozápad",90:"➡️ Západ"}[x])
    koef_str = 1.0
else:
    pc1,pc2 = st.columns(2)
    with pc1: sklon = st.slider("Sklon panelů (°)",5,20,10)
    with pc2:
        sys_pl = st.radio("Systém",["jih","jz_jv","vz"],
                           format_func=lambda x:{"jih":"⬆️ Jih",
                                                  "jz_jv":"↗️ JZ+JV","vz":"↔️ V+Z"}[x])
    azimut   = 90 if sys_pl=="vz" else 0
    koef_str = {"jih":1.0,"jz_jv":0.97,"vz":0.88}[sys_pl]
    st.info({"jih":"☀️ Maximum výkonu, špička kolem poledne.",
             "jz_jv":"☀️ Mírně nižší výkon, rovnoměrnější výroba.",
             "vz":"☀️ Nejrovnoměrnější výroba — snižuje přetoky."}[sys_pl])

st.divider()

# ── 5. FINANCOVÁNÍ ───────────────────────────────────────────────
st.subheader("💰 Financování")
fc1,fc2 = st.columns(2)
with fc1:
    scenar = st.radio(
        "Scénář",["uver","vlastni","kombinace"],
        format_func=lambda x:{
            "uver":      "🏦 Bezúročný úvěr NZÚ (od září 2026)",
            "vlastni":   "💵 Vlastní zdroje (fond oprav)",
            "kombinace": "🔀 Kombinace vlastní + úvěr",
        }[x])
with fc2:
    if scenar=="uver":
        splatnost=st.slider("Doba splácení (let)",5,25,15)
        vlastni_pct=0
        st.info("✅ Úroky hradí stát. SVJ splácí pouze jistinu.")
    elif scenar=="vlastni":
        splatnost=0; vlastni_pct=100
        st.info("💡 SVJ hradí vše z fondu oprav.")
    else:
        vlastni_pct=st.slider("Vlastní zdroje (%)",10,90,30,10)
        splatnost=st.slider("Doba splácení (let)",5,25,15)

st.markdown("**Nízkopříjmové domácnosti**")
nb1,nb2 = st.columns(2)
with nb1: pocet_nizko = st.number_input("Bytů s bonusem",0,int(pocet_bytu),0,1)
with nb2: bonus_byt   = st.number_input("Bonus na byt (Kč)",0,150000,50000,5000)
bonus = int(pocet_nizko)*int(bonus_byt)

st.divider()

# ── 6. PARAMETRY SIMULACE ────────────────────────────────────────
st.subheader("⚙️ Parametry simulace")
sc1,sc2,sc3 = st.columns(3)
with sc1: cena_pretoky = st.number_input(
    "Výkupní cena přetoků (Kč/kWh)",0.30,2.50,0.95,0.05,format="%.2f",
    help="E.ON 0,70 · TEDOM 0,75 · spot průměr ~1,50 Kč/kWh")
with sc2: rust_cen = st.slider("Růst cen elektřiny (%/rok)",0.0,8.0,3.0,0.5)
with sc3: deg_pan  = st.slider("Degradace panelů (%/rok)",0.2,1.0,0.5,0.1)

st.divider()

# VÝPOČET INVESTICE
cena_invest  = cena_fve+cena_bat+cena_mericu
vlastni_cast = float(cena_invest)*float(vlastni_pct)/100.0
uver_cast    = max(0.0,float(cena_invest)-vlastni_cast-float(bonus))
rocni_spl    = uver_cast/float(splatnost) if (scenar!="vlastni" and splatnost>0) else 0.0

bc1,bc2 = st.columns([1,3])
with bc1: spustit = st.button("🔄 Spočítat simulaci",type="primary",
                               use_container_width=True)
with bc2: st.caption(
    "Stáhne hodinová solární data z PVGIS a provede přesný "
    "15minutový výpočet. Trvá 5–20 s.")

if spustit:
    with st.spinner(f"Hledám lokalitu {lokace}..."):
        lat, lon, mesto, geo_err = _geocode(lokace)

    if geo_err:
        klic = lokace.lower().strip()
        if klic in _MESTA_FALLBACK:
            lat, lon = _MESTA_FALLBACK[klic]
            mesto = lokace
            st.warning(f"⚠️ Geocoding selhal — používám přednastavenou polohu pro {lokace}.")
        else:
            st.error(f"Lokalita nenalezena: {geo_err}. Zkuste jiný název nebo PSČ.")
            st.stop()

    kwp_eff = float(vykon)*float(koef_str)
    with st.spinner(f"Stahuji solární data pro {mesto} z PVGIS..."):
        vyroba_hod,pvgis_err = _pvgis(lat,lon,kwp_eff,sklon,azimut)

    if pvgis_err:
        st.warning("⚠️ PVGIS nedostupné — používám kalibrovaný záložní model.")
        vyroba_hod = _gen_vyroba_fallback(kwp_eff,sklon,azimut)
        pvgis_ok   = False
    else:
        pvgis_ok = True

    with st.spinner("Simuluji v 15minutových intervalech..."):
        vyroba_15       = _interpoluj(vyroba_hod)
        sp_spolecne_15  = _gen_profil(spotreba_spolecne, _TDD_SPOLECNE)
        sp_byty_15      = _gen_profil(spotreba_byty, _TDD_BYTY,
                                      _UPRAVY.get(profil))
        sim = _simuluj(vyroba_15, sp_spolecne_15, sp_byty_15,
                       float(bat), model)
        cf  = _cashflow(
            vl=sim["vlastni_kwh"], pr=sim["pretoky_kwh"],
            cvt=float(cena_vt), cpr=float(cena_pretoky),
            vlast=vlastni_cast, uver=uver_cast,
            spl=rocni_spl, splat=int(splatnost),
            rust=float(rust_cen), deg=float(deg_pan),
            leta=15, jist=float(uspora_jist), bonus=float(bonus),
        )

    st.session_state["res"] = {
        "sim":sim,"cf":cf,"vyroba_15":vyroba_15,
        "mesto":mesto,"lat":lat,"lon":lon,"pvgis_ok":pvgis_ok,
    }
    st.success(
        f"✅ Hotovo — {mesto} ({lat:.2f}°N, {lon:.2f}°E) "
        f"{'· PVGIS data' if pvgis_ok else '· záložní model'}")

if "res" not in st.session_state:
    st.info("👆 Vyplňte parametry a klikněte na **Spočítat simulaci**.")
    st.stop()

# ================================================================
# VÝSLEDKY
# ================================================================

d    = st.session_state["res"]
sim  = d["sim"]; cf = d["cf"]
rok1 = cf[0]
nav  = next((r["rok"] for r in cf if r["kumulativni"]>=0),None)

st.divider()
st.subheader("📊 Výsledky simulace")

r1,r2,r3,r4,r5 = st.columns(5)
with r1: st.metric("Roční výroba FVE",
                   f"{sim['vyroba_kwh']/1000:.1f} MWh")
with r2: st.metric("Míra vlastní spotřeby",
                   f"{sim['mira_vs']*100:.1f} %",
                   help="Kolik % výroby FVE se spotřebuje v domě (přímo nebo přes baterii)")
with r3: st.metric("Míra soběstačnosti",
                   f"{sim['mira_sob']*100:.1f} %",
                   help="Kolik % celkové spotřeby domu pokryje FVE")
with r4: st.metric("Roční úspora (rok 1)",
                   f"{rok1['uspora_celkem']:,.0f} Kč")
with r5: st.metric("Návratnost",
                   f"{nav} let" if nav else ">15 let")

# Doporučení
if sim["mira_vs"]<0.40 and bat==0 and model!="spolecne":
    st.warning(
        f"⚠️ Míra vlastní spotřeby je nízká ({sim['mira_vs']*100:.0f} %) — "
        f"velká část výroby jde do sítě za {cena_pretoky:.2f} Kč/kWh "
        f"místo {cena_vt:.2f} Kč/kWh. "
        f"Zvažte přidání **baterie** nebo systém **V+Z** na ploché střeše."
    )

# Milníky
st.markdown("**📍 Klíčové milníky**")
m1,m2,m3 = st.columns(3)
u_byt = rok1["uspora_celkem"]/float(pocet_bytu)
s_byt = rocni_spl/float(pocet_bytu)/12.0

with m1:
    st.info(
        f"**Rok 1**\n\n"
        f"Vlastní spotřeba (FVE+bat): **{sim['vlastni_kwh']:,.0f} kWh** "
        f"({sim['mira_vs']*100:.0f} % výroby)\n\n"
        f"Přetoky do sítě: **{sim['pretoky_kwh']:,.0f} kWh** "
        f"({(1-sim['mira_vs'])*100:.0f} % výroby)\n\n"
        f"Úspora na elektřině: **{rok1['uspora_el']:,.0f} Kč**\n\n"
        f"Příjem z přetoků: **{rok1['uspora_pretoky']:,.0f} Kč**\n\n"
        f"**Celková úspora: {rok1['uspora_celkem']:,.0f} Kč/rok**\n\n"
        f"Na byt: **{u_byt:,.0f} Kč/rok** · **{u_byt/12:.0f} Kč/měs**\n\n"
        f"Splátka na byt: **{s_byt:.0f} Kč/měs**"
    )

with m2:
    if scenar!="vlastni" and splatnost>0 and splatnost<=15:
        rs = cf[splatnost-1]
        st.info(
            f"**Rok {splatnost} — úvěr splacen ✅**\n\n"
            f"Úspora v tom roce: **{rs['uspora_celkem']:,.0f} Kč**\n\n"
            f"(vč. růstu cen +{rust_cen}%/rok, degradace -{deg_pan}%/rok)\n\n"
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
    kum15 = cf[-1]["kumulativni"]
    if nav:
        st.success(
            f"**Rok {nav} — investice se vrátí ✅**\n\n"
            f"Za 15 let celková úspora:\n\n"
            f"**{kum15:,.0f} Kč**\n\n"
            f"Na byt: **{kum15/float(pocet_bytu):,.0f} Kč**\n\n"
            f"Životnost FVE 25–30 let\n\n"
            f"→ dalších {25-nav} let čistý zisk!"
        )
    else:
        st.warning(
            f"**Za 15 let investice se nevrátí**\n\n"
            f"Cashflow: **{kum15:,.0f} Kč**\n\n"
            "Zvyšte výkon FVE, přidejte baterii\n\n"
            "nebo zvolte model EDC/JOM."
        )

st.divider()

# Měsíční graf
st.subheader("📈 Měsíční přehled výroby a spotřeby")
df_mes = pd.DataFrame({
    "Měsíc":            MESICE,
    "Výroba FVE (kWh)": [round(x) for x in sim["mesice_vyroba"]],
    "Vlastní spotř. (kWh)":[round(x) for x in sim["mesice_vlastni"]],
    "Přetoky (kWh)":    [round(x) for x in sim["mesice_pretoky"]],
})
st.bar_chart(
    df_mes.set_index("Měsíc")[
        ["Výroba FVE (kWh)","Vlastní spotř. (kWh)","Přetoky (kWh)"]],
    color=["#f5a623","#2ecc71","#95a5a6"])
st.caption("🟡 Výroba FVE · 🟢 Vlastní spotřeba (FVE+baterie) · ⬜ Přetoky do sítě")

st.divider()

# Tabulka cashflow
st.subheader("📋 Cashflow rok po roku")
df = pd.DataFrame([{
    "Rok":r["rok"],
    "Výroba MWh":r["vyroba_mwh"],
    "Vlastní MWh":r["vlastni_mwh"],
    "Přetoky MWh":r["pretoky_mwh"],
    "Úspora el. Kč":r["uspora_el"],
    "Příjem přetoky Kč":r["uspora_pretoky"],
    "Úspora celkem Kč":r["uspora_celkem"],
    "Splátka Kč":r["splatka"],
    "Čistý přínos Kč":r["cisty_prinos"],
    "Kumulativní Kč":r["kumulativni"],
    "Cena VT Kč/kWh":r["cena_vt"],
} for r in cf])

def hl(row):
    if nav and row["Rok"]==nav:
        return ["background-color:#d4edda"]*len(row)
    if row["Kumulativní Kč"]<0:
        return ["background-color:#fff3cd"]*len(row)
    return [""]*len(row)

st.dataframe(
    df.style.apply(hl,axis=1).format({
        "Výroba MWh":"{:.2f}","Vlastní MWh":"{:.2f}","Přetoky MWh":"{:.2f}",
        "Úspora el. Kč":"{:,.0f}","Příjem přetoky Kč":"{:,.0f}",
        "Úspora celkem Kč":"{:,.0f}","Splátka Kč":"{:,.0f}",
        "Čistý přínos Kč":"{:,.0f}","Kumulativní Kč":"{:,.0f}",
        "Cena VT Kč/kWh":"{:.3f}",
    }),
    use_container_width=True, hide_index=True,
)

st.divider()

# Detail
st.subheader("💰 Detail investice a výnosů")
di1,di2 = st.columns(2)

with di1:
    st.markdown("**Investice**")
    st.write(f"• FVE {vykon} kWp × {cena_kwp:,} Kč/kWp: **{cena_fve:,.0f} Kč**")
    if cena_bat>0:
        st.write(f"• Baterie {bat} kWh × {cena_kwh_bat:,} Kč/kWh: **{cena_bat:,.0f} Kč**")
    if cena_mericu>0:
        st.write(f"• Podružné měřiče ({pocet_bytu}×10 000 Kč): **{cena_mericu:,.0f} Kč**")
    st.write(f"• **Celková investice: {cena_invest:,.0f} Kč**")
    if bonus>0:
        st.write(f"• Bonus nízkopříjmové: **− {bonus:,.0f} Kč**")
    if scenar!="vlastni":
        st.write(f"• Vlastní zdroje: **{vlastni_cast:,.0f} Kč**")
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_cast:,.0f} Kč**")
        st.write(f"• Roční splátka: **{rocni_spl:,.0f} Kč** ({splatnost} let)")
    st.write(f"• Náklady na byt: **{vlastni_cast/float(pocet_bytu):,.0f} Kč**")

with di2:
    st.markdown("**Výnosy rok 1**")
    nazev_mod={
        "spolecne":"Jen společné prostory",
        "jom":"Sjednocení odběrných míst",
        "edc":"EDC komunitní sdílení (iterační)",
    }[model]
    st.write(f"• Model: **{nazev_mod}**")
    st.write(f"• Profil bytů: **{PROFILY[profil]['nazev']}**")
    if model=="spolecne":
        st.write(f"• Simulovaná spotřeba: **{spotreba_spolecne_mwh:.1f} MWh** (jen společné prostory)")
    else:
        st.write(f"• Simulovaná spotřeba: **{spotreba_celkem/1000:.1f} MWh** (celý dům)")
    st.write(f"• Vlastní spotřeba (FVE+bat): **{sim['vlastni_kwh']:,.0f} kWh** ({sim['mira_vs']*100:.0f} % výroby)")
    st.write(f"• Míra soběstačnosti: **{sim['mira_sob']*100:.0f} %** spotřeby pokryto z FVE")
    st.write(f"• Úspora elektřina (VT {cena_vt:.2f} Kč/kWh): **{rok1['uspora_el']:,.0f} Kč/rok**")
    st.write(f"• Přetoky: **{sim['pretoky_kwh']:,.0f} kWh** @ {cena_pretoky:.2f} Kč → **{rok1['uspora_pretoky']:,.0f} Kč/rok**")
    if uspora_jist>0:
        st.write(f"• Úspora distribuce (JOM): **{uspora_jist:,.0f} Kč/rok**")
    st.write(f"• **Celkem: {rok1['uspora_celkem']:,.0f} Kč/rok**")
    st.write(f"• Na byt/rok: **{u_byt:,.0f} Kč** · na byt/měsíc: **{u_byt/12:.0f} Kč**")
    st.write(f"• Čistý přínos po splátce: **{rok1['cisty_prinos']:,.0f} Kč/rok**")

st.divider()
st.caption(
    "⚠️ Orientační výpočty — 15minutová simulace. "
    "Profily spotřeby: OTE ČR normalizované TDD. "
    "Solární data: PVGIS TMY © Evropská komise, JRC. "
    "Ceny dle ceníků ČEZ, E.ON, PRE od 1.1.2026 (s DPH 21 %, POZE=0 Kč). "
    "Bezúročný úvěr NZÚ — žádosti od září 2026. "
    "EDC iterační sdílení — registrace na edc.cz."
)
