# Estrazione delibere Regione Lazio

Pipeline per cercare le deliberazioni della Giunta regionale nel BUR della Regione Lazio e ricostruire l'uso del FESR.

## Uso rapido da VS Code

Apri `scraper.py`, modifica solo le variabili nella sezione iniziale e premi **Run Python File**.

Per scaricare tutto il FESR 2026, CSV e PDF, lascia:

```python
ANNI = "2026"
KEYWORD = "FESR"
SCARICA_LINK_PDF = True
SCARICA_PDF = True
MAX_FINESTRE = None
MAX_PDF = None
```

Puoi usare anche un range:

```python
ANNI = "2023-2026"
```

oppure una lista precisa:

```python
ANNI = ["2026", "2025", "2023"]
```

Output principali:

- `data/delibere_2026_fesr.csv`: tutte le righe trovate, con campi normalizzati.
- `data/delibere_2026_fesr.json`: stesso contenuto in JSON.
- `data/riepilogo_azioni_2026_fesr.csv`: conteggio per azione FESR.
- `data/riepilogo_manovre_2026_fesr.csv`: conteggio per tipo di manovra.
- `data/riepilogo_beneficiari_2026_fesr.csv`: primi beneficiari ricavati dall'oggetto.

La cartella `data/` e' ignorata da Git: contiene output rigenerabili, inclusi eventuali PDF.

Ricalcolare i riepiloghi da un CSV gia' scaricato:

```bash
python3 analisi.py data/delibere_2026_fesr.csv
```

## Note

Il BUR Lazio richiede un intervallo massimo di 2 mesi quando si cerca per categoria, tipo atto e parola nell'oggetto. Lo scraper divide automaticamente ogni anno in 6 finestre bimestrali e deduplica le righe trovate.

La fonte usata e' la banca dati delle deliberazioni della Giunta dal luglio 2012 in poi, raggiungibile dalla pagina "Delibere della Giunta regionale" della Regione Lazio. Nel BUR vengono selezionate la categoria `Deliberazioni`, il tipo `Deliberazione Giunta Regione Lazio` e la keyword configurata in `scraper.py`.

## Pubblicazione su GitHub

Dopo aver creato un repository vuoto su GitHub:

```bash
git remote add origin https://github.com/NOME_UTENTE/NOME_REPO.git
git push -u origin main
```
