import base64

from flask import Blueprint, current_app, g, jsonify, request

from ..auth import login_required
from ..extensions import db
from ..models import AIHO_API_NAME, UsageLog, count_usage_today
from ..providers.base import ProviderNotConfigured
from ..providers.factory import get_provider
from ..services import (
    ai_schema,
    bao_cao_tham_dinh_docx,
    baochay_reader,
    bot_chua_chay_reader,
    botcodinh_reader,
    ccnuoc_reader,
    cong_van_huong_dan_docx,
    credits,
    densucco_reader,
    dienpccc_reader,
    form_a_combiner,
    form_a_upload,
    gia_ke_hang_reader,
    hang_muc_store,
    khibotsolkhi_reader,
    ho_so_session,
    ket_luan_linter,
    kien_nghi_docx,
    mdc_filler,
    merged_reader,
    pham_vi_hien_huu_store,
    quy_mo_store,
    quymo_reader,
    scan_quymo_reader,
)
from ..services.ai_reader_common import AIReaderError

bp = Blueprint("aiho", __name__, url_prefix="/api/aiho")

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}

# Gioi han dung luong file, phan biet anh/PDF vi gioi han THAT cua Anthropic
# Messages API khac nhau ro ret giua 2 loai (da xac nhan truc tiep tu docs
# chinh thuc, khong doan): anh toi da 10MB SAU KHI encode base64 (rieng cho
# tung anh) -> file goc phai <= ~7.5MB, chon 7MB de co bien; PDF toi da 32MB
# cho CA request (base64 + JSON + system prompt) -> base64 hoa lam phinh dung
# luong x1,33 lan, 22MB file goc -> ~29,3MB sau base64, con du ~2,7MB cho
# prompt he thong - du an toan cho moi reader hien co.
#
# Ap dung THONG NHAT cho ca 3 luong dinh file (7 route doc tung hang muc rieng
# le "Buoc 1"/multi-attach VA route /read-merged) - gia tri giong het nhau vi
# cung 1 gioi han API goc, chi tach ten hang so theo tung nhom route de code
# de doc (khong gop chung 1 cap vi 2 nhom route nam o 2 doan code khac nhau).
SINGLE_MAX_BYTES_IMAGE = 7 * 1024 * 1024
SINGLE_MAX_BYTES_PDF = 22 * 1024 * 1024
MERGED_MAX_BYTES_IMAGE = 7 * 1024 * 1024
MERGED_MAX_BYTES_PDF = 22 * 1024 * 1024

# Gioi han so file dinh CHO 1 LAN GOI AI cua 1 hang muc (Batch 5A Pha 1 - dinh
# nhieu file vi noi dung 1 he thong doi khi nam tren file mang ten he thong
# khac) - KHAC HAN ho_so_session.MAX_FILES_PER_SESSION (gioi han CA PHIEN, van
# giu nguyen +1 file/+1(vai) form du dinh 1 hay ca 3 file, xem reserve_slot()
# ben duoi khong doi).
MAX_FILES_PER_CALL = 3

# file.mimetype la Content-Type client tu khai trong multipart request - gia mao
# duoc de dang (khong lien quan gi toi noi dung file that). Kiem tra them byte dau
# thuc te de xac nhan dung dinh dang, khong chi tin loi client noi.
_MAGIC_PREFIXES = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


def _sniff_magic_bytes(data: bytes, media_type: str) -> bool:
    if media_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    prefixes = _MAGIC_PREFIXES.get(media_type, ())
    return any(data.startswith(p) for p in prefixes)


def _answers_from_items(items):
    items = ket_luan_linter.fix_items(items)
    answers = []
    for item in items:
        try:
            row_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        # "khong_ap_dung" (muc tuy chon khong thiet ke) -> de trong cot Ket
        # luan, khong phai "KN" - khac voi chua_dat/chua_the_hien (that su
        # can kien nghi). Xem ai_schema.KetLuan.
        answers.append({
            "id": row_id,
            "noi_dung_thiet_ke": item.get("noi_dung_thiet_ke"),
            "ket_luan": mdc_filler.KET_LUAN_TO_DOCX.get(item.get("ket_luan"), "KN"),
        })
    return answers


def _build_mdc_file(loai: str, label: str, items: list) -> dict:
    """Điền 1 file MĐC từ danh sách items đã có noi_dung_thiet_ke/ket_luan, trả về entry cho mdc_docx_files."""
    try:
        docx_bytes = mdc_filler.fill_docx(loai, _answers_from_items(items))
        return {
            "loai": loai,
            "label": label,
            "filename": mdc_filler.filename_for(loai),
            "base64": base64.b64encode(docx_bytes).decode("ascii"),
        }
    except Exception:
        current_app.logger.exception("Khong dien duoc file MDC loai=%s", loai)
        return {"loai": loai, "label": label, "error": "Không tạo được file MĐC — vui lòng thử lại sau."}


