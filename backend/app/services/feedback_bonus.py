"""Thưởng góp ý (Batch 5A, sub-bước 5) — cứ đủ 5 góp ý "hoàn thành" (theo user)
thì cộng thêm 1 Bộ hồ sơ (CreditLedger reason=feedback_bonus).

"1 góp ý hoàn thành" được định nghĩa là góp ý gắn với 1 phiên Bộ hồ sơ THẬT đã
dùng (HoSoSession.status == 'closed_used') — không tính góp ý gửi từ luồng demo
thuần (không mở phiên nào) hay góp ý ẩn danh. Do luồng góp ý hiện tại KHÔNG gắn
feedback với đúng 1 session_id cụ thể (xem js/ai-doc-ho-so.js — nút GÓP Ý bật
sau finishUp() ở cả nhánh demo lẫn nhánh AI thật, và payload gửi lên không có
session_id), số góp ý "hoàn thành" được TÍNH GIỚI HẠN theo số phiên thật đã
dùng của chính user đó — không gắn cứng 1-1 với session cụ thể nào (quyết định
đã được xác nhận, xem docs/02-implementation-batches.md Batch 5A sub-bước 5).

Mốc thưởng được tính lại từ đầu mỗi lần (không lưu "lần kiểm tra trước") để
tránh bug bỏ sót mốc nếu đơn giản chỉ so sánh before/after: lấy số mốc "đáng lẽ
đã đạt" (eligible // FEEDBACK_BONUS_MILESTONE) trừ số lần đã thực sự cấp
thưởng (đếm từ CreditLedger — nguồn sự thật duy nhất, không cần cột/state mới).
"""

from ..models import CreditLedger, Feedback, HoSoSession
from . import credits

FEEDBACK_BONUS_FEATURE = "aiho_bo_ho_so"
FEEDBACK_BONUS_MILESTONE = 5


def maybe_grant_feedback_bonus(user_id: int) -> bool:
    """Kiem tra va cap thuong neu vua du 1 moc 5 gop y moi. Tra ve True neu vua
    cap (dung de FE hien dung cau thong bao du dieu kien), False neu chua du."""
    total_feedback = Feedback.query.filter_by(user_id=user_id, feature=FEEDBACK_BONUS_FEATURE).count()
    total_real_sessions = HoSoSession.query.filter_by(user_id=user_id, status="closed_used").count()
    eligible = min(total_feedback, total_real_sessions)

    bonuses_granted = CreditLedger.query.filter_by(
        user_id=user_id, reason=credits.CREDIT_REASON_FEEDBACK_BONUS
    ).count()
    milestones_reached = eligible // FEEDBACK_BONUS_MILESTONE

    if milestones_reached <= bonuses_granted:
        return False

    credits.grant_credits(
        user_id, 1, credits.CREDIT_REASON_FEEDBACK_BONUS,
        note=f"Thưởng góp ý — đủ {eligible} góp ý hoàn thành",
    )
    return True
