# Architektur und Modulübersicht

Diese Dokumentation beschreibt die wichtigsten Module des Projekts,
welche anderen Komponenten sie aufrufen und welche Erweiterungen
möglich sind. Sie richtet sich an Entwickler, die den Lernkarten‐
Generator anpassen oder erweitern möchten.

## GUI-Einstiegspunkte

### `app/main.py`
Die Datei `main.py` enthält die aktuelle Tkinter‑GUI. Die Klasse
`App` kümmert sich um Dateiauswahl, Modelleinstellungen und den
Start der Pipeline【F:app/main.py†L20-L116】. Über
`segment_and_estimate` werden PDF‑Texte eingelesen und auf Basis von
`tokenizer_utils.Tokenizer` sowie `pipeline.LernkartenPipeline`
Kosten geschätzt【F:app/main.py†L117-L181】. Die Methode
`start_pipeline` erzeugt einen `LernkartenPipeline`‑Thread, der die
weitere Verarbeitung übernimmt【F:app/main.py†L182-L241】.

### `app/gui.py`
`gui.py` stellt eine alternative, ältere GUI bereit. Sie nutzt die
Klasse `Pipeline` (ältere Variante der Verarbeitung) und die
Kostenfunktion `cost.estimate_cost_for_text` für eine grobe
Schätzung【F:app/gui.py†L8-L60】【F:app/gui.py†L96-L132】. Für neue
Features sollte bevorzugt `main.py` genutzt werden; `gui.py` kann als
Beispiel für eigene Oberflächen dienen.

## Pipeline und Verarbeitung

### `app/pipeline.py`
Die Klasse `LernkartenPipeline` bündelt Segmentierung, Klassifikation,
Fragen‑Generierung und Export【F:app/pipeline.py†L10-L73】.
Wesentliche Methoden:

- `load_and_segment` ruft `pdf_ingest.extract_text_from_pdf` und
  `segment_text` auf, um Rohtext in `Segment`‑Objekte zu zerlegen
  【F:app/pipeline.py†L24-L28】.
- `classify` nutzt `OpenAIClient.classify_segment` für jedes Segment
  und erlaubt Abbruch/Pause über Callbacks【F:app/pipeline.py†L31-L50】.
- `generate_cards` bestimmt pro Segment die Anzahl der Fragen auf
  Basis der Tokenanzahl (`Tokenizer.count`) und ruft
  `OpenAIClient.gen_qa_for_chunk` auf【F:app/pipeline.py†L52-L75】.
- `export_excel` delegiert an `excel_export.to_excel`.

Erweiterungen: neue Exportformate können durch zusätzliche Methoden
analog zu `export_excel` hinzugefügt werden; weitere Verarbeitungsschritte
(z. B. Nachbearbeitung der Fragen) lassen sich vor dem Export einbauen.

### `app/openai_client.py`
Kapselt den Zugriff auf die OpenAI‑API. `classify_segment` liefert pro
Textabschnitt ein Label und ein `keep`‑Flag, das in `LernkartenPipeline`
für die Filterung genutzt wird【F:app/openai_client.py†L24-L55】.
`gen_qa_for_chunk` erzeugt Lernkarten und wird von
`LernkartenPipeline.generate_cards` aufgerufen【F:app/openai_client.py†L57-L98】.
Die Modellnamen (`OpenAISettings`) können zentral angepasst werden.

### `app/models.py`
Enthält generische Hilfsfunktionen für OpenAI‑Aufrufe ohne GUI. Dazu
gehören Token‑Schätzungen (`count_tokens_rough`) und allgemeine
Chat‑Wrapper (`call_json_chat`, `call_text_chat`)【F:app/models.py†L15-L52】.
Diese Funktionen werden u. a. vom Modul `labeling` genutzt.

## PDF- und Textverarbeitung