def _handle_read_request(read_drawing_fn, build_mdc_files, forms_per_call, on_success=None):
    """Xử lý chung cho mọi hạng mục AI đọc bản vẽ: kiểm tra file, kiểm tra + tăng
    số file/form đã dùng trong phiên Bộ hồ sơ (session_id), sinh MĐC nếu cần.

    KHÔNG tự trừ/hoàn Bộ hồ sơ ở đây nữa (Batch 5A sub-bước 2) — việc đó diễn ra
    ở CẤP PHIÊN (/session/open trừ ngay 1 Bộ hồ sơ, /session/close giữ hoặc hoàn
    tuỳ có lần nào thành công hay không). Ở đây chỉ xác nhận phiên đang mở + còn
    trong giới hạn 5 file/7 form rồi mới gọi AI.

    build_mdc_files(result) -> list các entry {loai, label, filename, base64} hoặc {loai, label, error}
    — mỗi hạng mục tự quyết định cần điền mấy file MĐC (báo cháy/điện: 1 file; chữa cháy nước: 3 file).
    forms_per_call: số form MĐC mà 1 lần gọi hạng mục này chiếm trong giới hạn
    7 form/phiên (báo cháy/điện PCCC = 1, chữa cháy nước = 3 vì gộp B3+B5+B6).
    on_success(session, result): callback tuỳ chọn, chạy NGAY sau khi AI đọc
    thành công (trước khi build MĐC) — hiện chỉ dùng ở read-quymo để lưu lại
    dữ liệu quy mô trích xuất được (quy_mo_store.save_quy_mo()) cho các hạng
    mục khác trong cùng phiên tái dùng qua get_quy_mo().
    """
    user = g.current_user

    try:
        session_id = int(request.form.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ) — gọi /api/aiho/session/open trước khi đọc bản vẽ.",
        }), 400

    try:
        session = ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    files_raw = request.files.getlist("files")
    if not files_raw:
        return jsonify({"error": "Thiếu file bản vẽ (field 'files')."}), 400
    if len(files_raw) > MAX_FILES_PER_CALL:
        return jsonify({"error": f"Chỉ được đính tối đa {MAX_FILES_PER_CALL} file cho 1 hạng mục/lần gọi."}), 400

    files = []  # list[(bytes, media_type)]
    total_bytes_pdf = 0
    total_bytes_image = 0
    for f in files_raw:
        media_type = f.mimetype
        if media_type not in ALLOWED_TYPES:
            return jsonify({"error": f"Định dạng '{media_type}' không hỗ trợ — chỉ nhận PDF, PNG, JPEG, WEBP."}), 400
        data = f.read()
        if not _sniff_magic_bytes(data, media_type):
            return jsonify({"error": f"Nội dung file '{f.filename}' không khớp với định dạng khai báo — file có thể bị hỏng hoặc sai định dạng thật."}), 400
        if media_type == "application/pdf":
            total_bytes_pdf += len(data)
        else:
            total_bytes_image += len(data)
        files.append((data, media_type))

    # QUAN TRONG: gioi han goc SINGLE_MAX_BYTES_PDF/IMAGE (xem comment dau file,
    # dong ~38-53) duoc tinh CHO 1 REQUEST GUI ANTHROPIC, khong phai cho 1 file —
    # voi nhieu file trong CUNG 1 request phai kiem tra TONG dung luong, khong
    # phai tung file rieng le, neu khong request co the vuot han muc 32MB thuc
    # te cua API dan toi loi 502 lang phi 1 luot AI (van bi tinh vao count_usage_today()).
    if total_bytes_pdf > SINGLE_MAX_BYTES_PDF:
        return jsonify({"error": f"Tổng dung lượng các file PDF vượt quá {SINGLE_MAX_BYTES_PDF // (1024*1024)}MB (giới hạn cho 1 lần gọi, tính TỔNG nếu đính nhiều file)."}), 400
    if total_bytes_image > SINGLE_MAX_BYTES_IMAGE:
        return jsonify({"error": f"Tổng dung lượng các file ảnh vượt quá {SINGLE_MAX_BYTES_IMAGE // (1024*1024)}MB (giới hạn cho 1 lần gọi, tính TỔNG nếu đính nhiều file)."}), 400

    # Han muc goi AI/ngay (khac gioi han file/form cua 1 phien Bo ho so o tren) -
    # dung lai dung logic cua /api/ai/comment (routes/ai.py): so count_usage_today()
    # voi effective_quota() cua user, chan som TRUOC KHI goi AI neu da dat/vuot.
    limit = user.effective_quota()
    used_today = count_usage_today(user.id, AIHO_API_NAME)
    if used_today >= limit:
        return jsonify({
            "error": f"Đã đạt hạn mức {limit} lượt gọi AI/ngày cho tính năng này — thử lại vào ngày mai.",
            "quota": {"limit": limit, "used_today": used_today, "remaining_today": 0},
        }), 429

    wants_mdc = "mdc" in {o.strip() for o in (request.form.get("outputs") or "").split(",")}

    provider_name = request.form.get("provider")
    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        ho_so_session.reserve_slot(session, 1, forms_per_call)
    except ho_so_session.SessionCapExceeded as exc:
        return jsonify({"error": str(exc)}), 400

    # Du lieu "Quy mo" cua CUNG phien, neu nguoi dung CO dinh (hoan toan tuy
    # chon - dinh kem hang muc la tu nguyen, xem quy_mo_store.get_quy_mo()).
    # None khi chua dinh -> read_drawing_fn tu doc/suy luan tu ban ve rieng
    # nhu binh thuong, KHONG bi chan/bat buoc boi hang muc nay.
    quy_mo = quy_mo_store.get_quy_mo(session.id)

    try:
        result = read_drawing_fn(files, provider, quy_mo=quy_mo)
    except ProviderNotConfigured as exc:
        # Chua cau hinh API key - chua thuc su goi AI nao, khong tinh la 1
        # luot dung (giong het nhanh nay o /api/ai/comment, routes/ai.py).
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except AIReaderError as exc:
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        return jsonify({"error": str(exc)}), 502
    except Exception:  # lỗi mạng/SDK bên thứ ba — không lộ chi tiết ra client
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        current_app.logger.exception("Loi goi provider '%s'", provider.name)
        return jsonify({"error": f"Lỗi gọi máy chủ AI ('{provider.name}') — vui lòng thử lại sau."}), 502

    db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="success"))
    db.session.commit()

    ho_so_session.mark_success(session)

    if on_success:
        on_success(session, result)

    result["provider"] = provider.name
    result["ho_so"] = {
        "session_id": session.id,
        "files_used": session.files_used,
        "forms_used": session.forms_used,
        "max_files": ho_so_session.MAX_FILES_PER_SESSION,
        "max_forms": ho_so_session.MAX_FORMS_PER_SESSION,
    }

    if wants_mdc:
        result["mdc_docx_files"] = build_mdc_files(result)

    return jsonify(result)


