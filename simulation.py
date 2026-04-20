"""
FVE Simulační engine pro SVJ
- 15min rozlišení, 8760 hodin × 4 = 35 040 intervalů/rok
- PVGIS hodinová data výroby
- TDD třída 4 profily spotřeby (OTE normalizované)
- Baterie SOC simulace
- 15letý cashflow s degradací a růstem cen
"""

import numpy as np
import requests

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False


def _cache(fn):
    """Cache wrapper — použije st.cache_data pokud je dostupný."""
    if _HAS_STREAMLIT:
        return st.cache_data(ttl=86400, show_spinner=False)(fn)
    return fn

# ============================================================
# TDD PROFILY SPOTŘEBY (OTE, třída 4 = D02d domácnosti)
# Normalizované hodnoty — průměrný den pro každý typ dne a sezónu
# Zdroj: OTE ČR, vyhláška 541/2005 Sb.
# Hodnoty jsou relativní podíly (součet = 1 za rok)
# Převedeny na tvar: [hodina 0-23] pro každý typ dne
# ============================================================

# Profil TDD třídy 4 — standardní domácnost D02d
# Normalizovaný hodinový profil (relativní, součet = 24)
# Rozlišujeme: ZIMA (Nov-Feb), PŘECHODNÉ (Mar-Apr, Sep-Oct), LÉTO (May-Aug)
# A: pracovní den, B: sobota, C: neděle/svátek

TDD_PROFIL_ZAKLADNI = {
    # Pracovní den — zima
    "zima_prac": np.array([
        0.42, 0.38, 0.36, 0.35, 0.35, 0.38,
        0.52, 0.78, 0.88, 0.82, 0.76, 0.74,
        0.76, 0.74, 0.72, 0.74, 0.82, 1.12,
        1.28, 1.22, 1.08, 0.92, 0.72, 0.55,
    ]),
    # Pracovní den — léto
    "leto_prac": np.array([
        0.38, 0.34, 0.32, 0.31, 0.32, 0.36,
        0.48, 0.68, 0.76, 0.72, 0.68, 0.66,
        0.68, 0.66, 0.64, 0.66, 0.74, 0.96,
        1.08, 1.02, 0.90, 0.76, 0.58, 0.44,
    ]),
    # Pracovní den — přechodné
    "prechodne_prac": np.array([
        0.40, 0.36, 0.34, 0.33, 0.34, 0.37,
        0.50, 0.73, 0.82, 0.77, 0.72, 0.70,
        0.72, 0.70, 0.68, 0.70, 0.78, 1.04,
        1.18, 1.12, 0.99, 0.84, 0.65, 0.50,
    ]),
    # Víkend — zima
    "zima_vikend": np.array([
        0.45, 0.40, 0.37, 0.36, 0.36, 0.38,
        0.42, 0.55, 0.75, 0.90, 0.95, 0.94,
        0.90, 0.86, 0.82, 0.82, 0.88, 1.05,
        1.15, 1.10, 0.98, 0.82, 0.65, 0.52,
    ]),
    # Víkend — léto
    "leto_vikend": np.array([
        0.40, 0.36, 0.33, 0.32, 0.32, 0.34,
        0.38, 0.50, 0.68, 0.82, 0.86, 0.85,
        0.82, 0.78, 0.74, 0.74, 0.80, 0.95,
        1.04, 0.99, 0.88, 0.74, 0.58, 0.46,
    ]),
    # Víkend — přechodné
    "prechodne_vikend": np.array([
        0.42, 0.38, 0.35, 0.34, 0.34, 0.36,
        0.40, 0.52, 0.72, 0.86, 0.90, 0.89,
        0.86, 0.82, 0.78, 0.78, 0.84, 1.00,
        1.10, 1.04, 0.93, 0.78, 0.62, 0.49,
    ]),
}

# Úpravy profilů dle typu obyvatel
# Koeficienty mění tvar křivky — přes den více/méně
PROFIL_UPRAVY = {
    "mix": np.ones(24),
    "seniori": np.array([
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.0, 1.1, 1.3, 1.5, 1.6, 1.6,
        1.5, 1.5, 1.4, 1.4, 1.3, 1.1,
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    ]),
    "pracujici": np.array([
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.2, 1.3, 0.7, 0.5, 0.5, 0.5,
        0.5, 0.5, 0.5, 0.6, 0.8, 1.3,
        1.4, 1.3, 1.2, 1.1, 1.0, 1.0,
    ]),
    "rodiny": np.array([
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.1, 1.2, 0.9, 0.7, 0.7, 0.7,
        0.8, 0.8, 0.9, 1.1, 1.2, 1.2,
        1.2, 1.1, 1.1, 1.0, 1.0, 1.0,
    ]),
    "provozovna": np.array([
        0.8, 0.8, 0.8, 0.8, 0.8, 0.9,
        1.0, 1.2, 1.5, 1.6, 1.7, 1.7,
        1.6, 1.6, 1.6, 1.5, 1.3, 1.1,
        1.0, 0.9, 0.9, 0.8, 0.8, 0.8,
    ]),
}


