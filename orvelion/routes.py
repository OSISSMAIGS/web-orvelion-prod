import copy
import json
import os
import secrets
import threading
import time
from flask import Blueprint, Response, jsonify, redirect, render_template, request, session, url_for

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
    KETENTUAN_DETAIL,
    CABANG_LOMBA,
    CATEGORIES,
    FORMAT_REGISTRASI,
    NORDELIA_INFO,
    OLIMPIADE_9_DAN_AI_IDS,
    SHEET2_FORMAT_SPEC,
    get_cabang_by_id,
)
from orvelion.sheets_service import (
    export_registrations_csv,
    get_config,
    storage,
)
from orvelion.voting_data import NOMINATIONS, TEACHERS
from orvelion.voting_db import SCHOOL_DOMAIN, is_valid_school_email, voting_storage


def resolve_group_link(cabang_info=None):
    if cabang_info and cabang_info.get("group_link"):
        return cabang_info["group_link"].strip()
    return (
        get_config("NORDELIA_GROUP_LINK")
        or NORDELIA_INFO.get("group_link")
        or ""
    ).strip()


# Cache berbasis mtime untuk nordelia_events.json agar tidak dibaca ulang
# dari disk pada setiap request. Hasil dikembalikan sebagai salinan dalam
# (deep copy) karena route nordelia_category() memutasi objek kategori —
# perilaku ini identik dengan kode asli yang selalu mem-parse ulang file.
_nordelia_events_cache = {"key": None, "data": None}

# ======================================================================
# Micro-cache render untuk halaman yang isinya murni statis (home,
# before_us, event) — tidak ada data kuota/pendaftaran di dalamnya.
#
# Body HTML di-cache di memori proses; kunci cache = mtime file template
# + mtime sumber data (content.py / nordelia_events.json) sehingga setiap
# deploy atau perubahan file OTOMATIS membatalkan cache (tidak ada halaman
# basi). TTL hanyalah jaring pengaman tambahan. Hasil render identik byte
# per byte dengan render langsung — hanya CPU yang dihemat saat ramai.
# ======================================================================
_page_cache: dict = {}
_page_cache_lock = threading.Lock()

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(_BASE_DIR, "..", "templates")
_EVENTS_JSON_PATH = os.path.join(_BASE_DIR, "..", "nordelia_events.json")


def _f_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def render_cached(template_name: str, ctx_factory, ttl: float = 10.0, extra_key=()):
    """render_template + micro-cache body (aman untuk halaman statis).

    ctx_factory dipanggil HANYA saat cache miss (hemat pembuatan context
    berat). Kunci mencakup mtime template + mtime modul konten sehingga
    perubahan kode/deploy langsung membatalkan cache."""
    key = (
        template_name,
        _f_mtime(os.path.join(_TEMPLATES_DIR, template_name)),
        _f_mtime(os.path.join(_BASE_DIR, "content.py")),
        _f_mtime(os.path.join(_BASE_DIR, "nordelia_data.py")),
        tuple(extra_key),
    )
    now = time.time()
    with _page_cache_lock:
        hit = _page_cache.get(key)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]

    html = render_template(template_name, **ctx_factory())

    with _page_cache_lock:
        _page_cache[key] = (now, html)
        # buang kunci basi untuk template yang sama (mtime lama)
        if len(_page_cache) > 8:
            for k in [k for k in list(_page_cache) if k[0] == template_name and k != key]:
                _page_cache.pop(k, None)
    return html


