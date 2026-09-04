"""Batch 5A Pha 2 - doi chieu cheo mo rong + danh muc ban ve khi dinh >=2 file.

Kiem tra ai_reader_common.format_danh_muc_ban_ve_instruction() (Viec 2.1) va
viec danh_muc_ban_ve duoc lan truyen dung qua ca reader don (Viec 2.3) lan 2
reader nhieu sub-form ccnuoc/densucco (cho khop voi Viec 3 o frontend, vi
frontend doc d.forms[loai].danh_muc_ban_ve)."""

import json

from app.providers.base import GenerationResult
from app.services import ai_reader_common, ccnuoc_reader, densucco_reader, mdc_filler

EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}
DANH_MUC = [
    {"ky_hieu": "CCN-01", "ten_ban_ve": "Mặt bằng tầng 1", "file_index": 0},
    {"ky_hieu": "CCN-02", "ten_ban_ve": "Mặt bằng tầng 2", "file_index": 1},
]


def _items_for(loai):
    rows = mdc_filler.load_criteria_rows(loai)
    return [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows]


class _CapturingProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, payload_fn):
        self.payload_fn = payload_fn
        self.prompts = []

    def generate_with_documents(self, system_prompt, content_blocks):
        self.prompts.append(system_prompt)
        return GenerationResult(text=self.payload_fn(system_prompt))


# ---------------------------------------------------------------------------
# Viec 2.1 - format_danh_muc_ban_ve_instruction()
# ---------------------------------------------------------------------------
def test_format_danh_muc_ban_ve_instruction_empty_for_0_or_1_file():
    assert ai_reader_common.format_danh_muc_ban_ve_instruction(0) == ""
    assert ai_reader_common.format_danh_muc_ban_ve_instruction(1) == ""


def test_format_danh_muc_ban_ve_instruction_contains_count_and_file_indices():
    text = ai_reader_common.format_danh_muc_ban_ve_instruction(3)
    assert text.count("3") >= 2  # "dang doc 3 file" + "so 3 file" + "Du 3 phan tu"
    assert "file_index" in text
    assert "danh_muc_ban_ve" in text
    assert '"file_index": 0' in text  # mau JSON minh hoa dung file_index=0


# ---------------------------------------------------------------------------
# Viec 1 - cum tu moi trong NHOM_II_MAU_THUAN_CHECKLIST
# ---------------------------------------------------------------------------
def test_nhom_ii_checklist_mentions_multiple_files_not_just_same_file():
    assert "CÁC file đã đính cho lần đọc này" in ai_reader_common.NHOM_II_MAU_THUAN_CHECKLIST
    assert "CÙNG file cung cấp" not in ai_reader_common.NHOM_II_MAU_THUAN_CHECKLIST


# ---------------------------------------------------------------------------
# Viec 2.3 - instruction chi xuat hien trong system prompt khi >=2 file, va
# danh_muc_ban_ve AI tra ve lan truyen dung toi ket qua cuoi cung
# ---------------------------------------------------------------------------
def test_ccnuoc_reader_danh_muc_ban_ve_propagates_to_forms_out():
    def payload_fn(sp):
        if "B3" in sp:
            loai = "tram_bom"
        elif "B5" in sp:
            loai = "hong_nuoc"
        else:
            loai = "chua_chay_tu_dong"
        payload = {
            "items": _items_for(loai),
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "N-01",
            "danh_muc_ban_ve": DANH_MUC,
        }
        if loai == "chua_chay_tu_dong":
            payload["co_thiet_ke_tu_dong"] = True
        return json.dumps(payload)

    provider = _CapturingProvider(payload_fn)
    files = [(b"x", "image/png"), (b"y", "image/png")]
    result = ccnuoc_reader.read_drawing(files, provider)

    assert all("DANH MỤC BẢN VẼ" in p for p in provider.prompts)
    first_key = next(iter(result["forms"]))
    assert result["forms"][first_key]["danh_muc_ban_ve"] == DANH_MUC


def test_densucco_reader_danh_muc_ban_ve_propagates_to_forms_out():
    def payload_fn(sp):
        loai = "binh_chua_chay" if "B12" in sp else "den_su_co"
        return json.dumps({
            "items": _items_for(loai),
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "N-01",
            "danh_muc_ban_ve": DANH_MUC,
        })

    provider = _CapturingProvider(payload_fn)
    files = [(b"x", "image/png"), (b"y", "image/png")]
    result = densucco_reader.read_drawing(files, provider)

    assert all("DANH MỤC BẢN VẼ" in p for p in provider.prompts)
    first_key = next(iter(result["forms"]))
    assert result["forms"][first_key]["danh_muc_ban_ve"] == DANH_MUC


def test_ccnuoc_reader_no_danh_muc_instruction_with_1_file():
    def payload_fn(sp):
        loai = "tram_bom" if "B3" in sp else ("hong_nuoc" if "B5" in sp else "chua_chay_tu_dong")
        payload = {
            "items": _items_for(loai),
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": "N-01",
        }
        if loai == "chua_chay_tu_dong":
            payload["co_thiet_ke_tu_dong"] = True
        return json.dumps(payload)

    provider = _CapturingProvider(payload_fn)
    files = [(b"x", "image/png")]
    result = ccnuoc_reader.read_drawing(files, provider)

    assert all("DANH MỤC BẢN VẼ" not in p for p in provider.prompts)
    first_key = next(iter(result["forms"]))
    assert result["forms"][first_key]["danh_muc_ban_ve"] == []
