"""Batch 4, sub-bước 1 — test tích hợp field so_hieu_ban_ve + validate Pydantic
ngay trong 3 reader thật (baochay/dienpccc/ccnuoc), dùng provider giả lập hoàn
toàn (KHÔNG gọi AI thật, không tốn phí)."""

import json

from app.providers.base import GenerationResult
from app.services import baochay_reader, ccnuoc_reader, dienpccc_reader, mdc_filler
from app.services.ai_schema import KHONG_XAC_DINH_SO_HIEU

EMPTY_KIEN_NGHI = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, fn):
        self.fn = fn
        self.calls = 0

    def generate_with_documents(self, system_prompt, content_blocks):
        self.calls += 1
        return GenerationResult(text=self.fn(system_prompt))


def _items_for(loai):
    rows = mdc_filler.load_criteria_rows(loai)
    return [{"id": r["id"], "noi_dung_thiet_ke": "ok", "ket_luan": "dat"} for r in rows]


def test_dienpccc_reader_returns_so_hieu_ban_ve():
    payload = {
        "items": _items_for("dien_pccc"),
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "E-01",
    }
    provider = FakeProvider(lambda sp: json.dumps(payload))
    result = dienpccc_reader.read_drawing([(b"x", "image/png")], provider)
    assert result["so_hieu_ban_ve"] == "E-01"
    assert provider.calls == 1  # dung 1 lan, khong can retry vi hop le ngay


def test_dienpccc_reader_defaults_so_hieu_ban_ve_when_ai_omits_it():
    payload = {"items": _items_for("dien_pccc"), "tong_ket": "ok", "kien_nghi": EMPTY_KIEN_NGHI}
    provider = FakeProvider(lambda sp: json.dumps(payload))
    result = dienpccc_reader.read_drawing([(b"x", "image/png")], provider)
    assert result["so_hieu_ban_ve"] == KHONG_XAC_DINH_SO_HIEU


def test_baochay_reader_picks_expected_ids_by_loai_he_thong_and_keeps_so_hieu():
    payload = {
        "loai_he_thong": "dia_chi",
        "ly_do_nhan_dien": "co dia chi tung dau bao",
        "items": _items_for("dia_chi"),
        "tong_ket": "ok",
        "kien_nghi": EMPTY_KIEN_NGHI,
        "so_hieu_ban_ve": "PCCC-BC-02",
    }
    provider = FakeProvider(lambda sp: json.dumps(payload))
    result = baochay_reader.read_drawing([(b"x", "image/png")], provider)
    assert result["loai_he_thong"] == "dia_chi"
    assert result["so_hieu_ban_ve"] == "PCCC-BC-02"


def test_ccnuoc_reader_takes_so_hieu_ban_ve_from_first_form_with_real_value():
    """FORMS thu tu: tram_bom (B3), hong_nuoc (B5), chua_chay_tu_dong (B6). tram_bom
    khong xac dinh duoc, hong_nuoc co gia tri that -> phai lay tu hong_nuoc (lan
    dau tien co gia tri that theo dung thu tu FORMS)."""

    def fake_generate(system_prompt):
        if "B3" in system_prompt:
            loai, so_hieu = "tram_bom", KHONG_XAC_DINH_SO_HIEU
        elif "B5" in system_prompt:
            loai, so_hieu = "hong_nuoc", "N-05"
        else:
            loai, so_hieu = "chua_chay_tu_dong", "N-06-KHAC"
        payload = {
            "items": _items_for(loai),
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": so_hieu,
        }
        return json.dumps(payload)

    provider = FakeProvider(fake_generate)
    result = ccnuoc_reader.read_drawing([(b"x", "image/png")], provider)
    assert result["so_hieu_ban_ve"] == "N-05"


def test_ccnuoc_reader_all_placeholder_returns_placeholder():
    def fake_generate(system_prompt):
        loai = "tram_bom" if "B3" in system_prompt else ("hong_nuoc" if "B5" in system_prompt else "chua_chay_tu_dong")
        payload = {
            "items": _items_for(loai),
            "tong_ket": "ok",
            "kien_nghi": EMPTY_KIEN_NGHI,
            "so_hieu_ban_ve": KHONG_XAC_DINH_SO_HIEU,
        }
        return json.dumps(payload)

    provider = FakeProvider(fake_generate)
    result = ccnuoc_reader.read_drawing([(b"x", "image/png")], provider)
    assert result["so_hieu_ban_ve"] == KHONG_XAC_DINH_SO_HIEU