def load_nordelia_events():
    try:
        events_path = os.path.join(os.path.dirname(__file__), "..", "nordelia_events.json")
        if os.path.exists(events_path):
            st = os.stat(events_path)
            key = (st.st_mtime_ns, st.st_size)
            if _nordelia_events_cache["key"] == key and _nordelia_events_cache["data"] is not None:
                return copy.deepcopy(_nordelia_events_cache["data"])
            with open(events_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _nordelia_events_cache["key"] = key
            _nordelia_events_cache["data"] = data
            return copy.deepcopy(data)
    except Exception:
        pass
    return {"categories": []}


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
    return render_cached(
        "home.html",
        lambda: _ctx(
            active_page="home",
            pillars=PILLARS,
            divisions=DIVISIONS,
            missions=MISSIONS,
        ),
        ttl=10.0,
    )


@bp.get("/event")
def event():
    return render_cached(
        "event.html",
        lambda: _ctx(
            active_page="event",
            events=EVENTS,
            categories=EVENT_CATEGORIES,
            roadmap=ROADMAP,
            nordelia_events=load_nordelia_events(),
        ),
        ttl=15.0,
        extra_key=("events_json", _f_mtime(_EVENTS_JSON_PATH)),
    )


def _decode_jwt_payload(token_str: str) -> dict:
    try:
        import base64
        parts = token_str.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += "=" * (4 - rem)
            decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
            return json.loads(decoded)
    except Exception:
        pass
    return {}


@bp.get("/voting")
@bp.get("/eduvella")
@bp.get("/event/voting")
def voting():
    google_user = session.get("google_user")
    has_voted = False
    voted_at = None

    # Lapisan Proteksi: Cookie perangkat atau flag sesi
    cookie_token = request.cookies.get("eduvella_voted_token")
    if cookie_token or session.get("eduvella_has_voted"):
        has_voted = True
        voted_at = "Perangkat ini telah mencatat pengiriman suara sebelumnya."

    if google_user and not has_voted:
        has_voted, voted_at = voting_storage.check_email_voted(google_user.get("email", ""))

    return render_template(
        "voting.html",
        **_ctx(
            active_page="voting",
            nominations=NOMINATIONS,
            teachers=TEACHERS,
            stats=voting_storage.get_stats(),
            google_client_id=get_config("GOOGLE_CLIENT_ID", ""),
            school_domain=SCHOOL_DOMAIN,
            current_user=google_user,
            has_voted=has_voted,
            voted_at=voted_at,
        ),
    )


RESULTS_PASSWORD = get_config("VOTING_RESULTS_PASSWORD", "EduvellaVoting").strip()


@bp.route("/voting/hasil", methods=["GET", "POST"])
@bp.route("/eduvella/hasil", methods=["GET", "POST"])
@bp.route("/event/voting/hasil", methods=["GET", "POST"])
def voting_results():
    error_message = ""
    # Cek jika submit password form via POST
    if request.method == "POST":
        pwd = (request.form.get("password") or "").strip()
        if pwd == RESULTS_PASSWORD:
            session["voting_results_authed"] = True
            return redirect("/voting/hasil")
        else:
            error_message = "Password akses salah! Pastikan menggunakan password resmi panitia Eduvella."

    is_authed = bool(session.get("voting_results_authed"))
    results_data = voting_storage.get_voting_results() if is_authed else {
        "total_ballots": 0,
        "total_students_voted": 0,
        "categories": [],
        "last_updated": "Terkunci",
    }

    return render_template(
        "voting_results.html",
        **_ctx(
            active_page="event",
            is_authed=is_authed,
            error_message=error_message,
            results_data=results_data,
            nominations=NOMINATIONS,
            stats=voting_storage.get_stats() if is_authed else {},
        ),
    )


@bp.post("/voting/hasil/auth")
def voting_results_auth_ajax():
    data = request.get_json(silent=True) or {}
    pwd = (data.get("password") or request.form.get("password") or "").strip()
    if pwd == RESULTS_PASSWORD:
        session["voting_results_authed"] = True
        return jsonify({"ok": True, "message": "Autentikasi berhasil!"})
    return jsonify({"ok": False, "message": "Password salah! Hanya panitia OSIS yang berhak melihat hasil."}), 401


@bp.post("/voting/hasil/logout")
def voting_results_logout():
    session.pop("voting_results_authed", None)
    return redirect("/voting/hasil")


@bp.get("/api/voting/results")
def api_voting_results():
    pwd_query = request.args.get("password", "").strip()
    pwd_header = request.headers.get("X-Voting-Password", "").strip()
    is_authed = session.get("voting_results_authed") or (pwd_query == RESULTS_PASSWORD) or (pwd_header == RESULTS_PASSWORD)

    if not is_authed:
        return jsonify({
            "ok": False,
            "error": "Akses hasil voting terkunci. Password resmi diperlukan.",
            "requires_password": True,
        }), 401

    data = voting_storage.get_voting_results()
    return jsonify({
        "ok": True,
        "data": data,
    })


@bp.post("/api/voting/reset-ballots")
def api_reset_ballots():
    data = request.get_json(silent=True) or {}
    pwd = (request.headers.get("X-Voting-Password") or data.get("password") or "").strip()
    if pwd != RESULTS_PASSWORD and not session.get("voting_results_authed"):
        return jsonify({"ok": False, "message": "Akses ditolak. Password panitia diperlukan."}), 403
    ok, msg = voting_storage.reset_ballots()
    session.pop("eduvella_has_voted", None)
    session.pop("google_user", None)
    resp = jsonify({"ok": ok, "message": msg})
    resp.delete_cookie("eduvella_voted_token")
    return resp


@bp.get("/api/voting/db-status")
def api_voting_db_status():
    user = get_config("DB_USER", "")
    db_name = get_config("DB_NAME", "")
    try:
        driver, conn = voting_storage._get_db()
        conn.close()
        return jsonify({
            "ok": True,
            "driver": driver,
            "is_jagoan_hosting_mysql": (driver == "mysql"),
            "database_name": db_name if driver == "mysql" else "none",
            "database_user": user if driver == "mysql" else "none",
            "message": "Terhubung aktif ke MySQL JagoanHosting"
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "driver": "none",
            "is_jagoan_hosting_mysql": False,
            "database_name": db_name,
            "database_user": user,
            "error": str(e),
            "solution": "Pastikan library 'pymysql' dan 'cryptography' sudah terinstall di cPanel (pip install -r requirements.txt) dan user MySQL memiliki ALL PRIVILEGES."
        }), 503


@bp.get("/api/voting/check-nis")
def check_nis():
    nis = (request.args.get("nis") or "").strip()
    if not nis:
        return jsonify({"ok": False, "message": "NIS wajib diisi."})
    has_voted, voted_at = voting_storage.check_nis_voted(nis)
    return jsonify({
        "ok": True,
        "nis": nis,
        "has_voted": has_voted,
        "voted_at": voted_at,
    })


@bp.get("/api/voting/check-name")
def check_name():
    name = (request.args.get("name") or "").strip()
    if not name or len(name) < 2:
        return jsonify({"ok": True, "has_voted": False})
    has_voted, voted_at = voting_storage.check_name_voted(name)
    return jsonify({
        "ok": True,
        "name": name,
        "has_voted": has_voted,
        "voted_at": voted_at,
    })


@bp.get("/api/auth/me")
def auth_me():
    user = session.get("google_user")
    if not user:
        return jsonify({"logged_in": False, "user": None, "has_voted": False})
    has_voted, voted_at = voting_storage.check_email_voted(user.get("email", ""))
    return jsonify({
        "logged_in": True,
        "user": user,
        "has_voted": has_voted,
        "voted_at": voted_at,
    })


@bp.post("/api/auth/google")
def auth_google():
    data = request.get_json(silent=True) or {}
    credential = data.get("credential", "")
    email = data.get("email", "").strip().lower()
    name = data.get("name", "").strip()
    picture = data.get("picture", "")

    # Jika dikirim via Google Identity Services (JWT ID token)
    if credential:
        payload = _decode_jwt_payload(credential)
        if payload:
            email = payload.get("email", "").strip().lower()
            name = payload.get("name", "").strip() or payload.get("given_name", "")
            picture = payload.get("picture", "")

    if not email:
        return jsonify({"ok": False, "message": "Email Google tidak terdeteksi."}), 400

    if not is_valid_school_email(email):
        return jsonify({
            "ok": False,
            "message": f"Login ditolak. Hanya akun resmi siswa SMA IGS dengan domain @{SCHOOL_DOMAIN} yang berhak melakukan voting.",
        }), 403

    has_voted, voted_at = voting_storage.check_email_voted(email)
    user_info = {
        "email": email,
        "name": name or email.split("@")[0].replace(".", " ").title(),
        "picture": picture,
        "domain": SCHOOL_DOMAIN,
    }
    session["google_user"] = user_info

    msg = "Login berhasil dengan akun Google sekolah."
    if has_voted:
        msg = f"Anda login sebagai {user_info['name']}, namun akun ini sudah pernah digunakan untuk voting."

    return jsonify({
        "ok": True,
        "user": user_info,
        "has_voted": has_voted,
        "voted_at": voted_at,
        "message": msg,
    })


@bp.post("/api/auth/logout")
def auth_logout():
    session.pop("google_user", None)
    return jsonify({"ok": True, "message": "Berhasil logout."})


@bp.post("/api/voting/verify-coupon")
def verify_voting_coupon():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    valid, status, message = voting_storage.check_coupon(token)
    return jsonify({"ok": valid, "status": status, "message": message})


@bp.post("/api/voting/submit")
def submit_vote():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    votes = data.get("votes", {})
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    nis = (data.get("nis") or "").strip()
    class_name = (data.get("class_name") or "").strip()
    device_fp = (data.get("device_fp") or "").strip()

    # Lapisan Proteksi 1: Cek Cookie Keamanan Perangkat & Sesi
    cookie_token = request.cookies.get("eduvella_voted_token")
    if cookie_token or session.get("eduvella_has_voted"):
        return jsonify({
            "ok": False,
            "message": "Perangkat atau browser ini sudah pernah digunakan untuk voting. Demi asas pemilu yang jujur dan adil, 1 siswa hanya berhak mengirim 1 kali.",
            "already_voted": True,
        }), 403

    # Prioritaskan user yang sedang login di sesi
    session_user = session.get("google_user")
    if session_user:
        email = session_user.get("email", "").lower()
        name = session_user.get("name", "")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    ok = False
    message = ""

    # Sistem Utama: Cukup Masukkan Nama Pemilih / Siswa
    if name and not (email or nis or token):
        ok, message = voting_storage.submit_vote_by_name(name, votes, ip_address=ip, device_fp=device_fp)

    # Sistem 1: Voting via Akun Google Resmi Siswa (@students.ignatiusglobal.sch.id)
    elif email:
        if not is_valid_school_email(email):
            return jsonify({
                "ok": False,
                "message": f"Hanya akun Google resmi siswa @{SCHOOL_DOMAIN} yang diizinkan untuk voting.",
            }), 403

        ok, message = voting_storage.submit_vote_with_google(email, name, votes, ip_address=ip, device_fp=device_fp)

    # Sistem 2: Voting via Nomor Induk Siswa (NIS) Resmi
    elif nis:
        ok, message = voting_storage.submit_vote_with_nis(nis, name or f"Siswa ({nis})", class_name, votes, ip_address=ip, device_fp=device_fp)

    # Sistem 3: Voting via Kode Blind Kupon Unik OSIS
    elif token:
        ok, message = voting_storage.submit_vote(token, votes, ip_address=ip)

    elif name:
        ok, message = voting_storage.submit_vote_by_name(name, votes, ip_address=ip, device_fp=device_fp)

    else:
        return jsonify({
            "ok": False,
            "message": "Silakan masukkan nama lengkap Anda terlebih dahulu sebelum mengirim suara.",
        }), 400

    if ok:
        session["eduvella_has_voted"] = True
        resp = jsonify({"ok": True, "message": message, "already_voted": True})
        # Set cookie proteksi 365 hari (1 tahun)
        resp.set_cookie(
            "eduvella_voted_token",
            secrets.token_hex(16),
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
        )
        return resp
    else:
        return jsonify({"ok": False, "message": message}), 400


@bp.get("/api/voting/teachers")
def search_teachers():
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"results": TEACHERS[:30]})
    filtered = [t for t in TEACHERS if q in t.lower()]
    return jsonify({"results": filtered})



