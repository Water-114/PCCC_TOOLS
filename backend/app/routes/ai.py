from flask import Blueprint, current_app, g, jsonify, request

from ..auth import login_required
from ..extensions import db, limiter
from ..models import AI_COMMENT_API_NAME, UsageLog, count_usage_today
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
@login_required
@limiter.limit("10/minute")
def comment():
    user = g.current_user
    limit = user.effective_quota()
    used = count_usage_today(user.id, AI_COMMENT_API_NAME)
    if used >= limit:
        return jsonify({
            "error": f"Đã dùng hết {limit} lượt/ngày cho tính năng này — quay lại vào ngày mai.",
            "quota": {"limit": limit, "used_today": used, "remaining_today": 0},
        }), 429

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
    except Exception:  # loi tu SDK ben thu 3 (mang, quota, ...) — khong lo chi tiet ra client
        db.session.add(UsageLog(user_id=user.id, api_name=AI_COMMENT_API_NAME, status="error"))
        db.session.commit()
        current_app.logger.exception("Loi goi provider '%s' o /api/ai/comment", provider.name)
        return jsonify({"error": f"Lỗi gọi máy chủ AI ('{provider.name}') — vui lòng thử lại sau."}), 502

    db.session.add(UsageLog(user_id=user.id, api_name=AI_COMMENT_API_NAME, status="success"))
    db.session.commit()
    used_after = used + 1
    return jsonify({
        "provider": provider.name,
        "comment": text,
        "quota": {"limit": limit, "used_today": used_after, "remaining_today": max(0, limit - used_after)},
    })
