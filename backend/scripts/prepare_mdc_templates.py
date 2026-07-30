"""Tạo bản mẫu MĐC B1/B2 trống từ file gốc — chạy 1 lần (hoặc lại khi đổi file mẫu gốc).

File gốc (D:\\...) là bảng đối chiếu ĐÃ ĐIỀN của một dự án cũ, không phải mẫu trống.
Script này: giữ nguyên 100% cột TT / Nội dung đối chiếu / Nội dung quy định / Khoản-Điều,
xoá nội dung + định dạng ở cột "Nội dung thiết kế" và "Kết luận" để có mẫu trống,
lưu vào backend/app/services/mdc_templates/ — dùng làm mẫu điền lại cho từng bản vẽ.

Chạy: python scripts/prepare_mdc_templates.py
"""

import sys
import io
from pathlib import Path

from docx import Document

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SOURCE_DIR = Path(
    r"D:\AI MRS-WATER\5. CÁC QUY TRÌNH VÀ PROMT\PROMT MĐC\2.MĐC ĐỂ LẬP HỒ SƠ 2026\0.MĐC"
)
DEST_DIR = Path(__file__).resolve().parent.parent / "app" / "services" / "mdc_templates"

FILES = [
    ("B1. MĐC Hệ thống báo cháy loại thường.docx", "B1_bao_chay_thuong.docx"),
    ("B2. MĐC Hệ thống báo cháy loại địa chỉ.docx", "B2_bao_chay_dia_chi.docx"),
    ("B14. MĐC hệ thống điện phục vụ PCCC.docx", "B14_dien_pccc.docx"),
]

COL_THIET_KE = 2  # "Nội dung thiết kế"
COL_KET_LUAN = 5  # "Kết luận"


def make_blank_template(src_path: Path, dest_path: Path):
    doc = Document(src_path)
    table = doc.tables[0]
    cleared = 0
    for row in table.rows[1:]:  # bỏ dòng header
        quy_dinh = row.cells[3].text.strip()
        if not quy_dinh:
            continue  # dòng "mục" tiêu đề gộp nhóm — không phải dòng tiêu chí, không cần xoá gì (đã trống)
        row.cells[COL_THIET_KE].text = ""
        row.cells[COL_KET_LUAN].text = ""
        cleared += 1
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dest_path)
    return cleared, len(table.rows)


def main():
    for src_name, dest_name in FILES:
        src_path = SOURCE_DIR / src_name
        dest_path = DEST_DIR / dest_name
        if not src_path.exists():
            print(f"[BỎ QUA] Không thấy file gốc: {src_path}")
            continue
        cleared, total_rows = make_blank_template(src_path, dest_path)
        print(f"[OK] {dest_name}: {total_rows} dòng, đã xoá cột Thiết kế/Kết luận của {cleared} dòng tiêu chí -> {dest_path}")


if __name__ == "__main__":
    main()
