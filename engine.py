# engine.py — Simulační engine FVE kalkulačky pro SVJ
# Čistý Python, žádné Streamlit závislosti — připravený pro FastAPI
#
# Autoritativní hodnoty: ceníky 2026 (zdroj: TZB-info, ERÚ výměr 14/2025,
# ceníky ČEZ/EGD/PRE k 1.1.2026)
#
# Verze 2.1 — přidány funkce pro PM (podružné měření):
#   jistic_dum_ampery_pm(), vypocet_pm(), JISTIC_SP_OPTS

import datetime
import functools
import math
import requests
import numpy as np

# ================================================================
# CENÍKOVÉ TABULKY 2026 — autoritativní hodnoty
# ================================================================

CENY_VT = {
    "ČEZ Distribuce": {"D01d": 7320, "D02d": 6610, "D25d": 6920, "D26d": 5650, "D27d": 6920,
                       "D35d": 5410, "D45d": 5410, "D56d": 5410, "D57d": 5410, "D61d": 8050},
    "EG.D (E.ON)":    {"D01d": 7050, "D02d": 6550, "D25d": 6650, "D26d": 5430, "D27d": 6650,
                       "D35d": 4270, "D45d": 4270, "D56d": 4270, "D57d": 4270, "D61d": 7720},
    "PREdistribuce":  {"D01d": 5980, "D02d": 5570, "D25d": 5620, "D26d": 4840, "D27d": 5620,
                       "D35d": 3910, "D45d": 3910, "D56d": 3910, "D57d": 3910, "D61d": 6770},
}

CENY_NT = {
    "ČEZ Distribuce": {"D25d": 4070, "D26d": 4070, "D27d": 4020, "D35d": 4390,
                       "D45d": 4390, "D56d": 4390, "D57d": 4390, "D61d": 4200},
    "EG.D (E.ON)":    {"D25d": 3830, "D26d": 3830, "D27d": 3830, "D35d": 3830,
                       "D45d": 3830, "D56d": 3830, "D57d": 3830, "D61d": 3830},
    "PREdistribuce":  {"D25d": 3590, "D26d": 3590, "D27d": 3590, "D35d": 3590,
                       "D45d": 3590, "D56d": 3590, "D57d": 3590, "D61d": 3590},
}

STAY_PLAT = {"ČEZ Distribuce": 179, "EG.D (E.ON)": 160, "PREdistribuce": 157}

JISTIC_BYT = {
    "ČEZ Distribuce": {"1×25A": 132, "3×16A": 190, "3×20A": 238, "3×25A": 298, "3×32A": 381},
    "EG.D (E.ON)":    {"1×25A": 121, "3×16A": 193, "3×20A": 242, "3×25A": 303, "3×32A": 387},
    "PREdistribuce":  {"1×25A": 132, "3×16A": 190, "3×20A": 230, "3×25A": 287, "3×32A": 360},
}

JISTIC_DUM = {
    "ČEZ Distribuce": {10: 121, 16: 191, 20: 240, 25: 309, 32: 383,
                       40: 479, 50: 600, 63: 751, 80: 869, 100: 989},
    "EG.D (E.ON)":    {10: 116, 16: 186, 20: 232, 25: 290, 32: 373,
                       40: 465, 50: 581, 63: 729, 80: 845, 100: 961},
    "PREdistribuce":  {10: 106, 16: 169, 20: 213, 25: 266, 32: 339,
                       40: 424, 50: 530, 63: 667, 80: 773, 100: 879},
}
JISTIC_DUM_A = {"ČEZ Distribuce": 5.99, "EG.D (E.ON)": 5.81, "PREdistribuce": 5.30}

JISTIC_DUM_C = {
    "ČEZ Distribuce": {16: 286,  20: 358,  25: 450,  32: 572,
                       40: 715,  50: 894,  63: 1145, 80: 1265, 100: 1384, 125: 1549, 160: 1788},
    "EG.D (E.ON)":    {10: 116,  16: 186,  20: 232,  25: 290,  32: 373,
                       40: 465,  50: 581,  63: 729,  80: 845,  100: 961},
    "PREdistribuce":  {10: 144,  16: 230,  20: 288,  25: 359,  32: 460,
                       40: 575,  50: 719,  63: 905,  80: 1150, 100: 1437, 125: 1797, 160: 2300},
}
JISTIC_DUM_C_A = {"ČEZ Distribuce": 14.88, "EG.D (E.ON)": 5.81, "PREdistribuce": 14.37}

