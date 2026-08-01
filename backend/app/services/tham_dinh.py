"""BƯỚC 1 — Diện thẩm định thiết kế PCCC (Phụ lục III, NĐ 105/2025/NĐ-CP).

Port từ index.html (hàm evalThamDinh) — rule-based thuần, không dùng AI,
để tránh rủi ro suy diễn sai quy định pháp lý.
"""

import math

BASE_FIELDS = {
    "totalArea": {"label": "Tổng diện tích sàn ΣF (m²)", "ph": "VD: 3500"},
    "floors": {"label": "Số tầng (đã gộp bán hầm nếu có)", "ph": "VD: 8"},
    "volume": {"label": "Khối tích V (m³)", "ph": "VD: 12000"},
}

EXTRA_FIELDS = {
    "kids": {"label": "Số trẻ (cháu)", "ph": "VD: 120"},
    "seats": {"label": "Số chỗ ngồi / khán đài (chỗ)", "ph": "VD: 350"},
    "hazard": {
        "label": "Hạng nguy hiểm cháy nổ",
        "select": [["", "— Chọn hạng —"], ["A", "Hạng A"], ["B", "Hạng B"],
                   ["C", "Hạng C"], ["D", "Hạng D"], ["E", "Hạng E"]],
    },
    "tunnelLength": {"label": "Chiều dài hầm (m)", "ph": "VD: 1200"},
    "pplTransport": {"label": "Sức chở người (người)", "ph": "VD: 60"},
    "vesselGT": {"label": "Dung tích phương tiện (GT)", "ph": "VD: 600"},
    "enginePower": {"label": "Công suất máy chính (sức ngựa)", "ph": "VD: 350"},
}

# fields: trường cơ bản (F/T/V) thực sự dùng tới trong quyết định thẩm định của mục này.
# extra: trường phân nhánh riêng theo công năng.
OCCUPATIONS = [
    {"id": "chungcu", "label": "Chung cư / nhà ở tập thể / ký túc xá", "fields": ["floors", "totalArea"]},
    {"id": "nhatre", "label": "Nhà trẻ, mẫu giáo, mầm non", "fields": ["totalArea"], "extra": ["kids"]},
    {"id": "truonghoc", "label": "Trường học (tiểu học → đại học, dạy nghề)", "fields": ["floors", "totalArea"]},
    {"id": "yte", "label": "Y tế (bệnh viện, phòng khám, điều dưỡng…)", "fields": ["floors", "totalArea"]},
    {"id": "khachsan", "label": "Khách sạn / nhà nghỉ / cơ sở lưu trú", "fields": ["floors", "totalArea"]},
    {"id": "truso", "label": "Trụ sở / văn phòng làm việc", "fields": ["floors", "totalArea"]},
    {"id": "honhop", "label": "Nhà hỗn hợp (đa công năng)", "fields": ["floors", "totalArea"]},
    {"id": "tttm", "label": "Chợ / trung tâm thương mại / siêu thị", "fields": ["totalArea"]},
    {"id": "cuahang", "label": "Cửa hàng điện máy / bách hóa / KD hàng dễ cháy", "fields": ["totalArea"]},
    {"id": "nhahang", "label": "Nhà hàng / cửa hàng ăn uống", "fields": ["totalArea"]},
    {"id": "karaoke", "label": "Karaoke / vũ trường", "fields": ["floors", "totalArea"]},
    {"id": "vanhoa", "label": "Nhà văn hóa / trung tâm hội nghị / nhà đa năng", "fields": ["floors", "totalArea"]},
    {"id": "nhahat", "label": "Nhà hát / rạp chiếu phim / rạp xiếc", "extra": ["seats"]},
    {"id": "baotang", "label": "Bảo tàng / triển lãm / thư viện", "fields": ["floors", "totalArea"]},
    {"id": "thethao", "label": "Nhà thi đấu / nhà tập luyện thể thao", "fields": ["totalArea"], "extra": ["seats"]},
    {"id": "sanxuat", "label": "Nhà sản xuất (xưởng)", "fields": ["totalArea", "volume"], "extra": ["hazard"]},
    {"id": "kho", "label": "Nhà kho", "fields": ["totalArea", "volume"], "extra": ["hazard"]},
    {"id": "congnghiep_dacthu", "label": "Công nghiệp đặc thù (lọc/hóa dầu, kho xăng dầu/khí hóa lỏng, nhà máy điện, trạm biến áp ≥110kV, vật liệu nổ/vũ khí)"},
    {"id": "garakin", "label": "Nhà để xe (gara) ô tô/xe máy", "fields": ["totalArea"]},
    {"id": "buudien", "label": "Bưu điện / viễn thông", "fields": ["floors", "totalArea"]},
    {"id": "nhaga", "label": "Nhà ga / bến xe / trạm dừng nghỉ", "fields": ["totalArea"]},
    {"id": "sanvandong", "label": "Sân vận động", "extra": ["seats"]},
    {"id": "hatangkt", "label": "Hạ tầng kỹ thuật đô thị / KCN / khu du lịch, đào tạo, thể dục thể thao"},
    {"id": "hamgiaothong", "label": "Hầm đường ô tô / đường sắt / tàu điện ngầm", "extra": ["tunnelLength"]},
    {"id": "csohatnhan", "label": "Công trình thuộc cơ sở hạt nhân"},
    {"id": "phuongtiengt", "label": "Phương tiện giao thông (thủy nội địa/tàu biển) chở khách/xăng dầu/chất dễ cháy/vật liệu nổ",
     "extra": ["pplTransport", "vesselGT", "enginePower"]},
]

