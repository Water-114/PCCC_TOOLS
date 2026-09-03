"""AI đọc bản vẽ — hệ thống chữa cháy bằng nước.

Khác báo cháy (2 mẫu loại trừ nhau) và điện PCCC (1 mẫu duy nhất), "Chữa
cháy bằng nước" gộp 3 mẫu đối chiếu riêng biệt CÙNG áp dụng cho 1 bộ bản vẽ:
- MĐC B3 — trạm bơm cấp nước chữa cháy
- MĐC B5 — họng nước chữa cháy trong nhà
- MĐC B6 — chữa cháy tự động bằng nước, bọt (sprinkler/drencher)

Gọi AI 3 lần (mỗi lần 1 mẫu, cùng 1 file bản vẽ) chạy song song bằng
ThreadPoolExecutor để tổng thời gian chờ ≈ mẫu chậm nhất thay vì cộng dồn
cả 3, rồi gộp kết quả lại. Nếu 1-2 mẫu lỗi vẫn trả về mẫu còn thành công.

Chỉ đạo nghiệp vụ của owner (không phải suy đoán): B6 chỉ áp dụng cho công
trình THẬT SỰ thiết kế hệ sprinkler/drencher — nếu bản vẽ không có bất kỳ dấu
hiệu nào (sơ đồ/ghi chú/bảng tính) cho thấy hệ này được thiết kế, KHÔNG xuất
form B6 nữa (trước đây luôn xuất đủ cả 3 form bất kể có hay không). AI tự xác
định qua field mới "co_thiet_ke_tu_dong" (xem ChuaChayTuDongReaderResult,
ai_schema.py) TRƯỚC khi đối chiếu — nếu false thì loại B6 khỏi forms_out và
không sinh kiến nghị cho B6; nếu true thì đối chiếu bình thường như B3/B5.
"""

from concurrent.futures import ThreadPoolExecutor

from . import mdc_filler, quy_mo_store
from .ai_reader_common import (
    DOC_CHU_XOAY_VA_KY_HIEU,
    KHONG_UOC_LUONG_KHOANG_CACH,
    NHOM_II_MAU_THUAN_CHECKLIST,
    STANDARD_PHRASES,
    TOA_DO_TRUC_KHOANG_CACH,
    AIReaderError,
    read_and_validate_drawing_json,
    system_prompt_version,
)
from .ai_schema import ChuaChayTuDongReaderResult, KHONG_XAC_DINH_SO_HIEU, ReaderResult, validate_reader_result

FORMS = [
    {"loai": "tram_bom", "mdc_label": "MĐC B3", "ten_he_thong": "trạm bơm cấp nước chữa cháy"},
    {"loai": "hong_nuoc", "mdc_label": "MĐC B5", "ten_he_thong": "họng nước chữa cháy trong nhà"},
    {"loai": "chua_chay_tu_dong", "mdc_label": "MĐC B6", "ten_he_thong": "chữa cháy tự động bằng nước, bọt (sprinkler/drencher)"},
]


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


_TU_DONG_SCOPE_BLOCK = """
YÊU CẦU RIÊNG CHO MẪU NÀY (B6 — chữa cháy tự động bằng nước/bọt): TRƯỚC KHI đối chiếu từng tiêu chí, xác định công trình trên bản vẽ CÓ THIẾT KẾ hệ thống chữa cháy tự động bằng nước/bọt (sprinkler/drencher) hay không — căn cứ sơ đồ nguyên lý, ghi chú, bảng tính lưu lượng/số đầu phun hoặc bất kỳ chi tiết nào thể hiện hệ sprinkler/drencher trên chính bản vẽ này.
- Nếu KHÔNG có bất kỳ dấu hiệu nào (không sơ đồ, không ghi chú, không bảng tính liên quan tới hệ tự động): đặt "co_thiet_ke_tu_dong": false, "tong_ket": "Công trình không thiết kế hệ thống chữa cháy tự động bằng nước/bọt (sprinkler/drencher).", và với MỌI id trong danh sách tiêu chí bên dưới: "ket_luan": "dat", "noi_dung_thiet_ke": "Công trình không thiết kế hệ thống chữa cháy tự động bằng nước/bọt (sprinkler/drencher)." — để cả 4 nhóm kiến nghị đều rỗng (không tạo kiến nghị "Bổ sung" cho hệ không được thiết kế).
- Nếu CÓ dấu hiệu hệ sprinkler/drencher được thiết kế (dù chưa đầy đủ chi tiết): đặt "co_thiet_ke_tu_dong": true, rồi đối chiếu BÌNH THƯỜNG theo đúng Bước 1/Bước 2 bên dưới cho từng tiêu chí — tiêu chí nào bản vẽ chưa đủ thông tin vẫn ghi "chua_the_hien" như bình thường, KHÔNG tự đặt "dat" chỉ vì đã xác định có hệ tự động.
"""


