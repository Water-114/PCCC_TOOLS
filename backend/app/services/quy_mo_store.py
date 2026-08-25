"""Hạng mục "Quy mô" (Form A / MĐC Kiến trúc) — lưu + đối chiếu dữ liệu quy mô
công trình (occ, floors, totalArea, hFire...) dùng chung cho các hạng mục khác
trong CÙNG 1 phiên Bộ hồ sơ (xem get_quy_mo()).

Form A có 40 dòng cần điền (trong 64 dòng bảng gốc), chia 4 nhóm — đã khảo sát
lại TRỰC TIẾP từ app/services/mdc_templates/A_quy_mo.docx (không suy đoán từ
ghi nhớ cũ) trước khi viết module này:

1. Mục 1 "quy mô" (id 2,3,4): sinh câu chữ bằng code THUẦN từ QuyMoFields —
   id=2 dùng lại tham_dinh.evaluate_tham_dinh() (đúng là câu hỏi "đối tượng
   thẩm định"); id=3/4 chỉ diễn giải lại số tầng/chiều cao PCCC, không có
   ngưỡng nào để đối chiếu.
2. "Đối tượng trang bị" (Type 1, id 7,9,16,18,27,30,42,45,49,55,57,60): gọi
   THẲNG các hàm evaluate_*() có sẵn ở tham_dinh.py/he_thong_bat_buoc.py/
   phuong_tien.py — KHÔNG dùng AI. id=49 (bình chữa cháy xách tay) không có
   ngưỡng (luôn bắt buộc) nên ghi tĩnh, không cần gọi hàm.
3. Bảng A.2/A.4 (id 8,10,17,19): KHÔNG có rule sẵn — AI phải tự đọc bản vẽ,
   xem quymo_reader.py.
4. Dòng "Yêu cầu kỹ thuật chi tiết" (Type 2, dẫn chiếu form con hoặc placeholder
   tĩnh) — 3 nhóm nhỏ:
   - Dẫn chiếu form B đã có sẵn (id 13,25,28,34,43,46,50,63).
   - Chưa có mẫu B tương ứng (id 32 → B4, chưa đăng ký trong mdc_filler).
   - Cần đối chiếu mặt bằng cụ thể, không có rule/không phải AI trả lời được
     (id 12,21,22,31,56,58,61).
   - "Không thiết kế" — chữa cháy tự động bằng khí/bọt/bình tự động kích hoạt
     (id 36,37,38,51,52) — CÙNG NHÓM B8-B11 (chưa có AI đọc bản vẽ thật cho
     nhóm này). TODO: quay lại sửa 5 dòng này khi B8-B11 có AI thật.
"""

from datetime import datetime, timezone

from pydantic import ValidationError

from ..extensions import db
from ..models import HoSoSession, HoSoSessionQuyMo
from .ai_schema import QuyMoFields
from .he_thong_bat_buoc import (
    HeThongBatBuocInputError,
    evaluate_bao_chay,
    evaluate_gian_phong_bao_chay,
    evaluate_gian_phong_sprinkler,
    evaluate_hong_nuoc,
    evaluate_ngoai_nha,
    evaluate_sprinkler,
)
from .phuong_tien import (
    PhuongTienInputError,
    evaluate_bot_co_dinh,
    evaluate_co_gioi,
    evaluate_den,
    evaluate_dien_pccc_suy_luan,
    evaluate_loa,
    evaluate_mat_na,
    evaluate_pha_do,
)
from .tham_dinh import OCCUPATIONS, ThamDinhInputError, evaluate_tham_dinh

KHONG_XAC_DINH_AI = "Chưa xác định — cần đọc bản vẽ (Bảng A.2/A.4 QCVN 10:2025/BCA)."

_INPUT_ERRORS = (ThamDinhInputError, HeThongBatBuocInputError, PhuongTienInputError)

# "yes"/"no" tu evaluate_*() deu la ket luan RULE-BASED chac chan (thuoc dien
# hay khong), khong can kien nghi -> "dat". "na" (rule khong ap dung cho cong
# nang nay) -> "khong_ap_dung" (de trong cot Ket luan, xem ai_schema.KetLuan).
# "warn"/"chua_du_du_lieu" (thieu du lieu de ket luan chac chan) -> "chua_the_hien".
_RULE_TO_KET_LUAN = {
    "yes": "dat",
    "no": "dat",
    "na": "khong_ap_dung",
    "warn": "chua_the_hien",
    "chua_du_du_lieu": "chua_the_hien",
}


class QuyMoInputError(Exception):
    pass


def _fmt(n):
    n = float(n or 0)
    if n.is_integer():
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


