"""Batch 5A — B7 tách riêng (bọt cố định bể chứa xăng dầu/SPDM ngoài trời) —
khoá lại nội dung system prompt của botcodinh_reader.py: đúng 15 id (khớp danh
sách owner đã trích sẵn từ B7_bot_co_dinh.docx), khối loại trừ lẫn nhau
id=5/id=7 theo loại mái bể (dùng chung exclusive_alternative_block() với
khibotsolkhi_reader.py — xác nhận refactor không đổi nội dung), số liệu chốt từ
bot-co-dinh-tcvn5307.md (K=2/K=3, 189 l/phút, Bảng 9/10, Điều 5.9.11).

B7 KHÔNG có bước phân loại "1-trong-N" như B8-B11 — chỉ 1 mẫu duy nhất, không
có HE_THONG_LIST/he_thong trong payload.

Không gọi AI thật — chỉ kiểm tra chuỗi system prompt sinh ra (test hồi quy cho
prompt engineering, giống test_khibotsolkhi_reader_prompt_content.py)."""

from app.services import mdc_filler
from app.services.botcodinh_reader import SYSTEM_PROMPT, _EXPECTED_IDS

_EXPECTED_IDS_LIST = [2, 3, 5, 7, 8, 9, 11, 14, 15, 16, 17, 19, 21, 22, 23]


def test_expected_ids_match_real_docx():
    rows = mdc_filler.load_criteria_rows("bot_co_dinh")
    assert [r["id"] for r in rows] == _EXPECTED_IDS_LIST
    assert _EXPECTED_IDS == set(_EXPECTED_IDS_LIST)


def test_no_classification_step_single_form_only():
    """Khac han khibotsolkhi_reader.py (AI tu phan loai he_thong) - B7 chi co 1
    mau duy nhat, khong duoc co block "NEU he_thong =" nao trong prompt."""
    assert 'NẾU he_thong' not in SYSTEM_PROMPT
    assert '"he_thong"' not in SYSTEM_PROMPT


def test_mai_be_exclusive_pair_present():
    assert "YÊU CẦU RIÊNG CHO id=5 và id=7" in SYSTEM_PROMPT
    assert "MÁI CỐ ĐỊNH" in SYSTEM_PROMPT
    assert "MÁI NỔI" in SYSTEM_PROMPT
    assert "Điều 5.9.11" in SYSTEM_PROMPT
    assert '"ket_luan": "khong_ap_dung"' in SYSTEM_PROMPT


def test_mai_be_note_exact_wording_preserved():
    assert (
        "LƯU Ý: nhầm bảng cường độ/thời gian giữa 2 loại mái bể là lỗi phổ biến "
        "nhất khi rà B7 — xác định ĐÚNG loại mái bể từ bản vẽ (ghi chú/mặt cắt bể) "
        "trước khi chọn nhánh."
    ) in SYSTEM_PROMPT


def test_key_technical_figures_from_tcvn5307_present():
    assert "Bảng 9" in SYSTEM_PROMPT
    assert "Bảng 10" in SYSTEM_PROMPT
    assert "K = 3" in SYSTEM_PROMPT  # he so du tru bot no trung binh
    assert "K = 2" in SYSTEM_PROMPT  # he so du tru bot no thap
    assert "189 l/phút" in SYSTEM_PROMPT  # luu luong tru cap dung dich bo tro


def test_outdoor_tank_context_not_b8_b11_room_rules():
    """B7 la be chua NGOAI TROI (khac han B8-B11 phong kin) - khong duoc co 3
    quy tac mac dinh "tinh thuong xuyen co nguoi"/"ket cau bao che kin khi" cua
    khibotsolkhi_reader.py o day."""
    assert "NGOÀI TRỜI" in SYSTEM_PROMPT
    assert "khu vực thường không có người" not in SYSTEM_PROMPT
    assert "kín 100%, không có lỗ hở" not in SYSTEM_PROMPT


def test_shared_checklist_reused_not_duplicated():
    from app.services.ai_reader_common import NHOM_II_MAU_THUAN_CHECKLIST
    assert SYSTEM_PROMPT.count(NHOM_II_MAU_THUAN_CHECKLIST.strip()[:40]) == 1


def test_khong_uoc_luong_khoang_cach_rule_present():
    """id=7 va id=9 cua MDC B7 co nhac 'khoang cach' (lang phun theo chu vi be)
    - phai co quy tac chan AI tu uoc luong khoang cach bang mat khi ban ve
    khong ghi ro so do (dung chung voi baochay/densucco/ccnuoc/khibotsolkhi_reader.py)."""
    from app.services.ai_reader_common import KHONG_UOC_LUONG_KHOANG_CACH
    assert SYSTEM_PROMPT.count(KHONG_UOC_LUONG_KHOANG_CACH.strip()[:40]) == 1
    assert "KHÔNG tự ước lượng khoảng cách" in SYSTEM_PROMPT


def test_toa_do_truc_khoang_cach_present_twice():
    """TOA_DO_TRUC_KHOANG_CACH duoc chen 2 lan - 1 lan o BUOC 1 (noi_dung_thiet_ke,
    cot 3 bang MDC .docx) va 1 lan o BUOC 2 (cau kien nghi)."""
    assert SYSTEM_PROMPT.count("tại vị trí trục") == 2


def test_criteria_list_contains_all_15_ids():
    for i in _EXPECTED_IDS_LIST:
        assert f"id={i} |" in SYSTEM_PROMPT