def _build_system_prompt(loai, mdc_label, ten_he_thong):
    rows = mdc_filler.load_criteria_rows(loai)
    extra_scope_block = _TU_DONG_SCOPE_BLOCK if loai == "chua_chay_tu_dong" else ""
    extra_field_line = '\n  "co_thiet_ke_tu_dong": true | false,' if loai == "chua_chay_tu_dong" else ""
    # Chi B6 (sprinkler) co tieu chi khoang cach dau phun/den tuong/tran can
    # chan uoc luong bang mat - B3 (tram bom)/B5 (hong nuoc) khong co dang
    # tieu chi nay nen khong chen (tranh prompt dai khong can thiet).
    khoang_cach_block = KHONG_UOC_LUONG_KHOANG_CACH if loai == "chua_chay_tu_dong" else ""
    # Toa do truc chi co y nghia cho tieu chi khoang cach that su ton tai (B6) -
    # dung chung 1 dieu kien voi khoang_cach_block o tren.
    toa_do_truc_block = TOA_DO_TRUC_KHOANG_CACH if loai == "chua_chay_tu_dong" else ""
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống {ten_he_thong}, đối chiếu với mẫu đối chiếu {mdc_label}.

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này (thường ở góc dưới bên phải, ô ghi "Số bản vẽ" / "Ký hiệu bản vẽ" / "Drawing No."). Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "Không xác định được số hiệu bản vẽ" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán, không tự đặt số hiệu.
{extra_scope_block}
BƯỚC 1: Với MỖI dòng tiêu chí dưới đây (mỗi dòng có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id, không bỏ sót), đối chiếu với bản vẽ và trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
{toa_do_truc_block}
{STANDARD_PHRASES}
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận.

--- DANH SÁCH TIÊU CHÍ ({mdc_label} — {ten_he_thong}) ---
{_fmt_rows(rows)}