def build_decorated_cabang_list():
    counts = storage.get_counts_by_cabang()
    decorated = []
    for c in CABANG_LOMBA:
        c_copy = dict(c)
        cid = c["id"]
        reg_count = counts.get(cid, 0)
        c_copy["registered_count"] = reg_count
        
        c_copy["peserta_min"] = None
        # 1. Aturan Olimpiade (OSN 9 Cabang + Kecerdasan Artifisial): Max 20 Orang (Bahasa Asing Kuota Terbuka Bebas)
        is_bahasa = (c.get("category") == "bahasa") or "bahasa" in cid.lower()
        if not is_bahasa and (c.get("is_olimpiade_or_ai") or cid in OLIMPIADE_9_DAN_AI_IDS):
            c_copy["is_olimpiade_or_ai"] = True
            c_copy["peserta_max"] = "20"
            c_copy["max_quota"] = 20
            remaining = max(0, 20 - reg_count)
            c_copy["remaining_quota"] = remaining
            c_copy["is_full"] = reg_count >= 20
            c_copy["quota_text"] = f"Sisa {remaining} dari 20 Kuota" if remaining > 0 else "Kuota Penuh (20/20)"
            c_copy["quota_badge"] = f"Sisa {remaining} Kuota" if remaining > 0 else "Kuota Penuh"
        # 2. Sisanya (Literasi, Seni, Bahasa, Olahraga): Tanpa Min & Tanpa Max
        else:
            c_copy["is_olimpiade_or_ai"] = False
            c_copy["peserta_max"] = None
            c_copy["max_quota"] = None
            c_copy["remaining_quota"] = None
            c_copy["is_full"] = False
            c_copy["quota_text"] = "Kuota Terbuka"
            c_copy["quota_badge"] = "Kuota Terbuka"
            
        c_copy["is_team"] = c.get("is_team", False)
        c_copy["is_external_gform"] = c.get("is_external_gform", False)
        c_copy["gform_url"] = c.get("gform_url", "")
        c_copy["email_notice"] = "Gunakan akun email resmi sekolah untuk mendaftar" if c_copy["is_external_gform"] else ""
        c_copy["group_link"] = c.get("group_link", "")
        c_copy["group_label"] = c.get("group_label", "Masuk Grup LINE")
        c_copy["juknis_url"] = c.get("juknis_url", "")
        c_copy["is_literasi"] = c["name"].lower().startswith("literasi") or cid.startswith("literasi")
        c_copy["ketentuan"] = c.get("ketentuan")
        decorated.append(c_copy)
    return decorated