JISTIC_3x25 = {
    "ČEZ Distribuce": {"D01d": 132, "D02d": 298, "D25d": 287, "D26d": 422, "D27d": 272,
                       "D35d": 517, "D45d": 567, "D56d": 567, "D57d": 568, "D61d": 238},
    "EG.D (E.ON)":    {"D01d": 121, "D02d": 303, "D25d": 296, "D26d": 422, "D27d": 282,
                       "D35d": 575, "D45d": 575, "D56d": 575, "D57d": 572, "D61d": 271},
    "PREdistribuce":  {"D01d": 162, "D02d": 359, "D25d": 557, "D26d": 1262, "D27d": 529,
                       "D35d": 1545, "D45d": 1545, "D56d": 1545, "D57d": 1545, "D61d": 525},
}

SAZBY_NT = ["D25d", "D26d", "D27d", "D35d", "D45d", "D56d", "D57d", "D61d"]

PODIL_NT = {
    "D25d": 0.35, "D26d": 0.35, "D27d": 0.35, "D35d": 0.60,
    "D45d": 0.70, "D56d": 0.75, "D57d": 0.75, "D61d": 0.40,
}

NT_HODINY = {
    "D25d": set(list(range(22, 24)) + list(range(0, 6))),
    "D26d": set(list(range(22, 24)) + list(range(0, 6))),
    "D27d": set(list(range(22, 24)) + list(range(0, 6))),
    "D35d": set(list(range(22, 24)) + list(range(0, 6)) + list(range(10, 14))),
    "D45d": set(range(24)),
    "D56d": set(range(24)),
    "D57d": set(list(range(22, 24)) + list(range(0, 6)) + list(range(10, 14))),
    "D61d": set(list(range(22, 24)) + list(range(0, 8))),
}

SP_ZAR = {
    "zaklad":   {"vt": 1200, "nt": 0},
    "sporak":   {"vt": 400,  "nt": 0},
    "bojler":   {"vt": 0,    "nt": 800},
    "klima":    {"vt": 400,  "nt": 0},
    "akum":     {"vt": 0,    "nt": 2000},
    "primotop": {"vt": 0,    "nt": 2500},
    "tc":       {"vt": 0,    "nt": 3000},
    "ev":       {"vt": 0,    "nt": 1500},
}

# ================================================================
# TDD PROFILY
# ================================================================

_TDD4 = {
    "zima_prac":        np.array([0.412,0.371,0.348,0.339,0.343,0.377,0.524,0.784,0.883,0.819,0.762,0.741,0.758,0.738,0.717,0.739,0.820,1.118,1.284,1.222,1.082,0.917,0.718,0.551], dtype=float),
    "prechodne_prac":   np.array([0.395,0.355,0.333,0.325,0.329,0.366,0.500,0.730,0.822,0.768,0.719,0.699,0.717,0.697,0.676,0.698,0.778,1.037,1.181,1.119,0.989,0.837,0.648,0.496], dtype=float),
    "leto_prac":        np.array([0.378,0.339,0.319,0.311,0.316,0.356,0.476,0.676,0.761,0.718,0.676,0.657,0.676,0.656,0.636,0.657,0.737,0.957,1.079,1.017,0.897,0.757,0.578,0.441], dtype=float),
    "zima_vikend":      np.array([0.451,0.404,0.375,0.364,0.366,0.384,0.420,0.552,0.752,0.901,0.950,0.938,0.901,0.860,0.820,0.820,0.879,1.047,1.148,1.098,0.978,0.818,0.648,0.521], dtype=float),
    "prechodne_vikend": np.array([0.423,0.379,0.352,0.341,0.343,0.360,0.398,0.524,0.713,0.858,0.904,0.893,0.858,0.819,0.780,0.780,0.838,0.997,1.094,1.044,0.929,0.778,0.615,0.490], dtype=float),
    "leto_vikend":      np.array([0.396,0.355,0.329,0.319,0.321,0.337,0.377,0.497,0.675,0.816,0.859,0.848,0.816,0.778,0.741,0.741,0.797,0.948,1.040,0.991,0.881,0.738,0.582,0.458], dtype=float),
}
for _k in _TDD4:
    _TDD4[_k] = _TDD4[_k] / _TDD4[_k].mean()

