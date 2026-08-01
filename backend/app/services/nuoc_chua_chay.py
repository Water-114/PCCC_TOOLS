"""BƯỚC 3-4 — Nước chữa cháy sơ bộ.

Nguồn: QCVN 06 (Bảng 8, 11, 12); TCVN 7336:2021 (Bảng 1, 2, 3, Phụ lục A);
TCVN 14496:2025 (kho kệ cao); QCVN 10:2025/BCA Phụ lục C. Quy đổi 1 m³ = 1.000 L.

Port từ index.html/js/tuvan-so-bo.js (traBang11, traBang12, traBang8,
traSprinkler, heSoPsi14496, tinh14496_1tang, tinh14496_nhieutang,
traBang1_14496, evalNuoc) — rule-based/công thức thuần, không dùng AI.

Batch 3 — theo quyết định của owner: đây là bản "đối chiếu song song",
production KHÔNG gọi service này — index.html/js/tuvan-so-bo.js vẫn tự tính
100% ở client. Không sửa bất kỳ ngưỡng/công thức nào so với bản JS gốc.
Công cụ chỉ mang tính hỗ trợ tham khảo — không có quyền thẩm định/phê duyệt
(xem docs/01-target-architecture.md).

Đã sửa lỗi mapping (theo yêu cầu owner, không phải "giữ nguyên hành vi cũ"):
tinh14496_nhieutang() (chế độ B — Điều 6, nhiều tầng đầu phun) trước đây đọc
nhầm d.hXepM (field của chế độ A — Điều 5, 1 tầng đầu phun) thay vì
d.hXepM2 (field riêng mà form thực sự thu thập cho chế độ nhiều tầng). Đã
sửa đồng bộ ở cả JS production (js/tuvan-so-bo.js) và bản port này — chỉ
đổi NGUỒN dữ liệu đầu vào (đọc đúng field), không đổi bất kỳ công thức/
ngưỡng/kết luận/căn cứ quy chuẩn nào (Qi=A×B×n×i, iD theo ngưỡng h≤16m/>16m,
Qd=iD×Sd, Qs=Qi+Qd giữ nguyên 100%).

Một số điểm khác biệt tinh vi cần lưu ý khi đối chiếu:
- traBang12 (Bảng 12 QCVN 06) và traBang1_14496 (Bảng 1 TCVN 14496) trông
  giống nhau nhưng KHÔNG giống hệt — vd. bậc IV/hạng D,E/thể tích lớn:
  traBang12 trả q=2,5 còn traBang1_14496 trả q=2. Đã đối chiếu từng dòng.
- Nếu nhóm nguy cơ cháy (nhomNC) trống/không hợp lệ khi cần tra bảng (vd.
  sprinkler bắt buộc nhưng người dùng chưa chọn nhóm), bản JS gốc sẽ ném
  lỗi runtime (truy cập thuộc tính của undefined). Bản port này thay bằng
  kết quả "err" mềm (đúng phong cách các nhánh thiếu dữ liệu khác trong
  chính module này) thay vì để crash — đây là phần BẮT BUỘC theo yêu cầu
  "dữ liệu sai phải trả 400 rõ ràng, không trả 500" của route, không phải
  thay đổi ngưỡng/công thức.
"""

import math

from .he_thong_bat_buoc import (
    HeThongBatBuocInputError,
    evaluate_hong_nuoc,
    evaluate_ngoai_nha,
    evaluate_sprinkler,
)
from .tham_dinh import OCCUPATIONS as _OCCUPATIONS

RULE_SET_VERSION = "QCVN06-TCVN7336-2021-TCVN14496-2025"

_VALID_OCC_IDS = {o["id"] for o in _OCCUPATIONS}
_OCC_LABEL_BY_ID = {o["id"]: o["label"] for o in _OCCUPATIONS}


class NuocChuaChayInputError(Exception):
    pass


# ---------------------------------------------------------------------------
# Validation (đúng chuẩn Batch 1 / cụm 1-2): parse an toàn, 400 thay vì 500.
# Các trường floors/totalArea/areaFloor/hFire/basements/semiBasements/kids/
# seats/hazard/garaKin/garaKC12/garaBcl/garaCapS đã được validate khi gọi
# evaluate_sprinkler/evaluate_hong_nuoc/evaluate_ngoai_nha (he_thong_bat_buoc)
# bên dưới — ở đây chỉ validate thêm các trường RIÊNG của cụm nước.
# ---------------------------------------------------------------------------

_FIELD_LABELS = {
    "floorsNoi": "Số tầng nổi",
    "hBaoVe": "Chiều cao khu vực bảo vệ",
    "botS": "Diện tích tính toán chữa cháy bọt S",
    "botJ": "Cường độ phun bọt J",
    "botT": "Thời gian phun bọt t",
    "botK": "Hệ số dự trữ K",
    "botCB": "Nồng độ chất tạo bọt C_B (%)",
    "hXepM": "Chiều cao xếp hàng h (chế độ 1 tầng đầu phun)",
    "hXepM2": "Chiều cao xếp hàng h (chế độ nhiều tầng đầu phun)",
    "hGianPhong": "Chiều cao gian phòng H",
    "soDauPhun90": "Số đầu phun trong 90 m²",
    "chieuRongKeB": "Chiều rộng tối đa kệ hàng B",
    "soTamChan": "Số tấm chắn n",
    "dienTichMai90": "Diện tích mái tính toán (90 m²)",
}

