import base64

from flask import Blueprint, current_app, g, jsonify, request

from ..auth import login_required
from ..providers.base import ProviderNotConfigured
from ..providers.factory import get_provider
from ..services import baochay_reader, ccnuoc_reader, credits, dienpccc_reader, ho_so_session, kien_nghi_docx, mdc_filler
from ..services.ai_reader_common import AIReaderError

bp = Blueprint("aiho", __name__, url_prefix="/api/aiho")

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024  # 15MB, khớp ghi chú trên giao diện

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
    answers = []
    for item in items:
        try:
            row_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        answers.append({
            "id": row_id,
            "noi_dung_thiet_ke": item.get("noi_dung_thiet_ke"),
            "ket_luan": "Đạt" if item.get("ket_luan") == "dat" else "KN",
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


def _handle_read_request(read_drawing_fn, build_mdc_files, forms_per_call):
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

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file bản vẽ (field 'file')."}), 400

    media_type = file.mimetype
    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": f"Định dạng '{media_type}' không hỗ trợ — chỉ nhận PDF, PNG, JPEG, WEBP."}), 400

    data = file.read()
    if len(data) > MAX_BYTES:
        return jsonify({"error": "File vượt quá 15MB."}), 400

    if not _sniff_magic_bytes(data, media_type):
        return jsonify({"error": "Nội dung file không khớp với định dạng khai báo — file có thể bị hỏng hoặc sai định dạng thật."}), 400

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

    try:
        result = read_drawing_fn(data, media_type, provider)
    except ProviderNotConfigured as exc:
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except AIReaderError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception:  # lỗi mạng/SDK bên thứ ba — không lộ chi tiết ra client
        current_app.logger.exception("Loi goi provider '%s'", provider.name)
        return jsonify({"error": f"Lỗi gọi máy chủ AI ('{provider.name}') — vui lòng thử lại sau."}), 502

    ho_so_session.mark_success(session)
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


@bp.post("/read-baochay")
@login_required
def read_baochay():
    def build_mdc_files(result):
        loai = result.get("loai_he_thong") if result.get("loai_he_thong") in ("thuong", "dia_chi") else "thuong"
        return [_build_mdc_file(loai, "Báo cháy tự động", result.get("items", []))]
    return _handle_read_request(baochay_reader.read_drawing, build_mdc_files, forms_per_call=1)


@bp.post("/read-dienpccc")
@login_required
def read_dienpccc():
    def build_mdc_files(result):
        return [_build_mdc_file("dien_pccc", "Điện PCCC", result.get("items", []))]
    return _handle_read_request(dienpccc_reader.read_drawing, build_mdc_files, forms_per_call=1)


@bp.post("/read-ccnuoc")
@login_required
def read_ccnuoc():
    def build_mdc_files(result):
        files = []
        for loai, form_data in (result.get("forms") or {}).items():
            label = form_data.get("mdc_label", "") + " — " + form_data.get("label", loai)
            if "error" in form_data:
                files.append({"loai": loai, "label": label, "error": form_data["error"]})
            else:
                files.append(_build_mdc_file(loai, label, form_data.get("items", [])))
        return files
    return _handle_read_request(ccnuoc_reader.read_drawing, build_mdc_files, forms_per_call=3)


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