_OCC_BY_ID = {o["id"]: o for o in OCCUPATIONS}


def _fmt(n):
    n = n or 0
    n = float(n)
    if n.is_integer():
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _num(payload, key):
    v = payload.get(key)
    if v is None or v == "":
        return 0
    label = BASE_FIELDS.get(key, EXTRA_FIELDS.get(key, {})).get("label", key)
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ThamDinhInputError(f"Giá trị của '{label}' phải là số, không phải {type(v).__name__}.")
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise ThamDinhInputError(f"Giá trị của '{label}' không phải là số hợp lệ: {v!r}.")
    if not math.isfinite(n):
        raise ThamDinhInputError(f"Giá trị của '{label}' không hợp lệ (NaN/Infinity).")
    if n < 0:
        raise ThamDinhInputError(f"Giá trị của '{label}' không được âm.")
    return n


def _cc(muc):
    return f"Phụ lục III NĐ 105/2025, mục {muc}"


# Batch 3: dinh danh phien ban bo nguon phap ly dang dung cho service nay -
# doi khi va chi khi noi dung Phu luc III NĐ 105/2025 duoc thay the/sua doi
# chinh thuc VA da co kỹ su PCCC xac nhan lai toan bo nguong (khong tu y doi
# theo suy doan). Chua co ngay hieu luc cu the rieng duoc dan trong source
# hien tai nen dung dung ten van ban lam dinh danh.
RULE_SET_VERSION = "ND105-2025-PLIII"


def _result(v, detail, can_cu, notes=None):
    return {
        "result": v,
        "detail": detail,
        "can_cu": can_cu,
        "notes": notes or [],
        "rule_set_version": RULE_SET_VERSION,
    }


class ThamDinhInputError(Exception):
    pass


