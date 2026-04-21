# German Job Scraper

Ein vollautomatisches Job-Scraping-System für deutsche Jobportale mit erweiterten CAPTCHA-Lösungsfunktionen und Kontaktinformations-Extraktion.

## Features

### 🚀 Kern-Funktionen
- **Automatisierte Job-URL-Sammlung** - Sammelt systematisch Job-URLs von deutschen Jobportalen
- **Intelligente Job-Daten-Extraktion** - Extrahiert detaillierte Jobinformationen inklusive Kontaktdaten
- **CAPTCHA-Lösung** - Hybrid-Ansatz mit TrOCR und 2captcha API
- **Kontakt-Enhancement** - Automatische Suche nach fehlenden Kontaktinformationen auf Firmenwebsites
- **PostgreSQL Integration** - Robuste Datenbankanbindung für Datenmanagement

### 🛠️ Technische Features
- **Docker-Ready** - Vollständig containerisiert für einfaches Deployment
- **Headless Browser** - Playwright-basierte Automatisierung
- **Session Management** - Fortsetzbares Scraping mit Session-Wiederherstellung
- **Umfassende Validierung** - Datenqualitätskontrolle und -bereinigung
- **Monitoring & Logging** - Detaillierte Protokollierung und Performance-Überwachung

## Architektur

```
job-scraper/
├── src/
│   ├── config/         # Zentrale Konfiguration
│   ├── scrapers/       # Scraping-Module
│   ├── database/       # Datenbankanbindung
│   ├── utils/          # Utility-Funktionen
│   └── models/         # Datenmodelle
├── scripts/            # Ausführbare Skripte
├── tests/              # Unit Tests
├── docs/               # Dokumentation
├── demos/              # Beispiele und Demos
└── data/               # Datenverzeichnis
    ├── input/          # Eingabedaten
    ├── output/         # Ausgabedaten
    ├── logs/           # Log-Dateien
    └── temp/           # Temporäre Dateien
```

## Installation

### 1. Repository klonen
```bash
git clone https://github.com/qfc88/Deutsch_DE_T.git
cd Deutsch_DE_T
```

### 2. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Datenbank einrichten
```bash
python scripts/setup_database.py
```

### 4. Konfiguration anpassen
```python
# src/config/settings.py
DATABASE_SETTINGS = {
    'host': 'localhost',
    'database': 'scrape',
    'username': 'postgres',
    'password': 'your_password'
}

TWOCAPTCHA_API_KEY = "your_2captcha_api_key"
```

## Docker Deployment

### 1. Docker Image bauen
```bash
docker build -t job-scraper .
```

### 2. Mit Docker Compose starten
```bash
docker-compose up -d
```

### 3. Produktionsumgebung
```bash
export ENVIRONMENT=production
docker-compose -f docker-compose.yml up -d
```

## Verwendung

### Komplette Pipeline ausführen
```bash
python scripts/run_full_pipeline.py
```

### Einzelne Komponenten
```bash
# Nur URL-Sammlung
python scripts/run_link_scraper.py

# Nur Job-Scraping
python scripts/run_job_scraper.py

# Fehlende Kontakte verarbeiten
python scripts/process_missing_emails.py
```

### Monitoring
```bash
python scripts/monitor_server.py
```

## Konfiguration

### Environment-basierte Einstellungen
- **Production**: `ENVIRONMENT=production` (headless=True)
- **Development**: `ENVIRONMENT=development` (headless=False, debug logging)

### Hauptkonfigurationen
- **SCRAPER_SETTINGS**: Browser- und Scraping-Einstellungen
- **CAPTCHA_SETTINGS**: CAPTCHA-Lösungsstrategien
- **DATABASE_SETTINGS**: Datenbankverbindung
- **VALIDATION_SETTINGS**: Datenvalidierung

## CAPTCHA-Lösung

### Hybrid-Strategie
1. **TrOCR** - Lokale OCR-Engine (anuashok/ocr-captcha-v3)
2. **2captcha** - Cloud-basierter Service
3. **Manual Fallback** - Manuelle Eingabe bei Bedarf

### Konfiguration
```python
CAPTCHA_SETTINGS = {
    'solving_strategies': ['trocr', '2captcha', 'manual'],
    'confidence_threshold': 0.7,
    'max_total_attempts': 10
}
```

## Datenvalidierung

### Qualitätskontrolle
- **Vollständigkeits-Score** - Überprüft Pflichtfelder
- **Qualitäts-Score** - Bewertet Datenqualität (0-11)
- **Datenbereinigung** - Automatische Normalisierung

### Validierungslevel
- **strict**: Hohe Qualitätsanforderungen
- **moderate**: Ausgewogene Validierung (Standard)
- **lenient**: Minimale Anforderungen

## Performance & Monitoring

### Metriken
- Scraping-Geschwindigkeit (Jobs/Minute)
- CAPTCHA-Erfolgsrate
- Datenqualitäts-Metriken
- Speicher- und CPU-Überwachung

### Session Management
- Automatische Fortschritts-Speicherung
- Session-Wiederherstellung bei Unterbrechungen
- Batch-Verarbeitung für große Datenmengen

## Testing

```bash
# Alle Tests ausführen
pytest

# Spezifische Tests
pytest tests/test_scrapers/
pytest tests/test_utils/

# Mit Coverage
pytest --cov=src tests/
```

## API Referenz

### JobScraper
```python
from src.scrapers.job_scraper import JobScraper

scraper = JobScraper()
jobs = await scraper.scrape_jobs(job_urls)
```

### ContactScraper
```python
from src.scrapers.contact_scraper import ContactScraper

contact_scraper = ContactScraper(context=browser_context)
enhanced_jobs = await contact_scraper.process_missing_contacts(jobs)
```

### CaptchaSolver
```python
from src.scrapers.captcha_solver import CaptchaSolver

solver = CaptchaSolver()
solution = await solver.solve_captcha(captcha_image_path)
```

## Troubleshooting

### Häufige Probleme

**Playwright Installation**
```bash
playwright install-deps chromium
```

**Datenbankverbindung**
```bash
# PostgreSQL Service prüfen
sudo systemctl status postgresql

# Verbindung testen
python -c "from src.database.connection import test_connection; test_connection()"
```

**CAPTCHA-Probleme**
- 2captcha API-Key überprüfen
- TrOCR Model herunterladen
- Confidence threshold anpassen

## Lizenz

MIT License - siehe LICENSE file

## Beitragen

1. Fork das Repository
2. Feature Branch erstellen (`git checkout -b feature/neue-funktion`)
3. Änderungen committen (`git commit -am 'Neue Funktion hinzufügen'`)
4. Branch pushen (`git push origin feature/neue-funktion`)
5. Pull Request erstellen

## Support

Für Support und Fragen:
- Issues erstellen im GitHub Repository
- Dokumentation in `docs/` konsultieren
- Logs in `data/logs/` überprüfen