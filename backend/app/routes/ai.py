from flask import Blueprint, jsonify, request

from ..providers.base import ProviderNotConfigured
from ..providers.factory import get_provider

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _build_prompt(result: dict) -> str:
    tong = result.get("tong", {}).get("the_tich_m3")
    return (
        "Bạn là kỹ sư PCCC hỗ trợ diễn giải kết quả tính toán đã có sẵn "
        "(không tự tính lại số liệu). Dưới đây là kết quả tính dung tích bể "
        "nước chữa cháy (đơn vị m³, công thức V = Q x t):\n\n"
        f"{result}\n\n"
        f"Tổng dung tích bể cần dự trữ: {tong} m3.\n\n"
        "Hãy viết 1 đoạn ngắn (3-5 câu) bằng tiếng Việt: diễn giải kết quả này "
        "có ý nghĩa gì, những điểm cần lưu ý khi áp dụng (vd tra bảng lưu lượng "
        "đúng theo QCVN 06/TCVN 7336, không tự suy diễn số liệu kỹ thuật), và "
        "gợi ý bước tiếp theo. Không bịa thêm số liệu không có trong dữ liệu trên."
    )


@bp.post("/comment")
def comment():
    payload = request.get_json(silent=True) or {}
    result = payload.get("result")
    provider_name = payload.get("provider")

    if not result:
        return jsonify({"error": "Thiếu 'result' (kết quả tính toán cần diễn giải)."}), 400

    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    prompt = _build_prompt(result)

    try:
        text = provider.generate(prompt)
    except ProviderNotConfigured as exc:
        return jsonify({"error": str(exc), "provider": provider.name}), 503
    except Exception as exc:  # loi tu SDK ben thu 3 (mang, quota, ...)
        return jsonify({"error": f"Lỗi gọi provider '{provider.name}': {exc}"}), 502

    return jsonify({"provider": provider.name, "comment": text})