@bp.post("/session/open")
@login_required
def open_ho_so_session():
    """Mo 1 phien Bo ho so moi (tru ngay 1 Bo ho so) - goi 1 lan truoc khi bat
    dau doc bat ky hang muc nao. Idempotent: neu dang co san 1 phien 'open'
    chua het han (double-click/2 tab), tra ve chinh phien do, khong tru them."""
    try:
        session = ho_so_session.open_session(g.current_user.id)
    except ho_so_session.InsufficientCredits as exc:
        return jsonify({
            "error": str(exc),
            "bo_ho_so_con_lai": credits.credit_balance(g.current_user.id),
        }), 429
    return jsonify({
        "session_id": session.id,
        "bo_ho_so_con_lai": credits.credit_balance(g.current_user.id),
        "max_files": ho_so_session.MAX_FILES_PER_SESSION,
        "max_forms": ho_so_session.MAX_FORMS_PER_SESSION,
    })


@bp.post("/session/close")
@login_required
def close_ho_so_session():
    """Dong 1 phien Bo ho so - giu nguyen tru neu co it nhat 1 lan doc thanh
    cong, hoan lai neu khong co lan nao. Idempotent: goi voi phien da dong
    truoc do khong loi (client co the goi lai do retry mang)."""
    payload = request.get_json(silent=True) or {}
    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id."}), 400

    try:
        session = ho_so_session.close_session(g.current_user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({
        "session_id": session.id,
        "status": session.status,
        "bo_ho_so_con_lai": credits.credit_balance(g.current_user.id),
    })


def _build_baochay_mdc(result):
    loai = result.get("loai_he_thong") if result.get("loai_he_thong") in ("thuong", "dia_chi") else "thuong"
    return [_build_mdc_file(loai, "Báo cháy tự động", result.get("items", []))]


def _build_dienpccc_mdc(result):
    return [_build_mdc_file("dien_pccc", "Điện PCCC", result.get("items", []))]


def _build_forms_mdc(result):
    """Dung chung cho ccnuoc VA densucco — ca 2 cung tra ve result["forms"]
    {loai: {label, mdc_label, items}} tu read_drawing() cua reader tuong ung
    (hoac merged_reader.finalize_category_result() da dung lai dung shape nay)."""
    files = []
    for loai, form_data in (result.get("forms") or {}).items():
        label = form_data.get("mdc_label", "") + " — " + form_data.get("label", loai)
        if "error" in form_data:
            files.append({"loai": loai, "label": label, "error": form_data["error"]})
        else:
            files.append(_build_mdc_file(loai, label, form_data.get("items", [])))
    return files


def _build_khibot_mdc(result):
    he_thong = result.get("he_thong") if result.get("he_thong") in khibotsolkhi_reader.HE_THONG_LIST else "khi_hoa_long"
    label = khibotsolkhi_reader.HE_THONG_META[he_thong]["ten"].capitalize()
    return [_build_mdc_file(he_thong, label, result.get("items", []))]


def _build_botcodinh_mdc(result):
    return [_build_mdc_file("bot_co_dinh", "Chữa cháy bằng bọt cố định", result.get("items", []))]


def _build_gia_ke_hang_mdc(result):
    return [_build_mdc_file("chua_chay_gia_ke_hang", "Chữa cháy tự động giá kệ hàng", result.get("items", []))]


def _build_bot_chua_chay_mdc(result):
    return [_build_mdc_file("bot_chua_chay", "Chữa cháy bằng bột", result.get("items", []))]


def _build_quymo_mdc(result):
    items = quy_mo_store.build_form_a_items(
        result.get("quy_mo") or {},
        a2_bao_chay=result.get("bang_a2_bao_chay"),
        a4_bao_chay=result.get("bang_a4_bao_chay"),
        a2_sprinkler=result.get("bang_a2_sprinkler"),
        a4_sprinkler=result.get("bang_a4_sprinkler"),
    )
    # Ghi lai vao result["items"] (cung hinh dang {id, noi_dung_thiet_ke,
    # ket_luan} nhu baochay/dienpccc) - de frontend dung CHUNG itemsForMdcFile()
    # tinh dung so "da dien N muc doi chieu" cho the Quy mo, khong can sua rieng.
    result["items"] = items
    return [_build_mdc_file("quy_mo", "Quy mô công trình", items)]


# loai (khoa REAL_CATEGORIES/merged_reader) -> ham build MDC tuong ung — dung
# chung boi ca 5 route rieng le (duoi day) VA route /read-merged/confirm.
_BUILD_MDC_BY_CATEGORY = {
    "baochay": _build_baochay_mdc,
    "dienpccc": _build_dienpccc_mdc,
    "ccnuoc": _build_forms_mdc,
    "densucco": _build_forms_mdc,
    "quy_mo": _build_quymo_mdc,
    "khibot": _build_khibot_mdc,
    "botcodinh": _build_botcodinh_mdc,
}


@bp.post("/read-baochay")
@login_required
def read_baochay():
    return _handle_read_request(baochay_reader.read_drawing, _build_baochay_mdc, forms_per_call=1)


@bp.post("/read-dienpccc")
@login_required
def read_dienpccc():
    return _handle_read_request(dienpccc_reader.read_drawing, _build_dienpccc_mdc, forms_per_call=1)


@bp.post("/read-ccnuoc")
@login_required
def read_ccnuoc():
    return _handle_read_request(ccnuoc_reader.read_drawing, _build_forms_mdc, forms_per_call=3)


@bp.post("/read-densucco")
@login_required
def read_densucco():
    return _handle_read_request(densucco_reader.read_drawing, _build_forms_mdc, forms_per_call=2)


@bp.post("/scan-quymo")
@login_required
def scan_quymo():
    """"Lượt 0" (Quy mô Giai đoạn 1, Phần A.1) — quét NHẸ 1 file báo cháy/ccnuoc
    đã đính để tìm thông tin quy mô công trình tình cờ có trên đó, KHÔNG chạy
    đủ checklist tiêu chí kỹ thuật như /read-baochay, /read-ccnuoc.

    KHÔNG dùng _handle_read_request() dùng chung (route đó LUÔN gọi
    ho_so_session.reserve_slot() — cộng vào files_used/forms_used của phiên,
    đúng cho 7 hạng mục AI thật kia nhưng SAI cho route này: Lượt 0 chỉ là
    bước phụ trợ bên trong phiên đã mở, KHÔNG được tính là 1 hạng mục/form
    riêng) — viết route riêng, tái dùng ĐÚNG logic validate file (size/type/
    magic bytes) và hạn mức "lượt gọi AI/ngày" (count_usage_today/
    effective_quota) như _handle_read_request(), chỉ bỏ đúng đoạn
    reserve_slot()."""
    user = g.current_user

    try:
        session_id = int(request.form.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ) — gọi /api/aiho/session/open trước khi đọc bản vẽ.",
        }), 400

    try:
        session = ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file bản vẽ (field 'file')."}), 400

    media_type = file.mimetype
    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": f"Định dạng '{media_type}' không hỗ trợ — chỉ nhận PDF, PNG, JPEG, WEBP."}), 400

    data = file.read()
    single_limit_bytes = SINGLE_MAX_BYTES_PDF if media_type == "application/pdf" else SINGLE_MAX_BYTES_IMAGE
    if len(data) > single_limit_bytes:
        single_limit_mb = single_limit_bytes // (1024 * 1024)
        single_loai_file = "PDF" if media_type == "application/pdf" else "ảnh"
        return jsonify({"error": f"File {single_loai_file} vượt quá {single_limit_mb}MB."}), 400

    if not _sniff_magic_bytes(data, media_type):
        return jsonify({"error": "Nội dung file không khớp với định dạng khai báo — file có thể bị hỏng hoặc sai định dạng thật."}), 400

    limit = user.effective_quota()
    used_today = count_usage_today(user.id, AIHO_API_NAME)
    if used_today >= limit:
        return jsonify({
            "error": f"Đã đạt hạn mức {limit} lượt gọi AI/ngày cho tính năng này — thử lại vào ngày mai.",
            "quota": {"limit": limit, "used_today": used_today, "remaining_today": 0},
        }), 429

    provider_name = request.form.get("provider")
    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        result = scan_quymo_reader.read_drawing(data, media_type, provider)
    except ProviderNotConfigured as exc:
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except AIReaderError as exc:
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        return jsonify({"error": str(exc)}), 502
    except Exception:
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        current_app.logger.exception("Loi goi provider '%s' (scan-quymo)", provider.name)
        return jsonify({"error": f"Lỗi gọi máy chủ AI ('{provider.name}') — vui lòng thử lại sau."}), 502

    db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="success"))
    db.session.commit()

    result["provider"] = provider.name
    return jsonify(result)


