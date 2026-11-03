from flask import Blueprint, jsonify, render_template, request

from orvelion import nordelia
from orvelion.content import (
    CABINETS,
    DIVISIONS,
    EVENT_CATEGORIES,
    EVENTS,
    MISSIONS,
    NAV_LINKS,
    PILLARS,
    ROADMAP,
    SITE,
    SOCIAL_LINKS,
    TIMELINE,
)

bp = Blueprint("pages", __name__)


def _ctx(**extra):
    data = {
        "site": SITE,
        "nav_links": NAV_LINKS,
        "social_links": SOCIAL_LINKS,
        "active_page": extra.pop("active_page", "home"),
        "show_chrome": extra.pop("show_chrome", True),
    }
    data.update(extra)
    return data


@bp.get("/")
def home():
    return render_template(
        "home.html",
        **_ctx(
            active_page="home",
            pillars=PILLARS,
            divisions=DIVISIONS,
            missions=MISSIONS,
        ),
    )


@bp.get("/event")
def event():
    return render_template(
        "event.html",
        **_ctx(
            active_page="event",
            events=EVENTS,
            categories=EVENT_CATEGORIES,
            roadmap=ROADMAP,
        ),
    )


@bp.get("/daftar")
def daftar():
    return render_template(
        "daftar.html",
        **_ctx(
            active_page="daftar",
            kategori_lomba=nordelia.KATEGORI_LOMBA,
            kelas_contoh=nordelia.KELAS_CONTOH,
            preselect=request.args.get("cabang", ""),
            webhook_aktif=nordelia.webhook_aktif(),
        ),
    )


@bp.post("/daftar")
def daftar_kirim():
    data = request.get_json(silent=True) or {}

    galat = nordelia.validasi(data)
    if galat:
        return jsonify({"ok": False, "errors": galat}), 400

    if not nordelia.boleh_kirim():
        return jsonify({
            "ok": False,
            "errors": {"_global": "Kebanyakan percobaan dari perangkat ini. Tunggu sekitar 10 menit lagi ya."},
        }), 429

    payload = nordelia.susun_payload(data)
    if payload is None:
        return jsonify({"ok": False, "errors": {"cabang_id": "Cabang lomba tidak dikenal."}}), 400

    sukses, pesan = nordelia.kirim_ke_webhook(payload)
    if not sukses:
        return jsonify({"ok": False, "errors": {"_global": pesan}}), 502

    return jsonify({
        "ok": True,
        "message": pesan,
        "ringkasan": {
            "nama": payload["nama_lengkap"],
            "kelas": payload["kelas"],
            "cabang": payload["cabang_name"],
            "kategori": payload["category_id"].upper(),
        },
    })


@bp.get("/before-us")
def before_us():
    return render_template(
        "before_us.html",
        **_ctx(
            active_page="before-us",
            cabinets=CABINETS,
            timeline=TIMELINE,
        ),
    )


@bp.get("/waiting-room")
def waiting_room():
    return_url = request.args.get("returnUrl") or "/"
    # Tolak juga "//..." — protokol-relatif URL bisa jadi open redirect
    # (phishing) meski lolos cek startswith("/") biasa.
    if not return_url.startswith("/") or return_url.startswith("//"):
        return_url = "/"
    return render_template(
        "waiting_room.html",
        **_ctx(active_page="waiting", show_chrome=True, return_url=return_url),
    )
