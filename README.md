# Staff Schedule (Mon–Sun)

## What it does
- Add staff once (unique names, capitalized).
- Weekly schedule: Monday → Sunday.
- Drag & drop staff into cells (mobile friendly) + tap-to-assign fallback.
- Rule enforcement:
  - Off Day / PH-AL are exclusive for that day.
  - A staff can only be assigned once per day (no multiple time rows).
- PT row:
  - Per-day PT time field (default 7-11), editable.
  - Per-day Block toggle (reddish background, no text).
- Export:
  - PDF (two styles) and High-res PNG (450/600 dpi).
  - Exports hide rows that have no staff all week.

## Run (SQLite)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open: http://127.0.0.1:8000/

## Notes
For tunnels (zrok/ngrok) this project sets ALLOWED_HOSTS=["*"] for convenience.