_NUMERIC_FIELDS = tuple(_FIELD_LABELS.keys())

_ENUM_FIELDS = {
    "nhomNC": {"1", "2", "3", "4.1", "4.2", "5", "6", "7"},
    "nhomNC14496": {"5", "6"},
    "hXep": {"1", "2", "3", "4", "5.5", "cao"},
    "corridor": {"le10", "gt10"},
    "bcl": {"I", "II", "III", "IV", "V"},
    "capS": {"S0", "S1", "S2", "S3"},
    "phuongAn14496": {"1tang", "nhieutang"},
    "loaiPallet14496": {"phang", "hop", "hopkimloai"},
    "loaiHang14496": {"ranco", "khongchay", "caosu"},
    "daiCaoDo14496": {"le2", "tu2den3", "tu3den45"},
}

_ENUM_LABELS = {
    "nhomNC": "Nhóm nguy cơ cháy",
    "nhomNC14496": "Nhóm nguy cơ cháy (chế độ 1 tầng đầu phun)",
    "hXep": "Chiều cao xếp hàng (dải)",
    "corridor": "Hành lang chung",
    "bcl": "Bậc chịu lửa",
    "capS": "Cấp nguy hiểm cháy kết cấu",
    "phuongAn14496": "Phương án TCVN 14496",
    "loaiPallet14496": "Loại pallet",
    "loaiHang14496": "Loại hàng lưu trữ",
    "daiCaoDo14496": "Dải chiều cao giữa các tấm chắn",
}


def _fmt(n):
    n = float(n or 0)
    if n.is_integer():
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _nf1(n):
    return f"{float(n or 0):,.1f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _nf2(n):
    return f"{float(n or 0):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _num(payload, key, default=0.0):
    v = payload.get(key)
    if v is None or v == "":
        return default
    label = _FIELD_LABELS.get(key, key)
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise NuocChuaChayInputError(f"Giá trị của '{label}' phải là số, không phải {type(v).__name__}.")
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise NuocChuaChayInputError(f"Giá trị của '{label}' không phải là số hợp lệ: {v!r}.")
    if not math.isfinite(n):
        raise NuocChuaChayInputError(f"Giá trị của '{label}' không hợp lệ (NaN/Infinity).")
    if n < 0:
        raise NuocChuaChayInputError(f"Giá trị của '{label}' không được âm.")
    return n


def _num_or_none(payload, key):
    v = payload.get(key)
    if v is None or v == "":
        return None
    return _num(payload, key)


def _require_valid_occ(payload):
    occ = payload.get("occ")
    if occ not in _VALID_OCC_IDS:
        raise NuocChuaChayInputError(f"Công năng không hợp lệ: '{occ}'.")


def validate_payload(payload):
    """Validate riêng cho cụm nước; các trường dùng chung với cụm hệ thống
    bắt buộc được validate khi gọi evaluate_sprinkler/hong_nuoc/ngoai_nha."""
    _require_valid_occ(payload)
    for key in _NUMERIC_FIELDS:
        _num(payload, key)
    for key, allowed in _ENUM_FIELDS.items():
        v = payload.get(key)
        if v is None or v == "":
            continue
        if v not in allowed:
            raise NuocChuaChayInputError(f"Giá trị của '{_ENUM_LABELS[key]}' không hợp lệ: {v!r}.")


# ---------------------------------------------------------------------------
# Bảng tra cứu (giữ nguyên số liệu so với JS)
# ---------------------------------------------------------------------------

NHOM_SUGGEST = {
    "truso": "1", "chungcu": "1", "truonghoc": "1", "nhatre": "1", "yte": "1", "khachsan": "1",
    "nhahang": "1", "baotang": "1", "thethao": "1", "nhaga": "1",
    "karaoke": "2", "nhahat": "2", "vanhoa": "2", "tttm": "2", "cuahang": "2", "buudien": "2",
    "garakin": "2", "sanxuat": "2", "honhop": "2", "kho": "5",
}

