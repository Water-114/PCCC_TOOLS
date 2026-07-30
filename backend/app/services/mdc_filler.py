"""Trích tiêu chí thật từ mẫu MĐC (bảng đối chiếu) và điền lại cột "Nội dung
thiết kế" + "Kết luận" theo kết quả AI đối chiếu bản vẽ. Dùng chung cho mọi
hạng mục (báo cháy B1/B2, điện PCCC B14, ...) — mỗi hạng mục chỉ cần thêm 1
khoá vào TEMPLATE_PATHS/TEMPLATE_FILENAMES bên dưới.

Nguyên tắc theo đúng references/quy-tac-dien-form.md của skill ra-mau-doi-chieu-pccc:
chỉ điền cột 3, tô đỏ nội dung mới, giữ nguyên 100% các cột còn lại và bố cục bảng.
"""

import io
from pathlib import Path

from docx import Document
from docx.shared import RGBColor

TEMPLATES_DIR = Path(__file__).resolve().parent / "mdc_templates"
TEMPLATE_PATHS = {
    "thuong": TEMPLATES_DIR / "B1_bao_chay_thuong.docx",
    "dia_chi": TEMPLATES_DIR / "B2_bao_chay_dia_chi.docx",
    "dien_pccc": TEMPLATES_DIR / "B14_dien_pccc.docx",
}
TEMPLATE_FILENAMES = {
    "thuong": "B1_MDC_bao_chay_thuong.docx",
    "dia_chi": "B2_MDC_bao_chay_dia_chi.docx",
    "dien_pccc": "B14_MDC_dien_pccc.docx",
}

COL_DOI_CHIEU = 1
COL_THIET_KE = 2
COL_QUY_DINH = 3
COL_KHOAN_DIEU = 4
COL_KET_LUAN = 5

MAU_DO = RGBColor(0xEE, 0x00, 0x00)

_ROWS_CACHE = {}


def _extract_rows(path):
    doc = Document(path)
    table = doc.tables[0]
    rows = []
    for idx, row in enumerate(table.rows):
        if idx == 0:
            continue  # dòng tiêu đề bảng
        quy_dinh = row.cells[COL_QUY_DINH].text.strip()
        if not quy_dinh:
            continue  # dòng "mục" tiêu đề gộp nhóm — không phải dòng tiêu chí thật
        rows.append({
            "id": idx,
            "doi_chieu": row.cells[COL_DOI_CHIEU].text.strip(),
            "quy_dinh": quy_dinh,
            "khoan_dieu": row.cells[COL_KHOAN_DIEU].text.strip(),
        })
    return rows


def load_criteria_rows(loai: str) -> list:
    """loai: 'thuong' hoặc 'dia_chi'. Trả về list dict {id, doi_chieu, quy_dinh, khoan_dieu}."""
    if loai not in _ROWS_CACHE:
        _ROWS_CACHE[loai] = _extract_rows(TEMPLATE_PATHS[loai])
    return _ROWS_CACHE[loai]


def fill_docx(loai: str, answers: list) -> bytes:
    """answers: list dict {id, noi_dung_thiet_ke, ket_luan}. Trả về bytes file .docx đã điền."""
    doc = Document(TEMPLATE_PATHS[loai])
    table = doc.tables[0]
    answers_by_id = {a["id"]: a for a in answers if "id" in a}

    for idx, row in enumerate(table.rows):
        if idx == 0:
            continue
        ans = answers_by_id.get(idx)
        if not ans:
            continue
        cell = row.cells[COL_THIET_KE]
        cell.text = ans.get("noi_dung_thiet_ke") or ""
        if cell.paragraphs[0].runs:
            cell.paragraphs[0].runs[0].font.color.rgb = MAU_DO
        row.cells[COL_KET_LUAN].text = ans.get("ket_luan") or ""

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def filename_for(loai: str) -> str:
    return TEMPLATE_FILENAMES.get(loai, "MDC_bao_chay.docx")