_OCC_LABELS = {o["id"]: o["label"] for o in OCCUPATIONS}


# ---------------------------------------------------------------------------
# Muc 1 (tich hop vao 4 reader hien co: bao chay/dien PCCC/nuoc/den-binh) —
# GHI CHU QUAN TRONG: day la BO SUNG hoan toan TUY CHON, KHONG bao gio duoc
# goi neu quy_mo=None/rong. 4 reader kia van phai tu doc va suy luan tu ban ve
# rieng cua no NHU CU khi khong co du lieu nay (dinh chinh ro rang cua owner —
# dinh kem hang muc la tu nguyen, khong duoc bien Quy mo thanh dieu kien tien
# quyet cho bat ky reader nao khac).
# ---------------------------------------------------------------------------
def format_quy_mo_context(fields: dict) -> str:
    """Dựng đoạn text mô tả quy mô công trình để NỐI THÊM vào system prompt của
    1 trong 4 reader hiện có, tại THỜI ĐIỂM GỌI (không phải static lúc load
    module) — vì dữ liệu quy mô khác nhau tuỳ phiên. Caller (readers) tự quyết
    định có gọi hàm này hay không (chỉ gọi khi fields truthy)."""
    occ = fields.get("occ")
    lines = [f"- Công năng: {_OCC_LABELS.get(occ, occ)}"]
    if fields.get("floors") is not None:
        lines.append(f"- Số tầng nổi: {_fmt(fields['floors'])}")
    if fields.get("basements"):
        lines.append(f"- Số tầng hầm: {_fmt(fields['basements'])}")
    if fields.get("semiBasements"):
        lines.append(f"- Số tầng bán hầm: {_fmt(fields['semiBasements'])}")
    if fields.get("areaFloor") is not None:
        lines.append(f"- Diện tích 1 tầng điển hình: {_fmt(fields['areaFloor'])} m²")
    if fields.get("totalArea") is not None:
        lines.append(f"- Tổng diện tích sàn ΣF: {_fmt(fields['totalArea'])} m²")
    if fields.get("volume") is not None:
        lines.append(f"- Khối tích V: {_fmt(fields['volume'])} m³")
    if fields.get("hFire") is not None:
        lines.append(f"- Chiều cao phục vụ PCCC: {_fmt(fields['hFire'])} m")
    if fields.get("kids") is not None:
        lines.append(f"- Số trẻ: {_fmt(fields['kids'])} cháu")
    if fields.get("seats") is not None:
        lines.append(f"- Số chỗ ngồi/khán đài: {_fmt(fields['seats'])} chỗ")
    if fields.get("hazard"):
        lines.append(f"- Hạng nguy hiểm cháy nổ: {fields['hazard']}")
    if fields.get("pplFloor") is not None:
        lines.append(f"- Số người lớn nhất trên 1 tầng: {_fmt(fields['pplFloor'])}")
    if fields.get("hanhLangDaiNhat") is not None:
        lines.append(f"- Chiều dài hành lang thoát nạn dài nhất: {_fmt(fields['hanhLangDaiNhat'])} m")
    if fields.get("chieuCaoKeHang") is not None:
        lines.append(f"- Chiều cao sắp xếp hàng hoá trên giá đỡ/kệ hàng: {_fmt(fields['chieuCaoKeHang'])} m")
    if fields.get("coBeXangDauNgoaiTroi") is not None:
        lines.append(f"- Có bể chứa xăng dầu/dung môi ngoài trời: {'Có' if fields['coBeXangDauNgoaiTroi'] else 'Không'}")

    return (
        "\n\n--- QUY MÔ CÔNG TRÌNH ĐÃ XÁC NHẬN (tham khảo, KHÔNG thay thế việc tự đọc bản vẽ) ---\n"
        "Dữ liệu dưới đây do người dùng nhập tay hoặc AI đã trích xuất từ 1 bản vẽ khác (hạng mục \"Quy mô\") "
        "trong CÙNG bộ hồ sơ này — dùng để THAM KHẢO/ĐỐI CHIẾU THÊM, giúp xác định đúng hơn công trình có "
        "thuộc diện áp dụng hệ thống này hay không. VẪN phải tự đọc và đối chiếu bản vẽ được cung cấp trong "
        "lượt gọi này NHƯ BÌNH THƯỜNG — KHÔNG bỏ qua bước đọc bản vẽ chỉ vì đã có dữ liệu quy mô này. Nếu bản "
        "vẽ có thông tin MÂU THUẪN rõ ràng với dữ liệu dưới đây, ưu tiên thông tin THỰC TẾ trên bản vẽ.\n"
        + "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# Luu tru
# ---------------------------------------------------------------------------
def get_quy_mo(session_id):
    """Tra ve dict (dung ten field QuyMoFields) hoac None neu phien nay CHUA
    dinh hang muc Quy mo — luon phai xu ly None nhu 1 gia tri hop le o phia
    goi (4 reader khac coi day la OPTIONAL, khong duoc bat buoc)."""
    row = HoSoSessionQuyMo.query.filter_by(session_id=session_id).first()
    return row.to_dict() if row else None


def save_quy_mo(session_id, fields: dict, source: str):
    """Upsert theo session_id (UNIQUE) — goi lai voi cung session_id se GHI DE
    ban ghi cu (vd doc lai bang vẽ khac, hoac sua tay sau khi AI doc)."""
    row = HoSoSessionQuyMo.query.filter_by(session_id=session_id).first()
    if row is None:
        row = HoSoSessionQuyMo(session_id=session_id, source=source)
        db.session.add(row)
    row.source = source
    row.occ = fields.get("occ")
    row.floors = fields.get("floors")
    row.basements = fields.get("basements")
    row.semi_basements = fields.get("semiBasements")
    row.area_floor = fields.get("areaFloor")
    row.total_area = fields.get("totalArea")
    row.volume = fields.get("volume")
    row.h_fire = fields.get("hFire")
    row.kids = fields.get("kids")
    row.seats = fields.get("seats")
    row.hazard = fields.get("hazard")
    row.gara_kin = fields.get("garaKin")
    row.gara_kc12 = fields.get("garaKC12")
    row.gara_bcl = fields.get("garaBcl")
    row.gara_cap_s = fields.get("garaCapS")
    row.ppl_floor = fields.get("pplFloor")
    row.ext_level = fields.get("extLevel")
    row.hanh_lang_dai_nhat = fields.get("hanhLangDaiNhat")
    row.chieu_cao_ke_hang = fields.get("chieuCaoKeHang")
    row.co_be_xang_dau_ngoai_troi = fields.get("coBeXangDauNgoaiTroi")
    db.session.commit()
    return row.to_dict()


# ---------------------------------------------------------------------------
# "Luot 0" (Phan A) - quet nhe quy mo tu bao chay/ccnuoc, gop ket qua, luu
# hoac chi danh dau "da thu nhung khong thay gi" (Phan C).
# ---------------------------------------------------------------------------
_ALL_SCAN_FIELD_KEYS = (
    "occ", "floors", "basements", "semiBasements", "areaFloor", "totalArea",
    "volume", "hFire", "kids", "seats", "hazard", "garaKin", "garaKC12",
    "garaBcl", "garaCapS", "pplFloor", "extLevel", "hanhLangDaiNhat",
    "chieuCaoKeHang", "coBeXangDauNgoaiTroi",
)

_FIELD_LABELS_VI = {
    "occ": "công năng",
    "floors": "số tầng nổi",
    "basements": "số tầng hầm",
    "semiBasements": "số tầng bán hầm",
    "areaFloor": "diện tích 1 tầng",
    "totalArea": "tổng diện tích sàn ΣF",
    "volume": "khối tích V",
    "hFire": "chiều cao phục vụ PCCC",
    "kids": "số trẻ",
    "seats": "số chỗ ngồi",
    "hazard": "hạng nguy hiểm cháy nổ",
    "garaKin": "dạng nhà để xe",
    "garaKC12": "khoảng cách đến cạnh để hở",
    "garaBcl": "bậc chịu lửa",
    "garaCapS": "cấp nguy hiểm cháy kết cấu",
    "pplFloor": "số người lớn nhất trên 1 tầng",
    "extLevel": "mức nguy hiểm cháy (tính bình chữa cháy)",
    "hanhLangDaiNhat": "chiều dài hành lang thoát nạn dài nhất",
    "chieuCaoKeHang": "chiều cao sắp xếp hàng hoá trên kệ",
    "coBeXangDauNgoaiTroi": "có bể xăng dầu ngoài trời",
}


def _validate_scan_merged_fields(fields: dict) -> dict:
    """Validate NHE ket qua da gop cua Luot 0 truoc khi luu - dung
    ScanQuyMoFields (occ VAN duoc phep thieu, khac QuyMoFields cua
    validate_manual_fields() ben duoi) vi ban ve bao chay/ccnuoc thuong
    khong ghi ro cong nang tong the."""
    from .ai_schema import ScanQuyMoFields
    try:
        model = ScanQuyMoFields.model_validate(fields)
    except ValidationError as exc:
        raise QuyMoInputError(f"Dữ liệu quy mô (Lượt 0) không hợp lệ: {exc}") from exc
    data = model.model_dump()
    for key in (
        "floors", "basements", "semiBasements", "areaFloor", "totalArea",
        "volume", "hFire", "kids", "seats", "pplFloor", "hanhLangDaiNhat", "chieuCaoKeHang",
    ):
        v = data.get(key)
        if v is not None and v < 0:
            raise QuyMoInputError(f"Giá trị của '{key}' không được âm.")
    return data


def merge_scan_quymo_results(results: list) -> dict:
    """Gộp kết quả "Lượt 0" từ 1-2 file (báo cháy + ccnuoc) — xem Phần A.3.

    results: list [{"slot": "baochay"|"ccnuoc", "label": str, "tim_thay": bool,
    "quy_mo": dict|None}, ...] — ĐÚNG payload thô mà 1-2 lần gọi
    /api/aiho/scan-quymo trả về, frontend forward nguyên lại kèm slot/label.

    Trả về {"merged": dict|None, "conflicts": [{"field", "label", "values":
    [{"slot","label","value"}, ...]}], "found_count": int} — "merged" là
    None nếu KHÔNG có file nào tim_thay=True (Phần C xử lý tiếp)."""
    found = [r for r in results if r.get("tim_thay") and r.get("quy_mo")]
    if not found:
        return {"merged": None, "conflicts": [], "found_count": 0}

    if len(found) == 1:
        only = found[0]
        merged = {k: v for k, v in only["quy_mo"].items() if v is not None}
        return {"merged": merged, "conflicts": [], "found_count": 1}

    # 2 file deu tim thay - so tung field, "muc do day du" = so field KHAC None
    # (uu tien file day du hon lam nguon "da chon" cho field mau thuan).
    def _completeness(r):
        return sum(1 for v in r["quy_mo"].values() if v is not None)

    found_sorted = sorted(found, key=_completeness, reverse=True)
    priority = found_sorted[0]

    merged = {}
    conflicts = []
    for key in _ALL_SCAN_FIELD_KEYS:
        values = [(r["slot"], r["label"], r["quy_mo"].get(key)) for r in found if r["quy_mo"].get(key) is not None]
        if not values:
            continue
        distinct = {v for _, _, v in values}
        if len(distinct) == 1:
            merged[key] = values[0][2]
        else:
            # Mau thuan that - dung gia tri cua file "day du hon" (priority),
            # neu priority khong co field nay thi dung gia tri con lai.
            chosen = priority["quy_mo"].get(key)
            if chosen is None:
                chosen = values[0][2]
            merged[key] = chosen
            conflicts.append({
                "field": key,
                "label": _FIELD_LABELS_VI.get(key, key),
                "values": [{"slot": slot, "label": label, "value": v} for slot, label, v in values],
                "chosen": chosen,
            })

    return {"merged": merged, "conflicts": conflicts, "found_count": len(found)}


def finish_quy_mo_scan(session: "HoSoSession", results: list) -> dict:
    """Kết thúc Lượt 0: gộp kết quả rồi lưu (source='ai_auto_detected') NẾU có
    tìm thấy gì, hoặc CHỈ đánh dấu quy_mo_scan_attempted_at (Phần C — KHÔNG
    tạo bản ghi HoSoSessionQuyMo rỗng, xem lý do ở models.HoSoSession) nếu
    không tìm thấy gì cả. LUÔN đánh dấu attempted (dù có tìm thấy hay không)
    để Phần E biết Lượt 0 đã từng chạy cho phiên này."""
    merge_result = merge_scan_quymo_results(results)
    saved = None
    if merge_result["merged"]:
        clean = _validate_scan_merged_fields(merge_result["merged"])
        saved = save_quy_mo(session.id, clean, source="ai_auto_detected")

    session.quy_mo_scan_attempted_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        "saved": saved,
        "conflicts": merge_result["conflicts"],
        "found_count": merge_result["found_count"],
    }


