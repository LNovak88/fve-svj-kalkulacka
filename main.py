# main.py — FastAPI backend pro FVE SVJ kalkulačku
# Deploy: Render (free tier) + UptimeRobot keep-alive
#
# Endpointy:
#   GET  /health
#   GET  /geocode
#   GET  /geocode/search
#   GET  /pvgis
#   POST /recommend  — doporučení + PM výpočet
#   POST /simulate   — přesná 15min simulace + cashflow
#   GET  /ceniky

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import numpy as np

import engine as e

app = FastAPI(
    title="FVE SVJ Kalkulačka API",
    description="Simulace ekonomiky FVE pro bytové domy (SVJ).",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)


# ================================================================
# HEALTH CHECK
# ================================================================

@app.api_route("/health", methods=["GET", "HEAD"], tags=["system"])
def health():
    return {"status": "ok"}


# ================================================================
# GEOCODING
# ================================================================

@app.get("/geocode", tags=["lokace"])
def geocode(q: str = Query(...)):
    try:
        lat, lon, nazev, err = e.geocode(q)
        if err:
            return {"lat": None, "lon": None, "nazev": None, "err": err}
        return {"lat": lat, "lon": lon, "nazev": nazev, "err": None}
    except Exception as ex:
        return {"lat": None, "lon": None, "nazev": None, "err": str(ex)}


@app.get("/geocode/search", tags=["lokace"])
def geocode_search(q: str = Query(..., min_length=2)):
    try:
        return e.geocode_search(q)
    except Exception:
        return []


# ================================================================
# PVGIS
# ================================================================

@app.get("/pvgis", tags=["solar"])
def pvgis(
    lat:    float = Query(...),
    lon:    float = Query(...),
    kwp:    float = Query(..., gt=0),
    sklon:  int   = Query(35, ge=0, le=90),
    azimut: int   = Query(0),
):
    vyroba_hod, err = e.pvgis(lat, lon, kwp, sklon, azimut)
    if err:
        vyroba_hod = e._gen_vyroba_fallback(kwp, sklon, azimut if azimut < 900 else 0)
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
# RECOMMEND
# ================================================================

class RecommendVstup(BaseModel):
    model_config = {"extra": "ignore"}
    pocet_bytu:       int        = Field(..., gt=0, le=500)
    pocet_vchodu:     int        = Field(1,   ge=1, le=20)
    pocet_pater:      int        = Field(4,   ge=1, le=30)
    pocet_vytahu:     int        = Field(0,   ge=0, le=10)
    pocet_cerpadel:   int        = Field(1,   ge=0, le=20)
    ma_tuv_central:   bool       = Field(False)
    ma_tc_dum:        bool       = Field(False)
    pocet_ev_nabijec: int        = Field(0,   ge=0, le=50)
    zarizeni:         List[str]  = Field(["zaklad"])
    dist:             str        = Field("ČEZ Distribuce")


class RecommendVystup(BaseModel):
    # Bytová spotřeba
    sp_by_vt_mwh:   float
    sp_by_nt_mwh:   float
    sazba_byt:      str
    jistic_byt:     str

    # Společné prostory
    sp_sp_vt_mwh:   float
    sp_sp_nt_mwh:   float
    sp_sp_mwh:      float
    sazba_sp:       str
    jistic_sp:      str
    jistic_sp_a:    int
    sp_popis:       list

    # Jistič domu (EDC)
    jistic_dum:      str
    jistic_dum_a:    int
    jistic_dum_cena: int

    # FVE doporučení
    kwp:            float
    bat:            float
    cena_kwp:       int
    cena_fve:       int
    cena_bat:       int
    cena_celkem:    int

    # Finanční srovnání — stávající stav
    cena_jistic_byt_mes:  int
    cena_stay_mes:        int
    platby_nyni_mes:      int

    # PM (podružné měření)
    jistic_pm_str:      str
    jistic_pm_a:        int
    jistic_pm_cena_mes: int
    platby_ted_mes:     int
    platby_pm_mes:      int
    uspora_pm_mes:      int
    uspora_pm_rok:      int
    cena_mericu_pm:     int
    jistic_sp_opts:     list