_TDD_SP = {
    "zima_prac":        np.array([0.55,0.52,0.50,0.50,0.50,0.55,0.75,0.95,0.85,0.75,0.72,0.72,0.72,0.72,0.75,0.85,0.95,1.10,1.15,1.10,1.00,0.90,0.75,0.62], dtype=float),
    "prechodne_prac":   np.array([0.50,0.47,0.45,0.45,0.45,0.50,0.70,0.88,0.78,0.70,0.67,0.67,0.67,0.67,0.70,0.78,0.88,1.00,1.05,1.00,0.91,0.81,0.68,0.56], dtype=float),
    "leto_prac":        np.array([0.45,0.42,0.40,0.40,0.40,0.45,0.65,0.80,0.72,0.65,0.62,0.62,0.62,0.62,0.65,0.72,0.80,0.90,0.95,0.90,0.82,0.72,0.60,0.50], dtype=float),
    "zima_vikend":      np.array([0.58,0.54,0.52,0.51,0.51,0.54,0.62,0.78,0.90,0.95,0.95,0.93,0.90,0.88,0.85,0.88,0.92,1.05,1.10,1.05,0.95,0.85,0.72,0.63], dtype=float),
    "prechodne_vikend": np.array([0.53,0.49,0.47,0.46,0.46,0.49,0.57,0.72,0.82,0.88,0.88,0.86,0.82,0.80,0.78,0.80,0.84,0.97,1.01,0.97,0.88,0.78,0.66,0.58], dtype=float),
    "leto_vikend":      np.array([0.48,0.44,0.42,0.41,0.41,0.44,0.52,0.65,0.75,0.80,0.80,0.78,0.75,0.73,0.71,0.73,0.77,0.88,0.92,0.88,0.80,0.71,0.60,0.52], dtype=float),
}
for _k in _TDD_SP:
    _TDD_SP[_k] = _TDD_SP[_k] / _TDD_SP[_k].mean()

_UPRAVY = {
    "mix":        np.ones(24, dtype=float),
    "seniori":    np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.3,1.5,1.6,1.6,1.5,1.5,1.4,1.4,1.3,1.1,1.0,1.0,1.0,1.0,1.0,1.0], dtype=float),
    "pracujici":  np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.2,1.3,0.7,0.5,0.5,0.5,0.5,0.5,0.5,0.6,0.8,1.3,1.4,1.3,1.2,1.1,1.0,1.0], dtype=float),
    "rodiny":     np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.2,0.9,0.7,0.7,0.7,0.8,0.8,0.9,1.1,1.2,1.2,1.2,1.1,1.1,1.0,1.0,1.0], dtype=float),
    "provozovna": np.array([0.8,0.8,0.8,0.8,0.8,0.9,1.0,1.2,1.5,1.6,1.7,1.7,1.6,1.6,1.6,1.5,1.3,1.1,1.0,0.9,0.9,0.8,0.8,0.8], dtype=float),
}
for _k in _UPRAVY:
    _UPRAVY[_k] = _UPRAVY[_k] / _UPRAVY[_k].mean()

_MESICE = ["Led", "Úno", "Bře", "Dub", "Kvě", "Čvn", "Čvc", "Srp", "Zář", "Říj", "Lis", "Pro"]
_CD = 365 * 96


# ================================================================
# DOPORUČENÍ — SAZBA, JISTIČ, SP, kWp, BATERIE
# ================================================================

def doporuc_sazbu(zarizeni: list) -> str:
    if "tc"       in zarizeni: return "D57d"
    if "primotop" in zarizeni: return "D45d"
    if "akum"     in zarizeni: return "D26d"
    if "ev"       in zarizeni and "bojler" not in zarizeni: return "D27d"
    if "bojler"   in zarizeni or "ev" in zarizeni:          return "D25d"
    return "D02d"


def doporuc_jistic_byt(zarizeni: list) -> str:
    if "tc" in zarizeni or "primotop" in zarizeni or "akum" in zarizeni:
        return "3×32A"
    if "sporak" in zarizeni:
        return "3×25A"
    return "1×25A"


def doporuc_jistic_dum(pocet_bytu: int, zarizeni: list) -> tuple:
    pb = int(pocet_bytu)
    has_tc     = "tc"       in zarizeni
    has_primo  = "primotop" in zarizeni
    has_akum   = "akum"     in zarizeni
    has_sporak = "sporak"   in zarizeni
    has_bojler = "bojler"   in zarizeni
    has_ev     = "ev"       in zarizeni

    if has_tc:
        if pb <= 8:    return "3×50A", 50
        elif pb <= 16: return "3×63A", 63
        else:          return "3×80A", 80

    if has_primo or has_akum:
        if pb <= 6:    return "3×40A", 40
        elif pb <= 12: return "3×50A", 50
        else:          return "3×63A", 63

    if has_sporak and has_bojler:
        if pb <= 8:    return "3×32A", 32
        elif pb <= 16: return "3×40A", 40
        elif pb <= 24: return "3×50A", 50
        else:          return "3×63A", 63

    if has_sporak or has_bojler or has_ev:
        if pb <= 12:   return "3×32A", 32
        elif pb <= 24: return "3×40A", 40
        else:          return "3×50A", 50

    if pb <= 10:   return "3×25A", 25
    elif pb <= 20: return "3×32A", 32
    elif pb <= 40: return "3×40A", 40
    elif pb <= 60: return "3×50A", 50
    else:          return "3×63A", 63