# ---------------------------------------------------------------------------
# Phan E — doi chieu nguoc: tu phat hien "thieu ho so he thong X". Bang anh xa
# "thuoc dien" -> slot AIHO (E.1) — KHONG ap dung cho "khibot" (chua co
# nguong rule nao xac dinh thuoc dien, khong tu bia).
# ---------------------------------------------------------------------------
def _slot_thuoc_dien_baochay(fields):
    try:
        r = evaluate_bao_chay(fields)
    except HeThongBatBuocInputError:
        return False, None
    return r.get("result") == "yes", r.get("can_cu")


def _slot_thuoc_dien_ccnuoc(fields):
    can_cu_list = []
    thuoc_dien = False
    for fn in (evaluate_sprinkler, evaluate_hong_nuoc):
        try:
            r = fn(fields)
        except HeThongBatBuocInputError:
            continue
        if r.get("result") == "yes":
            thuoc_dien = True
            can_cu_list.append(r.get("can_cu"))
    return thuoc_dien, "; ".join(c for c in can_cu_list if c) or None


def _slot_thuoc_dien_densucco(fields):
    can_cu_list = ["TCVN 7435-1:2004 (bình chữa cháy xách tay — luôn bắt buộc)"]
    thuoc_dien = True  # binh chua chay xach tay luon bat buoc (id=49 Form A)
    for fn in (evaluate_den, evaluate_loa):
        try:
            r = fn(fields)
        except PhuongTienInputError:
            continue
        if r.get("result") == "yes":
            can_cu_list.append(r.get("can_cu"))
    return thuoc_dien, "; ".join(c for c in can_cu_list if c) or None


