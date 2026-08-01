import base64

from flask import Blueprint, current_app, g, jsonify, request

from ..auth import login_required
from ..extensions import db
from ..models import AIHO_API_NAME, UsageLog, count_usage_today
from ..providers.base import ProviderNotConfigured
from ..providers.factory import get_provider
from ..services import baochay_reader, ccnuoc_reader, dienpccc_reader, kien_nghi_docx, mdc_filler
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


def _log_usage(user_id: int, status: str):
    db.session.add(UsageLog(user_id=user_id, api_name=AIHO_API_NAME, status=status))
    db.session.commit()


def _reserve_usage_slot(user_id: int, limit: int):
    """Giữ trước 1 lượt dùng NGAY LẬP TỨC (trước khi gọi AI) bằng cách ghi 1 bản ghi
    'pending' trong cùng 1 lần kiểm tra+ghi — thu hẹp đáng kể khoảng thời gian có thể
    xảy ra race condition giữa nhiều request đồng thời (từ cỡ vài phút — thời gian gọi
    AI — xuống còn 1 lần truy vấn DB), so với trước đây chỉ ghi nhận SAU KHI AI gọi
    xong. Đây không phải khoá nguyên tử tuyệt đối cấp cơ sở dữ liệu (cần SERIALIZABLE +
    retry ở Postgres — để dành Batch 2 khi chuyển sang Postgres) nhưng giảm mạnh rủi ro
    thực tế với kiến trúc hiện tại. Trả về UsageLog vừa tạo nếu còn chỗ, None nếu hết.
    """
    used = count_usage_today(user_id, AIHO_API_NAME)
    if used >= limit:
        return None
    reservation = UsageLog(user_id=user_id, api_name=AIHO_API_NAME, status="pending")
    db.session.add(reservation)
    db.session.commit()
    return reservation


def _finalize_usage(reservation: UsageLog, status: str):
    reservation.status = status
    db.session.commit()


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


def _handle_read_request(read_drawing_fn, build_mdc_files):
    """Xử lý chung cho mọi hạng mục AI đọc bản vẽ: kiểm tra file, giữ chỗ quota nguyên
    tử ngay trước khi gọi AI, sinh MĐC nếu cần.

    build_mdc_files(result) -> list các entry {loai, label, filename, base64} hoặc {loai, label, error}
    — mỗi hạng mục tự quyết định cần điền mấy file MĐC (báo cháy/điện: 1 file; chữa cháy nước: 3 file).
    """
    user = g.current_user
    limit = user.effective_quota()

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

    reservation = _reserve_usage_slot(user.id, limit)
    if reservation is None:
        used = count_usage_today(user.id, AIHO_API_NAME)
        _log_usage(user.id, "quota_exceeded")
        return jsonify({
            "error": f"Đã dùng hết {limit} lượt đọc bản vẽ hôm nay — quay lại vào ngày mai.",
            "quota": {"limit": limit, "used_today": used, "remaining_today": 0},
        }), 429

    try:
        result = read_drawing_fn(data, media_type, provider)
    except ProviderNotConfigured as exc:
        _finalize_usage(reservation, "error")
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except AIReaderError as exc:
        _finalize_usage(reservation, "error")
        return jsonify({"error": str(exc)}), 502
    except Exception:  # lỗi mạng/SDK bên thứ ba — không lộ chi tiết ra client
        _finalize_usage(reservation, "error")
        current_app.logger.exception("Loi goi provider '%s'", provider.name)
        return jsonify({"error": f"Lỗi gọi máy chủ AI ('{provider.name}') — vui lòng thử lại sau."}), 502

    _finalize_usage(reservation, "success")
    used_after = count_usage_today(user.id, AIHO_API_NAME)
    result["provider"] = provider.name
    result["quota"] = {
        "limit": limit,
        "used_today": used_after,
        "remaining_today": max(0, limit - used_after),
    }

    if wants_mdc:
        result["mdc_docx_files"] = build_mdc_files(result)

    return jsonify(result)


@bp.post("/read-baochay")
@login_required
def read_baochay():
    def build_mdc_files(result):
        loai = result.get("loai_he_thong") if result.get("loai_he_thong") in ("thuong", "dia_chi") else "thuong"
        return [_build_mdc_file(loai, "Báo cháy tự động", result.get("items", []))]
    return _handle_read_request(baochay_reader.read_drawing, build_mdc_files)


@bp.post("/read-dienpccc")
@login_required
def read_dienpccc():
    def build_mdc_files(result):
        return [_build_mdc_file("dien_pccc", "Điện PCCC", result.get("items", []))]
    return _handle_read_request(dienpccc_reader.read_drawing, build_mdc_files)


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
    return _handle_read_request(ccnuoc_reader.read_drawing, build_mdc_files)


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
