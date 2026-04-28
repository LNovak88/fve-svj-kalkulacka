# main.py — FastAPI backend pro FVE SVJ kalkulačku
# Deploy: Render (free tier) + UptimeRobot keep-alive
# Docs: GET /docs

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import numpy as np

import engine as e

app = FastAPI(
    title="FVE SVJ Kalkulačka API",
    description="Simulace ekonomiky fotovoltaické elektrárny pro bytové domy (SVJ).",
    version="1.0.0",
)

# CORS — povoluje volání z frontendu (Vercel, vlastní doména)
# V produkci nahraď * za konkrétní doménu: ["https://fveprosvj.cz"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ================================================================
# HEALTH CHECK — UptimeRobot pinguje tuto URL každých 5 min
# ================================================================

@app.api_route("/health", methods=["GET", "HEAD"], tags=["system"])
def health():
    return {"status": "ok"}


# ================================================================
# GEOCODING
# ================================================================

@app.get("/geocode", tags=["lokace"])
def geocode(q: str = Query(..., description="Adresa nebo město v ČR")):
    """Převede adresu na GPS souřadnice (Nominatim/OSM)."""
    lat, lon, nazev, err = e.geocode(q)
    if err:
        raise HTTPException(status_code=404, detail=err)
    return {"lat": lat, "lon": lon, "nazev": nazev}


@app.get("/geocode/search", tags=["lokace"])
def geocode_search(q: str = Query(..., min_length=2)):
    """Autocomplete — vrátí až 5 návrhů lokalit."""
    return e.geocode_search(q)


# ================================================================
# PVGIS — SOLÁRNÍ DATA
# ================================================================

@app.get("/pvgis", tags=["solar"])
def pvgis(
    lat:    float = Query(..., description="Zeměpisná šířka"),
    lon:    float = Query(..., description="Zeměpisná délka"),
    kwp:    float = Query(..., gt=0, description="Instalovaný výkon FVE (kWp)"),
    sklon:  int   = Query(35,  ge=0, le=90,   description="Sklon panelů (°)"),
    azimut: int   = Query(0,   description="Azimut: 0=Jih, -90=Východ, +90=Západ, 999=V+Z, 998=JZ+JV"),
):
    """
    Stáhne hodinová TMY data výroby z PVGIS API (EU JRC).
    Vrátí roční výrobu kWh a měsíční rozpis.
    Cache: LRU 256 dotazů (v produkci: Redis TTL 24h).
    """
    vyroba_hod, err = e.pvgis(lat, lon, kwp, sklon, azimut)
    if err:
        # Fallback na analytický model
        vyroba_hod = e._gen_vyroba_fallback(kwp, sklon, azimut if azimut < 900 else 0)

    vyroba_15 = e._interpoluj(vyroba_hod)

    # Měsíční součty
    mesice = []
    for m in range(12):
        a = m * 30 * 24
        b = min((m + 1) * 30 * 24, len(vyroba_hod))
        mesice.append(round(float(vyroba_hod[a:b].sum()), 1))

    return {
        "vyroba_kwh_rok": round(float(vyroba_hod.sum()), 0),
        "mesice_kwh":     mesice,
        "mesice_nazvy":   e._MESICE,
        "zdroj":          "pvgis" if not err else "fallback",
    }


# ================================================================
# SIMULACE — hlavní endpoint
# ================================================================

class SimulaceVstup(BaseModel):
    # Lokalita a FVE
    lat:    float = Field(..., description="GPS šířka")
    lon:    float = Field(..., description="GPS délka")
    kwp:    float = Field(..., gt=0, description="Výkon FVE (kWp)")
    sklon:  int   = Field(35,  ge=0, le=90)
    azimut: int   = Field(0,   description="0=Jih, 999=V+Z, 998=JZ+JV")
    bat:    float = Field(0.0, ge=0, description="Kapacita baterie (kWh)")

    # Spotřeba domu
    pocet_bytu:  int   = Field(..., gt=0, le=500)
    sp_by_vt_mwh: float = Field(..., gt=0, description="Roční VT spotřeba bytu (MWh)")
    sp_by_nt_mwh: float = Field(0.0, ge=0, description="Roční NT spotřeba bytu (MWh)")
    sp_sp_mwh:    float = Field(0.0, ge=0, description="Spotřeba společných prostor (MWh)")
    sazba:        str   = Field("D02d", description="Distribuční sazba")
    dist:         str   = Field("ČEZ Distribuce", description="Distributor")

    # Profil spotřeby
    profil:        str   = Field("mix", description="mix / seniori / pracujici / rodiny")
    pct_pracujici: float = Field(33.0, ge=0, le=100)
    pct_seniori:   float = Field(33.0, ge=0, le=100)
    pct_rodiny:    float = Field(34.0, ge=0, le=100)

    # Model sdílení
    model: str = Field("edc", description="edc / jom / spolecne")
    edc_ztrata: float = Field(15.0, ge=0, le=50)

    # Ekonomika
    cena_invest:  float = Field(...,  gt=0,  description="Celková investice (Kč)")
    vlastni_pct:  float = Field(30.0, ge=0,  le=100, description="Vlastní zdroje (%)")
    splatnost:    int   = Field(20,   ge=1,  le=30,  description="Splatnost úvěru (roky)")
    rust_cen:     float = Field(3.0,  ge=0,  le=15)
    deg_pan:      float = Field(0.5,  ge=0,  le=2)
    cena_pretoky: float = Field(1.5,  ge=0,  description="Výkupní cena přetoků (Kč/kWh)")
    bonus_nzu:    float = Field(0.0,  ge=0,  description="Dotace NZÚ (Kč)")

    # JOM úspora jističe (volitelné — předvypočítat na klientovi nebo zadat 0)
    uspora_jistic: float = Field(0.0, ge=0, description="Roční úspora na jističi JOM (Kč/rok)")


