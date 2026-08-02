"""BƯỚC 2 — Hệ thống PCCC bắt buộc (QCVN 10:2025/BCA — Bảng A.1, Bảng A.3,
Phụ lục B, Phụ lục C).

Port từ index.html/js/tuvan-so-bo.js (evalBaoChay, evalA3, evalSprinkler,
evalHongNuoc, evalNgoaiNha) — rule-based thuần, không dùng AI.

Batch 3 — theo quyết định của owner: đây là bản "đối chiếu song song"
(golden-test khoá lại đúng ngưỡng đang chạy ở JS), production hiện KHÔNG gọi
service này — index.html/js/tuvan-so-bo.js vẫn tự tính 100% ở client. Không
sửa bất kỳ ngưỡng nào so với bản JS gốc. Công cụ chỉ mang tính hỗ trợ tham
khảo — không có quyền thẩm định/phê duyệt (xem docs/01-target-architecture.md).

Batch 3 (bổ sung validation, đúng chuẩn Batch 1): mọi trường số parse an
toàn qua _num() (chặn NaN/Infinity/kiểu sai/số âm -> HeThongBatBuocInputError,
route đổi thành 400), và occ được đối chiếu với danh mục công năng chung
(tham_dinh.OCCUPATIONS) trước khi tính — occ lạ cũng trả 400 thay vì lặng lẽ
trả "na".

Batch 3 (review lần 2 — đóng validation hole): validate_payload() kiểm tra
TOÀN BỘ trường số đã biết có mặt trong payload (không chỉ những trường mà
nhánh occ hiện tại thực sự đọc tới) và toàn bộ enum liên quan (hazard, các
trường gara) nếu người dùng có gửi — không bắt buộc các trường không áp
dụng cho công năng của họ (bỏ trống/None/"" luôn hợp lệ). Route phải tự
kiểm tra JSON gốc là object trước khi gọi bất kỳ hàm nào ở đây.
"""

import math

from .tham_dinh import OCCUPATIONS as _OCCUPATIONS

RULE_SET_VERSION = "QCVN10-2025-BCA"

_VALID_OCC_IDS = {o["id"] for o in _OCCUPATIONS}

# Toàn bộ trường số cụm này có thể dùng tới (tuỳ nhánh công năng) - validate
# hết nếu có mặt trong payload, bất kể nhánh occ hiện tại có đọc tới hay không.
_NUMERIC_FIELDS = (
    "floors", "totalArea", "areaFloor", "hFire",
    "basements", "semiBasements", "kids", "seats",
)

_FIELD_LABELS = {
    "floors": "Số tầng",
    "totalArea": "Tổng diện tích sàn ΣF",
    "areaFloor": "Diện tích 1 tầng (gian phòng)",
    "hFire": "Chiều cao PCCC",
    "basements": "Số tầng hầm",
    "semiBasements": "Số tầng bán hầm",
    "kids": "Số trẻ (cháu)",
    "seats": "Số chỗ ngồi / khán đài",
}

# Enum liên quan tới cụm này - chỉ validate khi người dùng có gửi giá trị
# (không bắt buộc nhập cho công năng không áp dụng).
_ENUM_FIELDS = {
    "hazard": {"A", "B", "C", "D", "E"},
    "garaKin": {"kin", "ho"},
    "garaKC12": {"le12", "gt12"},
    "garaBcl": {"I", "II", "III", "IV", "V"},
    "garaCapS": {"S0", "S1", "S2", "S3"},
}

_ENUM_LABELS = {
    "hazard": "Hạng nguy hiểm cháy nổ",
    "garaKin": "Dạng nhà để xe",
    "garaKC12": "Khoảng cách đến cạnh để hở (gara)",
    "garaBcl": "Bậc chịu lửa (gara)",
    "garaCapS": "Cấp nguy hiểm cháy kết cấu (gara)",
}


class HeThongBatBuocInputError(Exception):
    pass


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
        raise HeThongBatBuocInputError(f"Giá trị của '{label}' phải là số, không phải {type(v).__name__}.")
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise HeThongBatBuocInputError(f"Giá trị của '{label}' không phải là số hợp lệ: {v!r}.")
    if not math.isfinite(n):
        raise HeThongBatBuocInputError(f"Giá trị của '{label}' không hợp lệ (NaN/Infinity).")
    if n < 0:
        raise HeThongBatBuocInputError(f"Giá trị của '{label}' không được âm.")
    return n


