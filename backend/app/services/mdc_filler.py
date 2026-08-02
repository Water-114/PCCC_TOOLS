"""Trích tiêu chí thật từ mẫu MĐC (bảng đối chiếu) và điền lại cột "Nội dung
thiết kế" + "Kết luận" theo kết quả AI đối chiếu bản vẽ. Dùng chung cho mọi
hạng mục (báo cháy B1/B2, điện PCCC B14, ...) — mỗi hạng mục chỉ cần thêm 1
khoá vào TEMPLATE_PATHS/TEMPLATE_FILENAMES bên dưới.

Nguyên tắc theo đúng references/quy-tac-dien-form.md của skill ra-mau-doi-chieu-pccc:
chỉ điền cột 3, tô đỏ nội dung mới, giữ nguyên 100% các cột còn lại và bố cục bảng.
Cột "Kết luận" (cột 5): tô đỏ CHỈ khi giá trị là "KN" (kiến nghị/chưa đạt) —
"Đạt" và rỗng (mục không áp dụng) giữ màu mặc định. Áp dụng chung cho MỌI
hạng mục, không riêng form nào.
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
    "tram_bom": TEMPLATES_DIR / "B3_tram_bom.docx",
    "hong_nuoc": TEMPLATES_DIR / "B5_hong_nuoc.docx",
    "chua_chay_tu_dong": TEMPLATES_DIR / "B6_chua_chay_tu_dong.docx",
    "binh_chua_chay": TEMPLATES_DIR / "B12_binh_chua_chay.docx",
    "den_su_co": TEMPLATES_DIR / "B13_den_su_co.docx",
    "quy_mo": TEMPLATES_DIR / "A_quy_mo.docx",
}
TEMPLATE_FILENAMES = {
    "thuong": "B1_MDC_bao_chay_thuong.docx",
    "dia_chi": "B2_MDC_bao_chay_dia_chi.docx",
    "dien_pccc": "B14_MDC_dien_pccc.docx",
    "tram_bom": "B3_MDC_tram_bom.docx",
    "hong_nuoc": "B5_MDC_hong_nuoc.docx",
    "chua_chay_tu_dong": "B6_MDC_chua_chay_tu_dong.docx",
    "binh_chua_chay": "B12_MDC_binh_chua_chay.docx",
    "den_su_co": "B13_MDC_den_su_co.docx",
    "quy_mo": "A_MDC_quy_mo.docx",
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
        doi_chieu = row.cells[COL_DOI_CHIEU].text.strip()
        quy_dinh = row.cells[COL_QUY_DINH].text.strip()
        khoan_dieu = row.cells[COL_KHOAN_DIEU].text.strip()
        if not quy_dinh:
            continue  # dòng "mục" tiêu đề gộp nhóm — không phải dòng tiêu chí thật
        if doi_chieu == quy_dinh == khoan_dieu:
            # Dong tieu de bi merge NGUYEN CA HANG (ca 6 cot) thay vi chi merge
            # dung 1 cot nhan de - phat hien qua thuc te (B12 dong TT=1
            # "Binh chua chay xach tay" bi merge het, khien cot quy_dinh khong
            # rong nhu ky vong). Dau hieu: ca 3 cot deu giong het nhau tung chu -
            # khong the la 1 tieu chi that (quy_dinh/khoan_dieu luon khac
            # doi_chieu trong moi dong tieu chi hop le).
            continue
        rows.append({
            "id": idx,
            "doi_chieu": doi_chieu,
            "quy_dinh": quy_dinh,
            "khoan_dieu": khoan_dieu,
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

        ket_luan_cell = row.cells[COL_KET_LUAN]
        ket_luan_text = ans.get("ket_luan") or ""
        ket_luan_cell.text = ket_luan_text
        if ket_luan_text == "KN" and ket_luan_cell.paragraphs[0].runs:
            ket_luan_cell.paragraphs[0].runs[0].font.color.rgb = MAU_DO

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def filename_for(loai: str) -> str:
    return TEMPLATE_FILENAMES.get(loai, "MDC_bao_chay.docx")