class SimulaceVystup(BaseModel):
    sim:         dict
    cf:          list
    cena_invest: float
    splatka_mesic: float
    cvt:         float
    cnt:         float


@app.post("/simulate", response_model=SimulaceVystup, tags=["kalkulace"])
def simulate(vstup: SimulaceVstup):
    """
    Hlavní simulační endpoint.
    Přijme parametry domu a FVE, vrátí výsledky simulace + cashflow 25 let.
    """
    # 1. Výroba z PVGIS (nebo fallback)
    vyroba_hod, err = e.pvgis(vstup.lat, vstup.lon, vstup.kwp, vstup.sklon, vstup.azimut)
    if err:
        vyroba_hod = e._gen_vyroba_fallback(vstup.kwp, vstup.sklon,
                                             vstup.azimut if vstup.azimut < 900 else 0)
    vyroba_15 = e._interpoluj(vyroba_hod)

    # 2. Profil spotřeby
    uprava = e._smiseny_profil(vstup.pct_pracujici, vstup.pct_seniori, vstup.pct_rodiny)
    tdd = e._TDD4

    sp_by_vt  = vstup.sp_by_vt_mwh * 1000 * vstup.pocet_bytu
    sp_by_nt  = vstup.sp_by_nt_mwh * 1000 * vstup.pocet_bytu
    sp_sp     = vstup.sp_sp_mwh * 1000

    sp_vt15 = e._gen_profil_vt(sp_by_vt + sp_sp, tdd, uprava)
    sp_nt15 = e._gen_profil_nt(sp_by_nt, vstup.sazba)

    # 3. Simulace
    sim = e.simuluj(vyroba_15, sp_vt15, sp_nt15,
                    bat=vstup.bat, model=vstup.model, edc_ztrata=vstup.edc_ztrata)

    # 4. Ceny energie
    cvt = e.CENY_VT.get(vstup.dist, e.CENY_VT["ČEZ Distribuce"]).get(vstup.sazba, 6610) / 1000
    cnt_sazby = e.CENY_NT.get(vstup.dist, e.CENY_NT["ČEZ Distribuce"])
    cnt = cnt_sazby.get(vstup.sazba, cvt * 0.6) / 1000

    # 5. Cashflow
    vlastni  = vstup.cena_invest * vstup.vlastni_pct / 100
    uver     = vstup.cena_invest - vlastni
    splatka  = uver / vstup.splatnost if uver > 0 else 0.0
    splatka_mesic = round(splatka / 12)

    cf = e.cashflow(
        vl_vt=sim["vlastni_vt_kwh"],
        vl_nt=sim["vlastni_nt_kwh"],
        pr=sim["pretoky_kwh"],
        cvt=cvt, cnt=cnt,
        cpr=vstup.cena_pretoky / 1000,
        vlast=vlastni, uver=uver,
        spl=splatka, splat=vstup.splatnost,
        rust=vstup.rust_cen, deg=vstup.deg_pan,
        jist=vstup.uspora_jistic,
        bonus=vstup.bonus_nzu,
    )

    return {
        "sim":          sim,
        "cf":           cf,
        "cena_invest":  vstup.cena_invest,
        "splatka_mesic": splatka_mesic,
        "cvt":          round(cvt * 1000),
        "cnt":          round(cnt * 1000),
    }


# ================================================================
# CENÍKY — pro frontend (výběr distributora, sazby atd.)
# ================================================================

@app.get("/ceniky", tags=["data"])
def ceniky():
    """Vrátí aktuální ceníky 2026 pro frontend."""
    return {
        "distributori": list(e.CENY_VT.keys()),
        "ceny_vt":      e.CENY_VT,
        "ceny_nt":      e.CENY_NT,
        "stay_plat":    e.STAY_PLAT,
        "sazby_nt":     e.SAZBY_NT,
        "podil_nt":     e.PODIL_NT,
    }
