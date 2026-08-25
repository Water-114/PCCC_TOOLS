"""Quy mô Giai đoạn 1 — test thuần Python (không cần Flask client) cho:
- Phần D.3: evaluate_dien_pccc_suy_luan() (phuong_tien.py) — suy luận, không
  phải ngưỡng riêng.
- Phần D.4: evaluate_bot_co_dinh() (phuong_tien.py) — dùng field mới
  coBeXangDauNgoaiTroi.
- Phần A.3: merge_scan_quymo_results() (quy_mo_store.py) — gộp 1-2 kết quả
  Lượt 0, phát hiện mâu thuẫn.
- Phần E.1/E.2: compute_reverse_check_warnings() (quy_mo_store.py) — đối
  chiếu ngược "thiếu hồ sơ hệ thống X"."""

from app.services import quy_mo_store
from app.services.phuong_tien import evaluate_bot_co_dinh, evaluate_dien_pccc_suy_luan


def _p(occ="chungcu", **kwargs):
    base = {"occ": occ, "floors": 0, "basements": 0, "semiBasements": 0, "totalArea": 0, "areaFloor": 0, "volume": 0}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# D.3 — evaluate_dien_pccc_suy_luan
# ---------------------------------------------------------------------------
def test_dien_pccc_always_yes_because_binh_chua_chay_always_bat_buoc():
    """Binh chua chay xach tay LUON bat buoc (TCVN 7435-1:2004, khong nguong
    quy mo) - theo dung logic D.3 (danh sach 'yes' co it nhat 1 he thong thi
    dien PCCC 'yes'), ham nay THUC TE luon tra 'yes' cho moi occ hop le - dung
    thuc te PCCC (hau nhu cong trinh nao cung can dien phuc vu PCCC)."""
    r = evaluate_dien_pccc_suy_luan(_p("chungcu"))
    assert r["result"] == "yes"
    assert "bình chữa cháy xách tay" in r["detail"]
    assert "suy luận" in r["detail"].lower()
    assert "Suy luận nội bộ" in r["can_cu"]


def test_dien_pccc_yes_list_includes_bao_chay_when_thuoc_dien():
    # chungcu >=5 tang hoac >=700m2 -> bao chay "yes" (evaluate_bao_chay)
    r = evaluate_dien_pccc_suy_luan(_p("chungcu", floors=10, totalArea=2000))
    assert r["result"] == "yes"
    assert "báo cháy tự động" in r["detail"]


def test_dien_pccc_khong_bao_chay_van_yes_vi_binh_chua_chay():
    # chungcu duoi nguong -> bao chay "no", nhung binh chua chay van "yes"
    r = evaluate_dien_pccc_suy_luan(_p("chungcu", floors=2, totalArea=100))
    assert r["result"] == "yes"
    assert "báo cháy tự động" not in r["detail"]
    assert "bình chữa cháy xách tay" in r["detail"]


def test_dien_pccc_khong_can_field_gi_dac_biet_ngoai_occ():
    r = evaluate_dien_pccc_suy_luan(_p("khachsan"))
    assert r["result"] == "yes"


# ---------------------------------------------------------------------------
# D.4 — evaluate_bot_co_dinh
# ---------------------------------------------------------------------------
def test_bot_co_dinh_true_yields_yes():
    r = evaluate_bot_co_dinh({"coBeXangDauNgoaiTroi": True})
    assert r["result"] == "yes"
    assert "TCVN 5307:2009" in r["can_cu"]


def test_bot_co_dinh_false_yields_no():
    r = evaluate_bot_co_dinh({"coBeXangDauNgoaiTroi": False})
    assert r["result"] == "no"


def test_bot_co_dinh_none_yields_chua_du_du_lieu_not_no():
    """Chua khai bao KHONG duoc mac dinh la 'khong thuoc dien' - phai la
    'chua_du_du_lieu' (chua ket luan duoc)."""
    r = evaluate_bot_co_dinh({})
    assert r["result"] == "chua_du_du_lieu"


def test_bot_co_dinh_missing_key_same_as_none():
    r = evaluate_bot_co_dinh({"occ": "khac"})
    assert r["result"] == "chua_du_du_lieu"


# ---------------------------------------------------------------------------
# A.3 — merge_scan_quymo_results
# ---------------------------------------------------------------------------
def _scan(slot, label, tim_thay, **quy_mo):
    return {"slot": slot, "label": label, "tim_thay": tim_thay, "quy_mo": quy_mo or None}


def test_merge_no_results_found():
    out = quy_mo_store.merge_scan_quymo_results([
        _scan("baochay", "Báo cháy tự động", False),
        _scan("ccnuoc", "Chữa cháy bằng nước", False),
    ])
    assert out["merged"] is None
    assert out["conflicts"] == []
    assert out["found_count"] == 0


