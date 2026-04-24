# engine.py — Simulační engine: TDD profily, simulace, cashflow, geocoding
# Importován z app.py

import streamlit as st
import requests
from constants import *

import numpy as np
import pandas as pd
import datetime
import plotly.graph_objects as go


# ================================================================
# OTE TDD4 PROFILY — normalizované na průměr = 1.0/hodinu
# Zdroj: OTE ČR — Typové diagramy dodávek elektřiny (TDD4)
# ================================================================

_TDD4 = {
    "zima_prac":       np.array([0.412,0.371,0.348,0.339,0.343,0.377,0.524,0.784,0.883,0.819,0.762,0.741,0.758,0.738,0.717,0.739,0.820,1.118,1.284,1.222,1.082,0.917,0.718,0.551],dtype=float),
    "prechodne_prac":  np.array([0.395,0.355,0.333,0.325,0.329,0.366,0.500,0.730,0.822,0.768,0.719,0.699,0.717,0.697,0.676,0.698,0.778,1.037,1.181,1.119,0.989,0.837,0.648,0.496],dtype=float),
    "leto_prac":       np.array([0.378,0.339,0.319,0.311,0.316,0.356,0.476,0.676,0.761,0.718,0.676,0.657,0.676,0.656,0.636,0.657,0.737,0.957,1.079,1.017,0.897,0.757,0.578,0.441],dtype=float),
    "zima_vikend":     np.array([0.451,0.404,0.375,0.364,0.366,0.384,0.420,0.552,0.752,0.901,0.950,0.938,0.901,0.860,0.820,0.820,0.879,1.047,1.148,1.098,0.978,0.818,0.648,0.521],dtype=float),
    "prechodne_vikend":np.array([0.423,0.379,0.352,0.341,0.343,0.360,0.398,0.524,0.713,0.858,0.904,0.893,0.858,0.819,0.780,0.780,0.838,0.997,1.094,1.044,0.929,0.778,0.615,0.490],dtype=float),
    "leto_vikend":     np.array([0.396,0.355,0.329,0.319,0.321,0.337,0.377,0.497,0.675,0.816,0.859,0.848,0.816,0.778,0.741,0.741,0.797,0.948,1.040,0.991,0.881,0.738,0.582,0.458],dtype=float),
}
for _k in _TDD4: _TDD4[_k] = _TDD4[_k] / _TDD4[_k].mean()

_TDD_SP = {
    "zima_prac":       np.array([0.55,0.52,0.50,0.50,0.50,0.55,0.75,0.95,0.85,0.75,0.72,0.72,0.72,0.72,0.75,0.85,0.95,1.10,1.15,1.10,1.00,0.90,0.75,0.62],dtype=float),
    "prechodne_prac":  np.array([0.50,0.47,0.45,0.45,0.45,0.50,0.70,0.88,0.78,0.70,0.67,0.67,0.67,0.67,0.70,0.78,0.88,1.00,1.05,1.00,0.91,0.81,0.68,0.56],dtype=float),
    "leto_prac":       np.array([0.45,0.42,0.40,0.40,0.40,0.45,0.65,0.80,0.72,0.65,0.62,0.62,0.62,0.62,0.65,0.72,0.80,0.90,0.95,0.90,0.82,0.72,0.60,0.50],dtype=float),
    "zima_vikend":     np.array([0.58,0.54,0.52,0.51,0.51,0.54,0.62,0.78,0.90,0.95,0.95,0.93,0.90,0.88,0.85,0.88,0.92,1.05,1.10,1.05,0.95,0.85,0.72,0.63],dtype=float),
    "prechodne_vikend":np.array([0.53,0.49,0.47,0.46,0.46,0.49,0.57,0.72,0.82,0.88,0.88,0.86,0.82,0.80,0.78,0.80,0.84,0.97,1.01,0.97,0.88,0.78,0.66,0.58],dtype=float),
    "leto_vikend":     np.array([0.48,0.44,0.42,0.41,0.41,0.44,0.52,0.65,0.75,0.80,0.80,0.78,0.75,0.73,0.71,0.73,0.77,0.88,0.92,0.88,0.80,0.71,0.60,0.52],dtype=float),
}
for _k in _TDD_SP: _TDD_SP[_k] = _TDD_SP[_k] / _TDD_SP[_k].mean()