### `app/pdf_ingest.py`
Extrahiert Text aus PDF‑Dateien (pdfplumber oder pypdf) und segmentiert
Absätze heuristisch nach Länge【F:app/pdf_ingest.py†L1-L44】【F:app/pdf_ingest.py†L46-L85】.
Die Funktion `segment_text` wird sowohl in der GUI als auch in der
Pipeline verwendet.

### `app/pdf_utils.py`
Bietet ein alternatives, stärker bereinigendes PDF‑Parsing mit
Heuristiken für Kopf‑/Fußzeilen und Silbentrennungen【F:app/pdf_utils.py†L1-L27】.
`try_extract_text` fällt bei TXT‑Dateien auf einfaches Lesen zurück.

### `app/chunking.py`
Teilt langen Text in überlappende Segmente, um Tokenlimits einzuhalten.
Die Funktion `split_into_chunks` wird von `cost.estimate_cost_for_text`
verwendet, um die Anzahl der Chunks für die Kostenschätzung zu
bestimmen【F:app/chunking.py†L1-L56】. Erweiterungen können z. B. andere
Heuristiken zur Überschriften‑Erkennung einbringen.

### `app/tokenizer_utils.py`
Kapselt Tokenzählung mittels `tiktoken` mit Fallback auf eine einfache
Heuristik【F:app/tokenizer_utils.py†L1-L33】. Wird in der Pipeline und in
anderen Modulen genutzt, um eine Abhängigkeit von `tiktoken` optional
zu machen.

## Kosten, Export und Logging

### `app/cost.py`
Schätzt Kosten, indem `chunking.split_into_chunks` und
`models.count_tokens_rough` kombiniert werden. Preise werden aus
`config.toml` geladen; Änderungen an Modellpreisen oder Schätzparametern
können dort erfolgen【F:app/cost.py†L1-L24】.

### `app/excel_export.py` und `app/export.py`
`excel_export.to_excel` exportiert generierte Karten in eine einfache
Excel‑Datei【F:app/excel_export.py†L1-L17】. `export.export_to_excel`
erzeugt zusätzlich CSV und Metadaten und kann als Vorlage für komplexere
Exporte dienen【F:app/export.py†L1-L20】.

### `app/logging_utils.py`
Stellt einen Logger bereit, der sowohl auf die Konsole als auch in eine
Datei schreibt. Damit kann die Pipeline leicht um detaillierte
Protokollierung erweitert werden【F:app/logging_utils.py†L1-L10】.

## Prompts und Klassifikation

### `app/prompts.py`
Definiert System‑ und Nutzer‑Prompts für die Klassifikation und
Frage‑Generierung【F:app/prompts.py†L1-L30】【F:app/prompts.py†L32-L48】.
Änderungen an den Prompts wirken sich direkt auf die Antworten der
OpenAI‑Modelle aus und ermöglichen z. B. andere Zielsprachen oder
Fragetypen.

### `app/labeling.py`
`classify_chunk` nutzt `prompts.LABEL_SYSTEM` und `models.call_json_chat`
für eine eigenständige Klassifikation einzelner Textstücke【F:app/labeling.py†L1-L11】.
Die Rückgabestruktur enthält Nutzungsdaten, die zur späteren
Kostenanalyse verwendet werden können.

## Erweiterungshinweise

- **Neue Modelle**: Modellnamen und Preise werden in `config.toml`
  gepflegt. Für zusätzliche Modelle Preise ergänzen und ggf.
  `OpenAISettings` erweitern.
- **Alternative Exporte**: Weitere Formate (z. B. Anki‑Decks) lassen
  sich ähnlich wie `export.export_to_excel` implementieren.
- **Zusätzliche Verarbeitung**: Vor oder nach der Frage‑Generierung
  können Funktionen eingefügt werden, z. B. zur Qualitätskontrolle oder
  zum Entfernen redundanter Karten.
- **GUI‑Anpassungen**: `main.py` bietet Einstiegspunkte für zusätzliche
  Bedienelemente oder Fortschrittsanzeigen.
