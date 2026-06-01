import csv
import json
import re
import time
from calendar import monthrange
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup


BUR_BASE_URL = "https://sicer.regione.lazio.it/PublicBur/burlazio"
SEARCH_URL = f"{BUR_BASE_URL}/FrontEnd/RicercaAtto"
FRONTEND_URL = f"{BUR_BASE_URL}/FrontEnd"
PDF_URL = f"{BUR_BASE_URL}/DynRes/GENERIC_FILE.4"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}

FIELDNAMES = [
    "anno_ricerca",
    "keyword_ricerca",
    "finestra_ricerca",
    "pagina",
    "proponente",
    "tipo_atto",
    "numero_adozione",
    "data_adozione",
    "protocollo",
    "oggetto",
    "pubblicazione_bur",
    "data_pubblicazione_bur",
    "dettaglio_url",
    "pdf_url",
    "bur_file",
    "numero_edizione_bur",
    "tipo_edizione_bur",
    "programma",
    "azioni",
    "obiettivi_specifici",
    "priorita",
    "cup",
    "dgr",
    "determinazioni",
    "tipo_manovra",
    "beneficiario",
    "importi",
]


def decodehtml(response):
    response.encoding = response.encoding or "utf-8"
    return response.text


def cleantext(value):
    return re.sub(r"\s+", " ", value or "").strip()


def formdatafromhtml(html):
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    for tag in soup.select("input[name]"):
        data[tag.get("name")] = tag.get("value", "")
    for select in soup.select("select[name]"):
        selected = select.find("option", selected=True)
        data[select.get("name")] = selected.get("value", "") if selected else ""
    return data


def selectoptionvalue(soup, selectname, label):
    select = soup.find("select", attrs={"name": selectname})
    if not select:
        return ""
    for option in select.find_all("option"):
        if cleantext(option.get_text(" ", strip=True)).lower() == label.lower():
            return cleantext(option.get("value", ""))
    return ""


def categorychangedhtml(session, timeout):
    response = session.get(SEARCH_URL, timeout=timeout)
    response.raise_for_status()
    html = decodehtml(response)
    soup = BeautifulSoup(html, "html.parser")
    categoryvalue = selectoptionvalue(soup, "BL_PAR_CATEG_ATTO_0", "Deliberazioni") or "7"
    data = formdatafromhtml(html)
    data.update({"BL_PAR_CATEG_ATTO_0": categoryvalue, "BL_ACTION": "CATEG_CHANGED"})
    response = session.post(FRONTEND_URL, data=data, timeout=timeout)
    response.raise_for_status()
    return decodehtml(response)


def buildpayload(html, keyword, startdate, enddate):
    soup = BeautifulSoup(html, "html.parser")
    data = formdatafromhtml(html)
    categoryvalue = selectoptionvalue(soup, "BL_PAR_CATEG_ATTO_0", "Deliberazioni") or "7"
    typevalue = selectoptionvalue(soup, "BL_PAR_TIPO_ATTO_0", "Deliberazione Giunta Regione Lazio") or "9999"
    data.update(
        {
            "BL_PAR_NUMERO_ATTO_0": "",
            "BL_PAR_DATA_ATTO_0": "",
            "BL_PAR_CATEG_ATTO_0": categoryvalue,
            "BL_PAR_TIPO_ATTO_0": typevalue,
            "BL_PAR_OGGETTO_ATTO_0": keyword,
            "BL_PAR_NUMERO_EDIZ_0": "",
            "BL_PAR_DATA_DA_EDIZ_0": startdate,
            "BL_PAR_DATA_A_EDIZ_0": enddate,
            "BL_ACTION": "CERCA",
        }
    )
    return data


def fetchwindow(session, keyword, startdate, enddate, timeout):
    html = categorychangedhtml(session, timeout)
    response = session.post(
        FRONTEND_URL,
        data=buildpayload(html, keyword, startdate, enddate),
        timeout=timeout,
    )
    response.raise_for_status()
    return decodehtml(response)


def buildwindows(anno):
    year = int(anno)
    windows = []
    for month in range(1, 13, 2):
        start = date(year, month, 1)
        endmonth = month + 1
        end = date(year, endmonth, monthrange(year, endmonth)[1])
        windows.append((start.strftime("%d/%m/%Y"), end.strftime("%d/%m/%Y")))
    return windows


def fileidfromlink(link):
    if not link:
        return ""
    onclick = link.get("onclick") or link.get("ONCLICK") or ""
    match = re.search(r"onGenericStreamRead\('([^']+)'\)", onclick, flags=re.I)
    return match.group(1) if match else ""


def publicationtext(number, kind):
    values = [value for value in [kind, f"n. {number}" if number else ""] if value]
    return " ".join(values)


def protocollofromdata(number, adopteddate):
    year = ""
    match = re.search(r"/(\d{4})$", adopteddate or "")
    if match:
        year = match.group(1)
    return f"DGR/{year}/{number}" if year and number else number