_UPRAVY = {
    "mix":        np.ones(24,dtype=float),
    "seniori":    np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.3,1.5,1.6,1.6,1.5,1.5,1.4,1.4,1.3,1.1,1.0,1.0,1.0,1.0,1.0,1.0],dtype=float),
    "pracujici":  np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.2,1.3,0.7,0.5,0.5,0.5,0.5,0.5,0.5,0.6,0.8,1.3,1.4,1.3,1.2,1.1,1.0,1.0],dtype=float),
    "rodiny":     np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.2,0.9,0.7,0.7,0.7,0.8,0.8,0.9,1.1,1.2,1.2,1.2,1.1,1.1,1.0,1.0,1.0],dtype=float),
    "provozovna": np.array([0.8,0.8,0.8,0.8,0.8,0.9,1.0,1.2,1.5,1.6,1.7,1.7,1.6,1.6,1.6,1.5,1.3,1.1,1.0,0.9,0.9,0.8,0.8,0.8],dtype=float),
}
for _k in _UPRAVY: _UPRAVY[_k] = _UPRAVY[_k] / _UPRAVY[_k].mean()

# NT hodiny dle sazby (set hodin kdy platí nízký tarif)
NT_HODINY = {
    "D25d": set(list(range(22,24))+list(range(0,6))),
    "D26d": set(list(range(22,24))+list(range(0,6))),
    "D27d": set(list(range(22,24))+list(range(0,6))),
    "D35d": set(list(range(22,24))+list(range(0,6))+list(range(10,14))),
    "D45d": set(range(24)),
    "D56d": set(range(24)),
    "D57d": set(list(range(22,24))+list(range(0,6))+list(range(10,14))),
    "D61d": set(list(range(22,24))+list(range(0,8))),
}

_CD = 365 * 96
_MESICE = ["Led","Úno","Bře","Dub","Kvě","Čvn","Čvc","Srp","Zář","Říj","Lis","Pro"]


def _sezona(m):
    if m in [11,12,1,2]: return "zima"
    if m in [5,6,7,8]: return "leto"
    return "prechodne"


def _tdd4_klic(sezona, vikend):
    """Bezpečný výběr TDD4 klíče bez f-stringu."""
    tp = "vikend" if vikend else "prac"
    if sezona == "zima" and not vikend:    return "zima_prac"
    if sezona == "zima" and vikend:        return "zima_vikend"
    if sezona == "leto" and not vikend:    return "leto_prac"
    if sezona == "leto" and vikend:        return "leto_vikend"
    if sezona == "prechodne" and not vikend: return "prechodne_prac"
    if sezona == "prechodne" and vikend:   return "prechodne_vikend"
    return "prechodne_prac"


def _gen_profil_vt(kwh, tdd, uprava=None):
    """Generuje 15min profil VT spotřeby."""
    vals = []
    den = datetime.date(2026,1,1)
    for _ in range(365):
        sz = _sezona(den.month)
        vi = den.weekday() >= 5
        klic = _tdd4_klic(sz, vi) if tdd is _TDD4 else (
            "zima_prac" if sz=="zima" and not vi else
            "zima_vikend" if sz=="zima" else
            "leto_prac" if sz=="leto" and not vi else
            "leto_vikend" if sz=="leto" else
            "prechodne_prac" if not vi else "prechodne_vikend"
        )
        p = tdd[klic].copy()
        if uprava is not None:
            p = p * uprava; p = p / p.mean()
        for h in range(24):
            v = float(p[h]) / 4.0
            vals.extend([v,v,v,v])
        den += datetime.timedelta(days=1)
    arr = np.array(vals,dtype=float)[:_CD]
    if arr.sum() > 0: arr = arr * (float(kwh) / arr.sum())
    return arr


def _gen_profil_nt(kwh, sazba):
    """Generuje 15min profil NT spotřeby — jen v NT hodinách."""
    nt_h = NT_HODINY.get(sazba, set())
    if not nt_h or kwh <= 0:
        return np.zeros(_CD, dtype=float)
    vals = []
    for _ in range(365):
        for h in range(24):
            v = 1.0 / 4.0 if h in nt_h else 0.0
            vals.extend([v,v,v,v])
    arr = np.array(vals,dtype=float)[:_CD]
    if arr.sum() > 0: arr = arr * (float(kwh) / arr.sum())
    return arr


def _gen_vyroba_fallback(kwp, sklon=35, azimut=0):
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