def _slot_thuoc_dien_dienpccc(fields):
    r = evaluate_dien_pccc_suy_luan(fields)
    return r.get("result") == "yes", r.get("can_cu")


def _slot_thuoc_dien_botcodinh(fields):
    r = evaluate_bot_co_dinh(fields)
    return r.get("result") == "yes", r.get("can_cu")


_REVERSE_CHECK_SLOTS = (
    ("baochay", _slot_thuoc_dien_baochay),
    ("ccnuoc", _slot_thuoc_dien_ccnuoc),
    ("densucco", _slot_thuoc_dien_densucco),
    ("dienpccc", _slot_thuoc_dien_dienpccc),
    ("botcodinh", _slot_thuoc_dien_botcodinh),
)


def compute_reverse_check_warnings(fields: dict, slots_with_data) -> list:
    """Phần E.2 — với mỗi slot trong _REVERSE_CHECK_SLOTS, nếu THUỘC DIỆN
    (theo evaluate_*() có sẵn) mà KHÔNG có trong slots_with_data (đã đính +
    đọc thành công, do frontend gửi lên — backend không tự biết) → sinh 1
    cảnh báo {slot, can_cu}. "Tên hệ thống" KHÔNG dựng ở đây — frontend tự
    ghép bằng REAL_CATEGORIES[slot].label (E.2 yêu cầu dùng đúng label đã có,
    không đặt tên mới), backend chỉ trả can_cu (trích từ evaluate_*() tương
    ứng, không tự bịa)."""
    slots_with_data = set(slots_with_data or [])
    warnings = []
    for slot, check_fn in _REVERSE_CHECK_SLOTS:
        thuoc_dien, can_cu = check_fn(fields)
        if thuoc_dien and slot not in slots_with_data:
            warnings.append({"slot": slot, "can_cu": can_cu or "—"})
    return warnings