def get_sezona(mesic: int) -> str:
    """Vrátí sezónu pro daný měsíc."""
    if mesic in [11, 12, 1, 2]:
        return "zima"
    elif mesic in [5, 6, 7, 8]:
        return "leto"
    else:
        return "prechodne"


def je_vikend(den_tydne: int) -> bool:
    """0=Po, 6=Ne"""
    return den_tydne >= 5


def generuj_profil_spotreby_rocni(
    rocni_spotreba_kwh: float,
    profil_obyvatel: str = "mix",
    sazba: str = "D02d",
) -> np.ndarray:
    """
    Generuje 35040 hodnot spotřeby (15min intervaly, celý rok).
    Výstup v kWh/15min.
    """
    import datetime

    upravy = PROFIL_UPRAVY.get(profil_obyvatel, np.ones(24))

    hodnoty = []
    rok = 2026
    den = datetime.date(rok, 1, 1)

    while den.year == rok:
        mesic = den.month
        dow = den.weekday()
        sezona = get_sezona(mesic)
        typ = "vikend" if je_vikend(dow) else "prac"
        klic = f"{sezona}_{typ}"

        profil_hod = TDD_PROFIL_ZAKLADNI[klic].copy()

        # Aplikuj úpravu dle profilu obyvatel
        profil_hod = profil_hod * upravy

        # Normalizuj — součet za den = 24 (pro snazší škálování)
        profil_hod = profil_hod / profil_hod.sum() * 24

        # Každou hodinu rozpiš na 4 × 15min intervaly
        for h in range(24):
            val_15min = profil_hod[h] / 4
            for _ in range(4):
                hodnoty.append(val_15min)

        den += datetime.timedelta(days=1)

    hodnoty = np.array(hodnoty)

    # Škáluj na roční spotřebu
    # Průměrná hodnota × 35040 intervalů = roční spotřeba v kWh
    scale = rocni_spotreba_kwh / (hodnoty.sum())
    return hodnoty * scale