@app.post("/recommend", response_model=RecommendVystup, tags=["kalkulace"])
def recommend(vstup: RecommendVstup):
    """Doporučení konfigurace FVE + výpočet PM úspory."""
    pb       = int(vstup.pocet_bytu)
    zarizeni = [z.lower().strip() for z in vstup.zarizeni]
    dist     = vstup.dist

    # 1. Sazba a spotřeba bytů
    sazba_byt    = e.doporuc_sazbu(zarizeni)
    sp_by_vt_mwh, sp_by_nt_mwh = e.sp_z_zarizeni(zarizeni, 1)
    if sp_by_vt_mwh < 0.5:
        sp_by_vt_mwh = 1.2

    # 2. Jistič bytu
    jistic_byt = e.doporuc_jistic_byt(zarizeni)

    # 3. Společné prostory
    sp = e.sp_sp_vypocet(
        pocet_bytu       = pb,
        pocet_pater      = vstup.pocet_pater,
        pocet_vytahu     = vstup.pocet_vytahu,
        ma_tuv_central   = vstup.ma_tuv_central,
        ma_tc_dum        = vstup.ma_tc_dum,
        pocet_ev_nabijec = vstup.pocet_ev_nabijec,
        pocet_cerpadel   = vstup.pocet_cerpadel,
    )

    # 4. Jistič domu (EDC)
    jistic_dum_str, jistic_dum_a = e.doporuc_jistic_dum(pb, zarizeni)
    jistic_dum_cena = e.cena_jistice_dum(dist, jistic_dum_a, c_tarif=False)

    # 5. Doporučené kWp a baterie
    sp_by_vt_celkem = sp_by_vt_mwh * pb * 1000
    fve = e.doporuc_kwp_bat(
        sp_vt_celkem_kwh = sp_by_vt_celkem,
        sp_nt_celkem_kwh = sp_by_nt_mwh * pb * 1000,
        sp_sp_mwh        = sp["sp_mwh"],
        zarizeni         = zarizeni,
        pocet_vchodu     = vstup.pocet_vchodu,
    )

    # 5b. Optimalizace baterie — hledej nejlepší návratnost v rozsahu kWp×1.0 až kWp×1.5
    # kWp je pevné (75% spotřeby), baterie se optimalizuje
    kwp_opt = fve["kwp"]
    cvt_opt = e.CENY_VT.get(dist, e.CENY_VT["ČEZ Distribuce"]).get(sazba_byt, 6610) / 1000
    uprava_opt = e._smiseny_profil(33.0, 33.0, 34.0)
    sp_vt15_opt = e._gen_profil_vt(sp_by_vt_celkem + sp["sp_mwh"] * 1000, e._TDD4, uprava_opt)
    sp_nt15_opt = e._gen_profil_nt(sp_by_nt_mwh * pb * 1000, sazba_byt)
    vyr_opt = e._interpoluj(e._gen_vyroba_fallback(kwp_opt, 35, 0))
    ez_opt  = min(5.0, round(10.0 / pb ** 0.5, 1))

    # Generuj kandidáty: baterie od kWp×1.0 do kWp×1.5, krok 5 kWh, min 10 kWh
    bat_min_kwh = max(10.0, round(kwp_opt * 1.0 / 5) * 5)
    bat_max_kwh = max(10.0, round(kwp_opt * 1.5 / 5) * 5)
    kandidati = []
    bat_k = bat_min_kwh
    while bat_k <= bat_max_kwh:
        kandidati.append(bat_k)
        bat_k = round(bat_k + 5, 1)
    if not kandidati:
        kandidati = [bat_min_kwh]

    def _cashflow_nav(bat_kwh):
        """Cashflow návratnost EDC pro danou baterii (realistický scénář +3%/rok)."""
        inv_k  = kwp_opt * e.cena_kwp(kwp_opt) + bat_kwh * 15000
        uver_k = min(inv_k, pb * 350000)  # vlastni_pct=0
        spl_k  = uver_k / 15.0            # roční splátka NZÚ, splatnost 15 let
        sim_k  = e.simuluj(vyr_opt, sp_vt15_opt, sp_nt15_opt,
                           bat=bat_kwh, model="edc", edc_ztrata=ez_opt)
        us_k   = (sim_k["vlastni_vt_kwh"] * cvt_opt
                  + sim_k["pretoky_kwh"] * 0.00095)
        if us_k <= 0:
            return 99, 0
        kum = -inv_k  # startuje od záporné celé investice
        for rok in range(1, 26):
            c   = 1.03 ** (rok - 1)
            kum += us_k * c - (spl_k if rok <= 15 else 0)
            if kum >= 0:
                return rok, kum
        return 99, kum  # nepřekročil 0 za 25 let

    # Otestuj všechny kandidáty, vyber nejlepší návratnost
    best_bat = bat_min_kwh
    best_nav = 99
    for bat_k in kandidati:
        nav_k, _ = _cashflow_nav(bat_k)
        if nav_k < best_nav:
            best_nav = nav_k
            best_bat = bat_k

    bat_opt = best_bat

    # Aktualizovat fve s optimální baterií
    if bat_opt != fve["bat"]:
        c_kwp_opt  = e.cena_kwp(kwp_opt)
        extra_v    = max(0, int(vstup.pocet_vchodu) - 1) * 30000
        fve = {
            "kwp":         kwp_opt,
            "bat":         bat_opt,
            "cena_kwp":    c_kwp_opt,
            "cena_fve":    round(kwp_opt * c_kwp_opt),
            "cena_bat":    round(bat_opt * 15000),
            "cena_celkem": round(kwp_opt * c_kwp_opt + bat_opt * 15000 + extra_v),
        }
    jistic_byt_tabulka = e.JISTIC_BYT.get(dist, e.JISTIC_BYT["ČEZ Distribuce"])
    cena_jistic_byt    = jistic_byt_tabulka.get(jistic_byt, 298)
    cena_stay          = e.STAY_PLAT.get(dist, 163)
    platby_nyni        = (pb * (cena_jistic_byt + cena_stay)
                          + (e.cena_jistice_dum(dist, sp["jistic_sp_a"], c_tarif=False) + cena_stay))

    # 7. PM výpočet — úspora a náklady podružného měření
    pm = e.vypocet_pm(
        pocet_bytu   = pb,
        pocet_vchodu = vstup.pocet_vchodu,
        zarizeni     = zarizeni,
        dist         = dist,
        jistic_byt   = jistic_byt,
        jistic_sp_a  = sp["jistic_sp_a"],
    )

    return {
        # Bytová spotřeba
        "sp_by_vt_mwh":  round(sp_by_vt_mwh, 3),
        "sp_by_nt_mwh":  round(sp_by_nt_mwh, 3),
        "sazba_byt":     sazba_byt,
        "jistic_byt":    jistic_byt,

        # Společné prostory
        "sp_sp_vt_mwh":  sp["sp_vt_mwh"],
        "sp_sp_nt_mwh":  sp["sp_nt_mwh"],
        "sp_sp_mwh":     sp["sp_mwh"],
        "sazba_sp":      sp["sazba_sp"],
        "jistic_sp":     sp["jistic_sp"],
        "jistic_sp_a":   sp["jistic_sp_a"],
        "sp_popis":      sp["popis"],

        # Jistič domu (EDC)
        "jistic_dum":      jistic_dum_str,
        "jistic_dum_a":    jistic_dum_a,
        "jistic_dum_cena": jistic_dum_cena,

        # FVE doporučení
        "kwp":          fve["kwp"],
        "bat":          fve["bat"],
        "cena_kwp":     fve["cena_kwp"],
        "cena_fve":     fve["cena_fve"],
        "cena_bat":     fve["cena_bat"],
        "cena_celkem":  fve["cena_celkem"],

        # Stávající platby
        "cena_jistic_byt_mes": cena_jistic_byt,
        "cena_stay_mes":       cena_stay,
        "platby_nyni_mes":     platby_nyni,

        # PM data
        "jistic_pm_str":      pm["jistic_pm_str"],
        "jistic_pm_a":        pm["jistic_pm_a"],
        "jistic_pm_cena_mes": pm["jistic_pm_cena_mes"],
        "platby_ted_mes":     pm["platby_ted_mes"],
        "platby_pm_mes":      pm["platby_pm_mes"],
        "uspora_pm_mes":      pm["uspora_pm_mes"],
        "uspora_pm_rok":      pm["uspora_pm_rok"],
        "cena_mericu_pm":     pm["cena_mericu_pm"],
        "jistic_sp_opts":     pm["jistic_sp_opts"],
    }