def validate_manual_fields(fields) -> dict:
    """Validate dữ liệu nhập tay (route quymo-manual) — dùng lại QuyMoFields
    (đã có sẵn field_validator kiểm tra occ hợp lệ), bổ sung chặn số âm cho
    đúng chuẩn các module evaluate_* khác (Batch 1)."""
    if not isinstance(fields, dict):
        raise QuyMoInputError("Dữ liệu quy mô phải là một JSON object.")
    try:
        model = QuyMoFields.model_validate(fields)
    except ValidationError as exc:
        raise QuyMoInputError(f"Dữ liệu quy mô không hợp lệ: {exc}") from exc
    data = model.model_dump()
    for key in (
        "floors", "basements", "semiBasements", "areaFloor", "totalArea",
        "volume", "hFire", "kids", "seats", "pplFloor", "hanhLangDaiNhat",
    ):
        v = data.get(key)
        if v is not None and v < 0:
            raise QuyMoInputError(f"Giá trị của '{key}' không được âm.")
    return data


# ---------------------------------------------------------------------------
# Muc 1 — ho so quy mo (id 2,3,4) — sinh cau chu bang code, dung CHUNG cho ca
# route AI va route nhap tay (khong AI-prose rieng cho tung route).
# ---------------------------------------------------------------------------
def build_quy_mo_profile_items(fields: dict) -> list:
    items = []

    try:
        r = evaluate_tham_dinh(fields)
        items.append({
            "id": 2,
            "noi_dung_thiet_ke": r["detail"],
            "ket_luan": _RULE_TO_KET_LUAN.get(r["result"], "chua_the_hien"),
        })
    except _INPUT_ERRORS as exc:
        items.append({
            "id": 2,
            "noi_dung_thiet_ke": f"Chưa đủ dữ liệu để xác định diện thẩm định: {exc}",
            "ket_luan": "chua_the_hien",
        })

    floors = fields.get("floors")
    if floors is None:
        items.append({"id": 3, "noi_dung_thiet_ke": "Chưa xác định số tầng.", "ket_luan": "chua_the_hien"})
    else:
        parts = [f"{_fmt(floors)} tầng nổi"]
        basements = fields.get("basements")
        semi = fields.get("semiBasements")
        if basements:
            parts.append(f"{_fmt(basements)} tầng hầm")
        if semi:
            parts.append(f"{_fmt(semi)} tầng bán hầm")
        items.append({"id": 3, "noi_dung_thiet_ke": "Công trình có " + ", ".join(parts) + ".", "ket_luan": "dat"})

    h_fire = fields.get("hFire")
    if h_fire is None:
        items.append({"id": 4, "noi_dung_thiet_ke": "Chưa xác định chiều cao phục vụ PCCC.", "ket_luan": "chua_the_hien"})
    else:
        items.append({
            "id": 4,
            "noi_dung_thiet_ke": f"Chiều cao phục vụ PCCC (Điều 1.4.9 QCVN 06:2022/BXD và Sửa đổi 1:2023): {_fmt(h_fire)} m.",
            "ket_luan": "dat",
        })

    return items