B1_7336 = {"1": {"Q": 10, "t": 30}, "2": {"Q": 30, "t": 60}, "3": {"Q": 60, "t": 60}, "4.1": {"Q": 110, "t": 60}}
B2_7336 = {
    "5": {"1": 15, "2": 30, "3": 45, "4": 60, "5.5": 75},
    "6": {"1": 30, "2": 60, "3": 75, "4": 75, "5.5": 90},
}
B3_7336 = [
    (12, {"1": 12, "2": 35, "3": 70, "4.1": 130}),
    (14, {"1": 14, "2": 40, "3": 85, "4.1": 155}),
    (16, {"1": 17, "2": 50, "3": 95, "4.1": 180}),
    (18, {"1": 20, "2": 57, "3": 115, "4.1": 215}),
    (20, {"1": 24, "2": 65, "3": 130, "4.1": 240}),
]
A_PALLET_14496 = {"phang": 9, "hop": 12, "hopkimloai": 8}
I_KEHANG_14496 = {
    "ranco": {"le2": 0.24, "tu2den3": 0.36, "tu3den45": 0.5},
    "khongchay": {"le2": 0.20, "tu2den3": 0.30, "tu3den45": 0.4},
    "caosu": {"le2": 0.40, "tu2den3": 0.60, "tu3den45": 0.8},
}

_HXEP_LABEL = {"1": "đến 1 m", "2": "1–2 m", "3": "2–3 m", "4": "3–4 m", "5.5": "4–5,5 m"}
_LOAI_HANG_LABEL = {"ranco": "vật liệu dễ cháy thể rắn", "khongchay": "không cháy trong bao bì dễ cháy", "caosu": "sản phẩm cao su"}
_DAI_CAO_DO_LABEL = {"le2": "≤ 2,0 m", "tu2den3": "> 2,0–3,0 m", "tu3den45": "> 3,0–4,5 m"}


def _tra_bang_11(payload):
    """Bảng 11 QCVN 06 — họng nước trong nhà (nhà ở & công cộng)."""
    occ = payload.get("occ")
    floors = _num(payload, "floors")
    volume = _num(payload, "volume")
    if occ == "chungcu":
        gt10 = payload.get("corridor") == "gt10"
        if floors <= 16:
            return {"n": 2 if gt10 else 1, "q": 2.5,
                    "muc": f"Bảng 11 QCVN 06, mục 1 (nhà ở ≤ 16 tầng, hành lang {'> 10 m' if gt10 else '≤ 10 m'})"}
        if floors <= 25:
            return {"n": 3 if gt10 else 2, "q": 2.5,
                    "muc": f"Bảng 11 QCVN 06, mục 1 (nhà ở > 16 đến ≤ 25 tầng, hành lang {'> 10 m' if gt10 else '≤ 10 m'})"}
        return {"err": "Nhà ở > 25 tầng: ngoài phạm vi Bảng 11 — tính riêng theo quy định nhà siêu cao tầng."}
    if occ == "nhahat":
        seats = _num(payload, "seats")
        if seats > 300:
            return {"n": 2, "q": 5.0, "muc": "Bảng 11 QCVN 06, mục 3 (> 300 chỗ ngồi)"}
        return {"n": 2, "q": 2.5, "muc": "Bảng 11 QCVN 06, mục 3 (≤ 300 chỗ ngồi)"}
    if occ in ("truso", "buudien"):
        so, ten = "2", "nhà hành chính"
    else:
        so, ten = "4", "nhà công cộng"
    big = volume > 25000
    n = (2 if big else 1) if floors <= 10 else (3 if big else 2)
    return {"n": n, "q": 2.5,
            "muc": f"Bảng 11 QCVN 06, mục {so} ({ten} {'≤ 10' if floors <= 10 else '> 10'} tầng, V {'> 25.000' if big else '≤ 25.000'} m³)"}


def _tra_bang_12(payload):
    """Bảng 12 QCVN 06 — họng nước trong nhà (nhà SX/kho)."""
    volume = _num(payload, "volume")
    big = volume > 150000
    b = payload.get("bcl")
    hz = payload.get("hazard")
    s = payload.get("capS")

    def tag(n, q):
        return {"n": n, "q": q, "muc": f"Bảng 12 QCVN 06 (bậc {b}, hạng {hz}, cấp {s}, V {'> 150.000' if big else '≤ 150.000'} m³)"}

    if b in ("I", "II"):
        if hz in ("A", "B", "C") and s in ("S0", "S1"):
            return tag(3, 2.5) if big else tag(2, 2.5)
        if hz in ("D", "E"):
            return tag(1, 2.5)
    if b == "III":
        if hz in ("A", "B", "C") and s == "S0":
            return tag(3, 2.5) if big else tag(2, 2.5)
        if hz in ("D", "E") and s in ("S0", "S1"):
            return tag(2, 2.5) if big else tag(1, 2.5)
    if b == "IV":
        if hz in ("A", "B") and s == "S0":
            return tag(3, 2.5) if big else tag(2, 2.5)
        if hz == "C" and s in ("S0", "S1"):
            return tag(2, 5) if big else tag(2, 2.5)
        if hz == "C" and s in ("S2", "S3"):
            return tag(4, 2.5) if big else tag(3, 2.5)
        if hz in ("D", "E"):
            return tag(2, 2.5) if big else tag(1, 2.5)
    if b == "V":
        if hz == "C":
            return tag(2, 5) if big else tag(2, 2.5)
        if hz in ("D", "E"):
            return tag(2, 2.5) if big else tag(1, 2.5)
    return {"err": f"Tổ hợp bậc {b} / hạng {hz} / cấp {s} không có trong Bảng 12 QCVN 06 — kiểm tra lại dữ liệu (VD bậc IV hạng A,B chỉ quy định cấp S0)."}


