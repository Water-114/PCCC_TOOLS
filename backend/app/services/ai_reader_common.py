"""Gọi AI provider để đọc bản vẽ (ảnh/PDF) và parse JSON trả về — dùng chung
cho mọi hạng mục rà soát MĐC (báo cháy, điện PCCC, ...). Ghi 1 dòng log cho
MỖI lần gọi AI (provider, model, phiên bản system prompt, thời gian xử lý,
usage) — Batch 4 sub-bước 2.
"""

import base64
import hashlib
import json
import logging
import time

from ..providers.resilience import CircuitBreakerOpen
from .ai_schema import SchemaValidationError

# Dung logger chuan (khong phai current_app.logger) vi ccnuoc_reader goi ham nay
# tu ben trong ThreadPoolExecutor - app context cua Flask la thread-local, KHONG
# tu dong co san trong cac worker thread do executor tao ra (da xac nhan bang
# script thu rieng: current_app.logger.* trong worker thread nem RuntimeError
# "Working outside of application context"). Logger ten "app.services.ai_reader_common"
# la con chau cua logger "app" (ten Flask app trong create_app()) trong logging
# hierarchy nen van chui qua dung handler/level Flask da cau hinh, khong can context.
logger = logging.getLogger(__name__)


class AIReaderError(Exception):
    pass


def system_prompt_version(system_prompt: str) -> str:
    """'Phiên bản' system prompt = 12 ký tự đầu sha256 nội dung prompt — tự động
    đổi mỗi khi nội dung prompt thay đổi, không cần nhớ tay bump số như semver
    (dễ quên, dễ sai). Dùng để biết log 1 lần gọi AI ứng với đúng bản prompt nào."""
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:12]


def _log_ai_call(provider, prompt_version, status, started_at, usage=None, error=None):
    elapsed_s = round(time.monotonic() - started_at, 2)
    logger.info(
        "aiho_ai_call provider=%s model=%s prompt_version=%s status=%s elapsed_s=%s usage=%s%s",
        getattr(provider, "name", "?"),
        getattr(provider, "model", "?"),
        prompt_version,
        status,
        elapsed_s,
        usage,
        f" error={error}" if error else "",
    )


def read_drawing_json(file_bytes: bytes, media_type: str, provider, system_prompt: str, prompt_version: str = None) -> dict:
    """Gửi bản vẽ (ảnh hoặc PDF) kèm system_prompt tới AI provider, trả về dict đã
    parse JSON. prompt_version: nhãn phiên bản prompt để ghi log (mặc định tự suy
    ra từ chính system_prompt nếu không truyền — xem system_prompt_version())."""
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

    version = prompt_version if prompt_version is not None else system_prompt_version(system_prompt)
    started_at = time.monotonic()

    try:
        result = provider.generate_with_document(system_prompt, content_block)
    except AttributeError:
        _log_ai_call(provider, version, "error", started_at, error="provider khong ho tro generate_with_document")
        raise AIReaderError(
            f"Provider '{getattr(provider, 'name', '?')}' chưa hỗ trợ đọc ảnh/PDF (generate_with_document)."
        )
    except CircuitBreakerOpen as exc:
        # Loi ro rang, dung mo ta san co san (bao nhieu lan lien tiep/con nghi bao
        # lau) - boc thanh AIReaderError de di dung duong 502 co san o routes/aiho.py
        # thay vi roi vao nhanh 500 chung chung.
        _log_ai_call(provider, version, "circuit_open", started_at, error=str(exc))
        raise AIReaderError(str(exc)) from exc
    except Exception as exc:
        _log_ai_call(provider, version, "error", started_at, error=str(exc))
        raise

    raw, usage = result.text, result.usage

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Trích đoạn quanh đúng vị trí lỗi (exc.pos) — hữu ích hơn nhiều so với chỉ hiện
        # đầu chuỗi, vì lỗi "Unterminated string" thường xảy ra ở cuối văn bản AI trả về
        # (bị cắt giữa chừng do hết max_tokens), cách xa phần đầu.
        start = max(0, exc.pos - 200)
        snippet = raw[start:exc.pos + 50]
        _log_ai_call(provider, version, "json_error", started_at, usage=usage, error=str(exc))
        raise AIReaderError(
            f"AI trả về không đúng định dạng JSON: {exc}. "
            f"Tổng độ dài phản hồi: {len(raw)} ký tự. "
            f"Đoạn quanh vị trí lỗi: ...{snippet}..."
        )

    _log_ai_call(provider, version, "success", started_at, usage=usage)
    return parsed


def read_and_validate_drawing_json(file_bytes: bytes, media_type: str, provider, system_prompt: str, validate_fn, prompt_version: str = None):
    """Gọi read_drawing_json(), rồi validate kết quả qua validate_fn(dict) -> model
    Pydantic (raise SchemaValidationError nếu sai). Nếu thất bại lần 1: retry ĐÚNG
    1 LẦN, gọi lại AI với system_prompt được bổ sung thông báo lỗi cụ thể để AI tự
    sửa. Nếu lần 2 vẫn sai: raise AIReaderError rõ ràng — KHÔNG trả kết quả nửa vời.

    prompt_version: override nhãn phiên bản ghi log — dùng khi system_prompt bị
    NỐI THÊM dữ liệu động ở call-time (vd context "Quy mô" — xem quy_mo_store.py,
    Mức 1 tích hợp vào 4 reader hiện có) khiến sha256 nội dung đổi mỗi lần gọi dù
    prompt GỐC (template) không đổi; truyền SYSTEM_PROMPT_VERSION tĩnh của reader
    vào đây để log vẫn phản ánh đúng "phiên bản template", không bị phân mảnh theo
    dữ liệu quy mô cụ thể của từng lần gọi.
    """
    version = prompt_version if prompt_version is not None else system_prompt_version(system_prompt)  # tinh 1 lan tu prompt GOC, dung cho ca 2 lan goi (repair khong tinh la "phien ban" khac)
    raw = read_drawing_json(file_bytes, media_type, provider, system_prompt, prompt_version=version)
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
        raw2 = read_drawing_json(file_bytes, media_type, provider, repair_prompt, prompt_version=version)
        try:
            return validate_fn(raw2)
        except SchemaValidationError as second_err:
            raise AIReaderError(
                f"AI trả kết quả không đúng định dạng ngay cả sau khi đã yêu cầu sửa lỗi 1 lần: {second_err}"
            ) from second_err