def _simuluj(vyroba_15, sp_vt15, sp_nt15, bat=0.0, model="edc", edc_ztrata=0.0):
    """
    Přesná 15min simulace FVE s oddělenou VT a NT spotřebou.
    Baterie: nabíjí se z přetoků FVE (VT), vybíjí do NT spotřeby.
    """
    v   = np.array(vyroba_15, dtype=float)
    svt = np.array(sp_vt15,   dtype=float)
    snt = np.array(sp_nt15,   dtype=float)
    bat = float(bat)

    # Pro model "spolecne" — NT je nulová (společné prostory NT nemají)
    if model == "spolecne":
        snt = np.zeros(len(v), dtype=float)

    n = int(min(len(v), len(svt), len(snt)))
    v, svt, snt = v[:n], svt[:n], snt[:n]

    bmin, bmax, bkwh = bat*0.10, bat*0.90, bat*0.50
    eta = 0.92

    vl_vt  = np.zeros(n, dtype=float)  # vlastní spotřeba z FVE (VT)
    vl_nt  = np.zeros(n, dtype=float)  # vlastní spotřeba z baterie (NT)
    pr     = np.zeros(n, dtype=float)  # přetoky do sítě
    od_vt  = np.zeros(n, dtype=float)  # odběr ze sítě VT
    od_nt  = np.zeros(n, dtype=float)  # odběr ze sítě NT

    for i in range(n):
        vi   = float(v[i])
        svti = float(svt[i])
        snti = float(snt[i])

        # 1. FVE pokryje VT spotřebu přímo
        prime = min(vi, svti)
        vl_vt[i] = prime
        zbyla_v = vi - prime
        zbyla_svt = svti - prime

        # 2. Přebytek výroby → nabít baterii
        if zbyla_v > 0.0 and bat > 0.0:
            nab = min(zbyla_v * eta, bmax - bkwh)
            bkwh += nab
            zbyla_v -= nab / eta

        # 3. Zbylá výroba → přetoky
        pr[i] = zbyla_v

        # 4. Zbylá VT spotřeba → vybít baterii (VT tarif = dražší → priorita!)
        if zbyla_svt > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(zbyla_svt, dos)
            bkwh -= vyb / eta
            zbyla_svt -= vyb
            vl_vt[i] += vyb  # z baterie do VT spotřeby → úspora VT cena

        # 5. Zbylá VT spotřeba → ze sítě
        od_vt[i] = zbyla_svt

        # 6. NT spotřeba → vybít zbylou baterii (VT spotřeba měla prioritu)
        if snti > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(snti, dos)
            bkwh -= vyb / eta
            snti -= vyb
            vl_nt[i] = vyb

        # 7. Zbylá NT spotřeba → ze sítě
        od_nt[i] = snti

    tv   = float(v.sum())
    tvl  = float(vl_vt.sum()) + float(vl_nt.sum())
    tpr  = float(pr.sum())
    tsp  = float(svt.sum()) + float(snt.sum())

    # EDC — dynamická efektivita sdílení
    # Míra časového překryvu výroby a spotřeby (bez baterie)
    # = kolik % výroby FVE nastane ve stejný čas jako poptávka domu
    # Nezávislé na baterii, max 100 %
    casovy_prekryv = float(np.minimum(v[:n], (svt+snt)[:n]).sum()) / float(v[:n].sum()) if float(v[:n].sum()) > 0 else 1.0
    casovy_prekryv = min(1.0, casovy_prekryv)  # cap na 100%
    edc_efektivita = casovy_prekryv  # přejmenováno pro zpětnou kompatibilitu

    if model == "edc":
        # Aplikuj uživatelsky nastavitelnou ztrátu sdílení
        if edc_ztrata > 0:
            korekce = 1.0 - float(edc_ztrata) / 100.0
            tvl *= korekce
            tpr = tv - tvl

    mv,ms,mvl,mpr = [],[],[],[]
    for m in range(12):
        a,b = m*30*96, min((m+1)*30*96,n)
        mv.append(float(v[a:b].sum()))
        ms.append(float(svt[a:b].sum())+float(snt[a:b].sum()))
        mvl.append(float(vl_vt[a:b].sum())+float(vl_nt[a:b].sum()))
        mpr.append(float(pr[a:b].sum()))

    return {
        "vlastni_vt_kwh":  float(vl_vt.sum()),
        "vlastni_nt_kwh":  float(vl_nt.sum()),
        "vlastni_kwh":     tvl,
        "pretoky_kwh":     tpr,
        "odber_vt_kwh":    float(od_vt.sum()),
        "odber_nt_kwh":    float(od_nt.sum()),
        "vyroba_kwh":      tv,
        "spotreba_kwh":    tsp,
        "mira_vs":         tvl/tv  if tv>0  else 0.0,
        "mira_sob":        tvl/tsp if tsp>0 else 0.0,  # přepočítáno v UI pro "spolecne"
        "edc_efektivita":  edc_efektivita,
        "mesice_vyroba":   mv,
        "mesice_spotreba": ms,
        "mesice_vlastni":  mvl,
        "mesice_pretoky":  mpr,
    }