@bp.post("/scan-quymo/finish")
@login_required
def scan_quymo_finish():
    """Kết thúc "Lượt 0" (Phần A.3/C) — nhận lại các kết quả thô từ 1-2 lần
    gọi /scan-quymo (frontend tự forward, KHÔNG gọi AI ở route này), gộp +
    lưu (source='ai_auto_detected') nếu có tìm thấy gì, hoặc chỉ đánh dấu
    quy_mo_scan_attempted_at nếu không (xem quy_mo_store.finish_quy_mo_scan)."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id."}), 400

    try:
        session = ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return jsonify({"error": "Thiếu 'results' (danh sách kết quả /scan-quymo đã gọi)."}), 400

    try:
        outcome = quy_mo_store.finish_quy_mo_scan(session, results)
    except quy_mo_store.QuyMoInputError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "saved": outcome["saved"],
        "conflicts": outcome["conflicts"],
        "found_count": outcome["found_count"],
    })


@bp.post("/quymo-reverse-check")
@login_required
def quymo_reverse_check():
    """Phần E.2 — đối chiếu ngược "thiếu hồ sơ hệ thống X". Chạy SAU khi Lượt 1
    hoàn tất, frontend gửi lên danh sách slot đã có kết quả thành công
    (slots_with_data — backend không tự biết trạng thái này, nó sống ở
    realData phía frontend). Nếu phiên KHÔNG có dữ liệu quy mô (get_quy_mo()
    trả None — kể cả trường hợp Lượt 0 đã thử nhưng không tìm thấy gì, xem
    Phần C) thì không có căn cứ gì để đối chiếu — trả về rỗng, KHÔNG lỗi."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id."}), 400

    try:
        ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    fields = quy_mo_store.get_quy_mo(session_id)
    if not fields:
        return jsonify({"has_quy_mo": False, "warnings": []})

    slots_with_data = payload.get("slots_with_data") or []
    if not isinstance(slots_with_data, list):
        return jsonify({"error": "'slots_with_data' phải là danh sách."}), 400

    warnings = quy_mo_store.compute_reverse_check_warnings(fields, slots_with_data)
    return jsonify({"has_quy_mo": True, "warnings": warnings})


@bp.post("/read-quymo")
@login_required
def read_quymo():
    def on_success(session, result):
        quy_mo = result.get("quy_mo")
        if quy_mo:
            quy_mo_store.save_quy_mo(session.id, quy_mo, source="ai")

    return _handle_read_request(quymo_reader.read_drawing, _build_quymo_mdc, forms_per_call=1, on_success=on_success)


@bp.post("/read-khibot")
@login_required
def read_khibot():
    return _handle_read_request(khibotsolkhi_reader.read_drawing, _build_khibot_mdc, forms_per_call=1)


@bp.post("/read-botcodinh")
@login_required
def read_botcodinh():
    return _handle_read_request(botcodinh_reader.read_drawing, _build_botcodinh_mdc, forms_per_call=1)


@bp.post("/read-b15")
@login_required
def read_b15():
    return _handle_read_request(gia_ke_hang_reader.read_drawing, _build_gia_ke_hang_mdc, forms_per_call=1)


@bp.post("/read-b16")
@login_required
def read_b16():
    return _handle_read_request(bot_chua_chay_reader.read_drawing, _build_bot_chua_chay_mdc, forms_per_call=1)