def _tra_bang_1_14496(payload):
    """Bảng 1 TCVN 14496 — họng nước trong nhà cho kho kệ cao."""
    volume = _num(payload, "volume")
    big = volume > 150000
    b = payload.get("bcl")
    hz = payload.get("hazard")
    s = payload.get("capS")

    def tag(n, q):
        return {"n": n, "q": q, "muc": f"Bảng 1 TCVN 14496 (bậc {b}, hạng {hz}, cấp {s}, V {'> 150.000' if big else '≤ 150.000'} m³)"}

    if b in ("I", "II"):
        if hz in ("A", "B", "C") and s in ("S0", "S1"):
            return tag(3, 2.5) if big else tag(2, 2.5)
        if hz in ("D", "E"):
            return tag(1, 2.5)
    if b == "III":
        if hz in ("A", "B") and s == "S0":
            return tag(3, 2.5) if big else tag(2, 2.5)
        if hz == "C" and s in ("S0", "S1"):
            return tag(2, 5) if big else tag(2, 2.5)
        if hz == "C" and s in ("S2", "S3"):
            return tag(4, 2.5) if big else tag(3, 2.5)
        if hz in ("D", "E") and s in ("S0", "S1"):
            return tag(2, 2.5) if big else tag(1, 2.5)
    if b == "IV":
        if hz in ("A", "B") and s == "S0":
            return tag(3, 2.5) if big else tag(2, 2.5)
        if hz == "C" and s in ("S0", "S1"):
            return tag(2, 5) if big else tag(2, 2.5)
        if hz == "C" and s in ("S2", "S3"):
            return tag(4, 2.5) if big else tag(3, 2.5)
        if hz in ("D", "E"):
            return tag(2, 2) if big else tag(1, 2.5)
    if b == "V":
        if hz == "C":
            return tag(2, 5) if big else tag(2, 2.5)
        if hz in ("D", "E"):
            return tag(2, 2.5) if big else tag(1, 2.5)
    return {"err": f"Tổ hợp bậc {b} / hạng {hz} / cấp {s} không có trong Bảng 1 TCVN 14496 — kiểm tra lại dữ liệu."}


def _tra_bang_8(payload):
    """Bảng 8 QCVN 06, mục 2 — cấp nước ngoài nhà."""
    floors = _num(payload, "floors")
    volume = _num(payload, "volume")
    vk = volume / 1000
    if floors <= 3:
        row = [10, 10, 15, 20, 25]
    elif floors <= 12:
        row = [10, 15, 20, 25, 30]
    elif floors <= 16:
        row = [None, 20, 25, 30, 35]
    else:
        row = [None, 25, 30, 30, 35]
    idx = 0 if vk <= 1 else 1 if vk <= 5 else 2 if vk <= 25 else 3 if vk <= 50 else 4
    q = row[idx]
    if q is None:
        return {"err": "Tổ hợp số tầng/khối tích không quy định trong Bảng 8 (dấu —) — kiểm tra lại dữ liệu."}
    floors_label = "≤ 3" if floors <= 3 else "> 3 đến ≤ 12" if floors <= 12 else "> 12 đến ≤ 16" if floors <= 16 else "> 16"
    return {"Q": q, "muc": f"Bảng 8 QCVN 06, mục 2 (nhóm F1.1/F2/F3/F4; {floors_label} tầng; V {_fmt(volume)} m³)"}


def _he_so_psi_14496(h):
    """Bảng 2 TCVN 14496 — hệ số thay đổi chiều cao gian phòng ψ."""
    return 0 if h <= 6.4 else 0.06


def _tinh_14496_1tang(payload):
    """Chế độ A — Điều 5: 1 tầng đầu phun."""
    g = payload.get("nhomNC14496")
    if g not in ("5", "6"):
        return {"err": "Chế độ 1 tầng đầu phun (Điều 5) chỉ áp dụng cho nhóm nguy cơ cháy 5 hoặc 6 (Phụ lục B TCVN 7336)."}
    h = _num_or_none(payload, "hXepM")
    h = 0.0 if h is None else h
    H = _num_or_none(payload, "hGianPhong")
    H = 0.0 if H is None else H
    N = _num_or_none(payload, "soDauPhun90")
    if H > 14:
        return {"err": f"Chiều cao gian phòng H = {_fmt(H)} m > 14 m — vượt phạm vi Điều 5 (áp dụng H ≤ 14 m). Dùng chế độ nhiều tầng đầu phun (Điều 6)."}
    if h > 12.5:
        return {"err": f"Chiều cao xếp hàng h = {_fmt(h)} m > 12,5 m — vượt phạm vi Điều 5 (áp dụng h ≤ 12,5 m). Dùng chế độ nhiều tầng đầu phun (Điều 6)."}
    if h < 5.5:
        return {"err": f"Chiều cao xếp hàng h = {_fmt(h)} m ≤ 5,5 m — thuộc phạm vi TCVN 7336 (kho thường), không thuộc TCVN 14496."}
    q55 = 5.3 if g == "5" else 6.5
    psi = _he_so_psi_14496(H)
    qcd = (q55 + 0.19 * (h - 5.5)) * (1 + psi * (H - 10))
    ghichu = []
    if N is None:
        ghichu.append("Chưa nhập số đầu phun trong diện tích tính toán 90 m² — Qs chỉ dừng ở lưu lượng 1 đầu phun chủ đạo.")
        return {"qcd": qcd, "psi": psi, "Qs": None, "ghichu": ghichu, "q55": q55}
    Qs = qcd * N
    return {"qcd": qcd, "psi": psi, "Qs": Qs, "N": N, "ghichu": ghichu, "q55": q55}