def sp_sp_vypocet(
    pocet_bytu: int,
    pocet_pater: int,
    pocet_vytahu: int,
    ma_tuv_central: bool,
    ma_tc_dum: bool,
    pocet_ev_nabijec: int,
    pocet_cerpadel: int = 0,
) -> dict:
    pb = int(pocet_bytu)
    pp = int(pocet_pater)
    pv = int(pocet_vytahu)
    pc = int(pocet_cerpadel)

    sp_osvetleni = pp * 200 + pb * 2 + 100
    sp_vytah     = 3000 * pv * (1 + pp / 20.0) if pv > 0 else 0.0
    sp_cerpadla  = 536  * pc * (1 + pp / 30.0) if pc > 0 else 0.0
    sp_vt = sp_osvetleni + sp_vytah + sp_cerpadla

    sp_tuv = 800  * pb if ma_tuv_central    else 0.0
    sp_tc  = 3000 * pb if ma_tc_dum         else 0.0
    sp_ev  = 1500 * int(pocet_ev_nabijec)
    sp_nt  = sp_tuv + sp_tc + sp_ev

    if ma_tc_dum:        sazba_sp = "D57d"
    elif ma_tuv_central: sazba_sp = "D25d"
    else:                sazba_sp = "D02d"

    P_sp_kw = (pv * 7.5) + pc * 0.25 + 1.0
    if ma_tc_dum:              P_sp_kw += pb * 3.0
    elif ma_tuv_central:       P_sp_kw += pb * 0.5
    if pocet_ev_nabijec > 0:   P_sp_kw += pocet_ev_nabijec * 7.4
    I_sp = P_sp_kw * 1000 / (math.sqrt(3) * 400)
    _std = [25, 32, 40, 50, 63, 80, 100]
    jistic_sp_a = next((j for j in _std if j >= I_sp), 100)

    popis = [f"Osvětlení chodeb: {sp_osvetleni:.0f} kWh/rok"]
    if pv > 0:               popis.append(f"Výtah ({pv}×): {sp_vytah:.0f} kWh/rok")
    if pc > 0:               popis.append(f"Čerpadla ({pc}×): {sp_cerpadla:.0f} kWh/rok")
    if ma_tuv_central:       popis.append(f"Centrální TUV: {sp_tuv:.0f} kWh/rok (NT)")
    if ma_tc_dum:            popis.append(f"TČ domu: {sp_tc:.0f} kWh/rok (NT)")
    if pocet_ev_nabijec > 0: popis.append(f"EV nabíječky ({pocet_ev_nabijec}×): {sp_ev:.0f} kWh/rok (NT)")

    return {
        "sp_mwh":      round((sp_vt + sp_nt) / 1000.0, 3),
        "sp_vt_mwh":   round(sp_vt / 1000.0, 3),
        "sp_nt_mwh":   round(sp_nt / 1000.0, 3),
        "sazba_sp":    sazba_sp,
        "jistic_sp":   f"3×{jistic_sp_a}A",
        "jistic_sp_a": jistic_sp_a,
        "P_sp_kw":     round(P_sp_kw, 1),
        "I_sp_a":      round(I_sp, 1),
        "popis":       popis,
    }


def sp_z_zarizeni(zarizeni: list, pocet_bytu: int) -> tuple:
    vt = sum(SP_ZAR[z]["vt"] for z in zarizeni if z in SP_ZAR)
    nt = sum(SP_ZAR[z]["nt"] for z in zarizeni if z in SP_ZAR)
    return vt / 1000.0, nt / 1000.0


def cena_kwp(kwp: float) -> int:
    if kwp < 10:   return 38000
    elif kwp < 20: return 33000
    elif kwp < 40: return 28000
    elif kwp < 80: return 24000
    else:          return 21000


def doporuc_kwp_bat(
    sp_vt_celkem_kwh: float,
    sp_nt_celkem_kwh: float,
    sp_sp_mwh: float,
    zarizeni: list,
    pocet_vchodu: int = 1,
) -> dict:
    sp_total_vt = sp_vt_celkem_kwh + sp_sp_mwh * 1000.0

    # OPRAVA: byl zde chybný vzorec /1.05 místo /1050
    kwp_min = max(5.0, sp_total_vt * 0.75 / 1050)
    kwp = round(kwp_min / 5) * 5
    kwp = max(5.0, kwp)

    if "tc" in zarizeni:
        kwp = round(kwp * 1.15 / 5) * 5
    if "ev" in zarizeni:
        kwp = round(kwp * 1.10 / 5) * 5

    kwp = max(5.0, kwp)

    bat = round(kwp * 1.4 / 5) * 5

    c_kwp = cena_kwp(kwp)
    cena_fve = round(kwp * c_kwp)
    cena_bat = round(bat * 15000)
    extra_vchod = max(0, int(pocet_vchodu) - 1) * 30000
    cena_celkem = cena_fve + cena_bat + extra_vchod

    return {
        "kwp":          kwp,
        "bat":          bat,
        "cena_kwp":     c_kwp,
        "cena_fve":     cena_fve,
        "cena_bat":     cena_bat,
        "cena_celkem":  cena_celkem,
    }


