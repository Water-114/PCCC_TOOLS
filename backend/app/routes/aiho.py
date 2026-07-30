from flask import Blueprint, jsonify, request

from ..providers.base import ProviderNotConfigured
from ..providers.factory import get_provider
from ..services.baochay_reader import BaoChayReaderError, read_drawing

bp = Blueprint("aiho", __name__, url_prefix="/api/aiho")

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024  # 15MB, khớp ghi chú trên giao diện


@bp.post("/read-baochay")
def read_baochay():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Thiếu file bản vẽ (field 'file')."}), 400

    media_type = file.mimetype
    if media_type not in ALLOWED_TYPES:
        return jsonify({"error": f"Định dạng '{media_type}' không hỗ trợ — chỉ nhận PDF, PNG, JPEG, WEBP."}), 400

    data = file.read()
    if len(data) > MAX_BYTES:
        return jsonify({"error": "File vượt quá 15MB."}), 400

    provider_name = request.form.get("provider")
    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        result = read_drawing(data, media_type, provider)
    except ProviderNotConfigured as exc:
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except BaoChayReaderError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:  # lỗi mạng/SDK bên thứ ba
        return jsonify({"error": f"Lỗi gọi provider '{provider.name}': {exc}"}), 502

    result["provider"] = provider.name
    return jsonify(result)