def evaluate_tham_dinh(payload: dict) -> dict:
    occ_id = payload.get("occ")
    occ = _OCC_BY_ID.get(occ_id)
    if not occ:
        raise ThamDinhInputError(f"Công năng không hợp lệ: '{occ_id}'.")

    missing = [k for k in occ.get("extra", []) if payload.get(k) in (None, "")]
    if missing:
        labels = ", ".join(EXTRA_FIELDS[k]["label"] for k in missing)
        raise ThamDinhInputError(f"Thiếu dữ liệu bắt buộc cho công năng này: {labels}.")

    F = _num(payload, "totalArea")
    T = _num(payload, "floors")
    V = _num(payload, "volume")
    fmt = _fmt
    cc = _cc
    R = _result

    if occ_id == "chungcu":
        return R("yes", f"Đạt ngưỡng: cao ≥ 7 tầng hoặc ΣF ≥ 3.000 m² (công trình: {fmt(T)} tầng, ΣF {fmt(F)} m²).", cc(1)) if T >= 7 or F >= 3000 \
            else R("no", f"Chưa đạt ngưỡng cao ≥ 7 tầng và ΣF ≥ 3.000 m² (công trình: {fmt(T)} tầng, ΣF {fmt(F)} m²).", cc(1))

    if occ_id == "nhatre":
        kids = _num(payload, "kids")
        return R("yes", f"Đạt ngưỡng: ≥ 150 cháu hoặc ΣF ≥ 2.000 m² (công trình: {fmt(kids)} cháu, ΣF {fmt(F)} m²).", cc(2)) if kids >= 150 or F >= 2000 \
            else R("no", f"Chưa đạt ngưỡng ≥ 150 cháu và ΣF ≥ 2.000 m² (công trình: {fmt(kids)} cháu, ΣF {fmt(F)} m²).", cc(2))

    if occ_id == "truonghoc":
        return R("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 3.000 m².", cc(2)) if T >= 5 or F >= 3000 \
            else R("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 3.000 m².", cc(2))

    if occ_id == "yte":
        return R("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 2.000 m².", cc(3)) if T >= 5 or F >= 2000 \
            else R("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 2.000 m².", cc(3))

    if occ_id == "thethao":
        seats = _num(payload, "seats")
        return R("yes", "Đạt ngưỡng: khán đài ≥ 5.000 chỗ hoặc ΣF ≥ 5.000 m².", cc(4)) if seats >= 5000 or F >= 5000 \
            else R("no", "Chưa đạt ngưỡng khán đài ≥ 5.000 chỗ và ΣF ≥ 5.000 m².", cc(4))

    if occ_id == "nhahat":
        seats = _num(payload, "seats")
        return R("yes", f"Đạt ngưỡng: ≥ 300 chỗ ngồi (công trình: {fmt(seats)} chỗ).", cc(5)) if seats >= 300 \
            else R("no", f"Chưa đạt ngưỡng ≥ 300 chỗ ngồi (công trình: {fmt(seats)} chỗ).", cc(5))

    if occ_id in ("vanhoa", "baotang"):
        return R("yes", "Đạt ngưỡng: cao ≥ 5 tầng hoặc ΣF ≥ 3.000 m².", cc(5)) if T >= 5 or F >= 3000 \
            else R("no", "Chưa đạt ngưỡng cao ≥ 5 tầng và ΣF ≥ 3.000 m².", cc(5))

    if occ_id == "karaoke":
        return R("yes", "Đạt ngưỡng: cao ≥ 4 tầng hoặc ΣF ≥ 1.000 m².", cc(5)) if T >= 4 or F >= 1000 \
            else R("no", "Chưa đạt ngưỡng cao ≥ 4 tầng và ΣF ≥ 1.000 m².", cc(5))

    if occ_id in ("tttm", "cuahang"):
        return R("yes", f"Đạt ngưỡng: ΣF ≥ 2.000 m² (công trình: {fmt(F)} m²).", cc(6)) if F >= 2000 \
            else R("no", f"Chưa đạt ngưỡng ΣF ≥ 2.000 m² (công trình: {fmt(F)} m²).", cc(6))

    if occ_id == "nhahang":
        return R("yes", f"Đạt ngưỡng: ΣF ≥ 3.000 m² (công trình: {fmt(F)} m²).", cc(6)) if F >= 3000 \
            else R("no", f"Chưa đạt ngưỡng ΣF ≥ 3.000 m² (công trình: {fmt(F)} m²).", cc(6))

    if occ_id in ("khachsan", "buudien", "truso"):
        return R("yes", "Đạt ngưỡng: cao ≥ 7 tầng hoặc ΣF ≥ 3.000 m².", cc(7)) if T >= 7 or F >= 3000 \
            else R("no", "Chưa đạt ngưỡng cao ≥ 7 tầng và ΣF ≥ 3.000 m².", cc(7))

    if occ_id == "honhop":
        note = ["Nhà hỗn hợp: nếu có phần công năng thuộc mục 1–7 PL III thì cũng thuộc diện — cần kỹ sư xét riêng từng phần công năng."]
        if T >= 7 or F >= 3000:
            return R("yes", "Đạt ngưỡng: cao ≥ 7 tầng hoặc ΣF ≥ 3.000 m².", cc(8), note)
        return R("warn", "Chưa đạt ngưỡng cao ≥ 7 tầng / ΣF ≥ 3.000 m² xét theo tổng thể — NHƯNG nếu có phần công năng thuộc mục 1–7 PL III thì vẫn thuộc diện. Cần kỹ sư xét riêng từng phần công năng.", cc(8))

    if occ_id == "congnghiep_dacthu":
        return R("yes",
                  "Thuộc mục 9a/9b/9c Phụ lục III NĐ 105/2025 (nhà máy lọc dầu/hóa dầu/lọc-hóa dầu/chế biến khí/nhiên liệu sinh học, "
                  "kho dầu mỏ-sản phẩm dầu mỏ, kho khí hóa lỏng, trạm chiết khí hóa lỏng, trạm phân phối khí, cửa hàng/trạm cấp xăng dầu "
                  "≥ 1 cột bơm; HOẶC nhà máy điện, trạm biến áp ≥ 110 kV; HOẶC nhà máy/kho vật liệu nổ, tiền chất thuốc nổ công nghiệp, "
                  "vũ khí, công cụ hỗ trợ): bắt buộc thẩm định, KHÔNG phụ thuộc quy mô.",
                  cc("9a/9b/9c"))

    if occ_id == "sanxuat":
        hazard = payload.get("hazard")
        if hazard in ("A", "B"):
            return R("yes", f"Đạt ngưỡng hạng A, B: V ≥ 7.000 m³ hoặc ΣF ≥ 1.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc("9d")) if V >= 7000 or F >= 1000 \
                else R("no", f"Chưa đạt ngưỡng hạng A, B: V ≥ 7.000 m³ và ΣF ≥ 1.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc("9d"))
        if hazard == "C":
            return R("yes", f"Đạt ngưỡng hạng C: V ≥ 15.000 m³ hoặc ΣF ≥ 2.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc("9d")) if V >= 15000 or F >= 2000 \
                else R("no", f"Chưa đạt ngưỡng hạng C: V ≥ 15.000 m³ và ΣF ≥ 2.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc("9d"))
        return R("yes", f"Đạt ngưỡng hạng D, E: V ≥ 30.000 m³ hoặc ΣF ≥ 10.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc("9d")) if V >= 30000 or F >= 10000 \
            else R("no", f"Chưa đạt ngưỡng hạng D, E: V ≥ 30.000 m³ và ΣF ≥ 10.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc("9d"))

    if occ_id == "kho":
        hazard = payload.get("hazard")
        if hazard in ("A", "B", "C"):
            return R("yes", f"Kho hạng {hazard}: đạt ngưỡng V ≥ 15.000 m³ hoặc ΣF ≥ 2.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc(10)) if V >= 15000 or F >= 2000 \
                else R("no", f"Kho hạng {hazard}: chưa đạt ngưỡng V ≥ 15.000 m³ và ΣF ≥ 2.000 m² (công trình: V {fmt(V)} m³, ΣF {fmt(F)} m²).", cc(10))
        return R("no", f"Kho hạng {hazard}: mục 10 PL III chỉ áp dụng kho hạng A, B, C.", cc(10))

    if occ_id == "garakin":
        return R("yes", "Đạt ngưỡng: ΣF ≥ 2.000 m².", cc(12)) if F >= 2000 \
            else R("no", "Chưa đạt ngưỡng ΣF ≥ 2.000 m².", cc(12))

    if occ_id == "nhaga":
        return R("yes", "Đạt ngưỡng: ΣF ≥ 3.000 m² (một số loại xét theo cấp công trình — kiểm tra thêm).", cc(13)) if F >= 3000 \
            else R("no", "Chưa đạt ngưỡng ΣF ≥ 3.000 m² (một số loại xét theo cấp công trình — kiểm tra thêm).", cc(13))

    if occ_id == "sanvandong":
        seats = _num(payload, "seats")
        return R("yes", f"Đạt ngưỡng: khán đài ≥ 5.000 chỗ (công trình: {fmt(seats)} chỗ).", cc(4)) if seats >= 5000 \
            else R("no", f"Chưa đạt ngưỡng khán đài ≥ 5.000 chỗ (công trình: {fmt(seats)} chỗ).", cc(4))

    if occ_id == "hatangkt":
        return R("yes",
                  "Hạ tầng kỹ thuật của khu đô thị, khu nhà ở, khu công nghiệp, cụm công nghiệp, khu du lịch, khu nghiên cứu, đào tạo, "
                  "khu thể dục, thể thao: bắt buộc thẩm định, không phụ thuộc quy mô.",
                  cc(11),
                  ["Công cụ này chỉ trả lời BƯỚC 1 (diện thẩm định) cho nhóm công trình này — hạ tầng kỹ thuật đô thị/KCN cần tra cứu riêng "
                   "quy chuẩn/tiêu chuẩn hạ tầng chuyên ngành cho các bước hệ thống PCCC tiếp theo."])

    if occ_id == "hamgiaothong":
        tunnel_length = _num(payload, "tunnelLength")
        if tunnel_length >= 1000:
            return R("yes", f"Đạt ngưỡng: chiều dài ≥ 1.000 m (công trình: {fmt(tunnel_length)} m).", cc(14),
                      ["Công cụ này chỉ trả lời BƯỚC 1 (diện thẩm định) cho nhóm công trình này — hầm giao thông cần tra cứu riêng "
                       "quy chuẩn/tiêu chuẩn hầm chuyên ngành cho các bước hệ thống PCCC tiếp theo."])
        return R("no", f"Chưa đạt ngưỡng chiều dài ≥ 1.000 m (công trình: {fmt(tunnel_length)} m).", cc(14))

    if occ_id == "csohatnhan":
        return R("yes", "Công trình thuộc cơ sở hạt nhân: bắt buộc thẩm định, không phụ thuộc quy mô.", cc(15),
                  ["Công trình hạt nhân chịu quản lý chuyên ngành riêng — công cụ này không thay thế được quy chuẩn/tiêu chuẩn "
                   "chuyên ngành hạt nhân cho các bước hệ thống PCCC tiếp theo."])

    if occ_id == "phuongtiengt":
        ppl = _num(payload, "pplTransport")
        gt = _num(payload, "vesselGT")
        hp = _num(payload, "enginePower")
        if ppl >= 50 or gt >= 500 or hp >= 300:
            return R("yes",
                      f"Đạt ngưỡng: sức chở ≥ 50 người, hoặc ≥ 500 GT, hoặc công suất máy chính ≥ 300 sức ngựa "
                      f"(phương tiện: {fmt(ppl)} người, {fmt(gt)} GT, {fmt(hp)} sức ngựa).",
                      cc(16),
                      ["Phương tiện giao thông không phải công trình xây dựng — công cụ này không áp dụng cho các bước hệ thống PCCC "
                       "tiếp theo, cần tra cứu riêng theo quy định PCCC phương tiện giao thông."])
        return R("no",
                  f"Chưa đạt ngưỡng sức chở ≥ 50 người, ≥ 500 GT, và công suất máy chính ≥ 300 sức ngựa "
                  f"(phương tiện: {fmt(ppl)} người, {fmt(gt)} GT, {fmt(hp)} sức ngựa).",
                  cc(16))

    return R("na", "Không xác định được nhóm công năng.", "—")
