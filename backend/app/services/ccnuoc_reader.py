"""AI đọc bản vẽ — hệ thống chữa cháy bằng nước.

Khác báo cháy (2 mẫu loại trừ nhau) và điện PCCC (1 mẫu duy nhất), "Chữa
cháy bằng nước" gộp 3 mẫu đối chiếu riêng biệt CÙNG áp dụng cho 1 bộ bản vẽ:
- MĐC B3 — trạm bơm cấp nước chữa cháy
- MĐC B5 — họng nước chữa cháy trong nhà
- MĐC B6 — chữa cháy tự động bằng nước, bọt (sprinkler/drencher)

Gọi AI 3 lần (mỗi lần 1 mẫu, cùng 1 file bản vẽ) chạy song song bằng
ThreadPoolExecutor để tổng thời gian chờ ≈ mẫu chậm nhất thay vì cộng dồn
cả 3, rồi gộp kết quả lại. Nếu 1-2 mẫu lỗi vẫn trả về mẫu còn thành công.
"""

from concurrent.futures import ThreadPoolExecutor

from . import mdc_filler
from .ai_reader_common import AIReaderError, read_drawing_json

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


def _build_system_prompt(loai, mdc_label, ten_he_thong):
    rows = mdc_filler.load_criteria_rows(loai)
    return f"""Bạn là kỹ sư PCCC rà soát bản vẽ hệ thống {ten_he_thong}, đối chiếu với mẫu đối chiếu {mdc_label}.

BƯỚC 1: Với MỖI dòng tiêu chí dưới đây (mỗi dòng có sẵn "id" — khi trả lời PHẢI giữ nguyên đúng id đó, và phải trả lời ĐỦ cho TẤT CẢ id, không bỏ sót), đối chiếu với bản vẽ và trả về:
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" của mẫu MĐC gốc — ngắn gọn, đúng mạch đối chiếu (dùng gạch đầu dòng "-" nếu nhiều ý), nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu bản vẽ không thể hiện đủ thông tin để kết luận: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
- "ket_luan": "dat" nếu nội dung trên bản vẽ đáp ứng đúng quy định; "chua_dat" nếu đã thể hiện nhưng vi phạm giá trị/quy định; "chua_the_hien" nếu bản vẽ không đủ thông tin để kết luận.

--- DANH SÁCH TIÊU CHÍ ({mdc_label} — {ten_he_thong}) ---
{_fmt_rows(rows)}

BƯỚC 2: Với MỖI id có "ket_luan" là "chua_dat" hoặc "chua_the_hien" ở bước 1, soạn thêm một câu kiến nghị theo đúng văn phong công văn PC07:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (nếu là "chua_the_hien" — thông tin đáng lẽ có trên bản vẽ nhưng chưa vẽ/ghi), "Bổ sung ..." (nếu cần thêm chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (nếu cần giải trình bằng lời).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể trên bản vẽ + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id tương ứng).
- Kết câu bằng phần căn cứ, in trong ngoặc đơn, lấy ĐÚNG "Khoản, Điều" đã ghi ở id đó — không tự bịa số Điều khác.
- Xếp mỗi kiến nghị vào đúng 1 trong 4 nhóm sau:
  - "chua_the_hien": nhóm I (nội dung chưa thể hiện trên bản vẽ).
  - "chua_dat": nhóm III (nội dung đã thể hiện nhưng vi phạm giá trị/quy định của tiêu chuẩn).
  - Nhóm II (chưa thống nhất giữa nhiều nguồn số liệu) và nhóm IV (đề xuất bổ sung hồ sơ/bản vẽ mới) CHỈ dùng khi có căn cứ rõ ràng từ chính bản vẽ này; nếu không có căn cứ, để mảng rỗng — KHÔNG cố tạo kiến nghị cho đủ 4 nhóm.
- Nếu mọi id đều "dat", để cả 4 mảng đều rỗng.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Bản vẽ có thể không thể hiện hệ thống {ten_he_thong} (ví dụ công trình không có hạng mục này) — khi đó ghi "chưa thể hiện trên bản vẽ cung cấp" cho toàn bộ, không suy đoán là "không áp dụng".
- Không được bỏ sót bất kỳ id nào.

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON:
{{
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

CcNuocReaderError = AIReaderError


def read_drawing(file_bytes: bytes, media_type: str, provider) -> dict:
    """Gọi AI 3 lần (B3/B5/B6) song song cho cùng 1 bản vẽ, gộp kết quả lại."""

    def _call(form):
        return read_drawing_json(file_bytes, media_type, provider, SYSTEM_PROMPTS[form["loai"]])

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
    for form in FORMS:
        loai = form["loai"]
        if loai in results:
            data = results[loai]
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
    }
