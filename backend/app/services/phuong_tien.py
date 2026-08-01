"""BƯỚC 5 — Phương tiện & hạng mục khác.

Nguồn: QCVN 10:2025/BCA Phụ lục D (phương tiện cơ giới), Phụ lục E (dụng cụ
phá dỡ thô sơ), Phụ lục F (mặt nạ lọc độc), Phụ lục G (loa thông báo & hướng
dẫn thoát nạn); TCVN 7435-1:2004 (bình chữa cháy xách tay); TCVN 13456:2022
(đèn chiếu sáng sự cố & chỉ dẫn thoát nạn).

Port từ index.html/js/tuvan-so-bo.js (evalPhaDo, evalMatNa, evalLoa,
evalCoGioi, evalBinh, evalDen) — rule-based thuần, không dùng AI.

Batch 3 — theo quyết định của owner: đây là bản "đối chiếu song song",
production KHÔNG gọi service này — index.html/js/tuvan-so-bo.js vẫn tự tính
100% ở client. Không sửa bất kỳ ngưỡng/công thức nào so với bản JS gốc.
Công cụ chỉ mang tính hỗ trợ tham khảo — không có quyền thẩm định/phê duyệt
(xem docs/01-target-architecture.md).

Khác với cụm 1-3, cụm này có 2 hàm (evaluate_binh, evaluate_den) LUÔN trả
result="yes" — không phải quyết định ngưỡng, mà tính/liệt kê NỘI DUNG cụ thể
(số lượng bình chữa cháy theo công thức; danh sách vị trí lắp đèn sự cố +
ghi chú có điều kiện). Đây là hành vi gốc của JS, giữ nguyên y hệt.
"""

import math

from .tham_dinh import OCCUPATIONS as _OCCUPATIONS

RULE_SET_VERSION = "QCVN10-2025-BCA-PhuLucD-E-F-G_TCVN7435-1-2004_TCVN13456-2022"

_VALID_OCC_IDS = {o["id"] for o in _OCCUPATIONS}


class PhuongTienInputError(Exception):
    pass


# ---------------------------------------------------------------------------
# Validation (đúng chuẩn Batch 1 / cụm 1-3): parse an toàn, 400 thay vì 500.
# extLevel và pplFloor là 2 trường MỚI (chưa dùng ở cụm nào trước).
# ---------------------------------------------------------------------------

_FIELD_LABELS = {
    "floors": "Số tầng",
    "basements": "Số tầng hầm",
    "semiBasements": "Số tầng bán hầm",
    "totalArea": "Tổng diện tích sàn ΣF",
    "areaFloor": "Diện tích 1 tầng",
    "volume": "Khối tích V",
    "pplFloor": "Số người lớn nhất trên 1 tầng",
}

_NUMERIC_FIELDS = ("floors", "basements", "semiBasements", "totalArea", "areaFloor", "volume")

_ENUM_FIELDS = {
    "extLevel": {"auto", "thap", "tb", "cao"},
    "garaKin": {"kin", "ho"},
}

_ENUM_LABELS = {
    "extLevel": "Mức nguy hiểm cháy (dùng tính bình chữa cháy)",
    "garaKin": "Dạng nhà để xe",
}


def _fmt(n):
    n = float(n or 0)
    if n.is_integer():
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _num(payload, key, default=0.0):
    v = payload.get(key)
    if v is None or v == "":
        return default
    label = _FIELD_LABELS.get(key, key)
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise PhuongTienInputError(f"Giá trị của '{label}' phải là số, không phải {type(v).__name__}.")
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise PhuongTienInputError(f"Giá trị của '{label}' không phải là số hợp lệ: {v!r}.")
    if not math.isfinite(n):
        raise PhuongTienInputError(f"Giá trị của '{label}' không hợp lệ (NaN/Infinity).")
    if n < 0:
        raise PhuongTienInputError(f"Giá trị của '{label}' không được âm.")
    return n


def _num_or_none(payload, key):
    v = payload.get(key)
    if v is None or v == "":
        return None
    return _num(payload, key)