def _require_valid_occ(payload):
    occ = payload.get("occ")
    if occ not in _VALID_OCC_IDS:
        raise HeThongBatBuocInputError(f"Công năng không hợp lệ: '{occ}'.")


def validate_payload(payload):
    """Validate toàn bộ payload MỘT LẦN, trước khi chạy bất kỳ rule nào -
    đảm bảo trường số sai ở nhánh công năng khác vẫn bị chặn (không chỉ
    trường mà occ hiện tại thực sự dùng tới)."""
    _require_valid_occ(payload)
    for key in _NUMERIC_FIELDS:
        _num(payload, key)
    for key, allowed in _ENUM_FIELDS.items():
        v = payload.get(key)
        if v is None or v == "":
            continue
        if v not in allowed:
            raise HeThongBatBuocInputError(f"Giá trị của '{_ENUM_LABELS[key]}' không hợp lệ: {v!r}.")


def _result(v, detail, can_cu, notes=None):
    return {
        "result": v,
        "detail": detail,
        "can_cu": can_cu,
        "notes": notes or [],
        "rule_set_version": RULE_SET_VERSION,
    }


def _has_basement(payload):
    return _num(payload, "basements") > 0 or _num(payload, "semiBasements") > 0


# ---------------------------------------------------------------------------
# Bảng A.3 — gian phòng SX/kho theo hạng nguy hiểm cháy nổ & vị trí
# (dùng chung cho báo cháy và chữa cháy tự động — for_sprinkler phân biệt cột)
# ---------------------------------------------------------------------------
def _eval_a3(payload, for_sprinkler=False):
    hz = payload.get("hazard")
    F = _num(payload, "areaFloor")
    B = _has_basement(payload)
    is_kho = payload.get("occ") == "kho"
    cc = lambda s: f"QCVN 10:2025/BCA, Bảng A.3, mục {s}"

    if is_kho:
        if hz in ("A", "B"):
            if for_sprinkler:
                return _result("yes", f"Kho hạng {hz}: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("1.1")) if F >= 300 \
                    else _result("no", f"Kho hạng {hz}: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("1.1"))
            return _result("yes", f"Kho hạng {hz}: bắt buộc báo cháy tự động, không phụ thuộc diện tích.", cc("1.1"))
        if hz == "C":
            if B:
                return _result("yes", "Kho hạng C tại tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.", cc("1.4.1"))
            if for_sprinkler:
                return _result("yes", "Kho hạng C trên mặt đất: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("1.4.2")) if F >= 300 \
                    else _result("no", "Kho hạng C trên mặt đất: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("1.4.2"))
            return _result("yes", "Kho hạng C trên mặt đất: đạt ngưỡng diện tích gian phòng ≥ 500 m² (báo cháy tự động).", cc("1.4.2")) if F >= 500 \
                else _result("no", "Kho hạng C trên mặt đất: chưa đạt ngưỡng diện tích gian phòng ≥ 500 m² (báo cháy tự động).", cc("1.4.2"))
        return _result("na", "Kho hạng D, E: Bảng A.3 chỉ quy định cụ thể cho hạng A, B, C (mục 1.1–1.5) — hạng D, E đối chiếu thêm mục 1.5/1.6 hoặc xin ý kiến kỹ sư.", cc("1"))

    # Nhà sản xuất — gian phòng theo hạng nguy hiểm cháy nổ
    if hz in ("A", "B"):
        if for_sprinkler:
            return _result("yes", f"Xưởng SX hạng {hz}: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("2.1")) if F >= 300 \
                else _result("no", f"Xưởng SX hạng {hz}: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("2.1"))
        return _result("yes", f"Xưởng SX hạng {hz}: bắt buộc báo cháy tự động, không phụ thuộc diện tích.", cc("2.1"))
    if hz == "C":
        if B:
            return _result("yes", "Xưởng SX hạng C tại tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích (báo cháy và chữa cháy tự động).", cc("2.2.1/2.3.1"))
        if for_sprinkler:
            return _result("yes", "Xưởng SX hạng C trên mặt đất: đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("2.2.2")) if F >= 300 \
                else _result("no", "Xưởng SX hạng C trên mặt đất: chưa đạt ngưỡng diện tích gian phòng ≥ 300 m² (chữa cháy tự động).", cc("2.2.2"))
        return _result("yes", "Xưởng SX hạng C trên mặt đất: bắt buộc báo cháy tự động, không phụ thuộc diện tích.", cc("2.2.2"))
    return _result("na", "Xưởng SX hạng D, E: Bảng A.3 mục 2 chủ yếu quy định cho hạng C1–C3 (mục 2.2–2.4) — hạng D, E cần đối chiếu thêm hoặc xin ý kiến kỹ sư.", cc("2"))


def evaluate_gian_phong_bao_chay(payload):
    """Dòng "Đối với gian phòng" (báo cháy) trong Form A — tách riêng khỏi
    evaluate_bao_chay() ("Đối với nhà") vì Form A coi đây là 2 dòng "Đối
    tượng trang bị" độc lập, không dùng chung 1 kết quả."""
    validate_payload(payload)
    if payload.get("occ") not in ("sanxuat", "kho"):
        return _result(
            "na",
            "Bảng A.3 chỉ quy định cho nhà sản xuất/kho — công năng khác không thuộc phạm vi bảng này "
            "(không có nghĩa là không cần báo cháy, xem dòng 'Đối với nhà').",
            "QCVN 10:2025/BCA, Bảng A.3",
        )
    return _eval_a3(payload, for_sprinkler=False)


def evaluate_gian_phong_sprinkler(payload):
    """Dòng "Đối với gian phòng" (chữa cháy tự động) trong Form A — tương tự
    evaluate_gian_phong_bao_chay() nhưng cho hệ sprinkler."""
    validate_payload(payload)
    if payload.get("occ") not in ("sanxuat", "kho"):
        return _result(
            "na",
            "Bảng A.3 chỉ quy định cho nhà sản xuất/kho.",
            "QCVN 10:2025/BCA, Bảng A.3",
        )
    return _eval_a3(payload, for_sprinkler=True)


def _eval_garakin_bao_chay(payload):
    F = _num(payload, "totalArea")
    T = _num(payload, "floors")
    B = _has_basement(payload)
    cc = lambda s: f"QCVN 10:2025/BCA, Bảng A.1, STT {s}"
    if B or T >= 2:
        return _result("yes", "Dạng kín có tầng hầm/bán hầm hoặc trên mặt đất ≥ 2 tầng: bắt buộc, không phụ thuộc diện tích.", cc("25.1"))
    if payload.get("garaKin") == "ho":
        if payload.get("garaKC12") == "le12":
            return _result("yes", "Dạng hở, khoảng cách đến cạnh để hở ≤ 12 m: đạt ngưỡng ΣF ≥ 4.000 m² hoặc cao ≥ 4 tầng.", cc("25.3.1")) if (F >= 4000 or T >= 4) \
                else _result("no", "Dạng hở, khoảng cách ≤ 12 m: chưa đạt ngưỡng ΣF ≥ 4.000 m² và cao ≥ 4 tầng.", cc("25.3.1"))
        return _result("yes", "Dạng hở, khoảng cách đến cạnh để hở > 12 m: bắt buộc, không phụ thuộc diện tích.", cc("25.3.2"))
    b, s = payload.get("garaBcl"), payload.get("garaCapS")
    if b in ("I", "II", "III") and s == "S0":
        return _result("yes", "Bậc I/II/III, cấp S0: đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.1")) if F >= 2000 else _result("no", "Bậc I/II/III, cấp S0: chưa đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.1"))
    if b in ("I", "II", "III") and s == "S1":
        return _result("yes", "Bậc I/II/III, cấp S1: đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.2")) if F >= 2000 else _result("no", "Bậc I/II/III, cấp S1: chưa đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.2"))
    if b in ("IV", "V") and s == "S0":
        return _result("yes", "Bậc IV/V, cấp S0: đạt ngưỡng ΣF ≥ 1.000 m².", cc("25.2.3")) if F >= 1000 else _result("no", "Bậc IV/V, cấp S0: chưa đạt ngưỡng ΣF ≥ 1.000 m².", cc("25.2.3"))
    if b in ("IV", "V") and s == "S1":
        return _result("yes", "Bậc IV/V, cấp S1: đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.4")) if F >= 2000 else _result("no", "Bậc IV/V, cấp S1: chưa đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.4"))
    if b in ("IV", "V") and s in ("S2", "S3"):
        return _result("yes", "Bậc IV/V, cấp S2/S3: đạt ngưỡng ΣF ≥ 1.000 m².", cc("25.2.5")) if F >= 1000 else _result("no", "Bậc IV/V, cấp S2/S3: chưa đạt ngưỡng ΣF ≥ 1.000 m².", cc("25.2.5"))
    return _result("warn", "Dạng kín 1 tầng nổi: cần bổ sung bậc chịu lửa, cấp kết cấu S (hoặc dạng hở/khoảng cách cạnh hở) để tra đúng mục 25.2/25.3.", cc("25.2/25.3"))


