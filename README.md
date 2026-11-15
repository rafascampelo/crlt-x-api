# Ctrl X Backend

## Prerequisites (Windows)
- Python 3.12+, Docker Desktop with Linux containers / Compose v2
- Tesseract OCR installed on Windows, with Portuguese (`por`) and English (`eng`) language data

## Local setup (PowerShell)
```powershell
Copy-Item .env.example .env
# Edit .env and replace CHANGE_ME, CHANGE_ROOT_ME, SECRET_KEY with strong unique values.
docker compose up -d
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs.

Run tests in a separate activated PowerShell session:
```powershell
python -m pytest
python -m ruff check .
```

Tesseract check:
```powershell
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --list-langs
```

The MySQL service is bound to `127.0.0.1:3307` (container 3306). No migrations or DB connection have been implemented yet; Codex prompt 01 adds them. `.env` is for local development only; do not use real patient data.