def _int_or_none(payload, key):
    """pplFloor: số nguyên không âm, không bắt buộc nhập."""
    n = _num_or_none(payload, key)
    if n is None:
        return None
    if not float(n).is_integer():
        label = _FIELD_LABELS.get(key, key)
        raise PhuongTienInputError(f"Giá trị của '{label}' phải là số nguyên.")
    return int(n)


def _require_valid_occ(payload):
    occ = payload.get("occ")
    if occ not in _VALID_OCC_IDS:
        raise PhuongTienInputError(f"Công năng không hợp lệ: '{occ}'.")


def validate_payload(payload):
    _require_valid_occ(payload)
    for key in _NUMERIC_FIELDS:
        _num(payload, key)
    _int_or_none(payload, "pplFloor")
    for key, allowed in _ENUM_FIELDS.items():
        v = payload.get(key)
        if v is None or v == "":
            continue
        if v not in allowed:
            raise PhuongTienInputError(f"Giá trị của '{_ENUM_LABELS[key]}' không hợp lệ: {v!r}.")


def _result(v, detail, can_cu, notes=None):
    return {
        "result": v,
        "detail": detail,
        "can_cu": can_cu,
        "notes": notes or [],
        "rule_set_version": RULE_SET_VERSION,
    }


# ---------------------------------------------------------------------------
# evaluate_pha_do — Phụ lục E, Bảng E.1 (dụng cụ phá dỡ thô sơ)
# ---------------------------------------------------------------------------
PHADO_MAP = {
    "sanxuat": "1",
    "kho": "2",
    "chungcu": "3", "khachsan": "3",
    "truso": "4", "truonghoc": "4", "yte": "4",
    "nhaga": "5",
    "karaoke": "6", "nhahat": "6",
    "tttm": "7",
}
DUNG_CU = (
    "01 bộ dụng cụ phá dỡ thô sơ: rìu (thép cacbon cao, ≥ 2 kg); xà beng (một đầu nhọn một đầu dẹt, dài ≥ 100 cm); "
    "búa (thép cacbon cao, ≥ 5 kg); kìm cộng lực (tải cắt ≥ 60 kg)."
)


def evaluate_pha_do(payload):
    validate_payload(payload)
    stt = PHADO_MAP.get(payload.get("occ"))
    if stt:
        return _result(
            "yes",
            f"Thuộc đối tượng trang bị theo Bảng E.1, mục {stt} — không phụ thuộc quy mô. Định mức: {DUNG_CU}",
            f"QCVN 10:2025/BCA, Phụ lục E, Bảng E.1, mục {stt}",
        )
    return _result(
        "no",
        "Loại nhà không nêu trong 7 mục của Bảng E.1 Phụ lục E — không thuộc đối tượng bắt buộc trang bị dụng cụ phá dỡ thô sơ theo phụ lục này.",
        "QCVN 10:2025/BCA, Phụ lục E, Bảng E.1",
    )


# ---------------------------------------------------------------------------
# evaluate_mat_na — Phụ lục F (mặt nạ lọc độc)
# ---------------------------------------------------------------------------
def evaluate_mat_na(payload):
    validate_payload(payload)
    cc = "QCVN 10:2025/BCA, Phụ lục F"
    occ = payload.get("occ")
    if occ == "khachsan":
        floors = _num(payload, "floors")
        if floors >= 3:
            return _result(
                "yes",
                "Khách sạn/nhà nghỉ/lưu trú cao ≥ 3 tầng: trang bị mặt nạ LỌC ĐỘC tại mọi tầng, định mức 01 chiếc/người "
                "(gồm khách lưu trú + nhân viên thường xuyên) (TT 1).",
                cc,
            )
        return _result("no", "Khách sạn/lưu trú dưới 3 tầng: chưa thuộc diện theo TT 1.", cc)
    if occ == "karaoke":
        return _result(
            "yes",
            "Karaoke/vũ trường: bắt buộc không phụ thuộc quy mô — mặt nạ LỌC ĐỘC mọi tầng, tính theo số người trong "
            "phòng lớn nhất của tầng, 01 chiếc/người (TT 2).",
            cc,
        )
    return _result(
        "na",
        "Loại nhà không nêu trong Phụ lục F (các mục còn lại áp dụng công nghiệp/năng lượng quy mô lớn: lọc hóa dầu, "
        "kho dầu ≥ 100.000 m³, nhiệt điện ≥ 600 MW, KCN ≥ 75 ha…).",
        cc,
    )