# ---------------------------------------------------------------------------
# "Doi tuong trang bi" (Type 1, id 7,9,16,18,27,30,42,45,49,55,57,60) — goi
# thang evaluate_*() co san, KHONG dung AI.
# ---------------------------------------------------------------------------
def _safe_eval(fn, fields):
    try:
        return fn(fields)
    except _INPUT_ERRORS as exc:
        return {"result": "warn", "detail": f"Chưa đủ dữ liệu quy mô để xác định ({exc})", "can_cu": "—"}


_TYPE1_ROWS = (
    (7, evaluate_bao_chay),
    (9, evaluate_gian_phong_bao_chay),
    (16, evaluate_sprinkler),
    (18, evaluate_gian_phong_sprinkler),
    (27, evaluate_hong_nuoc),
    (30, evaluate_ngoai_nha),
    (45, evaluate_loa),
    (55, evaluate_pha_do),
    (57, evaluate_mat_na),
    (60, evaluate_co_gioi),
)


def build_type1_items(fields: dict) -> list:
    items = []
    for row_id, fn in _TYPE1_ROWS:
        r = _safe_eval(fn, fields)
        items.append({
            "id": row_id,
            "noi_dung_thiet_ke": r.get("detail", "—"),
            "ket_luan": _RULE_TO_KET_LUAN.get(r["result"], "chua_the_hien"),
        })

    # id=42: den su co — evaluate_den() luon "yes", tra ve danh sach vi tri
    # ("pos") thay vi "detail" nhu cac ham khac.
    r = _safe_eval(evaluate_den, fields)
    if r["result"] == "yes" and "pos" in r:
        noi_dung = "Vị trí bắt buộc lắp đặt: " + "; ".join(r["pos"]) + "."
    else:
        noi_dung = r.get("detail", "—")
    items.append({"id": 42, "noi_dung_thiet_ke": noi_dung, "ket_luan": _RULE_TO_KET_LUAN.get(r["result"], "chua_the_hien")})

    # id=49: binh chua chay xach tay — luon bat buoc, khong nguong quy mo nao
    # (TCVN 7435-1:2004) nen ghi tinh, khong can goi ham.
    items.append({
        "id": 49,
        "noi_dung_thiet_ke": "Bắt buộc trang bị bình chữa cháy xách tay — không phụ thuộc quy mô (TCVN 7435-1:2004).",
        "ket_luan": "dat",
    })

    return items


# "yes"/"no"/"na"/"warn" -> ket_luan RIENG cho preview "thuoc dien he thong
# gi" (Dự án nhiều công trình, Đợt 2a, hang_muc_store.py) - KHAC HAN
# _RULE_TO_KET_LUAN o tren (Form A gop ca "yes" LAN "no" thanh "dat", vi Form
# A chi quan tam "dong da tra loi chua", khong phai "co bat buoc khong"). O
# day can PHAN BIET that "yes" (bat buoc trang bi, "dat") voi "no" (rule da
# chay nhung KHONG bat buoc - gop chung voi "na" thanh "khong_ap_dung") -
# neu dung nham _RULE_TO_KET_LUAN se lam preview hien SAI he thong khong bat
# buoc (vd loa thong bao duoi nguong 18.000m2 van bi liet ke nham la "thuoc
# dien" vi evaluate_loa() tra ve "no" chu khong phai "na").
_RULE_TO_THUOC_DIEN_KET_LUAN = {
    "yes": "dat",
    "no": "khong_ap_dung",
    "na": "khong_ap_dung",
    "warn": "chua_the_hien",
    "chua_du_du_lieu": "chua_the_hien",
}