@bp.get("/nordelia")
@bp.get("/event/nordelia")
def nordelia():
    summary = storage.get_summary_stats()
    spreadsheet_url = get_config(
        "NORDELIA_SPREADSHEET_URL",
        "https://docs.google.com/spreadsheets/d/" + get_config("NORDELIA_SPREADSHEET_ID", "1I5PF4GTdkiMUcfQ-YBskctP6X_WnSruRGACEUnAwG-c") + "/edit",
    )
    nordelia_json = load_nordelia_events()
    return render_template(
        "nordelia.html",
        **_ctx(
            active_page="nordelia",
            nordelia=NORDELIA_INFO,
            categories=CATEGORIES,
            nordelia_categories=nordelia_json.get("categories", []),
            cabang_lomba=build_decorated_cabang_list(),
            sheet2_formats=SHEET2_FORMAT_SPEC,
            format_registrasi=FORMAT_REGISTRASI,
            ketentuan_detail=KETENTUAN_DETAIL,
            summary=summary,
            spreadsheet_url=spreadsheet_url,
            spreadsheet_id=get_config("NORDELIA_SPREADSHEET_ID"),
            group_link=resolve_group_link(),
            group_label=get_config("NORDELIA_GROUP_LABEL") or NORDELIA_INFO.get("group_label", "Masuk Grup WhatsApp"),
        ),
    )