def cena_jistice_dum(dist: str, ampery: int, c_tarif: bool = False) -> int:
    if c_tarif:
        tab   = JISTIC_DUM_C.get(dist, JISTIC_DUM_C["ČEZ Distribuce"])
        amp_a = JISTIC_DUM_C_A.get(dist, 14.88)
    else:
        tab   = JISTIC_DUM.get(dist, JISTIC_DUM["ČEZ Distribuce"])
        amp_a = JISTIC_DUM_A.get(dist, 5.99)
    klice = sorted(tab.keys())
    for k in klice:
        if ampery <= k:
            return tab[k]
    max_k = klice[-1]
    return round(tab[max_k] + (ampery - max_k) * amp_a)


# ================================================================
# PM (PODRUŽNÉ MĚŘENÍ) — výpočet úspory a nákladů
# Portováno z app.py — autoritativní logika
# ================================================================

# Seznam standardních jističů SP pro select ve wizardu
JISTIC_SP_OPTS = [25, 32, 40, 50, 63, 80, 100]


def jistic_dum_ampery_pm(pocet_bytu: int, zarizeni: list) -> int:
    """Odhadne velikost hlavního jističe PM (patka domu, C tarif) v ampérech.

    Empirická tabulka dle praxe distributorů (z app.py — autoritativní).
    PM = celý dům jako jedno ODM → větší jistič než pro SP.

    Byty  | Základní | Sporák | Bojler | TČ     | Elektrokotel/akum
    ------+----------+--------+--------+--------+------------------
    ≤10   |  3×32A   | 3×40A  | 3×40A  | 3×63A  | 3×80A
    ≤20   |  3×40A   | 3×50A  | 3×63A  | 3×80A  | 3×100A
    ≤30   |  3×50A   | 3×63A  | 3×80A  | 3×100A | 3×125A
    ≤50   |  3×63A   | 3×80A  | 3×100A | 3×125A | 3×160A
    ≤100  |  3×80A   | 3×100A | 3×125A | 3×160A | 3×200A
    ≤150  |  3×100A  | 3×125A | 3×160A | 3×200A | 3×250A
    ≤200  |  3×125A  | 3×160A | 3×200A | 3×250A | 3×315A
    >200  |  3×160A  | 3×200A | 3×250A | 3×315A | 3×400A
    """
    pb = int(pocet_bytu)
    has_ek  = "primotop" in zarizeni or "akum" in zarizeni
    has_tc  = "tc"       in zarizeni
    has_boj = "bojler"   in zarizeni
    has_sp  = "sporak"   in zarizeni

    _TAB = [
        ( 10,  32,  40,  40,  63,  80),
        ( 20,  40,  50,  63,  80, 100),
        ( 30,  50,  63,  80, 100, 125),
        ( 50,  63,  80, 100, 125, 160),
        (100,  80, 100, 125, 160, 200),
        (150, 100, 125, 160, 200, 250),
        (200, 125, 160, 200, 250, 315),
        (999, 160, 200, 250, 315, 400),
    ]
    for max_b, z, sp, boj, tc, ek in _TAB:
        if pb <= max_b:
            if has_ek:  return ek
            if has_tc:  return tc
            if has_boj: return boj
            if has_sp:  return sp
            return z
    return 160


