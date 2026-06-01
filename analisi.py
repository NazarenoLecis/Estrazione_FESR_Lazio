import argparse
import csv
from pathlib import Path

from delibere import writesummaries


def readcsv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def buildparser():
    parser = argparse.ArgumentParser(description="Ricalcola i riepiloghi da un CSV di delibere.")
    parser.add_argument("csvfile", help="CSV prodotto da scraper.py.")
    parser.add_argument("--anno", default=None, help="Anno per il nome dei file di riepilogo.")
    parser.add_argument("--keyword", default=None, help="Keyword per il nome dei file di riepilogo.")
    parser.add_argument("--output-dir", default=None, help="Cartella di output.")
    return parser


def main():
    args = buildparser().parse_args()
    path = Path(args.csvfile)
    records = readcsv(path)
    anno = args.anno or (records[0].get("anno_ricerca") if records else "anno")
    keyword = args.keyword or (records[0].get("keyword_ricerca") if records else "keyword")
    folder = Path(args.output_dir) if args.output_dir else path.parent
    writesummaries(records, anno, keyword, folder)
    print(f"Riepiloghi aggiornati in {folder}.")


if __name__ == "__main__":
    main()
