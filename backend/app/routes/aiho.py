import base64

from flask import Blueprint, g, jsonify, request

from ..auth import login_required
from ..config import Config
from ..extensions import db
from ..models import AIHO_API_NAME, UsageLog, count_usage_today
from ..providers.base import ProviderNotConfigured
from ..providers.factory import get_provider
from ..services import baochay_reader, dienpccc_reader, mdc_filler
from ..services.ai_reader_common import AIReaderError

bp = Blueprint("aiho", __name__, url_prefix="/api/aiho")

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024  # 15MB, khớp ghi chú trên giao diện


def _log_usage(user_id: int, status: str):
    db.session.add(UsageLog(user_id=user_id, api_name=AIHO_API_NAME, status=status))
    db.session.commit()


def _handle_read_request(read_drawing_fn, resolve_mdc_loai):
    """Xử lý chung cho mọi hạng mục AI đọc bản vẽ: kiểm tra quota, file, gọi AI, sinh MĐC nếu cần.

    resolve_mdc_loai(result) -> khoá tương ứng trong mdc_filler.TEMPLATE_PATHS để điền đúng mẫu.
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
        loai = resolve_mdc_loai(result)
        answers = []
        for item in result.get("items", []):
            try:
                row_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            answers.append({
                "id": row_id,
                "noi_dung_thiet_ke": item.get("noi_dung_thiet_ke"),
                "ket_luan": "Đạt" if item.get("ket_luan") == "dat" else "KN",
            })
        try:
            docx_bytes = mdc_filler.fill_docx(loai, answers)
            result["mdc_docx_base64"] = base64.b64encode(docx_bytes).decode("ascii")
            result["mdc_docx_filename"] = mdc_filler.filename_for(loai)
        except Exception as exc:
            result["mdc_docx_error"] = f"Không tạo được file MĐC: {exc}"

    return jsonify(result)


@bp.post("/read-baochay")
@login_required
def read_baochay():
    return _handle_read_request(
        baochay_reader.read_drawing,
        lambda result: result.get("loai_he_thong") if result.get("loai_he_thong") in ("thuong", "dia_chi") else "thuong",
    )


@bp.post("/read-dienpccc")
@login_required
def read_dienpccc():
    return _handle_read_request(dienpccc_reader.read_drawing, lambda result: "dien_pccc")