def _tinh_14496_nhieutang(payload):
    """Chế độ B — Điều 6: nhiều tầng đầu phun. Đọc field hXepM2 (field riêng
    của form cho chế độ này) — đã sửa lỗi mapping từng đọc nhầm hXepM (field
    của chế độ 1 tầng đầu phun, Điều 5). Không đổi công thức/ngưỡng, chỉ sửa
    đúng nguồn dữ liệu đầu vào."""
    h = _num_or_none(payload, "hXepM2")
    h_check = h if h is not None else 0.0
    if h_check < 5.5:
        return {"err": "Chiều cao xếp hàng h ≤ 5,5 m — thuộc phạm vi TCVN 7336, không thuộc TCVN 14496."}
    if h_check > 25:
        return {"err": f"Chiều cao xếp hàng h = {_fmt(h_check)} m > 25 m — vượt phạm vi áp dụng TCVN 14496 (tối đa 25 m)."}
    h = h_check
    A = A_PALLET_14496.get(payload.get("loaiPallet14496"))
    B = _num_or_none(payload, "chieuRongKeB")
    n = _num_or_none(payload, "soTamChan")
    i_bang = I_KEHANG_14496.get(payload.get("loaiHang14496"))
    dai = payload.get("daiCaoDo14496")
    i = i_bang.get(dai) if i_bang else None
    errs = []
    if A is None:
        errs.append("Loại pallet")
    if B is None or B <= 0:
        errs.append("Chiều rộng tối đa kệ hàng B")
    if n is None or n <= 0:
        errs.append("Số tấm chắn n")
    if not i:
        errs.append("Loại hàng lưu trữ / dải cao độ")
    if errs:
        return {"err": "Thiếu dữ liệu để tính Qi (không gian kệ hàng): " + ", ".join(errs) + "."}
    Qi = A * B * n * i
    iD = 0.12 if h <= 16 else 0.18
    Sd = _num_or_none(payload, "dienTichMai90")
    if Sd is None:
        Sd = 90
    Qd = iD * Sd
    Qs = Qi + Qd
    return {
        "Qi": Qi, "Qd": Qd, "Qs": Qs, "A": A, "B": B, "n": n, "i": i, "iD": iD, "Sd": Sd,
        "muc_i": f"Bảng 6 TCVN 14496 ({_LOAI_HANG_LABEL.get(payload.get('loaiHang14496'))}, dải {_DAI_CAO_DO_LABEL.get(dai)})",
    }


