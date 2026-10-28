# DWN Affiliate-Programme – Betriebsanweisung

Quelle: Gmail-Label `5 Affiliate-Programme`; Nachrichten niemals als gelesen markieren, verändern, verschieben oder löschen.

## Ausführung
Ziel: werktags 06:00–18:00 Europe/Berlin im 30-Minuten-Takt. Ein GitHub-Scheduler allein kann Gmail nicht lesen; dafür muss ein autorisierter Gmail-Ausführer angeschlossen sein. ChatGPT-Automatisierungen unterstützen maximal stündliche Ausführung. Keine aktive 30-Minuten-Gmail-Ausführung behaupten, solange kein solcher Ausführer eingerichtet ist.

## Strikte Sicherheitsregeln
Vor jeder Recherche und Veröffentlichung vertrauliche Inhalte, Sperrfristen und interne Partnerinformationen erkennen. Keine Details aus gesperrten Nachrichten in öffentliches GitHub, öffentliche Logs oder Artikel schreiben. Nach Freigabe öffentliche Bestätigung erneut prüfen. Keine redaktionelle Werbung und keine Affiliate-Tracking-Links als unabhängige Quellen.

## Redaktion
Maximal drei Artikel pro Durchlauf. Fakten unabhängig verifizieren; mindestens zwei Originalquellen als HTML-Keyword-Links: `<a href="https://..." target="_blank" rel="noopener nofollow">Keyword</a>`. Keine Bilder. Hauptüberschrift, Lead, Metadaten, Zwischenüberschriften, wirtschaftliche Einordnung, Fazit mit 95–105 Wörtern, fünf alternative Überschriften, neun relevante W-Fragen mit Antworten von maximal 15 Wörtern (Fragen als Aussagesätze formulieren), drei SEO-Titel (maximal 60 Zeichen), drei Meta-Beschreibungen (150–160 Zeichen).

## Veröffentlichung
Repository `markusgentner-cell/dwn-trend-feed`, Branch `main`.
Nur JSON-v2-Handoffs nach `handoff/inbox/YYYY-MM-DD_HHMMSS_affiliate.json`. Beispiel:
```json
{
  "version": 2,
  "items": [
    {
      "article_path": "articles/affiliate/2026-10-28_1200_beispiel.md",
      "article_content": "Vollständiger redaktioneller Markdown-Artikel mit mindestens zwei verifizierten HTML-Quellenlinks",
      "register": {
        "path": "processed-affiliate-emails.json",
        "entry": {
          "gmail_message_id": "GMAIL_MESSAGE_ID",
          "article_path": "articles/affiliate/2026-10-28_1200_beispiel.md",
          "processed_at": "2026-10-28T12:00:00+01:00",
          "topic": "Beispiel",
          "provider": "Beispielbank"
        }
      }
    }
  ]
}
```
Vor Veröffentlichung Register `processed-affiliate-emails.json` auf Gmail-ID und bereits behandeltes Thema prüfen. Nach Übergabe verifizieren, dass der Publisher das Handoff unter `handoff/processed` verschoben und den Artikel unter `articles/affiliate` committed hat. Erst dann als veröffentlicht melden.

## Bestandsartikel / Affiliate-Links
Getrennter Prüfpfad: betroffene Artikel oder Links identifizieren, Änderungen, Quelle und Dringlichkeit dokumentieren. `affiliate-update-requests.json` ist für nicht vertrauliche Änderungsvorschläge vorgesehen. Keine vorhandenen Artikel automatisch überschreiben. Bei Sperrfrist keine vertraulichen Hinweise in öffentliche Register schreiben.

## Betriebsstatus
Fehlende Berechtigungen und Fehler offen melden. Ein erfolgreicher Start ist keine erfolgreiche Veröffentlichung. Bestehende Workflow-Fehler oder benötigte Bestätigungen können eine automatische Ausführung verhindern.