@bp.post("/read-merged")
@login_required
def read_merged():
    """"Đính 1 bản vẽ — AI tự nhận diện nhiều hạng mục" (Batch 5A sub-bước 5),
    BƯỚC 1/2 (xem/preview): 1 lượt gọi AI DUY NHẤT vừa xác định bản vẽ thuộc
    (các) hạng mục nào trong 5 hạng mục AI thật hiện có, vừa điền luôn kết quả
    đầy đủ. CHỈ giữ chỗ 1 file (files_used +1) — CHƯA trừ form nào (forms_used
    giữ nguyên) vì số form cần thiết chỉ biết được SAU khi có kết quả AI. Người
    dùng xem kỹ kết quả rồi mới gọi /read-merged/confirm để thực sự giữ chỗ
    form + xuất file MĐC — xem module-docstring merged_reader.py."""
    user = g.current_user

    try:
        session_id = int(request.form.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ) — gọi /api/aiho/session/open trước khi đọc bản vẽ."}), 400

    try:
        session = ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file bản vẽ (field 'file')."}), 400

    media_type = file.mimetype
    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": f"Định dạng '{media_type}' không hỗ trợ — chỉ nhận PDF, PNG, JPEG, WEBP."}), 400

    data = file.read()
    limit_bytes = MERGED_MAX_BYTES_PDF if media_type == "application/pdf" else MERGED_MAX_BYTES_IMAGE
    if len(data) > limit_bytes:
        limit_mb = limit_bytes // (1024 * 1024)
        loai_file = "PDF" if media_type == "application/pdf" else "ảnh"
        return jsonify({"error": f"File {loai_file} vượt quá {limit_mb}MB (giới hạn riêng cho tính năng này)."}), 400

    if not _sniff_magic_bytes(data, media_type):
        return jsonify({"error": "Nội dung file không khớp với định dạng khai báo — file có thể bị hỏng hoặc sai định dạng thật."}), 400

    limit = user.effective_quota()
    used_today = count_usage_today(user.id, AIHO_API_NAME)
    if used_today >= limit:
        return jsonify({
            "error": f"Đã đạt hạn mức {limit} lượt gọi AI/ngày cho tính năng này — thử lại vào ngày mai.",
            "quota": {"limit": limit, "used_today": used_today, "remaining_today": 0},
        }), 429

    provider_name = request.form.get("provider")
    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Giai doan 1: chi giu cho 1 FILE (chac chan ngay tu dau) - KHONG giu cho
    # form nao ca (forms_delta=0), vi so form can thiet phu thuoc AI phat hien
    # duoc bao nhieu hang muc, chi biet SAU khi co ket qua.
    try:
        ho_so_session.reserve_slot(session, 1, 0)
    except ho_so_session.SessionCapExceeded as exc:
        return jsonify({"error": str(exc)}), 400

    quy_mo = quy_mo_store.get_quy_mo(session.id)

    try:
        result = merged_reader.read_and_detect(data, media_type, provider, quy_mo=quy_mo)
    except ProviderNotConfigured as exc:
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except AIReaderError as exc:
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        return jsonify({"error": str(exc)}), 502
    except Exception:
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        current_app.logger.exception("Loi goi provider '%s' (read-merged)", provider.name)
        return jsonify({"error": f"Lỗi gọi máy chủ AI ('{provider.name}') — vui lòng thử lại sau."}), 502

    db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="success"))
    db.session.commit()
    ho_so_session.mark_success(session)

    detected = result.get("detected_categories", [])
    forms_needed = sum(merged_reader.CATEGORY_FORMS_PER_CALL[c] for c in detected)

    return jsonify({
        "provider": provider.name,
        "detection": result,
        "category_labels": {c: merged_reader.CATEGORY_LABELS[c] for c in detected},
        "forms_needed": forms_needed,
        "ho_so": {
            "session_id": session.id,
            "files_used": session.files_used,
            "forms_used": session.forms_used,
            "max_files": ho_so_session.MAX_FILES_PER_SESSION,
            "max_forms": ho_so_session.MAX_FORMS_PER_SESSION,
        },
    })