def _cashflow(vl_vt, vl_nt, pr, cvt, cnt, cpr,
              vlast, uver, spl, splat,
              rust=3.0, deg=0.5, leta=25, jist=0.0, bonus=0.0, deg_bat=2.0):
    res=[]; kum=-(float(vlast)+float(uver)-float(bonus))
    for rok in range(1,int(leta)+1):
        d=(1.0-float(deg)/100.0)**(rok-1)
        d_bat=(1.0-float(deg_bat)/100.0)**(rok-1)  # degradace baterie
        c=(1.0+float(rust)/100.0)**(rok-1)
        # NT úspora z baterie degraduje rychleji než panely
        u = (float(vl_vt)*d*float(cvt)*c +
             float(vl_nt)*d_bat*float(cnt)*c +
             float(pr)*d*float(cpr)*c +
             float(jist)*c)
        s = float(spl) if rok<=int(splat) else 0.0
        kum += u-s
        res.append({"rok":rok,
                    "vyroba_mwh":round((float(vl_vt)+float(vl_nt)+float(pr))*d/1000.0,2),
                    "vlastni_mwh":round((float(vl_vt)+float(vl_nt))*d/1000.0,2),
                    "pretoky_mwh":round(float(pr)*d/1000.0,2),
                    "uspora_vt":round(float(vl_vt)*d*float(cvt)*c),
                    "uspora_nt":round(float(vl_nt)*d*float(cnt)*c),
                    "uspora_pretoky":round(float(pr)*d*float(cpr)*c),
                    "uspora_celkem":round(u),
                    "splatka":round(s),
                    "cisty_prinos":round(u-s),
                    "kumulativni":round(kum),
                    "cena_vt":round(float(cvt)*c,3)})
    return res


@st.cache_data(ttl=300)
def _geocode_search(dotaz):
    """Hledá lokality pro našeptávání."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format":"json",
                    "limit":5, "addressdetails":1, "countrycodes":"cz"},
            headers={"User-Agent":"FVE-SVJ-Kalkulacka/1.0"},
            timeout=5)
        if r.status_code == 200 and r.text.strip():
            return r.json()
    except: pass
    return []


@st.cache_data(ttl=3600)
def _geocode(dotaz):
    _FB = {
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
                       params={"q":f"{dotaz}, Česká republika","format":"json",
                               "limit":1,"addressdetails":1,"countrycodes":"cz"},
                       headers={"User-Agent":"FVE-SVJ-Kalkulacka/1.0"},timeout=10)
        if r.status_code==200 and r.text.strip():
            res=r.json()
            if res:
                addr=res[0].get("address",{})
                m=(addr.get("road","") + " " + addr.get("house_number","")).strip()
                m = m or addr.get("city") or addr.get("town") or addr.get("village") or dotaz
                return float(res[0]["lat"]),float(res[0]["lon"]),m,None
    except: pass
    klic=dotaz.lower().strip().split(",")[0].strip()
    if klic in _FB: return _FB[klic][0],_FB[klic][1],dotaz,None
    return None,None,None,"Nenalezeno — zkuste jiný formát adresy"


@st.cache_data(ttl=86400)
def _pvgis(lat,lon,kwp,sklon,azimut):
    try:
        r=requests.get("https://re.jrc.ec.europa.eu/api/v5_2/seriescalc",
                       params={"lat":float(lat),"lon":float(lon),
                               "peakpower":float(kwp),"loss":14,
                               "angle":int(sklon),"aspect":int(azimut),
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


def _gen_vyroba_den(kwp, sezona, pocasi):
    koef = {"jasno":1.0,"polojasno":0.5,"zatazeno":0.15}[pocasi]
    intenzita = {"zima":0.220,"prechodne":0.408,"leto":0.647}[sezona]
    delka = {"zima":8.0,"prechodne":12.0,"leto":15.0}[sezona]
    vychod=12-delka/2; zapad=12+delka/2
    v=np.zeros(96,dtype=float)
    for i in range(96):
        h=i/4.0
        if vychod<=h<=zapad:
            t=(h-vychod)/delka; elev=np.sin(np.pi*t)
            v[i]=float(kwp)*elev*intenzita*koef*0.85*0.25
    return v


def _gen_spotreba_den(kwh_rok, sezona, profil, vikend=False):
    klic = _tdd4_klic(sezona, vikend)
    uprava = _UPRAVY.get(str(profil), np.ones(24,dtype=float))
    p = _TDD4[klic].copy() * uprava
    p = p / p.mean()
    vals = np.zeros(96,dtype=float)
    for h in range(24):
        for j in range(4):
            vals[h*4+j] = float(p[h]) / 4.0
    kwh_den = float(kwh_rok)/365.0
    if vals.sum()>0: vals = vals*(kwh_den/vals.sum())
    return vals


# Plotly config
_CFG = {"scrollZoom":False,"displayModeBar":False}
_LAY = dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10,r=10,t=30,b=10),
            legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
            xaxis=dict(fixedrange=True),yaxis=dict(fixedrange=True))