def findall(pattern, text):
    values = re.findall(pattern, text or "", flags=re.I)
    cleaned = []
    for value in values:
        if isinstance(value, tuple):
            value = next((item for item in value if item), "")
        value = cleantext(str(value)).upper()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def extractdgr(text):
    values = []
    patterns = [
        r"\bD\.?\s*G\.?\s*R\.?\s*(?:N\.?\s*)?(\d+)\s*(?:DEL|DEL\.)\s*\d{1,2}/\d{1,2}/(\d{4})",
        r"\bD\.?\s*G\.?\s*R\.?\s*(?:N\.?\s*)?(\d+/\d{4})",
        r"DELIBERAZIONE(?:\s+DELLA\s+GIUNTA\s+REGIONALE)?\s*(?:N\.?\s*)?(\d+)\s*(?:DEL|DEL\.)\s*\d{1,2}/\d{1,2}/(\d{4})",
    ]
    for pattern in patterns:
        for value in re.findall(pattern, text or "", flags=re.I):
            if isinstance(value, tuple):
                value = "/".join(part for part in value if part)
            value = cleantext(value).upper()
            if value and value not in values:
                values.append(value)
    return values


def classifymanovra(text):
    upper = (text or "").upper()
    checks = [
        ("revoca", ["REVOCA"]),
        ("liquidazione saldo", ["LIQUIDAZIONE SALDO", "SALDO IN UNICA SOLUZIONE"]),
        ("liquidazione sal", ["LIQUIDAZIONE SAL"]),
        ("liquidazione", ["LIQUIDAZIONE"]),
        ("concessione", ["CONCESSIONE", "CONCESSO"]),
        ("approvazione", ["APPROVAZIONE", "APPROVATO"]),
        ("impegno", ["IMPEGNO", "IMPEGNARE"]),
        ("accertamento", ["ACCERTAMENTO"]),
        ("proroga", ["PROROGA"]),
        ("rideterminazione", ["RIDETERMINAZIONE"]),
        ("modifica", ["MODIFICA", "VARIAZIONE"]),
        ("scorrimento", ["SCORRIMENTO"]),
        ("ammissione", ["AMMISSIONE", "AMMESS"]),
    ]
    for label, keywords in checks:
        if any(keyword in upper for keyword in keywords):
            return label
    return "altro"


