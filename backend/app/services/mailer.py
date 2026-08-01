"""Gửi email qua SMTP — cấu hình HOÀN TOÀN qua biến môi trường (SMTP_HOST/
SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM_EMAIL trong config.py), KHÔNG
hardcode provider hay thông tin đăng nhập nào trong code (Batch 5A).

Nếu SMTP_HOST chưa cấu hình (vd môi trường dev local chưa thiết lập): KHÔNG
gửi thật, chỉ log ra console — để luồng đăng ký/xác thực vẫn chạy được lúc
dev/test mà không cần dựng SMTP thật.
"""

import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body_text: str) -> bool:
    """Trả về True nếu đã thật sự gửi (SMTP có cấu hình), False nếu chỉ log
    (chưa cấu hình SMTP_HOST) — KHÔNG raise lỗi cho trường hợp chưa cấu hình,
    vì đây là trạng thái hợp lệ lúc dev/test, không phải lỗi."""
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    if not host:
        logger.warning(
            "SMTP_HOST chưa cấu hình — KHÔNG gửi email thật tới %s. Chủ đề: %s\n%s",
            to_email, subject, body_text,
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("SMTP_FROM_EMAIL") or cfg.get("SMTP_USERNAME") or ""
    msg["To"] = to_email
    msg.set_content(body_text)

    username = cfg.get("SMTP_USERNAME")
    password = cfg.get("SMTP_PASSWORD")

    with smtplib.SMTP(host, cfg.get("SMTP_PORT", 587), timeout=10) as smtp:
        smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)
    return True