@bp.get("/nordelia/<category_id>")
def nordelia_category(category_id: str):
    cat_id_clean = category_id.lower().strip()
    if cat_id_clean in ("olimpiade-9-cabang", "osn"):
        target_ids = ("osn", "olimpiade-9-cabang")
    elif cat_id_clean in ("lomba-debat", "lomba-debat-indonesia"):
        target_ids = ("lomba-debat", "lomba-debat-indonesia")
    else:
        target_ids = (cat_id_clean, category_id)

    # Cari di nordelia_events.json
    nordelia_json = load_nordelia_events()
    cat_match = None
    for c in nordelia_json.get("categories", []):
        if c.get("id") in target_ids:
            cat_match = c
            break

    # Jika tidak ada di nordelia_events.json, cari di CATEGORIES utama
    if not cat_match:
        for c in CATEGORIES:
            if c.get("id") == category_id:
                sub_events = [
                    {
                        "id": cb["id"],
                        "name": cb["name"],
                        "pic": cb["pic"],
                        "tempat": cb["tempat"],
                        "peserta_max": cb["peserta_max"],
                        "is_olimpiade_or_ai": cb["is_olimpiade_or_ai"],
                        "registrationFormat": ["Nama Lengkap", "Kelas"],
                        "is_external_gform": cb.get("is_external_gform", False),
                        "gform_url": cb.get("gform_url", ""),
                        "ketentuan": cb.get("ketentuan"),
                        "note": cb.get("note", "-"),
                    }
                    for cb in CABANG_LOMBA
                    if cb["category"] == category_id
                ]
                cat_match = {
                    "id": c["id"],
                    "name": c["name"],
                    "description": c["description"],
                    "hasSubEvents": True,
                    "subEvents": sub_events,
                }
                break

    if not cat_match:
        return redirect(url_for("pages.nordelia"))

    jurusan = request.args.get("jurusan", "").lower().strip()
    # Aturan Peminatan OSN: Matematika boleh dipilih kelas IPS
    OSN_IPA_ONLY_IDS = {
        "olimpiade-fisika",
        "olimpiade-kimia",
        "olimpiade-biologi",
        "olimpiade-astronomi",
        "olimpiade-informatika",
    }
    OSN_IPS_ALLOWED_IDS = {
        "olimpiade-matematika",
        "olimpiade-kebumian",
        "olimpiade-geografi",
        "olimpiade-ekonomi",
    }

    counts = storage.get_counts_by_cabang()
    if not cat_match.get("subEvents"):
        cabang_info = get_cabang_by_id(cat_match["id"])
        sub_name = cabang_info["name"] if cabang_info else cat_match["name"]
        is_bahasa_cat = (cat_match.get("id") == "bahasa") or "bahasa" in cat_match["id"].lower() or "bahasa" in sub_name.lower()
        is_olimp = not is_bahasa_cat and ((cabang_info.get("is_olimpiade_or_ai", False) if cabang_info else False) or cat_match["id"] in OLIMPIADE_9_DAN_AI_IDS or "ai" in cat_match["id"].lower() or "artifisial" in sub_name.lower())
        is_lit = sub_name.lower().startswith("literasi") or cat_match["id"].startswith("literasi")
        reg_c = counts.get(cabang_info["id"] if cabang_info else cat_match["id"], 0)
        rem = max(0, 20 - reg_c) if is_olimp else None
        
        cat_match["subEvents"] = [
            {
                "id": cabang_info["id"] if cabang_info else cat_match["id"],
                "name": sub_name,
                "pic": cabang_info["pic"] if cabang_info else "-",
                "tempat": cabang_info["tempat"] if cabang_info else "-",
                "peserta_min": None,
                "peserta_max": "20" if is_olimp else None,
                "is_olimpiade_or_ai": is_olimp,
                "is_literasi": is_lit,
                "registered_count": reg_c,
                "remaining_quota": rem,
                "is_full": reg_c >= 20 if is_olimp else False,
                "quota_text": (f"Sisa {rem} dari 20 Kuota" if rem > 0 else "Kuota Penuh (20/20)") if is_olimp else "Kuota Terbuka",
                "quota_badge": (f"Sisa {rem} Kuota" if rem > 0 else "Kuota Penuh") if is_olimp else "Kuota Terbuka",
                "registrationFormat": ["Nama Lengkap", "Kelas"],
                "is_team": cabang_info.get("is_team", False) if cabang_info else False,
                "is_external_gform": cabang_info.get("is_external_gform", False) if cabang_info else False,
                "gform_url": cabang_info.get("gform_url", "") if cabang_info else "",
                "email_notice": "Gunakan akun email resmi sekolah untuk mendaftar" if (cabang_info.get("is_external_gform", False) if cabang_info else False) else "",
                "group_link": cabang_info.get("group_link", "") if cabang_info else "",
                "group_label": cabang_info.get("group_label", "Masuk Grup LINE") if cabang_info else "Masuk Grup LINE",
                "juknis_url": cabang_info.get("juknis_url", "") if cabang_info else "",
                "ketentuan": cabang_info.get("ketentuan") if cabang_info else None,
                "note": cabang_info.get("note", "-") if cabang_info else "-",
            }
        ]
    else:
        for sub in cat_match.get("subEvents", []):
            cb = get_cabang_by_id(sub.get("id"))
            if not cb and (sub.get("id", "").lower() in ("ai", "olimpiade-ai") or "artifisial" in sub.get("name", "").lower()):
                cb = get_cabang_by_id("olimpiade-ai")
            
            sub_id = cb["id"] if cb else sub.get("id", "")
            sub_name = cb.get("name", sub.get("name", ""))
            is_bahasa = (cb.get("category") == "bahasa" if cb else False) or "bahasa" in sub_id.lower() or "bahasa" in sub_name.lower()
            is_olimp = not is_bahasa and not ("desain" in sub_id.lower() or "poster" in sub_id.lower()) and (
                (cb.get("is_olimpiade_or_ai", False) if cb else False)
                or sub_id in OLIMPIADE_9_DAN_AI_IDS
                or sub_id in ("ai", "olimpiade-ai")
                or "artifisial" in sub_name.lower()
            )
            is_lit = sub_name.lower().startswith("literasi") or sub_id.startswith("literasi")
            reg_c = counts.get(sub_id, 0)
            rem = max(0, 20 - reg_c) if is_olimp else None
            
            sub["peserta_min"] = None
            sub["peserta_max"] = "20" if is_olimp else None
            sub["tempat"] = cb.get("tempat", "-") if cb else "-"
            sub["pic"] = cb.get("pic", "-") if cb else "-"
            sub["is_olimpiade_or_ai"] = is_olimp
            sub["is_literasi"] = is_lit
            sub["registered_count"] = reg_c
            sub["remaining_quota"] = rem
            sub["is_full"] = reg_c >= 20 if is_olimp else False
            sub["quota_text"] = (f"Sisa {rem} dari 20 Kuota" if rem > 0 else "Kuota Penuh (20/20)") if is_olimp else "Kuota Terbuka"
            sub["quota_badge"] = (f"Sisa {rem} Kuota" if rem > 0 else "Kuota Penuh") if is_olimp else "Kuota Terbuka"
            sub["format_type"] = cb.get("format_type", "olimpiade_akademik") if cb else "olimpiade_akademik"
            sub["is_team"] = cb.get("is_team", False) if cb else False
            sub["is_external_gform"] = cb.get("is_external_gform", False) if cb else sub.get("is_external_gform", False)
            sub["gform_url"] = cb.get("gform_url", "") if cb else sub.get("gform_url", "")
            sub["email_notice"] = "Gunakan akun email resmi sekolah untuk mendaftar" if sub["is_external_gform"] else ""
            sub["group_link"] = cb.get("group_link", "") if cb else sub.get("group_link", "")
            sub["group_label"] = cb.get("group_label", "Masuk Grup LINE") if cb else sub.get("group_label", "Masuk Grup LINE")
            sub["juknis_url"] = cb.get("juknis_url", "") if cb else sub.get("juknis_url", "")
            sub["ketentuan"] = cb.get("ketentuan") if cb else sub.get("ketentuan")
            sub["note"] = cb.get("note", "-") if cb else sub.get("note", "-")
            
            # Pengecekan Peminatan IPA/IPS untuk OSN
            sub["is_ipa_only"] = sub_id in OSN_IPA_ONLY_IDS
            sub["is_ips_allowed"] = sub_id in OSN_IPS_ALLOWED_IDS
            if jurusan == "ips" and sub["is_ipa_only"]:
                sub["is_disabled_jurusan"] = True
                sub["jurusan_notice"] = "Khusus Siswa IPA"
            else:
                sub["is_disabled_jurusan"] = False
                sub["jurusan_notice"] = None

    return render_template(
        "nordelia_sub.html",
        **_ctx(
            active_page="nordelia",
            category=cat_match,
            format_registrasi=FORMAT_REGISTRASI,
            cabang_lomba=build_decorated_cabang_list(),
            summary=storage.get_summary_stats(),
            group_link=resolve_group_link(),
            group_label=get_config("NORDELIA_GROUP_LABEL") or NORDELIA_INFO.get("group_label", "Masuk Grup WhatsApp"),
            selected_jurusan=jurusan,
            ketentuan_detail=KETENTUAN_DETAIL,
        ),
    )