def vypocet_pm(
    pocet_bytu: int,
    pocet_vchodu: int,
    zarizeni: list,
    dist: str,
    jistic_byt: str,
    jistic_sp_a: int,
) -> dict:
    """Vypočítá úsporu a náklady při přechodu na PM (podružné měření).

    Logika z app.py (řádky 1155-1171) — autoritativní:

    Stávající stav (bez PM):
      (N+1) × stálý plat  [N bytů + 1 ODM SP]
      N × cena_jistic_byt [D tarif, individuální ODM]
      cena_jistic_SP      [D tarif, SP jako samostatné ODM]

    PM stav:
      1 × stálý plat      [jeden ODM pro celý dům]
      cena_jistic_PM      [C tarif — SVJ jako podnikatel, dražší!]

    Úspora/rok = (stávající_mes - PM_mes) × 12

    Náklady PM (z app.py):
      N × 10 000 Kč       [podružné měřiče na byty]
      75 000 Kč           [projekt elektro + přepojení]
      (vchody-1) × 30 000 [každý další vchod = extra rozvaděč]
    """
    pb   = int(pocet_bytu)
    stay = float(STAY_PLAT.get(dist, 179))

    jbyt_tab  = JISTIC_BYT.get(dist, JISTIC_BYT["ČEZ Distribuce"])
    jbyt_cena = float(jbyt_tab.get(jistic_byt, 298))

    jsp_cena = float(cena_jistice_dum(dist, jistic_sp_a, c_tarif=False))

    jpm_a    = jistic_dum_ampery_pm(pb, zarizeni)
    jpm_cena = float(cena_jistice_dum(dist, jpm_a, c_tarif=True))

    platby_ted_mes = (pb + 1) * stay + pb * jbyt_cena + jsp_cena
    platby_pm_mes  = stay + jpm_cena

    uspora_mes = platby_ted_mes - platby_pm_mes
    uspora_rok = round(uspora_mes * 12.0)

    cena_mericu = pb * 10000 + 75000 + max(0, int(pocet_vchodu) - 1) * 30000

    return {
        "jistic_pm_a":        jpm_a,
        "jistic_pm_str":      f"3×{jpm_a}A",
        "jistic_pm_cena_mes": round(jpm_cena),
        "platby_ted_mes":     round(platby_ted_mes),
        "platby_pm_mes":      round(platby_pm_mes),
        "uspora_pm_mes":      round(uspora_mes),
        "uspora_pm_rok":      uspora_rok,
        "cena_mericu_pm":     cena_mericu,
        "jistic_sp_opts":     JISTIC_SP_OPTS,
    }


# ================================================================
# PROFILY SPOTŘEBY
# ================================================================

def _sezona(m: int) -> str:
    if m in [11, 12, 1, 2]: return "zima"
    if m in [5, 6, 7, 8]:   return "leto"
    return "prechodne"


def _tdd4_klic(sezona: str, vikend: bool) -> str:
    if sezona == "zima"      and not vikend: return "zima_prac"
    if sezona == "zima"      and vikend:     return "zima_vikend"
    if sezona == "leto"      and not vikend: return "leto_prac"
    if sezona == "leto"      and vikend:     return "leto_vikend"
    if sezona == "prechodne" and not vikend: return "prechodne_prac"
    if sezona == "prechodne" and vikend:     return "prechodne_vikend"
    return "prechodne_prac"


def _smiseny_profil(pct_pracujici: float, pct_seniori: float, pct_rodiny: float) -> np.ndarray:
    total = pct_pracujici + pct_seniori + pct_rodiny
    if total <= 0:
        return _UPRAVY["mix"].copy()
    p = (_UPRAVY["pracujici"] * pct_pracujici +
         _UPRAVY["seniori"]   * pct_seniori +
         _UPRAVY["rodiny"]    * pct_rodiny) / total
    return p / p.mean()


def _gen_profil_vt(kwh: float, tdd: dict, uprava: np.ndarray = None) -> np.ndarray:
    vals = []
    den = datetime.date(2026, 1, 1)
    for _ in range(365):
        sz = _sezona(den.month)
        vi = den.weekday() >= 5
        klic = _tdd4_klic(sz, vi)
        p = tdd[klic].copy()
        if uprava is not None:
            p = p * uprava
            p = p / p.mean()
        for h in range(24):
            v = float(p[h]) / 4.0
            vals.extend([v, v, v, v])
        den += datetime.timedelta(days=1)
    arr = np.array(vals, dtype=float)[:_CD]
    if arr.sum() > 0:
        arr = arr * (float(kwh) / arr.sum())
    return arr


def _gen_profil_nt(kwh: float, sazba: str) -> np.ndarray:
    nt_h = NT_HODINY.get(sazba, set())
    if not nt_h or kwh <= 0:
        return np.zeros(_CD, dtype=float)
    vals = []
    for _ in range(365):
        for h in range(24):
            v = 1.0 / 4.0 if h in nt_h else 0.0
            vals.extend([v, v, v, v])
    arr = np.array(vals, dtype=float)[:_CD]
    if arr.sum() > 0:
        arr = arr * (float(kwh) / arr.sum())
    return arr


def _interpoluj(hod) -> np.ndarray:
    h = np.array(hod, dtype=float)
    res = np.repeat(h, 4) / 4.0
    return res[:_CD]


def _gen_vyroba_fallback(kwp: float, sklon: int = 35, azimut: int = 0) -> np.ndarray:
    vh = np.zeros(8760, dtype=float)
    for h in range(8760):
        dr = h // 24
        hod = h % 24
        uhel = 2 * np.pi * (dr - 80) / 365.0
        delka = 12 + 4.5 * np.sin(uhel)
        vychod = 12 - delka / 2
        zapad  = 12 + delka / 2
        if vychod <= hod <= zapad:
            t = (hod - vychod) / delka
            elev  = np.sin(np.pi * t)
            sezon = max(0.3, min(1.0, 0.5 + 0.5 * np.sin(uhel + np.pi / 2)))
            koef  = 1.0 + 0.15 * np.sin(np.pi * float(sklon) / 90.0)
            vh[h] = float(kwp) * elev * sezon * koef * 0.85
    if vh.sum() > 0:
        vh = vh * (float(kwp) * 1050.0 / vh.sum())
    return vh


