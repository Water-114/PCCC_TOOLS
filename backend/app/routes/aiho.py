import base64

from flask import Blueprint, g, jsonify, request

from ..auth import login_required
from ..config import Config
from ..extensions import db
from ..models import AIHO_API_NAME, UsageLog, count_usage_today
from ..providers.base import ProviderNotConfigured
from ..providers.factory import get_provider
from ..services import baochay_reader, ccnuoc_reader, dienpccc_reader, mdc_filler
from ..services.ai_reader_common import AIReaderError

bp = Blueprint("aiho", __name__, url_prefix="/api/aiho")

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024  # 15MB, khớp ghi chú trên giao diện


def _log_usage(user_id: int, status: str):
    db.session.add(UsageLog(user_id=user_id, api_name=AIHO_API_NAME, status=status))
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
    except Exception as exc:
        return {"loai": loai, "label": label, "error": f"Không tạo được file MĐC: {exc}"}


def _handle_read_request(read_drawing_fn, build_mdc_files):
    """Xử lý chung cho mọi hạng mục AI đọc bản vẽ: kiểm tra quota, file, gọi AI, sinh MĐC nếu cần.

    build_mdc_files(result) -> list các entry {loai, label, filename, base64} hoặc {loai, label, error}
    — mỗi hạng mục tự quyết định cần điền mấy file MĐC (báo cháy/điện: 1 file; chữa cháy nước: 3 file).
    """
    user = g.current_user
    used = count_usage_today(user.id, AIHO_API_NAME)
    if used >= Config.AIHO_DAILY_QUOTA:
        _log_usage(user.id, "quota_exceeded")
        return jsonify({
            "error": f"Đã dùng hết {Config.AIHO_DAILY_QUOTA} lượt đọc bản vẽ hôm nay — quay lại vào ngày mai.",
            "quota": {"limit": Config.AIHO_DAILY_QUOTA, "used_today": used, "remaining_today": 0},
        }), 429

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file bản vẽ (field 'file')."}), 400

    media_type = file.mimetype
    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": f"Định dạng '{media_type}' không hỗ trợ — chỉ nhận PDF, PNG, JPEG, WEBP."}), 400

    data = file.read()
    if len(data) > MAX_BYTES:
        return jsonify({"error": "File vượt quá 15MB."}), 400

    wants_mdc = "mdc" in {o.strip() for o in (request.form.get("outputs") or "").split(",")}

    provider_name = request.form.get("provider")
    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        result = read_drawing_fn(data, media_type, provider)
    except ProviderNotConfigured as exc:
        _log_usage(user.id, "error")
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except AIReaderError as exc:
        _log_usage(user.id, "error")
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:  # lỗi mạng/SDK bên thứ ba
        _log_usage(user.id, "error")
        return jsonify({"error": f"Lỗi gọi provider '{provider.name}': {exc}"}), 502

    _log_usage(user.id, "success")
    used_after = used + 1
    result["provider"] = provider.name
    result["quota"] = {
        "limit": Config.AIHO_DAILY_QUOTA,
        "used_today": used_after,
        "remaining_today": max(0, Config.AIHO_DAILY_QUOTA - used_after),
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