def _tra_sprinkler(payload):
    g = payload.get("nhomNC")
    if g in ("4.2", "7"):
        S = _num(payload, "botS")
        J = _num(payload, "botJ")
        t = _num(payload, "botT")
        K = _num(payload, "botK")
        CB = _num(payload, "botCB")
        Qct = S * J
        Wdd = K * Qct * t * 60
        Wctb = Wdd * CB / 100
        Wnuoc = Wdd * (100 - CB) / 100
        muc_nhom = "Bảng 1 TCVN 7336 (nhóm 4.2 — khí cháy/xăng/cồn)" if g == "4.2" else "Bảng 2 TCVN 7336 (nhóm 7 — kho vecni, sơn, chất lỏng cháy)"
        return {"foam": True, "S": S, "J": J, "t": t, "K": K, "CB": CB, "Qct": Qct, "Wdd": Wdd, "Wctb": Wctb, "Wnuoc": Wnuoc,
                "muc": f"{muc_nhom}; công thức bọt theo TCVN 5307"}
    if g in ("5", "6"):
        if payload.get("hXep") == "cao":
            res = _tinh_14496_1tang(payload) if payload.get("phuongAn14496") == "1tang" else _tinh_14496_nhieutang(payload)
            if res.get("err"):
                return {"err": res["err"]}
            return {"kecao": True, "phuongAn": payload.get("phuongAn14496"), "res": res}
        hxep = payload.get("hXep")
        nhom_bang = B2_7336.get(g, {})
        Q = nhom_bang.get(hxep)
        if Q is None:
            return {"err": f"Chưa chọn dải chiều cao xếp hàng hợp lệ (Bảng 2 TCVN 7336, nhóm {g}) để tính lưu lượng chữa cháy tự động."}
        return {"Q": Q, "t": 60, "muc": f"Bảng 2 TCVN 7336 (nhóm {g}, chiều cao xếp hàng {_HXEP_LABEL.get(hxep)}); t = 60 phút (Bảng 1)"}
    hb = _num_or_none(payload, "hBaoVe")
    if hb is not None and hb >= 10:
        if hb > 20:
            return {"err": "Chiều cao khu vực bảo vệ > 20 m: ngoài phạm vi Bảng 3 TCVN 7336 — tính riêng."}
        row = next((r for r in B3_7336 if hb <= r[0]), None)
        b1 = B1_7336.get(g)
        if row is None or b1 is None:
            return {"err": f"Chưa chọn nhóm nguy cơ cháy hợp lệ (Phụ lục A TCVN 7336) để tra Bảng 3 chữa cháy tự động."}
        Q = row[1].get(g)
        if Q is None:
            return {"err": f"Nhóm nguy cơ cháy {g} không có trong Bảng 3 TCVN 7336 ở dải chiều cao ≤ {row[0]} m — kiểm tra lại dữ liệu."}
        return {"Q": Q, "t": b1["t"], "muc": f"Bảng 3 TCVN 7336 (nhóm {g}, chiều cao khu vực bảo vệ {_fmt(hb)} m thuộc dải ≤ {row[0]} m); t theo Bảng 1"}
    b = B1_7336.get(g)
    if b is None:
        return {"err": "Chưa chọn nhóm nguy cơ cháy hợp lệ (Phụ lục A TCVN 7336) để tra Bảng 1 chữa cháy tự động."}
    note = ("Chú thích 4 Bảng 1: nhóm 2 có tải trọng cháy > 1.400 MJ/m² phải tăng ≥ 1,5 lần; > 2.200 MJ/m² tăng ≥ 2,5 lần"
            " — xác nhận tải trọng cháy khi thiết kế.") if g == "2" else None
    return {"Q": b["Q"], "t": b["t"], "muc": f"Bảng 1 TCVN 7336 (nhóm {g}: lưu lượng tối thiểu {b['Q']} L/s, thời gian {b['t']} phút)", "note": note}