# ---------------------------------------------------------------------------
# evaluate_co_gioi — Phụ lục D (phương tiện chữa cháy cơ giới) — luôn "na"
# ---------------------------------------------------------------------------
def evaluate_co_gioi(payload):
    validate_payload(payload)
    cc = "QCVN 10:2025/BCA, Phụ lục D"
    occ = payload.get("occ")
    if occ in ("sanxuat", "kho"):
        return _result(
            "na",
            "Phụ lục D áp dụng chủ yếu cho kho dầu mỏ, cảng, nhà máy điện, lọc hóa dầu, KCN/cụm CN. Nhà SX/kho đơn lẻ "
            "thường không thuộc diện; nếu nằm trong KCN/cụm CN thì phương tiện cơ giới xét theo hạ tầng KCN (định mức "
            "⚠️ — đọc bản gốc khi rơi vào diện).",
            cc,
        )
    return _result(
        "na",
        "Công trình dân dụng thông thường không thuộc diện trang bị phương tiện chữa cháy cơ giới (Phụ lục D áp dụng "
        "công nghiệp/hạ tầng quy mô lớn).",
        cc,
    )


# ---------------------------------------------------------------------------
# evaluate_loa — Phụ lục G, Bảng G.1 (loa thông báo & hướng dẫn thoát nạn)
# TT1-TT4, TT6 là các điều kiện ĐỘC LẬP, có thể đạt đồng thời nhiều mục.
# ---------------------------------------------------------------------------
TT1_CONGCONG = {
    "chungcu", "truonghoc", "nhatre", "yte", "thethao", "nhahat", "baotang",
    "vanhoa", "khachsan", "cuahang", "nhahang", "truso", "buudien", "honhop", "nhaga",
}


def evaluate_loa(payload):
    validate_payload(payload)
    cc = "QCVN 10:2025/BCA, Phụ lục G"
    occ = payload.get("occ")
    notes = []
    P = _int_or_none(payload, "pplFloor")
    tt_hits = []

    if occ in TT1_CONGCONG:
        floors = _num(payload, "floors")
        basements = _num(payload, "basements")
        if floors > 10 or basements >= 2:
            tt_hits.append((1, f"Đạt ngưỡng TT 1: cao trên 10 tầng (công trình: {_fmt(floors)} tầng tính toán) hoặc có "
                               f"từ 2 tầng hầm trở lên (công trình: {_fmt(basements)} tầng hầm)."))

    if occ in ("karaoke", "nhahat", "yte"):
        if P is None:
            notes.append("TT 2 (karaoke/vũ trường, nhà hát/rạp, bệnh viện, nhà dưỡng lão): ngưỡng ≥ 50 người trên 1 "
                         "tầng — chưa khai báo số người/tầng nên chưa kiểm tra được mục này.")
        elif P >= 50:
            tt_hits.append((2, f"Đạt ngưỡng TT 2: ≥ 50 người trên 1 tầng (khai báo: {_fmt(P)} người)."))

    if occ == "garakin" and payload.get("garaKin") == "kin":
        total_area = _num(payload, "totalArea")
        if total_area >= 18000:
            tt_hits.append((3, f"Đạt ngưỡng TT 3: nhà để xe dạng kín ΣF ≥ 18.000 m² (công trình: {_fmt(total_area)} m²)."))

    if occ == "sanxuat":
        total_area = _num(payload, "totalArea")
        if P is None:
            notes.append("TT 4 (nhà sản xuất): ngưỡng ΣF ≥ 18.000 m² VÀ ≥ 300 người/tầng (đồng thời) — chưa khai báo "
                         "số người/tầng nên chưa kiểm tra được mục này.")
        elif total_area >= 18000 and P >= 300:
            tt_hits.append((4, f"Đạt điều kiện đồng thời TT 4: ΣF ≥ 18.000 m² ({_fmt(total_area)} m²) VÀ ≥ 300 "
                               f"người/tầng ({_fmt(P)} người)."))

    if occ == "nhaga":
        tt_hits.append((6, "Đạt ngưỡng TT 6: nhà ga hành khách — không phụ thuộc quy mô."))

    if tt_hits:
        stt_list = ", ".join(str(h[0]) for h in tt_hits)
        detail = " ".join(h[1] for h in tt_hits)
        return _result("yes", detail, f"{cc}, Bảng G.1, mục {stt_list}", notes)

    na_note = notes if notes else ["Không đạt ngưỡng của bất kỳ mục nào (TT 1–6) trong Bảng G.1 với dữ liệu hiện tại."]
    return _result("no", "Chưa thuộc đối tượng trang bị loa thông báo & hướng dẫn thoát nạn theo Bảng G.1 với dữ liệu hiện tại.", cc, na_note)