SPREADSHEET_AUTH_PASSWORD = os.environ.get("SPREADSHEET_PASSWORD") or "DataOSIS123"


@bp.route("/nordelia/spreadsheet", methods=["GET", "POST"])
def nordelia_spreadsheet():
    # 1. Tangani verifikasi password saat submit form
    if request.method == "POST":
        input_password = request.form.get("password", "").strip()
        if input_password == SPREADSHEET_AUTH_PASSWORD:
            session["nordelia_spreadsheet_authed"] = True
            return redirect(url_for("pages.nordelia_spreadsheet"))
        return render_template(
            "nordelia_spreadsheet_login.html",
            **_ctx(
                active_page="nordelia",
                error="Password salah! Silakan masukkan password otorisasi OSIS yang valid.",
            )
        ), 401

    # 2. Cek apakah session sudah terautentikasi
    if not session.get("nordelia_spreadsheet_authed"):
        return render_template(
            "nordelia_spreadsheet_login.html",
            **_ctx(
                active_page="nordelia",
                error=None,
            )
        )

    # 3. Jika sudah lolos password, tampilkan spreadsheet viewer
    selected_cat = request.args.get("category", "semua")
    selected_cabang = request.args.get("cabang", "")
    force_sync = request.args.get("sync") == "1"
    if force_sync:
        storage.invalidate_cache()

    all_regs = storage.get_all_registrations(force_refresh=force_sync)
    if selected_cabang:
        regs = [r for r in all_regs if r.get("cabang_id") == selected_cabang or r.get("sheet_name") == selected_cabang or r.get("cabang_name") == selected_cabang]
    elif selected_cat and selected_cat != "semua":
        regs = storage.get_all_registrations(selected_cat)
    else:
        regs = all_regs

    summary = storage.get_summary_stats()
    spreadsheet_url = get_config(
        "NORDELIA_SPREADSHEET_URL",
        "https://docs.google.com/spreadsheets/d/" + get_config("NORDELIA_SPREADSHEET_ID", "1I5PF4GTdkiMUcfQ-YBskctP6X_WnSruRGACEUnAwG-c") + "/edit",
    )
    return render_template(
        "nordelia_spreadsheet.html",
        **_ctx(
            active_page="nordelia",
            nordelia=NORDELIA_INFO,
            categories=CATEGORIES,
            cabang_lomba=build_decorated_cabang_list(),
            selected_category=selected_cat,
            selected_cabang=selected_cabang,
            registrations=regs,
            summary=summary,
            sheet2_formats=SHEET2_FORMAT_SPEC,
            spreadsheet_url=spreadsheet_url,
            spreadsheet_id=get_config("NORDELIA_SPREADSHEET_ID"),
        ),
    )