def test_merge_single_result_found():
    out = quy_mo_store.merge_scan_quymo_results([
        _scan("baochay", "Báo cháy tự động", True, occ="chungcu", floors=8),
        _scan("ccnuoc", "Chữa cháy bằng nước", False),
    ])
    assert out["merged"] == {"occ": "chungcu", "floors": 8}
    assert out["conflicts"] == []
    assert out["found_count"] == 1


def test_merge_two_results_no_conflict_union_fields():
    out = quy_mo_store.merge_scan_quymo_results([
        _scan("baochay", "Báo cháy tự động", True, occ="chungcu", floors=8),
        _scan("ccnuoc", "Chữa cháy bằng nước", True, totalArea=3000),
    ])
    assert out["merged"]["occ"] == "chungcu"
    assert out["merged"]["floors"] == 8
    assert out["merged"]["totalArea"] == 3000
    assert out["conflicts"] == []
    assert out["found_count"] == 2


def test_merge_two_results_conflict_detected_and_priority_chosen():
    """2 file cho ra floors KHAC nhau -> conflict; uu tien file day du hon
    (nhieu field khac None hon) lam nguon 'da chon'."""
    out = quy_mo_store.merge_scan_quymo_results([
        _scan("baochay", "Báo cháy tự động", True, occ="chungcu", floors=8, totalArea=3000, hFire=22),
        _scan("ccnuoc", "Chữa cháy bằng nước", True, floors=10),
    ])
    assert len(out["conflicts"]) == 1
    c = out["conflicts"][0]
    assert c["field"] == "floors"
    assert c["chosen"] == 8  # baochay day du hon (4 field vs 1 field)
    assert out["merged"]["floors"] == 8
    assert out["merged"]["occ"] == "chungcu"  # field khong mau thuan van gop binh thuong


def test_merge_ignores_none_values_when_only_one_side_has_it():
    out = quy_mo_store.merge_scan_quymo_results([
        _scan("baochay", "Báo cháy tự động", True, occ="chungcu"),
        _scan("ccnuoc", "Chữa cháy bằng nước", True, occ="chungcu", floors=5),
    ])
    assert out["conflicts"] == []
    assert out["merged"] == {"occ": "chungcu", "floors": 5}


# ---------------------------------------------------------------------------
# E.1/E.2 — compute_reverse_check_warnings
# ---------------------------------------------------------------------------
def test_reverse_check_warns_when_thuoc_dien_but_slot_missing():
    fields = _p("chungcu", floors=10, totalArea=2000)  # bao chay thuoc dien
    warnings = quy_mo_store.compute_reverse_check_warnings(fields, slots_with_data=[])
    slots_warned = {w["slot"] for w in warnings}
    assert "baochay" in slots_warned
    # densucco va dienpccc luon thuoc dien (binh chua chay/dien PCCC luon bat buoc)
    assert "densucco" in slots_warned
    assert "dienpccc" in slots_warned
    # botcodinh: coBeXangDauNgoaiTroi khong khai bao -> chua_du_du_lieu, KHONG canh bao
    assert "botcodinh" not in slots_warned


def test_reverse_check_no_warning_when_slot_already_has_data():
    fields = _p("chungcu", floors=10, totalArea=2000)
    warnings = quy_mo_store.compute_reverse_check_warnings(
        fields, slots_with_data=["baochay", "densucco", "dienpccc", "ccnuoc"]
    )
    assert warnings == []


def test_reverse_check_no_warning_when_not_thuoc_dien():
    # chungcu duoi nguong -> bao chay "no" (khong thuoc dien) -> khong canh bao du thieu file
    fields = _p("chungcu", floors=2, totalArea=100)
    warnings = quy_mo_store.compute_reverse_check_warnings(fields, slots_with_data=[])
    slots_warned = {w["slot"] for w in warnings}
    assert "baochay" not in slots_warned
    # densucco/dienpccc van thuoc dien (binh chua chay luon bat buoc)
    assert "densucco" in slots_warned
    assert "dienpccc" in slots_warned


def test_reverse_check_botcodinh_warns_when_co_be_xang_dau_true_and_missing():
    fields = _p("khac", coBeXangDauNgoaiTroi=True)
    warnings = quy_mo_store.compute_reverse_check_warnings(fields, slots_with_data=[])
    slots_warned = {w["slot"] for w in warnings}
    assert "botcodinh" in slots_warned


def test_reverse_check_khibot_never_appears_no_rule():
    """khibot (B8-B11) khong co nguong rule nao xac dinh thuoc dien - khong
    duoc tu bia, khong bao gio xuat hien trong canh bao."""
    fields = _p("chungcu", floors=20, totalArea=5000, coBeXangDauNgoaiTroi=True)
    warnings = quy_mo_store.compute_reverse_check_warnings(fields, slots_with_data=[])
    slots_warned = {w["slot"] for w in warnings}
    assert "khibot" not in slots_warned
