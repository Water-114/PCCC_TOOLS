"""Gọi AI provider để đọc bản vẽ (ảnh/PDF) và parse JSON trả về — dùng chung
cho mọi hạng mục rà soát MĐC (báo cháy, điện PCCC, ...).
"""

import base64
import json


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