# ---------------------------------------------------------------------------
# evaluate_binh — TCVN 7435-1:2004 (bình chữa cháy xách tay) — luôn "yes",
# tính SỐ LƯỢNG bình theo công thức, không phải quyết định ngưỡng.
# ---------------------------------------------------------------------------
BINH_TBL = {
    "thap": {"cs": "2-A", "kc": 20, "dt": 300, "ten": "Thấp"},
    "tb": {"cs": "3-A", "kc": 20, "dt": 150, "ten": "Trung bình"},
    "cao": {"cs": "4-A", "kc": 15, "dt": 100, "ten": "Cao"},
}

# Mức nguy hiểm cháy suy ra theo công năng khi extLevel="auto" — khớp field
# "binh" trong OCCS (js/tuvan-so-bo.js, dòng 11-37).
_OCC_BINH_LEVEL = {
    "chungcu": "tb", "nhatre": "tb", "truonghoc": "thap", "yte": "tb", "khachsan": "tb",
    "truso": "thap", "honhop": "tb", "tttm": "tb", "cuahang": "tb", "nhahang": "tb",
    "karaoke": "tb", "vanhoa": "tb", "nhahat": "tb", "baotang": "tb", "thethao": "tb",
    "sanxuat": "cao", "kho": "cao", "congnghiep_dacthu": "cao", "garakin": "cao",
    "buudien": "thap", "nhaga": "tb", "sanvandong": "thap", "hatangkt": "tb",
    "hamgiaothong": "cao", "csohatnhan": "cao", "phuongtiengt": "cao",
}


def evaluate_binh(payload):
    validate_payload(payload)
    occ = payload.get("occ")
    ext_level = payload.get("extLevel") or "auto"
    auto = ext_level == "auto"
    lv = _OCC_BINH_LEVEL.get(occ) if auto else ext_level
    t = BINH_TBL.get(lv)
    if t is None:
        raise PhuongTienInputError(
            f"Không xác định được mức nguy hiểm cháy để tính bình chữa cháy (công năng: '{occ}', extLevel: '{ext_level}')."
        )
    area_floor = _num(payload, "areaFloor")
    n1 = math.ceil(area_floor / t["dt"])
    min_binh = 1 if area_floor < 100 else 2
    n = max(n1, min_binh)
    ten = t["ten"] + (" (giả thiết theo công năng — cần xác nhận)" if auto else "")
    detail = (
        f"Tầng điển hình {_fmt(area_floor)} m², mức nguy hiểm {t['ten']}{' (giả thiết)' if auto else ''}: "
        f"dự kiến ≥ {n} bình/tầng loại A, công suất tối thiểu {t['cs']}, khoảng cách di chuyển ≤ {t['kc']} m, "
        f"diện tích bảo vệ tối đa {_fmt(t['dt'])} m²/bình. Sàn tối thiểu: {min_binh} bình/tầng."
    )
    return {
        "result": "yes",
        "lv": lv,
        "ten": ten,
        "detail": detail,
        "can_cu": "TCVN 7435-1:2004, Bảng 1, mục 7.2.2 / 7.1.8",
        "notes": [
            "Số bình là DỰ KIẾN theo diện tích; bố trí thực tế theo mặt bằng để đảm bảo khoảng cách di chuyển — mặt "
            "bằng dài/ngóc ngách có thể cần nhiều hơn.",
            "Nếu có mối nguy hiểm loại B/C (chất lỏng cháy, khí): bổ sung bình theo Bảng 2 (55B/144B/233B, KC ≤ 15 m); "
            "vẫn phải đủ bình loại A (mục 7.1.6).",
            "Bố trí: dễ thấy, dễ lấy, trên lối đi/lối ra; bình ≤ 18 kg đặt đỉnh ≤ 1,5 m; > 18 kg ≤ 1,0 m; đáy cách sàn "
            "≥ 3 cm (điều 5).",
            "TCVN 7435-1 là bản 2004 — kiểm tra bản thay thế mới hơn nếu có.",
        ],
        "rule_set_version": RULE_SET_VERSION,
    }


