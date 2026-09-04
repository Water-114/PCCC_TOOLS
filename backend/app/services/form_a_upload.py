"""Dien Form A do nguoi dung TU DINH KEM (blank template, tu chon dung loai
tu folder MDC cua ho) - dua tren FINDINGS DA CO trong phien (tong_ket +
kien_nghi cua cac hang muc da doc), KHONG doc lai ban ve (app khong luu file
ban ve goc sau moi lan doc). Doi chieu tai lieu "Bo quy tac doc ban ve va
dien MDC" 03/9/2026, quyet dinh ky thuat da chot voi owner."""

import io

from docx import Document

from . import ai_schema, ket_luan_linter, mdc_filler
from .ai_reader_common import generate_and_validate_text


class FormAUploadError(Exception):
    pass


MAX_ROWS = 120  # gioi han an toan - Form A thuc te ~64 dong, du bien


def _build_prompt(criteria_rows: list, hang_muc_digest: list, quy_mo: dict) -> str:
    rows_text = "\n".join(
        f'id={r["id"]} | [{r["doi_chieu"]}] {r["quy_dinh"]} (Căn cứ: {r["khoan_dieu"]})'
        for r in criteria_rows
    )
    digest_parts = []
    if quy_mo:
        digest_parts.append("QUY MÔ CÔNG TRÌNH ĐÃ BIẾT: " + ", ".join(
            f"{k}={v}" for k, v in quy_mo.items() if v not in (None, "", [])
        ))
    for hm in hang_muc_digest:
        items_text = "; ".join(
            f'{it.get("noi_dung_thiet_ke", "")} ({it.get("ket_luan", "")})'
            for it in (hm.get("items") or [])
        )
        if items_text:
            digest_parts.append(f'HẠNG MỤC "{hm.get("ten_he_thong", "")}" ĐÃ ĐỌC: {items_text}')
    digest_text = "\n\n".join(digest_parts) or "(Chưa có hạng mục nào đã đọc trong phiên này.)"

    return f"""Bạn là kỹ sư PCCC tổng hợp kết quả rà soát đã có SẴN (KHÔNG đọc bản vẽ mới, KHÔNG tự suy đoán ngoài dữ liệu dưới đây) để điền vào 1 mẫu Form A tổng hợp.

DỮ LIỆU ĐÃ CÓ (từ các hạng mục đã đọc bản vẽ trong CÙNG bộ hồ sơ này):
{digest_text}

DANH SÁCH TIÊU CHÍ FORM A CẦN ĐỐI CHIẾU (mỗi dòng có "id" — PHẢI trả lời ĐỦ, giữ nguyên đúng id, KHÔNG bỏ sót, KHÔNG thêm id lạ):
{rows_text}

VỚI MỖI id, đối chiếu nội dung tiêu chí với DỮ LIỆU ĐÃ CÓ ở trên:
- Nếu dữ liệu đã có đề cập rõ ràng, đủ căn cứ trả lời: "noi_dung_thiet_ke" tóm tắt lại đúng nội dung liên quan (không bịa thêm chi tiết không có trong dữ liệu), "ket_luan" là "dat" nếu đạt yêu cầu, "chua_dat" nếu đã có nhưng chưa đạt (có kiến nghị liên quan trong dữ liệu).
- Nếu KHÔNG tìm thấy căn cứ liên quan trong dữ liệu đã có: "noi_dung_thiet_ke" ghi ĐÚNG NGUYÊN VĂN "Chưa đối chiếu được từ dữ liệu đã đọc trong bộ hồ sơ này — cần rà thêm", "ket_luan": "chua_the_hien". TUYỆT ĐỐI không suy đoán hoặc bịa nội dung không có trong dữ liệu đã cung cấp.

Trả lời DUY NHẤT bằng JSON hợp lệ: {{"items": [{{"id": 1, "noi_dung_thiet_ke": "...", "ket_luan": "dat"}}]}}"""


def dien_form_a_upload(file_bytes: bytes, hang_muc_digest: list, quy_mo: dict, provider) -> bytes:
    """file_bytes: noi dung file .docx Form A TRONG nguoi dung upload.
    hang_muc_digest: list dict {ten_he_thong, items: [{noi_dung_thiet_ke, ket_luan}]}
    tu frontend (KHONG kem id - id cua Form A khac hoan toan id cua B-form goc).
    Tra ve bytes file .docx da dien."""
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise FormAUploadError(f"Không mở được file .docx — file có thể bị hỏng hoặc sai định dạng: {exc}") from exc

    if not doc.tables:
        raise FormAUploadError("File không có bảng đối chiếu nào — không đúng định dạng Form A.")

    rows = mdc_filler._extract_rows_from_doc(doc)
    if not rows:
        raise FormAUploadError("Không đọc được dòng tiêu chí nào trong bảng — kiểm tra lại đúng file Form A theo mẫu MĐC.")
    if len(rows) > MAX_ROWS:
        raise FormAUploadError(f"File có {len(rows)} dòng tiêu chí, vượt giới hạn {MAX_ROWS} — không đúng định dạng Form A.")

    prompt = _build_prompt(rows, hang_muc_digest, quy_mo)
    expected_ids = {r["id"] for r in rows}

    def _validate(data):
        return ai_schema.validate_reader_result(data, expected_ids, ai_schema.FormAUploadResult)

    model = generate_and_validate_text(prompt, provider, _validate)
    items = ket_luan_linter.fix_items([it.model_dump() if hasattr(it, "model_dump") else it for it in model.items])

    # Chuyen ket_luan THAT cua AI (dat/chua_dat/chua_the_hien/khong_ap_dung)
    # sang chu hien thi cot 5 ("Đạt"/""/"KN") - dung CHUNG 1 nguon voi
    # routes/aiho.py::_answers_from_items() (xem mdc_filler.KET_LUAN_TO_DOCX),
    # KHONG tu dinh nghia lai o day.
    answers = [
        {
            "id": it.get("id"),
            "noi_dung_thiet_ke": it.get("noi_dung_thiet_ke"),
            "ket_luan": mdc_filler.KET_LUAN_TO_DOCX.get(it.get("ket_luan"), "KN"),
        }
        for it in items
    ]

    mdc_filler.fill_doc_in_place(doc, answers)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
