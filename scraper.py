from pathlib import Path
from delibere import scraperesults, writecsv, writejson, writesummaries

# ============================================================
# MODIFICA SOLO QUESTA SEZIONE
# ============================================================
#
# Come usare questo file da VS Code:
# 1. Modifica le variabili qui sotto.
# 2. Apri scraper.py.
# 3. Premi "Run Python File".
#
# Configurazioni tipiche:
#
# - Scaricare tutto il FESR 2026, CSV + PDF:
#   ANNI = "2026"
#   KEYWORD = "FESR"
#   SCARICA_LINK_PDF = True
#   SCARICA_PDF = True
#   MAX_FINESTRE = None
#   MAX_PDF = None
#
# - Scaricare un range di anni:
#   ANNI = "2023-2026"
#
# - Scaricare una lista precisa di anni:
#   ANNI = ["2026", "2025", "2023"]
#
# - Fare solo un test veloce sulle prime 2 finestre bimestrali:
#   SCARICA_LINK_PDF = False
#   SCARICA_PDF = False
#   MAX_FINESTRE = 2
#   MAX_PDF = None
#
# - Scaricare solo CSV/JSON/riepiloghi, senza PDF:
#   SCARICA_LINK_PDF = False
#   SCARICA_PDF = False
#   MAX_FINESTRE = None
#   MAX_PDF = None
#
# - Scaricare tutti i CSV ma solo i primi 20 PDF:
#   SCARICA_LINK_PDF = True
#   SCARICA_PDF = True
#   MAX_FINESTRE = None
#   MAX_PDF = 20

ANNI = "2026"
KEYWORD = "FESR"
CARTELLA_OUTPUT = "data"

SCARICA_LINK_PDF = True
SCARICA_PDF = True

MAX_FINESTRE = 2
MAX_PDF = None

PAUSA_SECONDI = 0.4
TIMEOUT_SECONDI = 30


def leggianni(value):
    if isinstance(value, int):
        return [str(value)]

    if isinstance(value, str):
        value = value.strip()
        if "-" in value:
            start, end = value.split("-", 1)
            start = int(start.strip())
            end = int(end.strip())
            step = 1 if start <= end else -1
            return [str(year) for year in range(start, end + step, step)]
        return [value]

    return [str(year) for year in value]


def main():
    folder = Path(CARTELLA_OUTPUT)
    anni = leggianni(ANNI)
    allrecords = []

    for anno in anni:
        print("")
        print(f"Scarico anno {anno}, keyword {KEYWORD}")
        suffix = f"{anno}_{KEYWORD.lower()}".replace(" ", "_")

        records = scraperesults(
            anno=anno,
            keyword=KEYWORD,
            maxpages=MAX_FINESTRE,
            delay=PAUSA_SECONDI,
            includelinks=SCARICA_LINK_PDF,
            download=SCARICA_PDF,
            maxpdf=MAX_PDF,
            timeout=TIMEOUT_SECONDI,
            outputfolder=CARTELLA_OUTPUT,
        )

        csvpath = folder / f"delibere_{suffix}.csv"
        jsonpath = folder / f"delibere_{suffix}.json"

        writecsv(csvpath, records)
        writejson(jsonpath, records)
        writesummaries(records, anno, KEYWORD, folder)
        allrecords.extend(records)

        print(f"Anno {anno} completato.")
        print(f"Record salvati: {len(records)}")
        print(f"CSV: {csvpath}")
        print(f"JSON: {jsonpath}")

    if len(anni) > 1:
        suffix = f"{anni[0]}_{anni[-1]}_{KEYWORD.lower()}".replace(" ", "_")
        csvpath = folder / f"delibere_{suffix}_tutti_gli_anni.csv"
        jsonpath = folder / f"delibere_{suffix}_tutti_gli_anni.json"
        writecsv(csvpath, allrecords)
        writejson(jsonpath, allrecords)
        writesummaries(allrecords, f"{anni[0]}_{anni[-1]}", KEYWORD, folder)

    print("")
    print("Download completato.")
    print(f"Anni scaricati: {', '.join(anni)}")
    print(f"Record totali salvati: {len(allrecords)}")
    if SCARICA_PDF:
        print(f"PDF: {folder / 'pdf'}")


if __name__ == "__main__":
    main()