def evaluate_bao_chay(payload):
    validate_payload(payload)
    occ = payload.get("occ")
    F = _num(payload, "totalArea")
    T = _num(payload, "floors")
    B = _has_basement(payload)
    cc = lambda s: f"QCVN 10:2025/BCA, Bảng A.1, STT {s}"

    if occ == "chungcu":
        notes = ["Cho phép dùng thiết bị báo cháy độc lập khi < 5 tầng và < 1.500 m²."] if (T < 5 and F < 1500) else []
        return _result("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 700 m².", cc(3), notes) if (T >= 5 or F >= 700) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 700 m².", cc(3))
    if occ == "nhatre":
        kids = _num(payload, "kids")
        notes = ["Cho phép thiết bị báo cháy độc lập khi ΣF < 500 m²."] if F < 500 else []
        return _result("yes", "Đạt ngưỡng: ≥ 100 cháu hoặc ΣF ≥ 300 m².", cc(4), notes) if (kids >= 100 or F >= 300) \
            else _result("no", "Chưa đạt ngưỡng ≥ 100 cháu và ΣF ≥ 300 m².", cc(4))
    if occ == "truonghoc":
        return _result("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 1.500 m².", cc(5)) if (T >= 5 or F >= 1500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 1.500 m².", cc(5))
    if occ == "yte":
        return _result("yes", "Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 300 m².", cc(6)) if (T >= 3 or F >= 300) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 300 m².", cc(6))
    if occ == "thethao":
        seats = _num(payload, "seats")
        return _result("yes", "Đạt ngưỡng: ΣF ≥ 500 m² hoặc khán đài ≥ 200 chỗ.", cc(8)) if (F >= 500 or seats >= 200) \
            else _result("no", "Chưa đạt ngưỡng ΣF ≥ 500 m² và khán đài ≥ 200 chỗ.", cc(8))
    if occ == "nhahat":
        return _result("yes", "Đạt ngưỡng: ΣF ≥ 500 m².", cc(9)) if F >= 500 else _result("no", "Chưa đạt ngưỡng ΣF ≥ 500 m².", cc(9))
    if occ == "baotang":
        if B:
            return _result("yes", "Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.", cc("11.1"))
        if T >= 3:
            return _result("yes", "Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.", cc("11.2.2"))
        return _result("yes", "1–2 tầng: đạt ngưỡng ΣF ≥ 500 m².", cc("11.2.1")) if F >= 500 else _result("no", "1–2 tầng: chưa đạt ngưỡng ΣF ≥ 500 m².", cc("11.2.1"))
    if occ == "vanhoa":
        return _result("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 500 m².", cc(12)) if (T >= 5 or F >= 500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 500 m².", cc(12))
    if occ == "karaoke":
        return _result("yes", "Bắt buộc, không phụ thuộc diện tích (mọi trường hợp karaoke/vũ trường).", cc(13))
    if occ == "tttm":
        return _result("yes", "Bắt buộc, không phụ thuộc diện tích.", cc(15))
    if occ == "nhahang":
        notes = ["Cho phép thiết bị báo cháy độc lập khi < 3 tầng và < 1.500 m²."] if (T < 3 and F < 1500) else []
        return _result("yes", "Đạt ngưỡng: ΣF ≥ 500 m².", cc(16), notes) if F >= 500 else _result("no", "Chưa đạt ngưỡng ΣF ≥ 500 m².", cc(16))
    if occ == "cuahang":
        if B:
            return _result("yes", "Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.", cc("17.1"))
        notes = ["Nhà KD chất lỏng cháy/dễ cháy (trừ can, bình ≤ 20 lít): bắt buộc không phụ thuộc diện tích (STT 17.3)."]
        return _result("yes", "Trên mặt đất: đạt ngưỡng cao ≥ 3 tầng hoặc ΣF ≥ 300 m².", cc("17.2"), notes) if (T >= 3 or F >= 300) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 300 m².", cc("17.2"), notes)
    if occ == "khachsan":
        notes = ["Cho phép thiết bị báo cháy độc lập khi < 5 tầng và < 1.500 m²."] if (T < 5 and F < 1500) else []
        return _result("yes", "Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 700 m².", cc(18), notes) if (T >= 3 or F >= 700) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 700 m².", cc(18))
    if occ == "buudien":
        return _result("yes", "Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 500 m².", cc(19)) if (T >= 3 or F >= 500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 500 m².", cc(19))
    if occ == "truso":
        notes = ["Cho phép thiết bị báo cháy độc lập khi < 5 tầng và < 1.500 m²."] if (T < 5 and F < 1500) else []
        return _result("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 500 m².", cc(20), notes) if (T >= 5 or F >= 500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 500 m².", cc(20))
    if occ == "honhop":
        return _result("yes", "Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 500 m².", cc(21)) if (T >= 3 or F >= 500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 500 m².", cc(21))
    if occ == "nhaga":
        return _result("yes", "Đạt ngưỡng: ΣF ≥ 500 m².", cc(22)) if F >= 500 else _result("no", "Chưa đạt ngưỡng ΣF ≥ 500 m².", cc(22))
    if occ == "garakin":
        return _eval_garakin_bao_chay(payload)
    if occ in ("sanxuat", "kho"):
        return _eval_a3(payload, for_sprinkler=False)
    return _result("na", "—", "—")


def _eval_garakin_sprinkler(payload):
    F = _num(payload, "totalArea")
    T = _num(payload, "floors")
    B = _has_basement(payload)
    cc = lambda s: f"QCVN 10:2025/BCA, Bảng A.1, STT {s}"
    if B or T >= 2:
        return _result("yes", "Dạng kín có tầng hầm/bán hầm hoặc trên mặt đất ≥ 2 tầng: bắt buộc, không phụ thuộc diện tích.", cc("25.1"))
    if payload.get("garaKin") == "ho":
        if payload.get("garaKC12") == "le12":
            return _result("yes", "Dạng hở, khoảng cách đến cạnh để hở ≤ 12 m: đạt ngưỡng ΣF ≥ 4.000 m² hoặc cao ≥ 4 tầng — kiểm tra lại quy mô.", cc("25.3.1"))
        return _result("yes", "Dạng hở, khoảng cách > 12 m: đạt ngưỡng ΣF ≥ 4.000 m² hoặc cao ≥ 4 tầng.", cc("25.3.2")) if (F >= 4000 or T >= 4) \
            else _result("no", "Dạng hở, khoảng cách > 12 m: chưa đạt ngưỡng ΣF ≥ 4.000 m² và cao ≥ 4 tầng.", cc("25.3.2"))
    b, s = payload.get("garaBcl"), payload.get("garaCapS")
    if b in ("I", "II", "III") and s in ("S0", "S1"):
        return _result("yes", "Bậc I/II/III, cấp S0/S1: đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.1/25.2.2")) if F >= 2000 \
            else _result("no", "Bậc I/II/III, cấp S0/S1: chưa đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.1/25.2.2"))
    if b in ("IV", "V"):
        return _result("yes", "Bậc IV/V: đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.3/25.2.4/25.2.5")) if F >= 2000 \
            else _result("no", "Bậc IV/V: chưa đạt ngưỡng ΣF ≥ 2.000 m².", cc("25.2.3/25.2.4/25.2.5"))
    return _result("warn", "Dạng kín 1 tầng nổi: cần bổ sung bậc chịu lửa, cấp kết cấu S (hoặc dạng hở/khoảng cách cạnh hở) để tra đúng mục 25.2/25.3.", cc("25.2/25.3"))


def evaluate_sprinkler(payload):
    validate_payload(payload)
    occ = payload.get("occ")
    F = _num(payload, "totalArea")
    T = _num(payload, "floors")
    H = _num(payload, "hFire")
    B = _has_basement(payload)
    cc = lambda s: f"QCVN 10:2025/BCA, Bảng A.1, STT {s}"

    if occ == "chungcu":
        return _result("yes", f"Đạt ngưỡng: chiều cao PCCC {_fmt(H)} m so ngưỡng ≥ 30 m.", cc(3)) if H >= 30 \
            else _result("no", f"Chưa đạt ngưỡng chiều cao PCCC ≥ 30 m (công trình: {_fmt(H)} m).", cc(3))
    if occ == "nhatre":
        kids_ok = T >= 4 and F >= 5000
        return _result("yes", "Đạt ngưỡng: cao ≥ 4 tầng VÀ ΣF ≥ 5.000 m² (điều kiện đồng thời).", cc(4)) if kids_ok \
            else _result("no", "Chưa đạt điều kiện đồng thời cao ≥ 4 tầng VÀ ΣF ≥ 5.000 m².", cc(4))
    if occ == "truonghoc":
        return _result("yes", f"Đạt ngưỡng: chiều cao PCCC {_fmt(H)} m so ngưỡng ≥ 25 m.", cc(5)) if H >= 25 \
            else _result("no", f"Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m (công trình: {_fmt(H)} m).", cc(5))
    if occ == "yte":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 2.000 m².", cc(6)) if (H >= 25 or F >= 2000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 2.000 m².", cc(6))
    if occ == "thethao":
        return _result("yes", f"Đạt ngưỡng: chiều cao PCCC {_fmt(H)} m so ngưỡng ≥ 25 m.", cc(8)) if H >= 25 \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m.", cc(8))
    if occ == "nhahat":
        return _result("yes", f"Đạt ngưỡng: chiều cao PCCC {_fmt(H)} m so ngưỡng ≥ 25 m.", cc(9)) if H >= 25 \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m.", cc(9))
    if occ == "baotang":
        if B:
            return _result("yes", "Tầng hầm/bán hầm: đạt ngưỡng ΣF ≥ 200 m².", cc("11.1")) if F >= 200 else _result("no", "Tầng hầm/bán hầm: chưa đạt ngưỡng ΣF ≥ 200 m².", cc("11.1"))
        if T >= 3:
            return _result("yes", "≥ 3 tầng: đạt ngưỡng ΣF ≥ 500 m².", cc("11.2.2")) if F >= 500 else _result("no", "≥ 3 tầng: chưa đạt ngưỡng ΣF ≥ 500 m².", cc("11.2.2"))
        return _result("yes", "1–2 tầng: đạt ngưỡng ΣF ≥ 4.000 m².", cc("11.2.1")) if F >= 4000 else _result("no", "1–2 tầng: chưa đạt ngưỡng ΣF ≥ 4.000 m².", cc("11.2.1"))
    if occ == "vanhoa":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².", cc(12)) if (H >= 25 or F >= 5000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².", cc(12))
    if occ == "karaoke":
        if B:
            return _result("yes", "Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.", cc("13.1"))
        if T >= 3:
            return _result("yes", "Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.", cc("13.2.2"))
        return _result("yes", "1–2 tầng: đạt ngưỡng ΣF ≥ 500 m².", cc("13.2.1")) if F >= 500 else _result("no", "1–2 tầng: chưa đạt ngưỡng ΣF ≥ 500 m².", cc("13.2.1"))
    if occ == "tttm":
        if B:
            return _result("yes", "Tầng hầm/bán hầm: đạt ngưỡng ΣF ≥ 200 m².", cc("15.1")) if F >= 200 else _result("no", "Tầng hầm/bán hầm: chưa đạt ngưỡng ΣF ≥ 200 m².", cc("15.1"))
        if T >= 3:
            return _result("yes", "Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.", cc("15.2.2"))
        return _result("yes", "1–2 tầng: đạt ngưỡng ΣF ≥ 3.500 m².", cc("15.2.1")) if F >= 3500 else _result("no", "1–2 tầng: chưa đạt ngưỡng ΣF ≥ 3.500 m².", cc("15.2.1"))
    if occ == "nhahang":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².", cc(16)) if (H >= 25 or F >= 5000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².", cc(16))
    if occ == "cuahang":
        if B:
            return _result("yes", "Tầng hầm/bán hầm: đạt ngưỡng ΣF ≥ 200 m².", cc("17.1")) if F >= 200 else _result("no", "Tầng hầm/bán hầm: chưa đạt ngưỡng ΣF ≥ 200 m².", cc("17.1"))
        notes = ["Nhà KD chất lỏng cháy/dễ cháy (trừ can, bình ≤ 20 lít): bắt buộc không phụ thuộc diện tích (STT 17.3)."]
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 3.500 m².", cc("17.2"), notes) if (H >= 25 or F >= 3500) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 3.500 m².", cc("17.2"), notes)
    if occ == "khachsan":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².", cc(18)) if (H >= 25 or F >= 5000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².", cc(18))
    if occ == "buudien":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².", cc(19)) if (H >= 25 or F >= 5000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².", cc(19))
    if occ == "truso":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².", cc(20)) if (H >= 25 or F >= 5000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².", cc(20))
    if occ == "honhop":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 5.000 m².", cc(21)) if (H >= 25 or F >= 5000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 5.000 m².", cc(21))
    if occ == "nhaga":
        return _result("yes", "Đạt ngưỡng: chiều cao PCCC ≥ 25 m hoặc ΣF ≥ 10.000 m².", cc(22)) if (H >= 25 or F >= 10000) \
            else _result("no", "Chưa đạt ngưỡng chiều cao PCCC ≥ 25 m và ΣF ≥ 10.000 m².", cc(22))
    if occ == "garakin":
        return _eval_garakin_sprinkler(payload)
    if occ in ("sanxuat", "kho"):
        return _eval_a3(payload, for_sprinkler=True)
    return _result("na", "—", "—")