def build_thuoc_dien_preview_items(fields: dict) -> list:
    """Dự án nhiều công trình (Đợt 2a) — rút gọn "công trình này thuộc diện
    bắt buộc trang bị hệ thống gì" cho 1 bộ quy mô, dùng CHUNG _TYPE1_ROWS/
    _safe_eval/evaluate_den với build_type1_items() (KHÔNG viết lại/KHÔNG
    đổi bất kỳ ngưỡng nào) — chỉ khác cách map "ket_luan" (xem
    _RULE_TO_THUOC_DIEN_KET_LUAN) để "dat" ĐÚNG NGHĨA "bắt buộc trang bị",
    dùng để lọc hiển thị (khác build_type1_items(), nơi "dat" chỉ có nghĩa
    "đã có kết luận rule-based", có thể là yes HOẶC no)."""
    items = []
    for row_id, fn in _TYPE1_ROWS:
        r = _safe_eval(fn, fields)
        items.append({
            "id": row_id,
            "noi_dung_thiet_ke": r.get("detail", "—"),
            "ket_luan": _RULE_TO_THUOC_DIEN_KET_LUAN.get(r["result"], "chua_the_hien"),
        })

    r = _safe_eval(evaluate_den, fields)
    if r["result"] == "yes" and "pos" in r:
        noi_dung = "Vị trí bắt buộc lắp đặt: " + "; ".join(r["pos"]) + "."
    else:
        noi_dung = r.get("detail", "—")
    items.append({
        "id": 42,
        "noi_dung_thiet_ke": noi_dung,
        "ket_luan": _RULE_TO_THUOC_DIEN_KET_LUAN.get(r["result"], "chua_the_hien"),
    })

    items.append({
        "id": 49,
        "noi_dung_thiet_ke": "Bắt buộc trang bị bình chữa cháy xách tay — không phụ thuộc quy mô (TCVN 7435-1:2004).",
        "ket_luan": "dat",
    })

    return items


# ---------------------------------------------------------------------------
# Bang A.2/A.4 (id 8,10,17,19) — AI doc ban ve, khong co rule san.
# ---------------------------------------------------------------------------
def _build_ai_answered_items(a2_bao_chay, a4_bao_chay, a2_sprinkler, a4_sprinkler):
    def item(row_id, text):
        text = (text or "").strip() or KHONG_XAC_DINH_AI
        ket_luan = "chua_the_hien" if text == KHONG_XAC_DINH_AI else "dat"
        return {"id": row_id, "noi_dung_thiet_ke": text, "ket_luan": ket_luan}

    return [
        item(8, a2_bao_chay),
        item(10, a4_bao_chay),
        item(17, a2_sprinkler),
        item(19, a4_sprinkler),
    ]


# ---------------------------------------------------------------------------
# "Yeu cau ky thuat chi tiet" (Type 2) — tinh, dung chung cho ca 2 route.
# ---------------------------------------------------------------------------
_DAN_CHIEU_ITEMS = {
    13: "B1 (báo cháy tự động thường)/B2 (báo cháy tự động địa chỉ)",
    25: "B6 (chữa cháy tự động bằng nước)",
    28: "B5 (họng nước chữa cháy trong nhà)",
    34: "B3 (trạm bơm cấp nước chữa cháy)",
    # id 36/37: Form A chỉ có 1 cặp dòng chung "hệ thống chữa cháy bằng khí" cho
    # CẢ 4 hạng mục AI đọc riêng biệt (B8/B9/B10/B11, xem khibotsolkhi_reader.py)
    # — liệt kê đủ cả 4, người dùng tự chọn đúng form đã đối chiếu cho công trình
    # này (giống cách id=13 liệt kê B1/B2 cùng lúc).
    36: "B8 (khí hóa lỏng)/B9 (khí nén)/B10 (khí CO2)/B11 (sol-khí)",
    37: "B8 (khí hóa lỏng)/B9 (khí nén)/B10 (khí CO2)/B11 (sol-khí)",
    # id=38: B7 (bọt cố định) nay đã có reader riêng (botcodinh_reader.py) —
    # dẫn chiếu như mọi hạng mục B khác.
    38: "B7 (chữa cháy bằng bọt cố định cho bể chứa xăng dầu)",
    43: "B13 (đèn chiếu sáng sự cố & chỉ dẫn thoát nạn)",
    46: "B13 (loa thông báo & hướng dẫn thoát nạn)",
    50: "B12 (bình chữa cháy xách tay)",
    63: "B14 (điện phục vụ PCCC)",
}