BƯỚC 2: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở bước 1, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (nếu là "chua_the_hien" — thông tin đáng lẽ có trên bản vẽ nhưng chưa vẽ/ghi), "Bổ sung ..." (nếu cần thêm chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (nếu cần giải trình bằng lời).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
{toa_do_truc_block}
- Kết câu bằng phần căn cứ, in trong ngoặc đơn, lấy ĐÚNG "Khoản, Điều" đã ghi ở id đó — không tự bịa số Điều khác.
- Xếp mỗi kiến nghị vào đúng 1 trong 4 nhóm sau:
  - "chua_the_hien": nhóm I (nội dung chưa thể hiện trên bản vẽ).
  - "chua_dat": nhóm III (nội dung đã thể hiện nhưng vi phạm giá trị/quy định của tiêu chuẩn).
  - Nhóm II (chưa thống nhất giữa nhiều nguồn số liệu) và nhóm IV (đề xuất bổ sung hồ sơ/bản vẽ mới) CHỈ dùng khi có căn cứ rõ ràng từ chính bản vẽ này; nếu không có căn cứ, để mảng rỗng — KHÔNG cố tạo kiến nghị cho đủ 4 nhóm.
{NHOM_II_MAU_THUAN_CHECKLIST}
- Nếu mọi id đều "dat", để cả 4 mảng đều rỗng.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Bản vẽ có thể không thể hiện hệ thống {ten_he_thong} (ví dụ công trình không có hạng mục này) — khi đó ghi "chưa thể hiện trên bản vẽ cung cấp" cho toàn bộ, không suy đoán là "không áp dụng".
- Không được bỏ sót bất kỳ id nào.
{khoang_cach_block}
{DOC_CHU_XOAY_VA_KY_HIEU}

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
  "so_hieu_ban_ve": "số hiệu bản vẽ đọc từ khung tên, hoặc \"Không xác định được số hiệu bản vẽ\"",{extra_field_line}
  "items": [
    {{"id": 2, "noi_dung_thiet_ke": "...", "ket_luan": "dat" | "chua_dat" | "chua_the_hien"}}
  ],
  "tong_ket": "1-2 câu tổng kết tình trạng chung của riêng hệ thống {ten_he_thong}",
  "kien_nghi": {{
    "I_chua_the_hien": ["câu kiến nghị theo khuôn PC07, kết bằng (Căn cứ Điều ..., Mục ... TCVN/QCVN ....)"],
    "II_chua_thong_nhat": [],
    "III_chua_phu_hop": ["câu kiến nghị tương tự cho các id chua_dat"],
    "IV_de_xuat_bo_sung": []
  }}
}}"""


SYSTEM_PROMPTS = {f["loai"]: _build_system_prompt(f["loai"], f["mdc_label"], f["ten_he_thong"]) for f in FORMS}
SYSTEM_PROMPT_VERSIONS = {loai: system_prompt_version(prompt) for loai, prompt in SYSTEM_PROMPTS.items()}

CcNuocReaderError = AIReaderError

_EXPECTED_IDS = {f["loai"]: {r["id"] for r in mdc_filler.load_criteria_rows(f["loai"])} for f in FORMS}

_MODEL_FOR = {
    "tram_bom": ReaderResult,
    "hong_nuoc": ReaderResult,
    "chua_chay_tu_dong": ChuaChayTuDongReaderResult,
}


def _validate_for(loai):
    def _validate(data: dict):
        return validate_reader_result(data, _EXPECTED_IDS[loai], _MODEL_FOR[loai])
    return _validate


def read_drawing(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gọi AI 3 lần (B3/B5/B6) song song cho cùng 1 bản vẽ, mỗi lần validate qua
    Pydantic (kèm retry-repair riêng từng lần nếu sai), rồi gộp kết quả lại.

    quy_mo: dữ liệu quy mô công trình (hạng mục "Quy mô") của CÙNG phiên Bộ hồ
    sơ, nếu người dùng CÓ đính kèm — HOÀN TOÀN TUỲ CHỌN (None nếu không đính,
    hành vi giữ nguyên 100% như trước).
    """
    context = quy_mo_store.format_quy_mo_context(quy_mo) if quy_mo else ""

    def _call(form):
        prompt = SYSTEM_PROMPTS[form["loai"]] + context
        return read_and_validate_drawing_json(
            file_bytes, media_type, provider, prompt, _validate_for(form["loai"]),
            prompt_version=SYSTEM_PROMPT_VERSIONS[form["loai"]],
        )

    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=len(FORMS)) as executor:
        future_to_form = {executor.submit(_call, f): f for f in FORMS}
        for future, form in future_to_form.items():
            try:
                results[form["loai"]] = future.result()
            except Exception as exc:
                errors[form["loai"]] = str(exc)

    if not results:
        raise AIReaderError("; ".join(errors.values()) or "Không rõ nguyên nhân.")

    combined_kien_nghi = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}
    tong_ket_parts = []
    forms_out = {}
    so_hieu_ban_ve = None
    for form in FORMS:
        loai = form["loai"]
        if loai in results:
            data = results[loai].model_dump()
            # Chi dao nghiep vu cua owner: B6 chi xuat khi cong trinh THAT SU
            # thiet ke he sprinkler/drencher - AI tu xac dinh qua field
            # "co_thiet_ke_tu_dong" (xem _TU_DONG_SCOPE_BLOCK). Neu false: loai
            # han B6 khoi forms_out (khong sinh MDC B6, khong cong kien nghi),
            # chi giu lai cau tong_ket de nguoi dung biet ly do.
            if loai == "chua_chay_tu_dong" and data.get("co_thiet_ke_tu_dong") is False:
                if data.get("tong_ket"):
                    tong_ket_parts.append(form["ten_he_thong"].capitalize() + ": " + data["tong_ket"])
                if so_hieu_ban_ve is None and data.get("so_hieu_ban_ve") and data["so_hieu_ban_ve"] != KHONG_XAC_DINH_SO_HIEU:
                    so_hieu_ban_ve = data["so_hieu_ban_ve"]
                continue

            forms_out[loai] = {
                "label": form["ten_he_thong"],
                "mdc_label": form["mdc_label"],
                "items": data.get("items", []),
            }
            kn = data.get("kien_nghi") or {}
            for key in combined_kien_nghi:
                combined_kien_nghi[key].extend(kn.get(key) or [])
            if data.get("tong_ket"):
                tong_ket_parts.append(form["ten_he_thong"].capitalize() + ": " + data["tong_ket"])
            # Lấy so_hieu_ban_ve từ lần đọc ĐẦU TIÊN (theo thứ tự FORMS) có giá trị
            # thật (khác placeholder "không xác định") — 3 lần gọi đều đọc cùng 1
            # file nên số hiệu phải giống nhau, chỉ cần 1 nguồn đáng tin.
            if so_hieu_ban_ve is None and data.get("so_hieu_ban_ve") and data["so_hieu_ban_ve"] != KHONG_XAC_DINH_SO_HIEU:
                so_hieu_ban_ve = data["so_hieu_ban_ve"]
        else:
            forms_out[loai] = {
                "label": form["ten_he_thong"],
                "mdc_label": form["mdc_label"],
                "error": errors.get(loai),
            }
            tong_ket_parts.append(form["ten_he_thong"].capitalize() + ": lỗi khi phân tích — " + str(errors.get(loai)))

    return {
        "forms": forms_out,
        "tong_ket": " ".join(tong_ket_parts),
        "kien_nghi": combined_kien_nghi,
        "so_hieu_ban_ve": so_hieu_ban_ve or KHONG_XAC_DINH_SO_HIEU,
    }