@bp.get("/nordelia/spreadsheet/logout")
def nordelia_spreadsheet_logout():
    session.pop("nordelia_spreadsheet_authed", None)
    return redirect(url_for("pages.nordelia_spreadsheet"))


@bp.post("/api/nordelia/registrations/delete")
def api_nordelia_delete_registration():
    if not session.get("nordelia_spreadsheet_authed"):
        return jsonify({"success": False, "error": "Akses ditolak. Silakan login terlebih dahulu."}), 403

    data = request.get_json(silent=True) or request.form
    reg_id = data.get("id")
    if not reg_id:
        return jsonify({"success": False, "error": "ID pendaftar tidak disertakan."}), 400

    try:
        reg_id_int = int(reg_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Format ID tidak valid."}), 400

    ok = storage.delete_registration(reg_id_int)
    if ok:
        return jsonify({"success": True, "message": f"Data pendaftar #{reg_id_int} berhasil dihapus."})
    else:
        return jsonify({"success": False, "error": f"Data pendaftar #{reg_id_int} tidak ditemukan atau gagal dihapus."}), 404




# =========================================================================
# API REAL-TIME ENDPOINTS: FORM PENDAFTARAN & GOOGLE SPREADSHEET
# =========================================================================

@bp.post("/api/nordelia/register")
def api_nordelia_register():
    try:
        # Pendaftaran NORDELIA 2026 telah resmi ditutup
        return jsonify({
            "success": False,
            "error": "Maaf, pendaftaran NORDELIA 2026 telah resmi ditutup karena periode pendaftaran sudah selesai. Terima kasih atas antusiasme seluruh peserta!",
            "is_closed": True,
        }), 400

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

        # Validasi Peminatan Kelas IPA/IPS untuk Cabang OSN Sains Murni (Matematika boleh untuk IPS)
        OSN_IPA_ONLY_IDS = {
            "olimpiade-fisika",
            "olimpiade-kimia",
            "olimpiade-biologi",
            "olimpiade-astronomi",
            "olimpiade-informatika",
        }
        kelas_raw = str(data.get("kelas", "")).upper()
        jurusan_input = str(data.get("jurusan", "")).lower().strip()
        is_ips = "IPS" in kelas_raw or "SOSIAL" in kelas_raw or jurusan_input == "ips"
        is_ipa = "IPA" in kelas_raw or "MIPA" in kelas_raw or jurusan_input == "ipa"

        if cabang_id in OSN_IPA_ONLY_IDS and is_ips and not is_ipa:
            return jsonify({
                "success": False,
                "error": f"Cabang '{cabang_info['name']}' khusus untuk siswa kelas IPA. Siswa kelas IPS hanya diperbolehkan mendaftar cabang Matematika, Kebumian, Geografi, atau Ekonomi.",
            }), 400

        # ATURAN 2: Olimpiade 9 cabang + artificial intelligence maksimal 20 orang per cabang
        if cabang_id in OLIMPIADE_9_DAN_AI_IDS and not ("bahasa" in cabang_id.lower()):
            current_count = storage.get_cabang_count(cabang_id)
            if current_count >= 20:
                return jsonify({
                    "success": False,
                    "error": f"Pendaftaran cabang '{cabang_info['name']}' sudah PENUH! Kuota maksimal adalah 20 orang per cabang (terisi {current_count}/20).",
                    "quota_full": True,
                    "current_count": current_count,
                    "max_quota": 20,
                }), 400

        # Gabungkan nama peserta jika format tim / beregu (Tari Kreasi, Futsal, Basket, Voli)
        tim_label = str(data.get("nama_tim", "")).strip()
        anggota_label = str(data.get("nama_lengkap", "")).strip()
        p1 = str(data.get("nama_peserta_1", "")).strip()
        p2 = str(data.get("nama_peserta_2", "")).strip()
        if p1 and p2:
            combined = f"{tim_label}\n(1. {p1})\n(2. {p2})" if tim_label else f"(1. {p1})\n(2. {p2})"
            data["nama_lengkap"] = combined
        elif tim_label and anggota_label:
            if tim_label not in anggota_label:
                data["nama_lengkap"] = f"{tim_label}\n{anggota_label}"
        elif tim_label and not anggota_label:
            data["nama_lengkap"] = tim_label

        # Gabungkan nama anggota jika format debat (NSDC / LDBI)
        sp1 = str(data.get("speaker_1") or data.get("pembicara_1", "")).strip()
        sp2 = str(data.get("speaker_2") or data.get("pembicara_2", "")).strip()
        sp3 = str(data.get("speaker_3") or data.get("pembicara_3", "")).strip()
        if sp1 or sp2 or sp3:
            tim_label = str(data.get("nama_tim", "")).strip()
            speakers = [s for s in [sp1, sp2, sp3] if s]
            sp_str = ", ".join(speakers)
            combined = f"{tim_label} ({sp_str})" if tim_label else sp_str
            if not data.get("nama_lengkap"):
                data["nama_lengkap"] = combined

        if not data.get("whatsapp") and data.get("kontak"):
            data["whatsapp"] = data.get("kontak")

        # Validasi nama peserta / tim
        nama = str(data.get("nama_lengkap") or data.get("nama_tim") or data.get("nama") or "").strip()
        if not nama:
            return jsonify({
                "success": False,
                "error": "Nama lengkap peserta atau nama tim wajib diisi.",
            }), 400

        kelas = str(data.get("kelas") or "").strip()
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

        # Hitung sisa kuota jika cabang olimpiade
        quota_info = None
        if cabang_id in OLIMPIADE_9_DAN_AI_IDS:
            new_count = storage.get_cabang_count(cabang_id)
            quota_info = {
                "max": 20,
                "filled": new_count,
                "remaining": max(0, 20 - new_count),
            }

        return jsonify({
            "success": True,
            "message": f"Pendaftaran cabang '{cabang_info['name']}' berhasil dicatat! Terima kasih telah mendaftar.",
            "entry": saved_entry,
            "quota_info": quota_info,
            "already_registered": True,
            "cabang_name": cabang_info["name"],
            "participant_name": saved_entry.get("participant_name"),
            "group_link": resolve_group_link(cabang_info),
            "group_label": get_config("NORDELIA_GROUP_LABEL") or NORDELIA_INFO.get("group_label", "Masuk Grup WhatsApp"),
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Terjadi kendala saat memproses pendaftaran: {str(e)}",
        }), 500


@bp.get("/api/nordelia/cabang-quota")
def api_nordelia_cabang_quota():
    cabang_id = request.args.get("cabang_id", "")
    if not cabang_id:
        return jsonify({"error": "cabang_id is required"}), 400
    if request.args.get("refresh") == "1":
        storage.invalidate_cache()
    count = storage.get_cabang_count(cabang_id)
    cb_info = get_cabang_by_id(cabang_id)
    is_team = bool(cb_info.get("is_team", False)) if cb_info else False
    is_limited = (cabang_id in OLIMPIADE_9_DAN_AI_IDS) and not ("bahasa" in cabang_id.lower())
    rem = max(0, 20 - count) if is_limited else None
    return jsonify({
        "cabang_id": cabang_id,
        "count": count,
        "is_team": is_team,
        "is_limited": is_limited,
        "max_quota": 20 if is_limited else None,
        "remaining_quota": rem,
        "is_full": (count >= 20) if is_limited else False,
        "source": "google_sheet",
    })


@bp.get("/api/nordelia/sync")
def api_nordelia_sync():
    res = storage.fetch_from_google_sheet(force_refresh=True)
    if res:
        return jsonify({
            "success": True,
            "message": "Data berhasil disinkronkan langsung dari Google Sheet",
            "total": len(res.get("registrations", [])),
            "counts": res.get("counts", {}),
            "source": res.get("source", "google_sheet"),
        })
    return jsonify({
        "success": False,
        "message": "Gagal menghubungi Google Sheet, menggunakan cadangan lokal",
        "counts": storage.get_counts_by_cabang(),
        "source": "local_fallback",
    })


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
    if not session.get("nordelia_spreadsheet_authed"):
        return jsonify({"error": "Unauthorized. Password panitia OSIS diperlukan."}), 401
    cat = request.args.get("category")
    csv_content = export_registrations_csv(cat)
    filename = f"pendaftaran_nordelia_{cat or 'semua'}_{int(time.time())}.csv" if "time" in globals() else f"pendaftaran_nordelia_{cat or 'semua'}.csv"
    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@bp.get("/api/nordelia/format-pendaftaran.csv")
def api_nordelia_format_pendaftaran_csv():
    csv_path = os.path.join(os.path.dirname(__file__), "..", "nordelia_format_pendaftaran.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = "Format Pendaftaran Nordelia 2026\n"
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=format_pendaftaran_nordelia_2026.csv",
            "Cache-Control": "no-cache",
        },
    )


@bp.get("/before-us")
def before_us():
    return render_cached(
        "before_us.html",
        lambda: _ctx(
            active_page="before-us",
            cabinets=CABINETS,
            timeline=TIMELINE,
        ),
        ttl=10.0,
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