# ================================================================
# HLAVNÍ SIMULACE
# ================================================================

def simuluj(
    vyroba_15: np.ndarray,
    sp_vt15: np.ndarray,
    sp_nt15: np.ndarray,
    bat: float = 0.0,
    model: str = "edc",
    edc_ztrata: float = 0.0,
) -> dict:
    v   = np.array(vyroba_15, dtype=float)
    svt = np.array(sp_vt15,   dtype=float)
    snt = np.array(sp_nt15,   dtype=float)
    bat = float(bat)

    if model == "spolecne":
        snt = np.zeros(len(v), dtype=float)

    n = int(min(len(v), len(svt), len(snt)))
    v, svt, snt = v[:n], svt[:n], snt[:n]

    bmin, bmax, bkwh = bat * 0.10, bat * 0.90, bat * 0.50
    eta = 0.92

    vl_vt = np.zeros(n, dtype=float)
    vl_nt = np.zeros(n, dtype=float)
    pr    = np.zeros(n, dtype=float)
    od_vt = np.zeros(n, dtype=float)
    od_nt = np.zeros(n, dtype=float)

    for i in range(n):
        vi   = float(v[i])
        svti = float(svt[i])
        snti = float(snt[i])

        prime = min(vi, svti)
        vl_vt[i] = prime
        zbyla_v   = vi   - prime
        zbyla_svt = svti - prime

        if zbyla_v > 0.0 and bat > 0.0:
            nab = min(zbyla_v * eta, bmax - bkwh)
            bkwh += nab
            zbyla_v -= nab / eta

        pr[i] = zbyla_v

        if zbyla_svt > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(zbyla_svt, dos)
            bkwh -= vyb / eta
            zbyla_svt -= vyb
            vl_vt[i] += vyb

        od_vt[i] = zbyla_svt

        if snti > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(snti, dos)
            bkwh -= vyb / eta
            snti -= vyb
            vl_nt[i] = vyb

        od_nt[i] = snti

    tv  = float(v.sum())
    tvl = float(vl_vt.sum()) + float(vl_nt.sum())
    tsp = float(svt.sum()) + float(snt.sum())

    casovy_prekryv = (
        float(np.minimum(v[:n], (svt + snt)[:n]).sum()) / float(tv)
        if tv > 0 else 1.0
    )
    casovy_prekryv = min(1.0, casovy_prekryv)

    if model == "edc" and edc_ztrata > 0:
        korekce = 1.0 - float(edc_ztrata) / 100.0
        tvl *= korekce

    tpr = tv - tvl

    mv, ms, mvl, mpr = [], [], [], []
    for m in range(12):
        a, b = m * 30 * 96, min((m + 1) * 30 * 96, n)
        mv.append(float(v[a:b].sum()))
        ms.append(float(svt[a:b].sum()) + float(snt[a:b].sum()))
        mvl.append(float(vl_vt[a:b].sum()) + float(vl_nt[a:b].sum()))
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
        "mira_vs":         tvl / tv   if tv  > 0 else 0.0,
        "mira_sob":        min(1.0, tvl / tsp) if tsp > 0 else 0.0,
        "edc_efektivita":  casovy_prekryv,
        "mesice_vyroba":   mv,
        "mesice_spotreba": ms,
        "mesice_vlastni":  mvl,
        "mesice_pretoky":  mpr,
        "mesice_nazvy":    _MESICE,
    }


# ================================================================
# CASHFLOW 25 LET
# ================================================================