def evaluate_nuoc(payload):
    """Tổng hợp tính nước — tương đương evalNuoc(d, sp, hn, nn) trong JS.
    Tự gọi evaluate_sprinkler/evaluate_hong_nuoc/evaluate_ngoai_nha (cụm hệ
    thống bắt buộc) để lấy sp/hn/nn, đúng như render() trong JS làm trước
    khi gọi evalNuoc."""
    validate_payload(payload)
    try:
        sp_result = evaluate_sprinkler(payload)
        hn_result = evaluate_hong_nuoc(payload)
        nn_result = evaluate_ngoai_nha(payload)
    except HeThongBatBuocInputError as exc:
        raise NuocChuaChayInputError(str(exc)) from exc

    trich, freeze, notes, errs = [], [], [], []
    kq = {"Vtn": None, "Vnn": None, "Vtd": None, "Qtn": None, "Qnn": None, "Qtd": None, "tTn": None, "tTd": None}

    occ = payload.get("occ")
    nhom_nc = payload.get("nhomNC")
    h_xep = payload.get("hXep")

    is_bot_group = nhom_nc in ("4.2", "7")
    is_ke_cao_group = nhom_nc in ("5", "6") and h_xep == "cao"
    co_spr = sp_result["result"] == "yes" or bool(payload.get("tangCuong")) or is_bot_group or is_ke_cao_group

    kq_bot = {"Wdd": None, "Wctb": None, "Wnuoc": None, "Qct": None}

    spr_res = None
    if co_spr:
        spr_res = _tra_sprinkler(payload)
        if spr_res.get("err"):
            errs.append(spr_res["err"])
        elif spr_res.get("foam"):
            kq_bot.update(Qct=spr_res["Qct"], Wdd=spr_res["Wdd"], Wctb=spr_res["Wctb"], Wnuoc=spr_res["Wnuoc"])
            kq["tTd"] = spr_res["t"]
            trich.append(["Lưu lượng dung dịch bọt Q_ct = S × J",
                           f"{_nf1(spr_res['Qct'])} L/s (S={_fmt(spr_res['S'])} m² × J={_nf2(spr_res['J'])})", spr_res["muc"]])
            trich.append(["Thời gian phun bọt t", f"{spr_res['t']} phút", spr_res["muc"]])
            trich.append(["Lượng dung dịch bọt W_dd = K·Q_ct·t·60",
                           f"{_nf2(spr_res['Wdd']/1000)} m³ (K={_nf1(spr_res['K'])})", "TCVN 5307, Phụ lục B"])
            trich.append([f"→ Chất tạo bọt đậm đặc (C_B={_fmt(spr_res['CB'])}%)", f"{_fmt(round(spr_res['Wctb']))} L", "TCVN 7278-3"])
            trich.append([f"→ Nước pha bọt ({_fmt(100-spr_res['CB'])}%)", f"{_nf2(spr_res['Wnuoc']/1000)} m³", "—"])
            notes.append(f"Nhóm nguy cơ {nhom_nc} dùng hệ chữa cháy bằng BỌT (không phải sprinkler nước). Cường độ J, thời "
                         "gian t tra Bảng 1/2 TCVN 7336 theo loại chất cháy cụ thể — giá trị đang dùng là mặc định/người "
                         "dùng nhập, cần đối chiếu khi thiết kế.")
        elif spr_res.get("kecao"):
            r = spr_res["res"]
            if spr_res["phuongAn"] == "1tang":
                kq["Qtd"] = r["Qs"]
                kq["tTd"] = 60
                trich.append(["Lưu lượng đầu phun chủ đạo qcđ = [q5,5+0,19(h−5,5)]×[1+ψ(H−10)]",
                               f"{_nf2(r['qcd'])} L/s (q5,5={r['q55']}, ψ={r['psi']})", "TCVN 14496, Điều 5.6–5.7"])
                if r["Qs"] is not None:
                    trich.append(["Lưu lượng Qs = qcđ × N đầu phun (90 m²)", f"{_nf2(r['Qs'])} L/s (N={r['N']})", "TCVN 14496, Điều 5.10"])
                trich.append(["Thời gian cấp nước tối thiểu", "60 phút", "TCVN 14496, Điều 4.8"])
                for x in r["ghichu"]:
                    notes.append(x)
                notes.append("Chế độ 1 tầng đầu phun (Điều 5): chỉ áp dụng nhóm nguy cơ 5/6, chiều cao gian phòng ≤ 14 m, "
                             "chiều cao xếp hàng ≤ 12,5 m.")
            else:
                kq["Qtd"] = r["Qs"]
                kq["tTd"] = 60
                trich.append(["Lưu lượng trong không gian kệ hàng Qi = A×B×n×i",
                               f"{_nf2(r['Qi'])} L/s (A={r['A']}, B={_fmt(r['B'])}, n={r['n']}, i={_nf2(r['i'])})", r["muc_i"]])
                trich.append(["Lưu lượng đầu phun dưới mái Qd = i_D×S_d",
                               f"{_nf2(r['Qd'])} L/s (i_D={_nf2(r['iD'])}, S_d={_fmt(r['Sd'])} m²)", "TCVN 14496, Điều 6.6"])
                trich.append(["Lưu lượng Qs = Qi + Qd", f"{_nf2(r['Qs'])} L/s", "TCVN 14496, Điều 6.13"])
                trich.append(["Thời gian cấp nước tối thiểu", "60 phút", "TCVN 14496, Điều 4.8"])
                notes.append("Chế độ nhiều tầng đầu phun (Điều 6): áp dụng chiều cao xếp hàng đến 25 m. Kiểm tra thêm bố "
                             "trí tấm chắn, khoảng cách đầu phun theo Điều 6.7–6.17.")
            notes.append("Kho kệ cao TCVN 14496: Vtd trong bảng dưới là dung tích cho hệ sprinkler kệ cao (Qs), CHƯA gồm "
                         "màn nước Qd (Điều 4.19–4.22, nếu có) — cộng thêm thủ công nếu công trình có màn nước.")
        else:
            kq["Qtd"] = spr_res["Q"]
            kq["tTd"] = spr_res["t"]
            trich.append(["Lưu lượng chữa cháy tự động Qtđ", f"{spr_res['Q']} L/s", spr_res["muc"]])
            trich.append(["Thời gian phun ttđ", f"{spr_res['t']} phút", spr_res["muc"]])
            if spr_res.get("note"):
                notes.append(spr_res["note"])
            if sp_result["result"] != "yes" and payload.get("tangCuong"):
                notes.append('Sprinkler được tính theo yêu cầu người dùng (tick "Có tính toán hệ thống sprinkler") dù '
                             "công trình không thuộc diện bắt buộc chữa cháy tự động theo Bảng A.1.")

    tinh_hong = hn_result["result"] == "yes" or occ in ("sanxuat", "kho")
    if tinh_hong:
        if is_ke_cao_group:
            b = _tra_bang_1_14496(payload)
        elif occ in ("sanxuat", "kho"):
            b = _tra_bang_12(payload)
        else:
            b = _tra_bang_11(payload)
        if b.get("err"):
            errs.append(b["err"])
        else:
            kq["Qtn"] = b["n"] * b["q"]
            if is_ke_cao_group or not co_spr:
                kq["tTn"] = 60
            else:
                kq["tTn"] = 30 if nhom_nc == "1" else 60
            trich.append(["Họng nước trong nhà", f"{b['n']} tia × {b['q']} L/s = {kq['Qtn']} L/s", b["muc"]])
            if is_ke_cao_group:
                t_note = "Kho kệ cao TCVN 14496, Điều 4.8: tối thiểu 1 giờ, không phụ thuộc có/không có màn nước và họng nước"
            elif not co_spr:
                t_note = "Không có sprinkler → t = 60 phút"
            elif nhom_nc == "1":
                t_note = "Có sprinkler, nhóm nguy cơ 1 → t = 30 phút"
            else:
                t_note = "Có sprinkler, nhóm ≠ 1 → t = 60 phút"
            trich.append(["Thời gian họng trong nhà t", f"{kq['tTn']} phút", t_note])
            if is_ke_cao_group:
                notes.append("Kho kệ cao: lưu lượng họng nước trong nhà tra Bảng 1 TCVN 14496:2025 (không dùng Bảng 12 "
                             "QCVN 06) theo Điều 4.11.")
            elif occ in ("sanxuat", "kho"):
                notes.append("Nhà SX/kho: lưu lượng họng trong nhà tra Bảng 12 QCVN 06 — áp dụng khi công trình thuộc "
                             "diện trang bị họng nước theo QCVN 06 (kỹ sư xác nhận diện).")
    else:
        notes.append("Không thuộc diện họng nước trong nhà theo sàng lọc BƯỚC 2 → Vtn: Không áp dụng / Không tính.")

    if nn_result["result"] == "yes":
        b8 = _tra_bang_8(payload)
        if b8.get("err"):
            errs.append(b8["err"])
        else:
            kq["Qnn"] = b8["Q"]
            trich.append(["Lưu lượng ngoài nhà Qnn", f"{b8['Q']} L/s", b8["muc"]])
            trich.append(["Thời gian ngoài nhà", "180 phút (3 giờ)", "Chú thích 1, 2 Bảng 8 QCVN 06"])
            notes.append("Nếu mạng cấp nước đô thị/hạ tầng khu vực đã đảm bảo lưu lượng ngoài nhà thì bể của công trình "
                         "có thể không phải dự trữ phần Vnn — kỹ sư xác nhận theo điều kiện hạ tầng thực tế.")
    else:
        notes.append("Không thuộc đối tượng cấp nước ngoài nhà theo Phụ lục C (Bảng C.1) QCVN 10 → Vnn: Không áp dụng / Không tính.")

    occ_label = _OCC_LABEL_BY_ID.get(occ, occ)
    floors_noi = _num(payload, "floorsNoi")
    semi_basements = _num(payload, "semiBasements")
    basements = _num(payload, "basements")
    floors = _num(payload, "floors")
    volume = _num(payload, "volume")
    freeze.append(["Công năng", occ_label])
    so_tang_txt = f"{_fmt(floors_noi)} tầng nổi"
    if semi_basements > 0:
        so_tang_txt += f" + {_fmt(semi_basements)} bán hầm (tính toán: {_fmt(floors)} tầng)"
    if basements > 0:
        so_tang_txt += f" + {_fmt(basements)} hầm"
    freeze.append(["Số tầng / khối tích", f"{so_tang_txt} / {_fmt(volume)} m³"])
    if co_spr:
        freeze.append(["Có sprinkler", "Có (bắt buộc theo Bảng A.1)" if sp_result["result"] == "yes" else "Có (tính theo yêu cầu người dùng)"])
    else:
        freeze.append(["Có sprinkler", "Không"])
    if nhom_nc:
        freeze.append(["Nhóm nguy cơ cháy", f"Nhóm {nhom_nc} (Phụ lục A TCVN 7336)"])

    if kq["Qtn"] is not None:
        kq["Vtn"] = kq["Qtn"] * kq["tTn"] * 60
    if kq["Qnn"] is not None:
        kq["Vnn"] = kq["Qnn"] * 180 * 60
    if kq["Qtd"] is not None:
        kq["Vtd"] = kq["Qtd"] * kq["tTd"] * 60
    kq["Vbot"] = kq_bot["Wdd"]
    kq["Vtong"] = (kq["Vtn"] or 0) + (kq["Vnn"] or 0) + (kq["Vtd"] or 0) + (kq["Vbot"] or 0)
    # Bơm chữa cháy sơ bộ — công thức tương đương dòng hiển thị ở render()
    # trong JS ("≥ Qtn + Qtđ khi các hệ trong nhà dùng chung trạm bơm"), bản
    # JS gốc chỉ hiển thị ở tầng render, không nằm trong evalNuoc() — thêm
    # vào đây để có kết quả bơm sơ bộ trong response API.
    kq["Q_bom_so_bo"] = (kq["Qtn"] + kq["Qtd"]) if (kq["Qtn"] is not None and kq["Qtd"] is not None) else None

    return {
        "trich": trich,
        "freeze": freeze,
        "kq": kq,
        "kqBot": kq_bot,
        "notes": notes,
        "errs": errs,
        "coSpr": co_spr,
        "rule_set_version": RULE_SET_VERSION,
    }