@bp.post("/read-merged/confirm")
@login_required
def read_merged_confirm():
    """BƯỚC 2/2 (xác nhận) của /read-merged — KHÔNG gọi AI lần nào nữa (dữ liệu
    "detection" được client gửi lại NGUYÊN VẸN từ response của /read-merged).
    Chỉ tới đây mới thực sự giữ chỗ form (forms_used) — đúng đủ số form của các
    hạng mục người dùng CHỌN xác nhận (selected_categories — có thể là tập con
    của detected_categories nếu người dùng bỏ bớt hạng mục sau khi xem kết
    quả), rồi mới xuất file MĐC. Re-validate lại "detection" bằng đúng
    ai_schema.validate_merged_reader_result() (không tin dữ liệu client gửi
    lên mà không kiểm tra lại, dù đây vốn là echo lại đúng response server đã
    trả — phòng trường hợp bị sửa/hỏng khi gửi lại)."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id."}), 400

    try:
        session = ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    detection = payload.get("detection")
    selected = payload.get("selected_categories")
    if not isinstance(selected, list) or not selected:
        return jsonify({"error": "Thiếu 'selected_categories' (danh sách hạng mục cần xác nhận)."}), 400

    quy_mo_known = bool(quy_mo_store.get_quy_mo(session.id))
    try:
        validated = ai_schema.validate_merged_reader_result(detection, quy_mo_known=quy_mo_known).model_dump()
    except ai_schema.SchemaValidationError as exc:
        return jsonify({"error": f"Dữ liệu kết quả AI gửi lên không hợp lệ — vui lòng phân tích lại: {exc}"}), 400

    detected = set(validated.get("detected_categories", []))
    selected = list(dict.fromkeys(selected))  # bo trung, giu thu tu
    not_detected = [c for c in selected if c not in detected]
    if not_detected:
        return jsonify({"error": f"Hạng mục sau không có trong kết quả AI đã phát hiện, không thể xác nhận: {not_detected}."}), 400

    forms_needed = sum(merged_reader.CATEGORY_FORMS_PER_CALL[c] for c in selected)
    try:
        ho_so_session.reserve_slot(session, 0, forms_needed)
    except ho_so_session.SessionCapExceeded as exc:
        return jsonify({"error": str(exc)}), 400

    results = {}
    for cat in selected:
        finalized = merged_reader.finalize_category_result(cat, validated)
        finalized["mdc_docx_files"] = _BUILD_MDC_BY_CATEGORY[cat](finalized)
        if cat == "quy_mo":
            quy_mo_store.save_quy_mo(session.id, finalized.get("quy_mo") or {}, source="ai_merged")
        results[cat] = finalized

    return jsonify({
        "results": results,
        "category_labels": {c: merged_reader.CATEGORY_LABELS[c] for c in selected},
        "ho_so": {
            "session_id": session.id,
            "files_used": session.files_used,
            "forms_used": session.forms_used,
            "max_files": ho_so_session.MAX_FILES_PER_SESSION,
            "max_forms": ho_so_session.MAX_FORMS_PER_SESSION,
        },
    })


@bp.post("/quymo-manual")
@login_required
def quymo_manual():
    """Nhập tay dữ liệu Quy mô — KHÔNG gọi AI, KHÔNG trừ quota/Bộ hồ sơ (khác
    hoàn toàn _handle_read_request/reserve_slot). Vẫn xuất được Form A (.docx)
    giống route AI (/read-quymo) — dùng CHUNG quy_mo_store.build_form_a_items()
    để đảm bảo đồng nhất nội dung mục 1 và các dòng "Đối tượng trang bị" giữa
    2 cách nhập (AI đọc bản vẽ HOẶC nhập tay)."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    try:
        session = ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        clean_fields = quy_mo_store.validate_manual_fields(payload.get("quy_mo"))
    except quy_mo_store.QuyMoInputError as exc:
        return jsonify({"error": str(exc)}), 400

    quy_mo_store.save_quy_mo(session.id, clean_fields, source="manual")
    items = quy_mo_store.build_form_a_items(clean_fields)
    mdc_file = _build_mdc_file("quy_mo", "Quy mô công trình", items)

    return jsonify({
        "quy_mo": clean_fields,
        "mdc_docx_files": [mdc_file],
    })


# ---------------------------------------------------------------------------
# Dự án nhiều công trình (Đợt 2a) — khai báo + xem trước quy mô TỪNG công
# trình/khối trong 1 dự án (LƯU Ý: "hạng mục" ở nhóm route này nghĩa là 1
# CÔNG TRÌNH, khác "hạng mục" = 1 loại hệ thống PCCC ở các route phía trên —
# xem models.HoSoSessionHangMuc). Giống hệt /quymo-manual: KHÔNG gọi AI,
# KHÔNG trừ quota "lượt gọi AI/ngày", KHÔNG trừ Bộ hồ sơ — chỉ cần phiên
# đang mở đúng của user để lưu đúng phiên.
# ---------------------------------------------------------------------------
def _get_open_session_or_error(user_id, session_id):
    """Trả về (session, None) hoặc (None, (response, status)) — dùng chung
    cho cả 4 route hang-muc để tránh lặp lại try/except."""
    try:
        return ho_so_session.get_open_session_for_user(user_id, session_id), None
    except ho_so_session.SessionNotFound as exc:
        return None, (jsonify({"error": str(exc)}), 404)
    except ho_so_session.SessionNotOpen as exc:
        return None, (jsonify({"error": str(exc)}), 400)


def _get_own_session_any_status_or_error(user_id, session_id):
    """Giống _get_open_session_or_error() nhưng KHÔNG bắt buộc phiên đang
    'open' — dùng cho /export-form-a: xuất Form A là thao tác ĐỌC LẠI dữ
    liệu đã lưu (quy_mo/pham_vi/ha_tang_hien_huu), người dùng có thể bấm nút
    xuất SAU KHI phiên đã tự đóng (finishUp() đóng phiên trước khi hiện nút
    xuất, xem ai-doc-ho-so.js maybeShowFormAButton()) — chỉ cần xác nhận
    đúng chủ sở hữu, không cần trạng thái 'open'."""
    from ..models import HoSoSession
    session = db.session.get(HoSoSession, session_id)
    if session is None or session.user_id != user_id:
        return None, (jsonify({"error": "Không tìm thấy phiên Bộ hồ sơ."}), 404)
    return session, None


@bp.post("/hang-muc")
@login_required
def create_hang_muc():
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    try:
        result = hang_muc_store.save_hang_muc(session_id, payload.get("ten_hang_muc"), payload.get("quy_mo"))
    except hang_muc_store.HangMucInputError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result)


@bp.get("/hang-muc")
@login_required
def get_hang_muc_list():
    user = g.current_user
    try:
        session_id = int(request.args.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    return jsonify({"items": hang_muc_store.list_hang_muc(session_id)})


@bp.put("/hang-muc/<int:hang_muc_id>")
@login_required
def update_hang_muc_route(hang_muc_id):
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    try:
        result = hang_muc_store.update_hang_muc(hang_muc_id, session_id, payload.get("ten_hang_muc"), payload.get("quy_mo"))
    except hang_muc_store.HangMucNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except hang_muc_store.HangMucInputError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result)


@bp.delete("/hang-muc/<int:hang_muc_id>")
@login_required
def delete_hang_muc_route(hang_muc_id):
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    try:
        hang_muc_store.delete_hang_muc(hang_muc_id, session_id)
    except hang_muc_store.HangMucNotFound as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"deleted": True})


# ---------------------------------------------------------------------------
# Form A gốc (A14/A15) — Phần 0: "phạm vi đề nghị thẩm định lần này" + "hạ
# tầng hiện hữu". Giống hệt nhóm route /hang-muc: KHÔNG gọi AI, KHÔNG trừ
# quota/Bộ hồ sơ — dùng chung _get_open_session_or_error().
# ---------------------------------------------------------------------------
@bp.post("/pham-vi-de-nghi")
@login_required
def save_pham_vi_de_nghi_route():
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    try:
        saved = pham_vi_hien_huu_store.save_pham_vi_de_nghi(session_id, payload.get("pham_vi_de_nghi"))
    except pham_vi_hien_huu_store.PhamViHienHuuInputError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"pham_vi_de_nghi": saved})


