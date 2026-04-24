# constants.py — Ceníky, sazby, profily 2026
# Importován z engine.py a app.py

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
JISTIC_3x25={
    "ČEZ Distribuce":{"D01d":132,"D02d":298,"D25d":287,"D26d":422,"D27d":272,"D35d":517,"D45d":567,"D56d":567,"D57d":567,"D61d":238},
    "EG.D (E.ON)":   {"D01d":145,"D02d":575,"D25d":296,"D26d":422,"D27d":282,"D35d":575,"D45d":575,"D56d":575,"D57d":575,"D61d":271},
    "PREdistribuce": {"D01d":100,"D02d":280,"D25d":250,"D26d":350,"D27d":230,"D35d":420,"D45d":480,"D56d":480,"D57d":480,"D61d":200},
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
    "seniori":   {"nazev":"👴 Převaha seniorů",     "popis":"Více doma přes den — vyšší využití FVE"},
    "pracujici": {"nazev":"🏢 Převaha pracujících", "popis":"Většina pryč přes den"},
    "rodiny":    {"nazev":"👨‍👩‍👧‍👦 Rodiny s dětmi",    "popis":"Doma odpoledne a víkendy"},
    "provozovna":{"nazev":"🏪 S provozovnou",       "popis":"Vysoká spotřeba přes den"},
}

# ================================================================
# UI
