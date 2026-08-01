"""Batch 5A, sub-bước 1 — test app/services/mailer.py: gửi qua SMTP cấu hình
bằng biến môi trường; nếu chưa cấu hình SMTP_HOST thì KHÔNG gửi thật/KHÔNG lỗi
(chỉ log) — để luồng đăng ký/xác thực vẫn chạy được lúc dev/test."""

from unittest.mock import MagicMock, patch

from app.services import mailer


def test_send_email_without_smtp_host_configured_does_not_raise_and_returns_false(app, caplog):
    with app.app_context():
        app.config["SMTP_HOST"] = ""
        import logging
        with caplog.at_level(logging.WARNING, logger="app.services.mailer"):
            sent = mailer.send_email("someone@pccc.local", "Chu de", "Noi dung")
    assert sent is False
    assert "SMTP_HOST" in caplog.text


def test_send_email_with_smtp_configured_calls_smtplib(app):
    with app.app_context():
        app.config["SMTP_HOST"] = "smtp.example-test-only.local"
        app.config["SMTP_PORT"] = 587
        app.config["SMTP_USERNAME"] = "user@example-test-only.local"
        app.config["SMTP_PASSWORD"] = "fake-password"
        app.config["SMTP_FROM_EMAIL"] = "no-reply@example-test-only.local"

        with patch("smtplib.SMTP") as MockSMTP:
            smtp_instance = MockSMTP.return_value.__enter__.return_value
            sent = mailer.send_email("to@pccc.local", "Chu de test", "Noi dung test")

    assert sent is True
    MockSMTP.assert_called_once_with("smtp.example-test-only.local", 587, timeout=10)
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("user@example-test-only.local", "fake-password")
    smtp_instance.send_message.assert_called_once()
    sent_msg = smtp_instance.send_message.call_args[0][0]
    assert sent_msg["To"] == "to@pccc.local"
    assert sent_msg["Subject"] == "Chu de test"
    assert sent_msg["From"] == "no-reply@example-test-only.local"


def test_send_email_without_credentials_skips_login(app):
    with app.app_context():
        app.config["SMTP_HOST"] = "smtp.example-test-only.local"
        app.config["SMTP_USERNAME"] = ""
        app.config["SMTP_PASSWORD"] = ""

        with patch("smtplib.SMTP") as MockSMTP:
            smtp_instance = MockSMTP.return_value.__enter__.return_value
            mailer.send_email("to@pccc.local", "s", "b")

    smtp_instance.login.assert_not_called()