@bp.get("/pham-vi-de-nghi")
@login_required
def get_pham_vi_de_nghi_route():
    user = g.current_user
    try:
        session_id = int(request.args.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    return jsonify({"pham_vi_de_nghi": pham_vi_hien_huu_store.get_pham_vi_de_nghi(session_id)})


@bp.post("/ha-tang-hien-huu")
@login_required
def create_ha_tang_hien_huu_route():
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    try:
        result = pham_vi_hien_huu_store.save_ha_tang_hien_huu(
            session_id,
            payload.get("ten_he_thong"),
            payload.get("gcn_so"),
            payload.get("gcn_ngay"),
            gcn_bo_sung_so=payload.get("gcn_bo_sung_so"),
            gcn_bo_sung_ngay=payload.get("gcn_bo_sung_ngay"),
            nghiem_thu_so=payload.get("nghiem_thu_so"),
            nghiem_thu_ngay=payload.get("nghiem_thu_ngay"),
            ghi_chu_ban_ve=payload.get("ghi_chu_ban_ve"),
        )
    except pham_vi_hien_huu_store.PhamViHienHuuInputError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result)


@bp.get("/ha-tang-hien-huu")
@login_required
def list_ha_tang_hien_huu_route():
    user = g.current_user
    try:
        session_id = int(request.args.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    return jsonify({"items": pham_vi_hien_huu_store.list_ha_tang_hien_huu(session_id)})


@bp.delete("/ha-tang-hien-huu/<int:ha_tang_id>")
@login_required
def delete_ha_tang_hien_huu_route(ha_tang_id):
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_open_session_or_error(user.id, session_id)
    if err:
        return err

    try:
        pham_vi_hien_huu_store.delete_ha_tang_hien_huu(ha_tang_id, session_id)
    except pham_vi_hien_huu_store.HaTangHienHuuNotFound as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"deleted": True})