def cashflow(
    vl_vt: float, vl_nt: float, pr: float,
    cvt: float, cnt: float, cpr: float,
    vlast: float, uver: float, spl: float, splat: int,
    rust: float = 3.0, deg: float = 0.5, leta: int = 25,
    jist: float = 0.0, bonus: float = 0.0, deg_bat: float = 2.0,
) -> list:
    res = []
    kum = -(float(vlast) + float(uver) - float(bonus))
    for rok in range(1, int(leta) + 1):
        d     = (1.0 - float(deg)     / 100.0) ** (rok - 1)
        d_bat = (1.0 - float(deg_bat) / 100.0) ** (rok - 1)
        c     = (1.0 + float(rust)    / 100.0) ** (rok - 1)
        u = (float(vl_vt) * d     * float(cvt) * c +
             float(vl_nt) * d_bat * float(cnt) * c +
             float(pr)    * d     * float(cpr) * c +
             float(jist)  * c)
        s = float(spl) if rok <= int(splat) else 0.0
        kum += u - s
        res.append({
            "rok":            rok,
            "vyroba_mwh":     round((float(vl_vt) + float(vl_nt) + float(pr)) * d / 1000.0, 2),
            "vlastni_mwh":    round((float(vl_vt) + float(vl_nt)) * d / 1000.0, 2),
            "pretoky_mwh":    round(float(pr) * d / 1000.0, 2),
            "uspora_vt":      round(float(vl_vt) * d * float(cvt) * c),
            "uspora_nt":      round(float(vl_nt) * d_bat * float(cnt) * c),
            "uspora_pretoky": round(float(pr) * d * float(cpr) * c),
            "uspora_jom":     round(float(jist) * c),
            "uspora_fve":     round(float(vl_vt) * d * float(cvt) * c +
                                    float(vl_nt) * d_bat * float(cnt) * c +
                                    float(pr) * d * float(cpr) * c),
            "uspora_celkem":  round(u),
            "splatka":        round(s),
            "cisty_prinos":   round(u - s),
            "kumulativni":    round(kum),
            "cena_vt":        round(float(cvt) * c, 3),
        })
    return res


# ================================================================
# PVGIS — SOLÁRNÍ DATA
# ================================================================

@functools.lru_cache(maxsize=256)
def pvgis(lat: float, lon: float, kwp: float, sklon: int, azimut: int) -> tuple:
    def _jedno(latt, lonn, kwpp, sklonn, az):
        r = requests.get(
            "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc",
            params={
                "lat": float(latt), "lon": float(lonn),
                "peakpower": float(kwpp), "loss": 14,
                "angle": int(sklonn), "aspect": int(az),
                "outputformat": "json", "browser": 0,
                "startyear": 2020, "endyear": 2020,
                "pvcalculation": 1, "pvtechchoice": "crystSi",
                "mountingplace": "building", "trackingtype": 0,
            },
            timeout=30,
        )
        r.raise_for_status()
        return np.array(
            [float(h["P"]) / 1000.0 for h in r.json()["outputs"]["hourly"]],
            dtype=float,
        )[:8760]

    try:
        if azimut == 999:
            a = _jedno(lat, lon, kwp / 2, sklon, -90)
            b = _jedno(lat, lon, kwp / 2, sklon, +90)
            return (a + b), None
        elif azimut == 998:
            a = _jedno(lat, lon, kwp / 2, sklon, -45)
            b = _jedno(lat, lon, kwp / 2, sklon, +45)
            return (a + b), None
        else:
            return _jedno(lat, lon, kwp, sklon, azimut), None
    except Exception as ex:
        return None, str(ex)


# ================================================================
# GEOCODING
# ================================================================

_GEOCODE_FB = {
    "praha": (50.08, 14.44), "brno": (49.19, 16.61), "ostrava": (49.83, 18.29),
    "plzeň": (49.74, 13.37), "liberec": (50.77, 15.06), "olomouc": (49.59, 17.25),
    "zlín": (49.22, 17.66), "hradec králové": (50.21, 15.83),
    "pardubice": (50.04, 15.78), "české budějovice": (48.97, 14.47),
    "ústí nad labem": (50.66, 14.03), "havířov": (49.78, 18.43),
    "karviná": (49.85, 18.54), "opava": (49.94, 17.90),
    "frýdek-místek": (49.68, 18.35), "jihlava": (49.40, 15.59),
    "třinec": (49.68, 18.67), "znojmo": (48.86, 16.05),
}


def geocode(dotaz: str) -> tuple:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format": "json",
                    "limit": 1, "addressdetails": 1, "countrycodes": "cz"},
            headers={"User-Agent": "FVE-SVJ-Kalkulacka/1.0"},
            timeout=10,
        )
        if r.status_code == 200 and r.text.strip():
            res = r.json()
            if res:
                addr = res[0].get("address", {})
                nazev = (addr.get("road", "") + " " + addr.get("house_number", "")).strip()
                nazev = nazev or addr.get("city") or addr.get("town") or addr.get("village") or dotaz
                return float(res[0]["lat"]), float(res[0]["lon"]), nazev, None
    except Exception:
        pass
    klic = dotaz.lower().strip().split(",")[0].strip()
    if klic in _GEOCODE_FB:
        lat, lon = _GEOCODE_FB[klic]
        return lat, lon, dotaz, None
    return None, None, None, "Nenalezeno — zkuste jiný formát adresy"


def geocode_search(dotaz: str) -> list:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format": "json",
                    "limit": 5, "addressdetails": 1, "countrycodes": "cz"},
            headers={"User-Agent": "FVE-SVJ-Kalkulacka/1.0"},
            timeout=5,
        )
        if r.status_code == 200 and r.text.strip():
            return r.json()
    except Exception:
        pass
    return []