def evaluate_hong_nuoc(payload):
    validate_payload(payload)
    occ = payload.get("occ")
    F = _num(payload, "totalArea")
    T = _num(payload, "floors")
    B = _has_basement(payload)
    cc = "QCVN 10:2025/BCA, Phụ lục B"

    if occ == "chungcu":
        return _result("yes", "Đạt ngưỡng: nhà ở/công trình công cộng cao ≥ 7 tầng.", cc) if T >= 7 \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 7 tầng (nhóm nhà ở, công trình công cộng chung).", cc)
    if occ in ("honhop", "khachsan"):
        return _result("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 1.500 m².", cc) if (T >= 5 or F >= 1500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 1.500 m².", cc)
    if occ == "nhatre":
        kids = _num(payload, "kids")
        return _result("yes", "Đạt ngưỡng: ≥ 100 cháu hoặc cao ≥ 3 tầng hoặc ΣF ≥ 1.000 m².", cc) if (kids >= 100 or T >= 3 or F >= 1000) \
            else _result("no", "Chưa đạt ngưỡng ≥ 100 cháu, cao ≥ 3 tầng và ΣF ≥ 1.000 m².", cc)
    if occ in ("truonghoc", "yte"):
        return _result("yes", "Đạt ngưỡng: cao ≥ 3 tầng hoặc ΣF ≥ 600 m².", cc) if (T >= 3 or F >= 600) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 3 tầng và ΣF ≥ 600 m².", cc)
    if occ == "thethao":
        return _result("yes", "Đạt ngưỡng: cao ≥ 6 tầng hoặc ΣF ≥ 1.500 m² (nhóm văn hóa/thể thao).", cc) if (T >= 6 or F >= 1500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 6 tầng và ΣF ≥ 1.500 m².", cc)
    if occ == "nhahat":
        seats = _num(payload, "seats")
        return _result("yes", "Đạt ngưỡng: ≥ 300 chỗ ngồi hoặc ΣF ≥ 1.000 m².", cc) if (seats >= 300 or F >= 1000) \
            else _result("no", "Chưa đạt ngưỡng ≥ 300 chỗ và ΣF ≥ 1.000 m².", cc)
    if occ in ("vanhoa", "baotang", "cuahang"):
        return _result("yes", "Đạt ngưỡng: ΣF ≥ 1.500 m² (nhóm thư viện/nhà văn hóa/TT hội nghị/cửa hàng).", cc) if F >= 1500 \
            else _result("no", "Chưa đạt ngưỡng ΣF ≥ 1.500 m².", cc)
    if occ in ("truso", "buudien"):
        return _result("yes", "Đạt ngưỡng: cao ≥ 6 tầng hoặc ΣF ≥ 1.500 m².", cc) if (T >= 6 or F >= 1500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 6 tầng và ΣF ≥ 1.500 m².", cc)
    if occ == "karaoke":
        if B:
            return _result("yes", "Có tầng hầm/bán hầm: bắt buộc, không phụ thuộc diện tích.", cc)
        if T >= 3:
            return _result("yes", "Trên mặt đất ≥ 3 tầng: bắt buộc, không phụ thuộc diện tích.", cc)
        return _result("yes", "1–2 tầng: đạt ngưỡng ΣF ≥ 300 m².", cc) if F >= 300 else _result("no", "1–2 tầng: chưa đạt ngưỡng ΣF ≥ 300 m².", cc)
    if occ == "tttm":
        return _result("yes", "Chợ hạng 1, hạng 2, TTTM, siêu thị: bắt buộc, không phụ thuộc diện tích.", cc)
    if occ == "nhahang":
        return _result("yes", "Đạt ngưỡng: cao ≥ 6 tầng hoặc ΣF ≥ 1.500 m².", cc) if (T >= 6 or F >= 1500) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 6 tầng và ΣF ≥ 1.500 m².", cc)
    if occ == "nhaga":
        return _result("yes", "Đạt ngưỡng: ΣF ≥ 1.500 m².", cc) if F >= 1500 else _result("no", "Chưa đạt ngưỡng ΣF ≥ 1.500 m².", cc)
    if occ in ("sanxuat", "kho"):
        hz = payload.get("hazard")
        if hz in ("A", "B", "C", "D"):
            return _result("yes", f"Nhà SX/kho hạng {hz}: đạt ngưỡng ΣF ≥ 500 m² (công trình: ΣF {_fmt(F)} m²).", cc) if F >= 500 \
                else _result("no", f"Nhà SX/kho hạng {hz}: chưa đạt ngưỡng ΣF ≥ 500 m² (công trình: ΣF {_fmt(F)} m²).", cc)
        return _result("no", "Nhà SX/kho hạng E: mục 2 Phụ lục B chỉ áp dụng hạng A, B, C, D.", cc,
                        ["Chú thích 3 Phụ lục B: không trang bị họng nước trong nhà đối với nhà SX/kho có chất khi tiếp xúc nước có thể sinh cháy, nổ."])
    if occ == "garakin":
        if payload.get("garaKin") == "kin":
            if B:
                return _result("yes", "Nhà để xe dạng kín tại tầng hầm/bán hầm: đạt ngưỡng, không phụ thuộc diện tích (mục 3.1).", cc)
            return _result("yes", "Nhà để xe dạng kín: đạt ngưỡng ΣF ≥ 150 m².", cc) if F >= 150 else _result("no", "Nhà để xe dạng kín: chưa đạt ngưỡng ΣF ≥ 150 m².", cc)
        return _result("yes", "Nhà để xe dạng hở (trừ gara cơ khí): đạt ngưỡng ΣF ≥ 1.000 m².", cc) if F >= 1000 \
            else _result("no", "Nhà để xe dạng hở: chưa đạt ngưỡng ΣF ≥ 1.000 m².", cc)
    return _result("na", "—", cc)


def evaluate_ngoai_nha(payload):
    validate_payload(payload)
    occ = payload.get("occ")
    F = _num(payload, "totalArea")
    T = _num(payload, "floors")
    cc = "QCVN 10:2025/BCA, Phụ lục C"

    if occ == "yte":
        return _result("yes", "Nhà khám, chữa bệnh: đạt ngưỡng cao ≥ 5 tầng hoặc ΣF ≥ 3.000 m² (TT 1).", cc) if (T >= 5 or F >= 3000) \
            else _result("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 3.000 m² (TT 1).", cc)
    if occ == "tttm":
        return _result("yes", "Chợ hạng 1, hạng 2, TTTM: bắt buộc, không phụ thuộc quy mô (TT 2).", cc)
    if occ == "nhaga":
        return _result("yes", "Nhà ga/cảng/bến: bắt buộc, không phụ thuộc quy mô (TT 3). Lưu ý: trạm dừng nghỉ chỉ áp dụng trên đường cao tốc.", cc)
    return _result(
        "na",
        "Loại nhà không nêu trực tiếp trong Phụ lục C. Lưu ý: nếu công trình nằm trong khu đô thị, khu nhà ở, "
        "KCN/cụm CN, khu du lịch… thì hạ tầng khu vực thuộc diện cấp nước ngoài nhà (TT 10) — thường do hạ tầng "
        "chung đảm nhận; nhu cầu nước ngoài nhà của bản thân công trình xét theo QCVN 06.",
        cc,
    )
