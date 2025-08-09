# GSA Flashcards (GPT‑5 Serie, GUI)

Ein Desktop‑Tool (Python + Tkinter) zum Verarbeiten von Uni‑Skripten (PDF/TXT),
Segmentieren, automatischem Labeln (Fakten/Beispiele/Definitionen/Aufzählungen/Meta),
Filtern von Überschriften/Vorwort, Erzeugen von Lernkarten/Fragen sowie Export in Excel
und CSV (z. B. für Anki).

> **Hinweis:** Die hier konfigurierten Modellnamen (`gpt-5`, `gpt-5-mini`, `gpt-5-nano`) sind **Platzhalter**.
> Bitte passen Sie sie in `config.toml` an die tatsächlich verfügbaren OpenAI‑Modelle an.

## Highlights
- **GUI** mit Dateiauswahl, API‑Key‑Eingabe (ephemer), Budget‑Grenze, Gründlichkeits‑Slider (4/8/16 Fragen pro Segment), Fortschrittsbalken und Live‑Log.
- **Vor‑Filterung** (heuristisch + LLM/Nano) sortiert Überschriften/Gliederungen/Vorwort aus.
- **Labeling mit Nano**: Fakten / Beispiele / Definitionen / Aufzählungen / Meta.
- **Kosten‑Schätzung** mit Token‑Schätzung (tiktoken‑basiert, mit Fallback).
- **Budgetschutz**: Verarbeitung stoppt rechtzeitig oder skaliert die Gründlichkeit herunter.
- **Cache**: Ergebnisse pro Segment werden gehasht und wiederverwendet.
- **Exports**: Excel (`.xlsx`) mit Spalten: *Original*, *Frage*, *Antwort*, *Labels*, *Quelle*;
  zusätzlich CSV‑Export für Flashcards.
- **Installer‑Pfad**: `install.py` (ZIP-Entpacken, venv + requirements) und **PyInstaller**‑Skript für Windows.

## Schnellstart
1. **Python 3.10+** installieren.
2. In dieses Verzeichnis wechseln und ausführen:
   ```bash
   python install.py
   ```
3. Starten:
 - Windows: `run.bat`
  - macOS/Linux: `bash run.sh`
4. In der GUI: **Skript wählen**, **API‑Key eingeben**, **Gründlichkeit** & **Budget** setzen, **Schätzen** → **Start**.

### API‑Schlüssel bereitstellen

Der OpenAI‑Key wird standardmäßig nur über die GUI abgefragt und **nicht auf
der Festplatte gespeichert**. Beim Beenden der Anwendung wird der Wert
verworfen.

Alternativen:

- Umgebungsvariable `OPENAI_API_KEY`
- `config.toml` → Abschnitt `[auth]` mit `api_key` oder `api_key_file`

> **Warnung:** Das Ablegen des Schlüssels in Textdateien oder `config.toml`
> ist unsicher. Die Anwendung gibt beim Start eine Warnung aus, wenn solche
> Quellen genutzt werden.

## Ordnerstruktur

- `app/` – Quellcode der Anwendung
- `assets/` – statische Ressourcen
- `docs/` – Dokumentation und Lizenz
- `installer/` – Installationsskripte und `requirements.txt`
- `config_editor.py`, `gui_config_editor.py`, `run.sh`, `run.bat`, `install.py`, `config.toml`, `.env.example` – direkt startbare bzw. anpassbare Dateien

## Installation aus ZIP
1. `Lernkarten.zip` und `install.py` in denselben Ordner legen.
2. `python install.py` ausführen – das Archiv wird entpackt, Abhängigkeiten werden installiert und Startdateien (`start.*`) werden angelegt.
3. Starten:
   - Windows: `start.bat`
   - macOS/Linux: `./start.sh` oder `python start.py`

## Modelle & Preise
Die Preise stammen aus Ihrer Vorgabe und sind in `config.toml` hinterlegt. Falls Ihr Account / Ihr Modell andere Preise hat, passen Sie sie bitte dort an. Die Kostenschätzung basiert auf
geschätzten Eingabe‑/Ausgabe‑Tokens und differenziert zwischen *Eingabe*, *Zwischengespeicherte Eingabe* und *Ausgabe*. Für die meisten Workloads wird *Eingabe*+*Ausgabe* angesetzt.

## Bekannte Grenzen / Tipps
- PDF‑Textextraktion ist nie perfekt. Nutzen Sie einen klaren Export (TXT) wenn möglich.
- Token‑Schätzungen sind **nur Näherungen** – die tatsächlichen Kosten können abweichen.
- Modell‑IDs können sich ändern. Tragen Sie Ihre korrekten IDs in `config.toml` ein.
- Setzen Sie ein **Budget‑Limit** in der GUI, um Kosten zu kontrollieren.

## Lizenz
MIT