# Chua co mau B4 dang ky trong mdc_filler.TEMPLATE_PATHS — de trong, chua the hien.
_CHUA_TRIEN_KHAI_ITEMS = {
    32: "trạm bơm/bể nước chữa cháy ngoài nhà (B4)",
}

_CHUA_XAC_DINH_ITEMS = {
    12: "Khu vực được phép không trang bị báo cháy tự động (Điều 1.5.11 QCVN 10:2025/BCA)",
    21: "Sự phù hợp giữa loại hệ thống chữa cháy tự động và đối tượng cần bảo vệ (Điều 2.5.1 QCVN 10:2025/BCA)",
    22: "Khu vực được phép không trang bị chữa cháy tự động (Điều 1.5.11 QCVN 10:2025/BCA)",
    31: "Lưu ý cấp nước chữa cháy ngoài nhà (Điều 2.3.2 QCVN 10:2025/BCA)",
    56: "Vị trí bố trí dụng cụ phá dỡ thô sơ (Điều 2.7.1 QCVN 10:2025/BCA)",
    58: "Vị trí bố trí mặt nạ lọc độc (Điều 2.7.2 QCVN 10:2025/BCA)",
    61: "Địa điểm, nơi quản lý, bảo quản phương tiện chữa cháy cơ giới, nếu có trang bị xe (Thông tư 36/2025/TT-BCA)",
}

# id 51/52 (bình bột/bình khí tự động treo GẮN TẠI CHỖ, quy mô nhỏ) là hạng mục
# KHÁC với B7-B11 (hệ thống chữa cháy khí/bọt/sol-khí cho CẢ khu vực bảo vệ,
# quy mô lớn hơn hẳn) dù tên gọi dễ gây nhầm "sol-khí"/"khí" giống nhau — đã có
# xử lý riêng ở B12 (densucco_reader.py id 14,15/17-22, "khong_ap_dung" khi
# không thiết kế). KHÔNG gộp/dẫn chiếu 51/52 sang B7-B11 — giữ nguyên "Không
# thiết kế" như cũ (đúng yêu cầu owner: cân nhắc đổi cấu trúc này cần xác nhận
# riêng).
_KHONG_THIET_KE_ITEMS = {
    51: "bình bột chữa cháy tự động kích hoạt loại treo",
    52: "bình khí, bình sol-khí chữa cháy tự động kích hoạt",
}


def _build_static_items() -> list:
    items = []
    for row_id, label in _DAN_CHIEU_ITEMS.items():
        items.append({
            "id": row_id,
            "noi_dung_thiet_ke": f"Đã đối chiếu chi tiết tại mẫu {label} — xem kết luận cụ thể tại form tương ứng.",
            "ket_luan": "dat",
        })
    for row_id, label in _CHUA_TRIEN_KHAI_ITEMS.items():
        items.append({
            "id": row_id,
            "noi_dung_thiet_ke": f"Chưa có mẫu đối chiếu {label} trong hệ thống — chưa thể hiện.",
            "ket_luan": "chua_the_hien",
        })
    for row_id, label in _CHUA_XAC_DINH_ITEMS.items():
        items.append({
            "id": row_id,
            "noi_dung_thiet_ke": f"{label} — cần đối chiếu mặt bằng/hồ sơ cụ thể, chưa xác định.",
            "ket_luan": "chua_the_hien",
        })
    for row_id, label in _KHONG_THIET_KE_ITEMS.items():
        items.append({
            "id": row_id,
            "noi_dung_thiet_ke": f"Không thiết kế {label} — chưa có công cụ AI đọc bản vẽ riêng cho hạng mục này, tạm ghi không thiết kế.",
            "ket_luan": "khong_ap_dung",
        })
    return items


def build_form_a_items(fields: dict, a2_bao_chay=None, a4_bao_chay=None, a2_sprinkler=None, a4_sprinkler=None) -> list:
    """Combiner cấp cao nhất — dùng CHUNG cho cả route AI (có a2/a4 do AI đọc
    được) và route nhập tay (a2/a4=None -> KHONG_XAC_DINH_AI, vì nhập tay
    không có bản vẽ để đọc 2 mục này)."""
    items = []
    items += build_quy_mo_profile_items(fields)
    items += build_type1_items(fields)
    items += _build_ai_answered_items(a2_bao_chay, a4_bao_chay, a2_sprinkler, a4_sprinkler)
    items += _build_static_items()
    return items