# ================================================================
# SIMULATE
# ================================================================

class SimulaceVstup(BaseModel):
    model_config = {"extra": "ignore"}  # ignorovat neznámá pole (zpětná kompatibilita)
    lat:    float = Field(...)
    lon:    float = Field(...)
    kwp:    float = Field(..., gt=0)
    sklon:  int   = Field(35,  ge=0, le=90)
    azimut: int   = Field(0)
    bat:    float = Field(0.0, ge=0)

    pocet_bytu:    int   = Field(..., gt=0, le=500)
    pocet_vchodu:  int   = Field(1,   ge=1, le=20)
    sp_by_vt_mwh:  float = Field(..., gt=0)
    sp_by_nt_mwh:  float = Field(0.0, ge=0)
    sp_sp_mwh:     float = Field(0.0, ge=0)
    sazba:         str   = Field("D02d")
    dist:          str   = Field("ČEZ Distribuce")

    profil:        str   = Field("mix")
    pct_pracujici: float = Field(33.0, ge=0, le=100)
    pct_seniori:   float = Field(33.0, ge=0, le=100)
    pct_rodiny:    float = Field(34.0, ge=0, le=100)

    model:      str   = Field("edc")
    edc_ztrata: float = Field(15.0, ge=0, le=50)

    cena_invest:  float = Field(..., gt=0)
    cena_kwp:     float = Field(30000.0, ge=0)   # cena za kWp (pro SP výpočet)
    vlastni_pct:  float = Field(30.0, ge=0, le=100)
    splatnost:    int   = Field(20,   ge=1, le=30)
    rust_cen:     float = Field(3.0,  ge=0, le=15)
    deg_pan:      float = Field(0.5,  ge=0, le=2)
    cena_pretoky: float = Field(0.95, ge=0)
    bonus_nzu:    float = Field(0.0,  ge=0)
    uspora_jistic: float = Field(0.0, ge=0)
    jistic_sp_a:  int   = Field(25,   ge=0)
    zarizeni:     list  = Field(default_factory=lambda: ["zaklad"])
    bat_doporucena: float = Field(0.0, ge=0)  # doporučená bat pro srovnání EDC/PM