@_cache
def get_pvgis_hodinova_data(
    lat: float,
    lon: float,
    vykon_kwp: float,
    sklon: int,
    azimut: int,
) -> tuple:
    """
    Stáhne hodinová data výroby z PVGIS (TMY — typical meteorological year).
    Vrátí (pole 8760 hodnot kWh/h pro 1 kWp, chybová zpráva nebo None).
    """
    url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
    params = {
        "lat": lat,
        "lon": lon,
        "peakpower": 1,  # Normalizujeme na 1 kWp, pak vynásobíme
        "loss": 14,
        "angle": sklon,
        "aspect": azimut,
        "outputformat": "json",
        "browser": 0,
        "startyear": 2020,
        "endyear": 2020,
        "pvcalculation": 1,
        "pvtechchoice": "crystSi",
        "mountingplace": "building",
        "trackingtype": 0,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        hourly = data["outputs"]["hourly"]
        # Extrahujeme výkon P v W/kWp → převedeme na kWh/h/kWp
        vyroba_norm = np.array([h["P"] / 1000 for h in hourly])
        # Vynásobíme skutečným výkonem
        vyroba = vyroba_norm * vykon_kwp
        return vyroba, None
    except Exception as e:
        return None, str(e)


def interpoluj_na_15min(hodinova_data: np.ndarray) -> np.ndarray:
    """
    Interpoluje hodinová data (8760) na 15min intervaly (35040).
    Používá lineární interpolaci pro plynulý přechod.
    """
    result = np.zeros(len(hodinova_data) * 4)
    for i, val in enumerate(hodinova_data):
        next_val = hodinova_data[(i + 1) % len(hodinova_data)]
        for j in range(4):
            t = j / 4
            result[i * 4 + j] = (val * (1 - t) + next_val * t) / 4
    return result


def simuluj_fve(
    vyroba_15min: np.ndarray,
    spotreba_15min: np.ndarray,
    baterie_kapacita_kwh: float = 0,
    baterie_min_soc: float = 0.10,
    baterie_max_soc: float = 0.90,
    baterie_ucinnost: float = 0.92,
) -> dict:
    """
    Simuluje provoz FVE na 15min úrovni.
    Vrátí slovník s výsledky.
    """
    n = len(vyroba_15min)
    baterie_kwh = baterie_kapacita_kwh * 0.5  # Počáteční SOC 50%

    vlastni_spotreba = np.zeros(n)
    pretoky = np.zeros(n)
    odber_ze_site = np.zeros(n)
    soc = np.zeros(n)

    bat_min = baterie_kapacita_kwh * baterie_min_soc
    bat_max = baterie_kapacita_kwh * baterie_max_soc

    for i in range(n):
        v = vyroba_15min[i]
        s = spotreba_15min[i]

        if v >= s:
            # Přebytek výroby
            vlastni_spotreba[i] = s
            prebyt = v - s

            # Nabíjíme baterii
            if baterie_kapacita_kwh > 0:
                misto = (bat_max - baterie_kwh)
                nabijeni = min(prebyt * baterie_ucinnost, misto)
                baterie_kwh += nabijeni
                prebyt -= nabijeni / baterie_ucinnost

            pretoky[i] = prebyt
        else:
            # Nedostatek výroby
            vlastni_spotreba[i] = v
            nedostatek = s - v

            # Vybíjíme baterii
            if baterie_kapacita_kwh > 0:
                dostupne = (baterie_kwh - bat_min)
                vybijeni = min(nedostatek, dostupne * baterie_ucinnost)
                baterie_kwh -= vybijeni / baterie_ucinnost
                nedostatek -= vybijeni

            odber_ze_site[i] = nedostatek

        soc[i] = baterie_kwh / baterie_kapacita_kwh if baterie_kapacita_kwh > 0 else 0

    return {
        "vlastni_spotreba_kwh": vlastni_spotreba.sum(),
        "pretoky_kwh": pretoky.sum(),
        "odber_kwh": odber_ze_site.sum(),
        "mira_vlastni_spotreby": vlastni_spotreba.sum() / vyroba_15min.sum(),
        "mira_sobestacnosti": vlastni_spotreba.sum() / spotreba_15min.sum(),
        # Mesicni data pro graf
        "vlastni_mesicne": [vlastni_spotreba[m*4*24*30:(m+1)*4*24*30].sum()
                             for m in range(12)],
        "pretoky_mesicne": [pretoky[m*4*24*30:(m+1)*4*24*30].sum()
                            for m in range(12)],
        "odber_mesicne": [odber_ze_site[m*4*24*30:(m+1)*4*24*30].sum()
                          for m in range(12)],
    }


def simuluj_15let(
    vyroba_rocni_kwh: float,
    vlastni_spotreba_1rok: float,
    pretoky_1rok: float,
    odber_1rok: float,
    spotreba_rocni_kwh: float,
    cena_vt_kwh: float,
    cena_prumerna_kwh: float,
    cena_pretoky_kwh: float,
    stay_plat_mesic: float,
    cena_instalace: float,
    vlastni_castka: float,
    uver_castka: float,
    rocni_splatka: float,
    splatnost: int,
    rust_cen_pct: float = 3.0,
    degradace_pct: float = 0.5,
    leta: int = 15,
    uspora_jistic_rocni: float = 0,
    bonus_celkem: float = 0,
) -> list:
    """
    Simuluje 15letý cashflow.
    Vrátí list slovníků (jeden za rok).
    """
    vysledky = []
    kumulativni_cashflow = -(vlastni_castka + uver_castka - bonus_celkem)

    for rok in range(1, leta + 1):
        # Degradace panelů
        degradacni_faktor = (1 - degradace_pct / 100) ** (rok - 1)

        # Růst cen elektřiny
        cenovy_faktor = (1 + rust_cen_pct / 100) ** (rok - 1)

        # Upravená výroba
        vlastni_rok = vlastni_spotreba_1rok * degradacni_faktor
        pretoky_rok = pretoky_1rok * degradacni_faktor

        # Upravené ceny
        cena_vt_rok = cena_vt_kwh * cenovy_faktor
        cena_pret_rok = cena_pretoky_kwh * cenovy_faktor

        # Úspory
        uspora_elektrina = vlastni_rok * cena_vt_rok
        uspora_pretoky = pretoky_rok * cena_pret_rok
        uspora_distribuce = uspora_jistic_rocni * cenovy_faktor
        uspora_celkem = uspora_elektrina + uspora_pretoky + uspora_distribuce

        # Splátka (nominálně stejná, bez inflace)
        splatka = rocni_splatka if rok <= splatnost else 0

        # Čistý přínos
        cisty_prinos = uspora_celkem - splatka
        kumulativni_cashflow += cisty_prinos

        vysledky.append({
            "rok": rok,
            "vyroba_mwh": round(vlastni_rok / 1000 + pretoky_rok / 1000, 2),
            "vlastni_spotreba_mwh": round(vlastni_rok / 1000, 2),
            "pretoky_mwh": round(pretoky_rok / 1000, 2),
            "uspora_elektrina": round(uspora_elektrina),
            "uspora_pretoky": round(uspora_pretoky),
            "uspora_celkem": round(uspora_celkem),
            "splatka": round(splatka),
            "cisty_prinos": round(cisty_prinos),
            "kumulativni_cashflow": round(kumulativni_cashflow),
            "cena_vt_rok": round(cena_vt_rok, 2),
            "degradacni_faktor": round(degradacni_faktor, 4),
        })

    return vysledky
