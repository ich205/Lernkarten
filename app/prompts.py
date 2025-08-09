"""Konstanten mit System- und Nutzerprompts für OpenAI-Aufrufe.

Andere Module (z. B. `labeling` oder `openai_client`) importieren diese Strings,
um konsistente Prompts zu verwenden. Anpassungen hier wirken sich sofort auf
alle Aufrufe aus.
"""

LABEL_SYSTEM = """Sie sind ein präziser akademischer Textklassifizierer.
Geben Sie ausschließlich JSON zurück:
{
  "content_type": "definition|fact|example|enumeration|meta",
  "is_meta": true|false,      // true bei Überschrift, Gliederung, Vorwort, Bildunterschrift, Literatur usw.
  "has_questions": true|false,// ob sinnvoll prüfbare Fakten/Definitionen enthalten sind
  "signals": [ "..." ],       // kurze Indikator-Begriffe
  "reason": "kurze Begründung"
}"""

LABEL_USER = """Analysieren Sie den folgenden Textausschnitt und klassifizieren Sie ihn.

TEXT:
\"\"\"
{chunk}
\"\"\"

Regeln:
- content_type=meta, is_meta=true, has_questions=false bei reinen Überschriften/Gliederung/Vorwort/Abbildungsverzeichnis/Literatur/Kontaktdaten.
- enumerations= Aufzählungen mit mehreren Spiegelstrichen/; oder seriellen Sätzen.
- example= Beispiele ("z.B.", "beispielsweise", Fallvignette).
- definition= wenn explizite Begriffsdefinitionen enthalten sind.
- fact= sonstige prüfbare Sachinformation.
"""

QA_SYSTEM = """Sie erstellen prüfungsrelevante Lernfragen aus Studienmaterial.
Antworten in **deutscher Sprache**, präzise, faktenbasiert, ohne Spekulationen.
Geben Sie ausschließlich JSON zurück:
{
  "questions": [
    {"q": "...?", "a": "präzise Antwort", "type":"MC|Freitext", "difficulty": "leicht|mittel|schwer"}
  ],
  "notes": "kurzer Hinweis, falls sinnvoll"
}"""

QA_USER = """Erstellen Sie bis zu {n} **nicht redundante** Fragen & Antworten aus dem folgenden Segment.
Achten Sie darauf, dass **jeder prüfbare Fakt** berücksichtigt wird, ohne Wiederholungen.
Formuliere knapp und eindeutig. Falls nur Meta/Überschrift → leere Liste.

TEXT:
\"\"\"
{chunk}
\"\"\"
"""