@app.post("/simulate", tags=["kalkulace"])
def simulate(vstup: SimulaceVstup):
    """Hlavní simulační endpoint — přesná 15min simulace + cashflow 25 let + srovnání 3 modelů."""
    vyroba_hod, err = e.pvgis(vstup.lat, vstup.lon, vstup.kwp, vstup.sklon, vstup.azimut)
    if err:
        vyroba_hod = e._gen_vyroba_fallback(
            vstup.kwp, vstup.sklon, vstup.azimut if vstup.azimut < 900 else 0
        )
    vyroba_15 = e._interpoluj(vyroba_hod)

    uprava = e._smiseny_profil(vstup.pct_pracujici, vstup.pct_seniori, vstup.pct_rodiny)

    sp_by_vt  = vstup.sp_by_vt_mwh * 1000 * vstup.pocet_bytu
    sp_by_nt  = vstup.sp_by_nt_mwh * 1000 * vstup.pocet_bytu
    sp_sp     = vstup.sp_sp_mwh * 1000

    sp_vt15     = e._gen_profil_vt(sp_by_vt + sp_sp, e._TDD4, uprava)
    sp_nt15     = e._gen_profil_nt(sp_by_nt, vstup.sazba)
    sp_sp15     = e._gen_profil_vt(sp_sp, e._TDD4, uprava)   # jen SP (pro model spolecne)

    # Pro SP model simulujeme jen SP spotřebu a menší FVE
    if vstup.model == "spolecne":
        sp_kwp_main = max(9.9, round(vstup.sp_sp_mwh * 1000 * 0.75 / 1050 * 2) / 2)
        if abs(sp_kwp_main - vstup.kwp) > 0.1:
            # Přepočítat výrobu pro SP kWp
            vyroba_hod_sp, err_sp = e.pvgis(vstup.lat, vstup.lon, sp_kwp_main, vstup.sklon, vstup.azimut)
            if err_sp:
                vyroba_hod_sp = e._gen_vyroba_fallback(sp_kwp_main, vstup.sklon, vstup.azimut if vstup.azimut < 900 else 0)
            vyroba_15_main = e._interpoluj(vyroba_hod_sp)
        else:
            vyroba_15_main = vyroba_15
        sim = e.simuluj(vyroba_15_main, sp_sp15, np.zeros(len(sp_sp15), dtype=float),
                        bat=0, model="edc", edc_ztrata=vstup.edc_ztrata)
    else:
        sim = e.simuluj(vyroba_15, sp_vt15, sp_nt15,
                        bat=vstup.bat, model=vstup.model, edc_ztrata=vstup.edc_ztrata)

    cvt = e.CENY_VT.get(vstup.dist, e.CENY_VT["ČEZ Distribuce"]).get(vstup.sazba, 6610) / 1000
    cnt_sazby = e.CENY_NT.get(vstup.dist, e.CENY_NT["ČEZ Distribuce"])
    cnt = cnt_sazby.get(vstup.sazba, cvt * 0.6) / 1000

    vlastni  = vstup.cena_invest * vstup.vlastni_pct / 100
    uver     = vstup.cena_invest - vlastni
    splatka  = uver / vstup.splatnost if uver > 0 else 0.0

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
        bonus=0,  # bonus NZÚ pro zranitelné domácnosti nemění cashflow SVJ
    )

    # ================================================================
    # SROVNÁNÍ 3 MODELŮ — stejná logika jako app.py smyčka
    # ================================================================
    pb           = vstup.pocet_bytu
    dist         = vstup.dist
    sazba        = vstup.sazba
    stay         = e.STAY_PLAT.get(dist, 163)
    vchod_extra  = max(0, vstup.pocet_vchodu - 1) * 30000

    # Pro srovnání EDC/PM vždy použít kWp dimenzované na byty (ne SP kWp)
    # bat_byty = doporučená baterie pro EDC (bez ohledu na vybraný model)
    sp_sp     = vstup.sp_sp_mwh * 1000
    sp_by_vt_celk = vstup.sp_by_vt_mwh * 1000 * pb

    if vstup.model == "spolecne":
        kwp_byty      = max(9.9, round((sp_by_vt_celk + sp_sp) * 0.75 / 1050 * 2) / 2)
        cena_kwp_byty = e.cena_kwp(kwp_byty)
    else:
        kwp_byty      = vstup.kwp
        cena_kwp_byty = vstup.cena_kwp

    # Doporučená baterie pro srovnání EDC/PM
    # Pořadí priority: bat_doporucena (z frontendu) > vstup.bat (pokud > 0) > odhad kWp×1.2
    if vstup.bat_doporucena > 0:
        bat_byty = vstup.bat_doporucena
    elif vstup.bat > 0:
        bat_byty = vstup.bat
    else:
        bat_byty = max(10.0, round(kwp_byty * 1.2 / 5) * 5)

    cena_fve     = kwp_byty * cena_kwp_byty
    cena_bat_tot = bat_byty * 15000

    # SP kWp — malá FVE jen pro společné prostory
    sp_kwp = max(9.9, round(vstup.sp_sp_mwh * 1000 * 0.75 / 1050 * 2) / 2)

    srovnani = {}
    for mk in ["edc", "edc_bez_bat", "jom", "spolecne"]:
        # Investice
        mericu_mk = (pb * 10000 + 75000) if mk == "jom" else 0
        mericu_mk += vchod_extra if mk not in ("spolecne",) else 0

        # bat_mk: pro EDC s bat vždy bat_byty (doporučená), pro ostatní 0
        if mk == "edc":
            bat_mk = bat_byty
        elif mk == "jom":
            bat_mk = bat_byty  # PM také s baterií
        else:
            bat_mk = 0.0  # edc_bez_bat a spolecne bez baterie
        cena_bat_mk = bat_mk * 15000

        if mk == "spolecne":
            invest_mk = sp_kwp * e.cena_kwp(sp_kwp) * 0.85
        elif mk == "edc_bez_bat":
            invest_mk = cena_fve + mericu_mk  # bez baterie
        else:
            invest_mk = cena_fve + cena_bat_mk + mericu_mk

        vlast_mk = invest_mk * vstup.vlastni_pct / 100
        uver_mk  = max(0.0, min(invest_mk - vlast_mk, pb * 350000))
        spl_mk   = uver_mk / vstup.splatnost if vstup.splatnost > 0 else 0.0

        # Úspora jističe pro PM (JOM)
        jist_mk = 0.0
        if mk == "jom":
            jbyt_c = e.JISTIC_BYT.get(dist, e.JISTIC_BYT["ČEZ Distribuce"]).get(
                e.doporuc_jistic_byt(vstup.zarizeni), 132)
            jsp_c  = e.cena_jistice_dum(dist, vstup.jistic_sp_a, c_tarif=False)
            jdum_a = e.doporuc_jistic_dum(pb, vstup.zarizeni)[1]
            jdum_c = e.cena_jistice_dum(dist, jdum_a, c_tarif=True)
            platby_ted = (pb + 1) * stay + pb * jbyt_c + jsp_c
            platby_jom = stay + jdum_c
            jist_mk    = (platby_ted - platby_jom) * 12.0

        # Simulace pro daný model
        if mk == "spolecne":
            vyroba_sp_hod, err_sp = e.pvgis(vstup.lat, vstup.lon, sp_kwp, vstup.sklon, vstup.azimut)
            if err_sp:
                vyroba_sp_hod = e._gen_vyroba_fallback(sp_kwp, vstup.sklon, vstup.azimut if vstup.azimut < 900 else 0)
            vyroba_sp_15 = e._interpoluj(vyroba_sp_hod)
            sm = e.simuluj(vyroba_sp_15, sp_sp15, np.zeros(len(sp_sp15), dtype=float),
                           bat=0, model="edc", edc_ztrata=vstup.edc_ztrata)
        else:
            # Pokud uživatel vybral SP model, pro EDC/PM potřebujeme výrobu pro kWp_byty
            if vstup.model == "spolecne" and abs(kwp_byty - vstup.kwp) > 0.5:
                vyroba_byty_hod, err_b = e.pvgis(vstup.lat, vstup.lon, kwp_byty, vstup.sklon, vstup.azimut)
                if err_b:
                    vyroba_byty_hod = e._gen_vyroba_fallback(kwp_byty, vstup.sklon, vstup.azimut if vstup.azimut < 900 else 0)
                vyroba_byty_15 = e._interpoluj(vyroba_byty_hod)
            else:
                vyroba_byty_15 = vyroba_15  # stejné kWp — použít existující výrobu

            if mk == "jom":
                sm = e.simuluj(vyroba_byty_15, sp_vt15, sp_nt15,
                               bat=bat_byty, model="jom", edc_ztrata=0.0)
            elif mk == "edc_bez_bat":
                sm = e.simuluj(vyroba_byty_15, sp_vt15, sp_nt15,
                               bat=0, model="edc", edc_ztrata=vstup.edc_ztrata)
            else:  # edc
                sm = e.simuluj(vyroba_byty_15, sp_vt15, sp_nt15,
                               bat=bat_byty, model="edc", edc_ztrata=vstup.edc_ztrata)

        cfm = e.cashflow(
            vl_vt=sm["vlastni_vt_kwh"], vl_nt=sm["vlastni_nt_kwh"],
            pr=sm["pretoky_kwh"],
            cvt=cvt, cnt=cnt,
            cpr=vstup.cena_pretoky / 1000,
            vlast=vlast_mk, uver=uver_mk,
            spl=spl_mk, splat=vstup.splatnost,
            rust=vstup.rust_cen, deg=vstup.deg_pan,
            jist=jist_mk, bonus=0,
        )

        nav_m     = next((r["rok"] for r in cfm if r["kumulativni"] >= 0), None)
        uspora1_m = cfm[0]["uspora_celkem"] if cfm else 0
        stat_m    = invest_mk / uspora1_m if uspora1_m > 0 else 999
        spl_byt   = round(spl_mk / pb / 12)
        # cisty_byt = čistý měsíční přínos na byt (úspora - splátka)
        # uspora1_m z cashflow již zahrnuje jist_mk (úsporu jističe PM)
        cisty_byt = round(cfm[0]["cisty_prinos"] / pb / 12) if cfm else 0
        kum25_m   = cfm[24]["kumulativni"] if len(cfm) >= 25 else 0

        # Citlivostní analýza pro tento model
        scenare_mk = []
        spotreba_kwh_mk = (vstup.sp_by_vt_mwh * 1000 * pb) + (vstup.sp_sp_mwh * 1000) + (vstup.sp_by_nt_mwh * 1000 * pb)
        for rust_sc, label_sc in [(1.0, "📉 Pomalý růst cen EE +1 %/rok"),
                                   (3.0, "📊 Realistický scénář +3 %/rok"),
                                   (6.0, "🔥 Rychlý růst cen EE +6 %/rok")]:
            kum_sc = -(invest_mk - uver_mk)  # vlastní vklad = počáteční záporný stav
            nav_sc = None
            bezfve_25 = 0.0
            for rok in range(1, 26):
                c = (1 + rust_sc / 100) ** (rok - 1)
                d = (1 - vstup.deg_pan / 100) ** (rok - 1)
                u = (sm["vlastni_vt_kwh"] * d * cvt * c
                     + sm["vlastni_nt_kwh"] * d * cnt * c
                     + sm["pretoky_kwh"]    * d * (vstup.cena_pretoky / 1000) * c
                     + jist_mk * c)  # úspora jističe (PM)
                s = spl_mk if rok <= vstup.splatnost else 0
                kum_sc += u - s
                if kum_sc >= 0 and nav_sc is None:
                    nav_sc = rok
                bezfve_25 += spotreba_kwh_mk * cvt * c
            scenare_mk.append({
                "label":    label_sc,
                "rust":     rust_sc,
                "nav":      nav_sc,
                "kum25":    round(kum_sc),
                "bezfve25": round(bezfve_25),
            })

        srovnani[mk] = {
            "invest":            round(invest_mk),
            "mericu":            round(mericu_mk),
            "sp_kwp":            sp_kwp if mk == "spolecne" else None,
            "kwp":               sp_kwp if mk == "spolecne" else kwp_byty,
            "bat":               0 if mk in ("edc_bez_bat","spolecne") else bat_byty,
            "uspora_rok1":       round(uspora1_m),
            "uspora_jistic_rok": round(jist_mk),
            "nav":               nav_m,
            "stat":              round(stat_m, 1),
            "kum25":             round(kum25_m),
            "mira_vs":           round(sm.get("mira_vs", 0) * 100, 1),
            "mira_sob":          round(sm.get("mira_sob", 0) * 100, 1),
            "splatka_byt":       spl_byt,
            "cisty_byt":         cisty_byt,
            "uver":              round(uver_mk),
            "vlastni_vklad":     round(invest_mk - uver_mk),
            "splatka_rok":       round(spl_mk),
            "splatka_byt_mes":   spl_byt,
            "cvt":               round(cvt * 1000),
            "cnt":               round(cnt * 1000),
            "cf":                cfm,
            "sim":               {
                "vyroba_kwh":    sm.get("vyroba_kwh", 0),
                "vlastni_kwh":   sm.get("vlastni_kwh", 0),
                "vlastni_vt_kwh": sm.get("vlastni_vt_kwh", 0),
                "vlastni_nt_kwh": sm.get("vlastni_nt_kwh", 0),
                "pretoky_kwh":   sm.get("pretoky_kwh", 0),
                "mira_vs":       sm.get("mira_vs", 0),
                "mira_sob":      sm.get("mira_sob", 0),
                "profil_den":    sm.get("profil_den", []),
            },
            "scenare":           scenare_mk,
        }

    # ================================================================
    # CITLIVOSTNÍ ANALÝZA — 3 scénáře vývoje cen (backend)
    # ================================================================
    scenare = []
    spotreba_kwh = (vstup.sp_by_vt_mwh * 1000 * pb) + (vstup.sp_sp_mwh * 1000) + (vstup.sp_by_nt_mwh * 1000 * pb)
    for rust_sc, label in [(1.0, "📉 Pomalý růst cen EE +1 %/rok"),
                            (3.0, "📊 Realistický scénář +3 %/rok"),
                            (6.0, "🔥 Rychlý růst cen EE +6 %/rok")]:
        # Kumulativ = čistý cashflow SVJ
        # Startuje od záporného vlastního vkladu (co SVJ zaplatí z kapsy)
        # Splátky NZÚ jsou výdaj, úspory jsou příjem
        # Návratnost = kdy kumulativ přejde do kladna (vlastní vklad se vrátil)
        kum_sc    = -vlastni if vlastni > 0 else -vstup.cena_invest  # min. záporný start = celá investice
        nav_sc    = None
        bezfve_25 = 0.0
        for rok in range(1, 26):
            c = (1 + rust_sc / 100) ** (rok - 1)
            d = (1 - vstup.deg_pan / 100) ** (rok - 1)
            u = (sim["vlastni_vt_kwh"] * d * cvt * c
                 + sim["vlastni_nt_kwh"] * d * cnt * c
                 + sim["pretoky_kwh"]    * d * (vstup.cena_pretoky / 1000) * c)
            s = uver / vstup.splatnost if rok <= vstup.splatnost else 0
            kum_sc += u - s
            if kum_sc >= 0 and nav_sc is None:
                nav_sc = rok
            bezfve_25 += spotreba_kwh * cvt * c
        scenare.append({
            "label":    label,
            "rust":     rust_sc,
            "nav":      nav_sc,
            "kum25":    round(kum_sc),
            "bezfve25": round(bezfve_25),
        })

    return {
        "sim":             sim,
        "cf":              cf,
        "cena_invest":     vstup.cena_invest,
        "uver":            round(uver),
        "vlastni_vklad":   round(vlastni),
        "vlastni_pct":     vstup.vlastni_pct,
        "splatka_rok":     round(splatka),
        "splatka_mes":     round(splatka / 12),
        "splatka_byt_mes": round(splatka / 12 / pb),
        "splatnost":       vstup.splatnost,
        "cvt":             round(cvt * 1000),
        "cnt":             round(cnt * 1000),
        "srovnani":        srovnani,
        "scenare":         scenare,
        "kwp":             vstup.kwp,
        "bat":             vstup.bat,
        "bytu":            pb,
    }


# ================================================================
# CENÍKY
# ================================================================

@app.get("/ceniky", tags=["data"])
def ceniky():
    return {
        "distributori": list(e.CENY_VT.keys()),
        "ceny_vt":      e.CENY_VT,
        "ceny_nt":      e.CENY_NT,
        "stay_plat":    e.STAY_PLAT,
        "sazby_nt":     e.SAZBY_NT,
        "podil_nt":     e.PODIL_NT,
        "jistic_byt":   e.JISTIC_BYT,
    }