@bp.post("/export-kien-nghi")
@login_required
def export_kien_nghi():
    """Gộp kiến nghị của các hạng mục ĐÃ đọc AI từ trước (dữ liệu gửi sẵn từ
    frontend) thành 1 file .docx — KHÔNG gọi AI nên KHÔNG trừ quota."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là một object JSON."}), 400

    hang_muc_list = payload.get("hang_muc")
    if not isinstance(hang_muc_list, list) or not hang_muc_list:
        return jsonify({"error": "Thiếu dữ liệu 'hang_muc' (danh sách hạng mục kiến nghị)."}), 400

    for idx, hang_muc in enumerate(hang_muc_list):
        if not isinstance(hang_muc, dict):
            return jsonify({"error": f"Hạng mục thứ {idx + 1} không hợp lệ."}), 400
        if not isinstance(hang_muc.get("ten_he_thong"), str) or not hang_muc["ten_he_thong"].strip():
            return jsonify({"error": f"Hạng mục thứ {idx + 1} thiếu 'ten_he_thong'."}), 400
        if not isinstance(hang_muc.get("kien_nghi"), dict):
            return jsonify({"error": f"Hạng mục thứ {idx + 1} thiếu hoặc sai định dạng 'kien_nghi'."}), 400

    try:
        docx_bytes = kien_nghi_docx.build_kien_nghi_docx(hang_muc_list)
    except Exception:
        current_app.logger.exception("Khong tao duoc file kien nghi tong hop")
        return jsonify({"error": "Không tạo được file kiến nghị — vui lòng thử lại sau."}), 500

    return jsonify({
        "filename": kien_nghi_docx.FILENAME,
        "base64": base64.b64encode(docx_bytes).decode("ascii"),
    })


@bp.post("/export-form-a")
@login_required
def export_form_a():
    """Form A gốc (A14/A15) — combiner GỘP dữ liệu đã có trong phiên (quy mô
    rule-based + kết quả B-form đã đọc) thành 1 file .docx đúng khuôn mẫu gốc.
    KHÔNG gọi AI, KHÔNG trừ quota — giống hệt /export-kien-nghi ở trên.

    quy_mo/pham_vi_de_nghi/ha_tang_hien_huu TỰ LẤY từ DB theo session_id
    (khác b_form_results — chỉ tồn tại phía frontend, phải gửi kèm)."""
    user = g.current_user
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là một object JSON."}), 400

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_own_session_any_status_or_error(user.id, session_id)
    if err:
        return err

    loai_hinh = payload.get("loai_hinh")
    if loai_hinh not in ("A14", "A15"):
        return jsonify({"error": "Thiếu hoặc sai 'loai_hinh' — chỉ hỗ trợ 'A14' hoặc 'A15'."}), 400

    b_form_results = payload.get("b_form_results")
    if b_form_results is not None and not isinstance(b_form_results, dict):
        return jsonify({"error": "'b_form_results' phải là một object JSON."}), 400

    session_data = {
        "session_id": session_id,
        "quy_mo": quy_mo_store.get_quy_mo(session_id) or {},
        "b_form_results": b_form_results or {},
    }

    try:
        docx_bytes = form_a_combiner.build_form_a_goc(loai_hinh, session_data)
    except form_a_combiner.FormACombinerError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Khong tao duoc file Form A goc loai_hinh=%s", loai_hinh)
        return jsonify({"error": "Không tạo được file Form A — vui lòng thử lại sau."}), 500

    ten_du_an = (payload.get("ten_du_an") or "").strip()
    ten_hang_muc = (payload.get("ten_hang_muc") or "").strip()
    filename = mdc_filler.filename_for(loai_hinh)
    if ten_du_an or ten_hang_muc:
        stem = mdc_filler.TEMPLATE_FILENAMES[loai_hinh].rsplit(".docx", 1)[0]
        suffix = "_".join(part.replace(" ", "_") for part in (ten_du_an, ten_hang_muc) if part)
        filename = f"{stem}_{suffix}.docx"

    return jsonify({
        "filename": filename,
        "base64": base64.b64encode(docx_bytes).decode("ascii"),
    })


@bp.post("/export-cong-van-huong-dan")
@login_required
def export_cong_van_huong_dan():
    """Cong van huong dan (.docx that, dung file mau) - KHONG goi AI, KHONG
    tru quota, giong het /export-kien-nghi ve nguyen tac (frontend gui san
    hang_muc, backend chi render)."""
    user = g.current_user
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là một object JSON."}), 400

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_own_session_any_status_or_error(user.id, session_id)
    if err:
        return err

    hang_muc_list = payload.get("hang_muc")
    if not isinstance(hang_muc_list, list):
        return jsonify({"error": "Thiếu dữ liệu 'hang_muc'."}), 400

    session_data = {"quy_mo": quy_mo_store.get_quy_mo(session_id) or {}}

    try:
        docx_bytes = cong_van_huong_dan_docx.build_cong_van_huong_dan_docx(session_data, hang_muc_list)
    except cong_van_huong_dan_docx.CongVanHuongDanError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Khong tao duoc file cong van huong dan")
        return jsonify({"error": "Không tạo được file công văn hướng dẫn — vui lòng thử lại sau."}), 500

    return jsonify({
        "filename": cong_van_huong_dan_docx.FILENAME,
        "base64": base64.b64encode(docx_bytes).decode("ascii"),
    })


@bp.post("/export-bao-cao-tham-dinh")
@login_required
def export_bao_cao_tham_dinh():
    """Bao cao tham dinh PCCC (.docx that, dung file mau) - KHONG goi AI,
    KHONG tru quota, giong het /export-cong-van-huong-dan ve nguyen tac."""
    user = g.current_user
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là một object JSON."}), 400

    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id (phiên Bộ hồ sơ)."}), 400

    _session, err = _get_own_session_any_status_or_error(user.id, session_id)
    if err:
        return err

    hang_muc_list = payload.get("hang_muc")
    if not isinstance(hang_muc_list, list):
        return jsonify({"error": "Thiếu dữ liệu 'hang_muc'."}), 400

    session_data = {"quy_mo": quy_mo_store.get_quy_mo(session_id) or {}}

    try:
        docx_bytes = bao_cao_tham_dinh_docx.build_bao_cao_tham_dinh_docx(session_data, hang_muc_list)
    except bao_cao_tham_dinh_docx.BaoCaoThamDinhError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Khong tao duoc file bao cao tham dinh")
        return jsonify({"error": "Không tạo được file báo cáo thẩm định — vui lòng thử lại sau."}), 500

    return jsonify({
        "filename": bao_cao_tham_dinh_docx.FILENAME,
        "base64": base64.b64encode(docx_bytes).decode("ascii"),
    })


@bp.post("/fill-form-a-upload")
@login_required
def fill_form_a_upload():
    """Dien Form A do nguoi dung TU DINH KEM (blank template) - dua tren
    findings da co trong phien (KHONG doc lai ban ve). Lan DAU TIEN goi AI
    dang text-only (khong kem anh/PDF) - xem form_a_upload.py."""
    user = g.current_user

    try:
        session_id = int(request.form.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu hoặc sai session_id."}), 400

    try:
        session = ho_so_session.get_open_session_for_user(user.id, session_id)
    except ho_so_session.SessionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except ho_so_session.SessionNotOpen as exc:
        return jsonify({"error": str(exc)}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file Form A (field 'file')."}), 400
    data = file.read()
    if not data.startswith(b"PK"):  # .docx la file zip, magic bytes PK\x03\x04
        return jsonify({"error": "File không đúng định dạng .docx."}), 400
    if len(data) > 10 * 1024 * 1024:
        return jsonify({"error": "File Form A vượt quá 10MB."}), 400

    import json as _json
    try:
        hang_muc_digest = _json.loads(request.form.get("hang_muc_json") or "[]")
    except ValueError:
        return jsonify({"error": "Dữ liệu 'hang_muc_json' không hợp lệ."}), 400

    limit = user.effective_quota()
    used_today = count_usage_today(user.id, AIHO_API_NAME)
    if used_today >= limit:
        return jsonify({
            "error": f"Đã đạt hạn mức {limit} lượt gọi AI/ngày cho tính năng này — thử lại vào ngày mai.",
            "quota": {"limit": limit, "used_today": used_today, "remaining_today": 0},
        }), 429

    provider_name = request.form.get("provider")
    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        ho_so_session.reserve_slot(session, 1, 1)
    except ho_so_session.SessionCapExceeded as exc:
        return jsonify({"error": str(exc)}), 400

    quy_mo = quy_mo_store.get_quy_mo(session_id) or {}

    try:
        docx_bytes = form_a_upload.dien_form_a_upload(data, hang_muc_digest, quy_mo, provider)
    except form_a_upload.FormAUploadError as exc:
        return jsonify({"error": str(exc)}), 400
    except ProviderNotConfigured as exc:
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except AIReaderError as exc:
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        return jsonify({"error": str(exc)}), 502
    except Exception:
        db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="error"))
        db.session.commit()
        current_app.logger.exception("Loi dien Form A upload")
        return jsonify({"error": "Không điền được Form A — vui lòng thử lại sau."}), 502

    db.session.add(UsageLog(user_id=user.id, api_name=AIHO_API_NAME, status="success"))
    db.session.commit()
    ho_so_session.mark_success(session)

    return jsonify({
        "filename": "FormA_da_dien.docx",
        "base64": base64.b64encode(docx_bytes).decode("ascii"),
        "ho_so": {
            "session_id": session.id,
            "files_used": session.files_used,
            "forms_used": session.forms_used,
            "max_files": ho_so_session.MAX_FILES_PER_SESSION,
            "max_forms": ho_so_session.MAX_FORMS_PER_SESSION,
        },
    })