# ---------------------------------------------------------------------------
# evaluate_den — TCVN 13456:2022 (đèn sự cố & chỉ dẫn thoát nạn) — luôn
# "yes", trả về DANH SÁCH vị trí bắt buộc + ghi chú có điều kiện.
# ---------------------------------------------------------------------------
def evaluate_den(payload):
    validate_payload(payload)
    occ = payload.get("occ")
    floors = _num(payload, "floors")
    basements = _num(payload, "basements")
    semi_basements = _num(payload, "semiBasements")
    volume = _num(payload, "volume")
    area_floor = _num(payload, "areaFloor")

    pos = [
        "Cầu thang bộ thoát nạn",
        "Đường thoát nạn, vị trí chuyển hướng, nút giao hành lang",
        "Vị trí thay đổi cao độ",
        "Cửa / lối ra thoát nạn",
        "Phòng trạm biến áp, máy phát, kỹ thuật thang máy, gian lánh nạn (nếu có)",
        "Phòng trực điều khiển chống cháy, phòng bơm chữa cháy, vị trí đặt phương tiện PCCC",
        "Gian phòng có người làm việc mà điểm xa nhất → lối ra > 13 m",
    ]
    if occ == "garakin" or basements > 0 or semi_basements > 0:
        pos.insert(4, "Gara / tầng hầm, bán hầm để xe")

    notes = [
        "Nguồn dự phòng duy trì ≥ 120 phút (mục 4.5); độ rọi đường thoát nạn ≥ 1 lux tại tim đường, gian phòng ≥ 0,5 "
        "lux (5.1.2–5.1.3).",
        'Biển báo "LỐI RA/EXIT" nền xanh lá chữ trắng; khoảng cách giữa các biển ≤ 25 m (5.2.6); biển chỉ hướng tại vị '
        "trí tầm nhìn che khuất.",
        "Số lượng đèn/biển chính xác phụ thuộc mặt bằng bố trí — cần bản vẽ để định vị.",
    ]
    if occ == "khachsan" and floors >= 7:
        notes.insert(0, "Khách sạn ≥ 7 tầng: bổ sung BIỂN TẦM THẤP tại tầng có phòng nghỉ (đáy biển 150–200 mm so "
                        "sàn, khoảng cách ≤ 10 m) (5.2.3) và sơ đồ thoát nạn tại mọi phòng nghỉ (5.2.9).")
    elif occ == "khachsan":
        notes.insert(0, "Cơ sở lưu trú: sơ đồ thoát nạn tại mọi phòng nghỉ (5.2.9).")
    if volume >= 5000:
        notes.append("Khối tích ≥ 5.000 m³: nếu có hành lang thoát nạn > 10 m thì thuộc diện biển tầm thấp (5.2.3) — "
                     "cần xác nhận chiều dài hành lang.")
    if area_floor > 1000:
        notes.append(f"Tầng > 1.000 m² (tầng điển hình {_fmt(area_floor)} m²): bắt buộc SƠ ĐỒ CHỈ DẪN THOÁT NẠN tại "
                     "tầng, kích thước ≥ 600×400 mm, mép dưới cao 1,5 ± 0,2 m (5.2.9).")
    else:
        notes.append("Tầng có ≥ 2 lối ra thoát nạn: bắt buộc sơ đồ chỉ dẫn thoát nạn tại tầng (5.2.9) — xác nhận theo mặt bằng.")

    return {
        "result": "yes",
        "pos": pos,
        "notes": notes,
        "can_cu": "TCVN 13456:2022, mục 4.5, 5.1.1–5.1.6, 5.2",
        "rule_set_version": RULE_SET_VERSION,
    }