def extractbeneficiario(text):
    patterns = [
        r"A FAVORE (?:DEL|DELLA|DELL'|DEI|DEGLI|DELLE|DI)\s+(.+?)(?:\s+PER\s+LA|\s+PER\s+IL|\s+CUP\b|\s+-\s+|\.$)",
        r"BENEFICIARI(?:O|A)?\s+(.+?)(?:\s+PER\s+LA|\s+PER\s+IL|\s+CUP\b|\s+-\s+|\.$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.I)
        if match:
            return cleantext(match.group(1).strip(" .;:-\"'"))
    return ""


def enrichrecord(record):
    text = record.get("oggetto", "")
    upper = text.upper()
    record["programma"] = "PR Lazio FESR 2021-2027" if "FESR" in upper else ""
    record["azioni"] = ";".join(findall(r"\b\d(?:\.\d){1,2}\b", text))
    record["obiettivi_specifici"] = ";".join(
        findall(r"(?:OS|OBIETTIVO\s+SPECIFICO)\s*([0-9](?:\.[0-9]){1,2})", text)
    )
    record["priorita"] = ";".join(findall(r"(?:PRIORITA'|PRIORITÀ|OP)\s*[\s.:-]*(\d+[A-Z]*)", text))
    record["cup"] = ";".join(findall(r"\b[A-Z][0-9]{2}[A-Z0-9]{12}\b", text))
    record["dgr"] = ";".join(extractdgr(text))
    record["determinazioni"] = ";".join(findall(r"DET(?:ERMINAZION(?:E|I))?\.?\s*(?:N\.?\s*)?(\d+(?:/\d{4})?)", text))
    record["tipo_manovra"] = classifymanovra(text)
    record["beneficiario"] = extractbeneficiario(text)
    record["importi"] = ";".join(findall(r"(?:EURO|EUR|€)\s*([0-9][0-9.\s]*,\d{2})", text))
    return record


def parserows(html, anno, keyword, page, windowlabel=""):
    soup = BeautifulSoup(html, "html.parser")
    records = []
    table = soup.find("table", id="resultatti")
    if not table:
        message = cleantext(soup.get_text(" ", strip=True))
        return records, {"current_page": page, "total_pages": page, "total_records": 0, "message": message}

    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 10:
            continue
        link = cells[0].find("a")
        oggetto = cleantext(cells[0].get_text(" ", strip=True))
        numero = cleantext(cells[1].get_text(" ", strip=True))
        dataadozione = cleantext(cells[3].get_text(" ", strip=True))
        fileid = fileidfromlink(link)
        if not any([numero, oggetto, fileid]):
            continue
        numeroedizione = cleantext(cells[6].get_text(" ", strip=True))
        tipoedizione = cleantext(cells[7].get_text(" ", strip=True))
        record = {
            "anno_ricerca": str(anno),
            "keyword_ricerca": keyword,
            "finestra_ricerca": windowlabel,
            "pagina": str(page),
            "proponente": "",
            "tipo_atto": "Deliberazione Giunta Regione Lazio",
            "numero_adozione": numero,
            "data_adozione": dataadozione,
            "protocollo": protocollofromdata(numero, dataadozione),
            "oggetto": oggetto,
            "pubblicazione_bur": publicationtext(numeroedizione, tipoedizione),
            "data_pubblicazione_bur": cleantext(cells[8].get_text(" ", strip=True)),
            "dettaglio_url": "",
            "pdf_url": PDF_URL if fileid else "",
            "bur_file": fileid,
            "numero_edizione_bur": numeroedizione,
            "tipo_edizione_bur": tipoedizione,
        }
        records.append(enrichrecord(record))
    return records, {"current_page": page, "total_pages": page, "total_records": len(records)}


def findpdflink(session, dettaglio, timeout):
    return PDF_URL if dettaglio else ""


def contentfilename(response, fallback):
    header = response.headers.get("Content-Disposition", "")
    match = re.search(r'filename="([^"]+)"', header)
    if match:
        return Path(unquote(match.group(1))).name
    return fallback


def downloadpdf(session, fileid, html, folder, fallback, timeout):
    folder.mkdir(parents=True, exist_ok=True)
    data = formdatafromhtml(html)
    data["BL_PAR_GENERIC_FILE_0"] = fileid
    response = session.post(PDF_URL, data=data, stream=True, timeout=timeout)
    response.raise_for_status()
    filename = contentfilename(response, fallback)
    path = folder / filename
    with path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                handle.write(chunk)
    return str(path)


def dedupekey(record):
    return (
        record.get("numero_adozione", ""),
        record.get("data_adozione", ""),
        record.get("bur_file", ""),
    )


def scraperesults(
    anno,
    keyword,
    maxpages=None,
    delay=0.4,
    includelinks=False,
    download=False,
    maxpdf=None,
    timeout=30,
    outputfolder="data",
):
    session = requests.Session()
    session.headers.update(HEADERS)
    allrecords = []
    seen = set()
    pdfcount = 0
    windows = buildwindows(anno)
    if maxpages is not None:
        windows = windows[:maxpages]

    for page, (startdate, enddate) in enumerate(windows, start=1):
        windowlabel = f"{startdate}-{enddate}"
        html = fetchwindow(session, keyword, startdate, enddate, timeout)
        records, counter = parserows(html, anno, keyword, page, windowlabel)
        newrecords = []
        for record in records:
            key = dedupekey(record)
            if key in seen:
                continue
            seen.add(key)
            if not includelinks and not download:
                record["pdf_url"] = ""
            if download and record.get("bur_file") and (maxpdf is None or pdfcount < maxpdf):
                fallback = f"{record['protocollo'].replace('/', '-')}.pdf"
                record["pdf_file"] = downloadpdf(
                    session,
                    record["bur_file"],
                    html,
                    Path(outputfolder) / "pdf",
                    fallback,
                    timeout,
                )
                pdfcount += 1
                time.sleep(delay)
            newrecords.append(record)
        allrecords.extend(newrecords)
        totalrecords = counter.get("total_records") or len(records)
        print(
            f"Finestra {page}/{len(windows)} {windowlabel}: "
            f"{totalrecords} righe, nuove {len(newrecords)}, totale {len(allrecords)}."
        )
        time.sleep(delay)
    return allrecords


def writecsv(path, records, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or FIELDNAMES
    extras = sorted({key for record in records for key in record.keys()} - set(names))
    names = names + extras
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(records)


def writejson(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def splitvalues(value):
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def countfield(records, field):
    counter = Counter()
    for record in records:
        values = splitvalues(record.get(field, ""))
        if not values:
            values = ["non rilevato"]
        for value in values:
            counter[value] += 1
    return [{"valore": value, "conteggio": count} for value, count in counter.most_common()]


def writesummary(path, rows):
    writecsv(path, rows, ["valore", "conteggio"])


def writesummaries(records, anno, keyword, folder):
    suffix = f"{anno}_{keyword.lower()}".replace(" ", "_")
    writesummary(folder / f"riepilogo_azioni_{suffix}.csv", countfield(records, "azioni"))
    writesummary(folder / f"riepilogo_manovre_{suffix}.csv", countfield(records, "tipo_manovra"))
    writesummary(folder / f"riepilogo_beneficiari_{suffix}.csv", countfield(records, "beneficiario"))
    writesummary(folder / f"riepilogo_proponenti_{suffix}.csv", countfield(records, "proponente"))
