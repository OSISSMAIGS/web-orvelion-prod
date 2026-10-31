import time
import json
from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for

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
from orvelion.nordelia_data import (
    CABANG_LOMBA,
    CATEGORIES,
    FORMAT_REGISTRASI,
    NORDELIA_INFO,
    SHEET2_FORMAT_SPEC,
    get_cabang_by_id,
)
from orvelion.sheets_service import (
    export_registrations_csv,
    get_config,
    storage,
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


@bp.get("/nordelia")
@bp.get("/event/nordelia")
def nordelia():
    summary = storage.get_summary_stats()
    all_regs = storage.get_all_registrations()
    spreadsheet_url = get_config(
        "NORDELIA_SPREADSHEET_URL",
        "https://docs.google.com/spreadsheets/d/" + get_config("NORDELIA_SPREADSHEET_ID", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms") + "/edit"
    )
    return render_template(
        "nordelia.html",
        **_ctx(
            active_page="nordelia",
            nordelia=NORDELIA_INFO,
            categories=CATEGORIES,
            cabang_lomba=CABANG_LOMBA,
            sheet2_formats=SHEET2_FORMAT_SPEC,
            format_registrasi=FORMAT_REGISTRASI,
            summary=summary,
            registrations=all_regs[:10],
            spreadsheet_url=spreadsheet_url,
            spreadsheet_id=get_config("NORDELIA_SPREADSHEET_ID"),
        ),
    )


@bp.get("/nordelia/spreadsheet")
def nordelia_spreadsheet():
    selected_cat = request.args.get("category", "semua")
    regs = storage.get_all_registrations(selected_cat if selected_cat != "semua" else None)
    summary = storage.get_summary_stats()
    spreadsheet_url = get_config(
        "NORDELIA_SPREADSHEET_URL",
        "https://docs.google.com/spreadsheets/d/" + get_config("NORDELIA_SPREADSHEET_ID", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms") + "/edit"
    )
    return render_template(
        "nordelia_spreadsheet.html",
        **_ctx(
            active_page="nordelia",
            nordelia=NORDELIA_INFO,
            categories=CATEGORIES,
            selected_category=selected_cat,
            registrations=regs,
            summary=summary,
            sheet2_formats=SHEET2_FORMAT_SPEC,
            spreadsheet_url=spreadsheet_url,
            spreadsheet_id=get_config("NORDELIA_SPREADSHEET_ID"),
        ),
    )


# =========================================================================
# API REAL-TIME ENDPOINTS: FORM PENDAFTARAN & GOOGLE SPREADSHEET
# =========================================================================

@bp.post("/api/nordelia/register")
def api_nordelia_register():
    try:
        # Terima data dari JSON atau form-data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict()

        cabang_id = data.get("cabang_id", "").strip()
        cabang_info = get_cabang_by_id(cabang_id)
        if not cabang_info:
            return jsonify({
                "success": False,
                "error": "Cabang lomba tidak ditemukan atau belum dipilih.",
            }), 400

        # Validasi nama peserta / tim
        nama = data.get("nama_lengkap") or data.get("nama_tim") or data.get("nama", "").strip()
        if not nama:
            return jsonify({
                "success": False,
                "error": "Nama lengkap peserta atau nama tim wajib diisi.",
            }), 400

        kelas = data.get("kelas", "").strip()
        if not kelas:
            return jsonify({
                "success": False,
                "error": "Asal kelas wajib diisi (Contoh: 10.1 CGC, 10.2 MAYOR).",
            }), 400

        # Masukkan informasi cabang
        data["cabang_id"] = cabang_info["id"]
        data["cabang_name"] = cabang_info["name"]
        data["category_id"] = cabang_info["category"]

        # Simpan ke storage dan sinkronisasikan real-time ke Google Spreadsheet
        saved_entry = storage.save_registration(data)

        return jsonify({
            "success": True,
            "message": f"Pendaftaran cabang '{cabang_info['name']}' berhasil dicatat secara real-time!",
            "entry": saved_entry,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Terjadi kendala saat memproses pendaftaran: {str(e)}",
        }), 500


@bp.get("/api/nordelia/registrations")
def api_nordelia_registrations():
    cat = request.args.get("category", "")
    data = storage.get_all_registrations(cat if cat else None)
    return jsonify({
        "success": True,
        "count": len(data),
        "data": data,
    })


@bp.get("/api/nordelia/stats")
def api_nordelia_stats():
    stats = storage.get_summary_stats()
    return jsonify({
        "success": True,
        "stats": stats,
    })


@bp.get("/api/nordelia/export.csv")
def api_nordelia_export_csv():
    cat = request.args.get("category")
    csv_content = export_registrations_csv(cat)
    filename = f"pendaftaran_nordelia_{cat or 'semua'}_{int(time.time())}.csv" if 'time' in globals() else f"pendaftaran_nordelia_{cat or 'semua'}.csv"
    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


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
    if not return_url.startswith("/"):
        return_url = "/"
    return render_template(
        "waiting_room.html",
        **_ctx(active_page="waiting", show_chrome=True, return_url=return_url),
    )
