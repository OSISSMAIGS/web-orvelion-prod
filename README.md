# Portal OSIS Orvélion (Flask)

Situs resmi Kabinet Orvélion, OSIS SMA Ignatius Global School 2026–2027.

## Menjalankan lokal

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Buka [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Struktur

- `app.py` — titik masuk
- `orvelion/` — aplikasi Flask, data konten, dan pelindung kapasitas
- `templates/` — halaman Jinja
- `static/` — CSS, JavaScript, dan gambar
