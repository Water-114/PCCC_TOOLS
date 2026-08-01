"""Batch 4, sub-bước 1 — test cấu trúc file .docx tổng hợp kiến nghị thiết kế
(app/services/kien_nghi_docx.py): đúng khối/nhóm, nhóm rỗng ghi "(Không có)",
gộp nhiều hạng mục vào 1 file."""

import io

from docx import Document

from app.services.kien_nghi_docx import build_kien_nghi_docx


def _paragraph_texts(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    return [p.text for p in doc.paragraphs]


def _one_hang_muc(**overrides):
    hang_muc = {
        "ten_he_thong": "Báo cháy tự động",
        "so_hieu_ban_ve": "BC-01",
        "kien_nghi": {
            "I_chua_the_hien": ["Thể hiện rõ vị trí tủ trung tâm (Điều 1)."],
            "II_chua_thong_nhat": [],
            "III_chua_phu_hop": ["Bổ sung khoảng cách đầu báo (Điều 2)."],
            "IV_de_xuat_bo_sung": [],
        },
    }
    hang_muc.update(overrides)
    return hang_muc


def test_single_hang_muc_has_heading_and_so_hieu_line():
    docx_bytes = build_kien_nghi_docx([_one_hang_muc()])
    texts = _paragraph_texts(docx_bytes)
    assert "KIẾN NGHỊ THIẾT KẾ - Báo cháy tự động" in texts
    assert "Bản vẽ số: BC-01" in texts


def test_all_four_groups_present_with_labels():
    docx_bytes = build_kien_nghi_docx([_one_hang_muc()])
    texts = _paragraph_texts(docx_bytes)
    assert "I. Nội dung chưa thể hiện" in texts
    assert "II. Nội dung chưa thống nhất" in texts
    assert "III. Nội dung chưa phù hợp QCVN, TCVN" in texts
    assert "IV. Đề xuất bổ sung hồ sơ" in texts


def test_empty_group_shows_khong_co():
    docx_bytes = build_kien_nghi_docx([_one_hang_muc()])
    texts = _paragraph_texts(docx_bytes)
    assert texts.count("(Không có)") == 2  # nhom II va IV rong trong _one_hang_muc()


def test_non_empty_group_lists_each_item():
    docx_bytes = build_kien_nghi_docx([_one_hang_muc()])
    texts = _paragraph_texts(docx_bytes)
    assert "Thể hiện rõ vị trí tủ trung tâm (Điều 1)." in texts
    assert "Bổ sung khoảng cách đầu báo (Điều 2)." in texts


def test_missing_so_hieu_ban_ve_defaults_to_khong_xac_dinh():
    hang_muc = _one_hang_muc()
    del hang_muc["so_hieu_ban_ve"]
    docx_bytes = build_kien_nghi_docx([hang_muc])
    texts = _paragraph_texts(docx_bytes)
    assert "Bản vẽ số: Không xác định được số hiệu bản vẽ" in texts


def test_multiple_hang_muc_gop_vao_1_file():
    hang_muc_2 = _one_hang_muc(ten_he_thong="Điện PCCC", so_hieu_ban_ve="DP-02", kien_nghi={
        "I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": [],
    })
    docx_bytes = build_kien_nghi_docx([_one_hang_muc(), hang_muc_2])
    texts = _paragraph_texts(docx_bytes)
    assert "KIẾN NGHỊ THIẾT KẾ - Báo cháy tự động" in texts
    assert "KIẾN NGHỊ THIẾT KẾ - Điện PCCC" in texts
    assert "Bản vẽ số: BC-01" in texts
    assert "Bản vẽ số: DP-02" in texts


def test_all_groups_empty_shows_khong_co_four_times():
    hang_muc = _one_hang_muc(kien_nghi={
        "I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": [],
    })
    docx_bytes = build_kien_nghi_docx([hang_muc])
    texts = _paragraph_texts(docx_bytes)
    assert texts.count("(Không có)") == 4
