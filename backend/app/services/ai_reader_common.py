"""Gọi AI provider để đọc bản vẽ (ảnh/PDF) và parse JSON trả về — dùng chung
cho mọi hạng mục rà soát MĐC (báo cháy, điện PCCC, ...).
"""

import base64
import json

from .ai_schema import SchemaValidationError


class AIReaderError(Exception):
    pass


def read_drawing_json(file_bytes: bytes, media_type: str, provider, system_prompt: str) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm system_prompt tới AI provider, trả về dict đã parse JSON."""
    b64 = base64.standard_b64encode(file_bytes).decode("ascii")

    if media_type == "application/pdf":
        content_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        content_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }

    try:
        raw = provider.generate_with_document(system_prompt, content_block)
    except AttributeError:
        raise AIReaderError(
            f"Provider '{getattr(provider, 'name', '?')}' chưa hỗ trợ đọc ảnh/PDF (generate_with_document)."
        )

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        # Trích đoạn quanh đúng vị trí lỗi (exc.pos) — hữu ích hơn nhiều so với chỉ hiện
        # đầu chuỗi, vì lỗi "Unterminated string" thường xảy ra ở cuối văn bản AI trả về
        # (bị cắt giữa chừng do hết max_tokens), cách xa phần đầu.
        start = max(0, exc.pos - 200)
        snippet = raw[start:exc.pos + 50]
        raise AIReaderError(
            f"AI trả về không đúng định dạng JSON: {exc}. "
            f"Tổng độ dài phản hồi: {len(raw)} ký tự. "
            f"Đoạn quanh vị trí lỗi: ...{snippet}..."
        )


def read_and_validate_drawing_json(file_bytes: bytes, media_type: str, provider, system_prompt: str, validate_fn):
    """Gọi read_drawing_json(), rồi validate kết quả qua validate_fn(dict) -> model
    Pydantic (raise SchemaValidationError nếu sai). Nếu thất bại lần 1: retry ĐÚNG
    1 LẦN, gọi lại AI với system_prompt được bổ sung thông báo lỗi cụ thể để AI tự
    sửa. Nếu lần 2 vẫn sai: raise AIReaderError rõ ràng — KHÔNG trả kết quả nửa vời.
    """
    raw = read_drawing_json(file_bytes, media_type, provider, system_prompt)
    try:
        return validate_fn(raw)
    except SchemaValidationError as first_err:
        repair_prompt = (
            system_prompt
            + "\n\n--- SỬA LỖI ĐỊNH DẠNG (bắt buộc) ---\n"
            + "Lần trả lời TRƯỚC của bạn KHÔNG đạt yêu cầu định dạng, lý do cụ thể:\n"
            + str(first_err)
            + "\nHãy đọc lại bản vẽ và trả lời LẠI TỪ ĐẦU, đúng nguyên cấu trúc JSON đã yêu cầu ở trên, sửa đúng lỗi trên. "
              "Không lặp lại lỗi này, không thêm văn bản nào khác ngoài JSON."
        )
        raw2 = read_drawing_json(file_bytes, media_type, provider, repair_prompt)
        try:
            return validate_fn(raw2)
        except SchemaValidationError as second_err:
            raise AIReaderError(
                f"AI trả kết quả không đúng định dạng ngay cả sau khi đã yêu cầu sửa lỗi 1 lần: {second_err}"
            ) from second_err
