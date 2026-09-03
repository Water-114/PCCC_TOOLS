"""AI đọc bản vẽ — "Đính 1 bản vẽ, AI tự nhận diện và điền nhiều mẫu đối chiếu"
(Batch 5A sub-bước 5). 1 LƯỢT GỌI AI DUY NHẤT vừa xác định bản vẽ thuộc (các)
hạng mục nào trong 5 hạng mục ĐÃ CÓ AI thật, vừa điền luôn kết quả đầy đủ cho
TỪNG hạng mục phát hiện được — không tách "quét trước, xác nhận sau" ở tầng AI
(việc xác nhận-trước-khi-trừ nằm ở tầng route/UI, xem routes/aiho.py).

5 hạng mục trong phạm vi (khớp đúng 5 route AI thật hiện có — KHÔNG bao gồm
B4/B8-B11 vì chưa có reader thật):
- "baochay"  -> B1 (thường) / B2 (địa chỉ)
- "ccnuoc"   -> B3 (trạm bơm) + B5 (họng nước) + B6 (chữa cháy tự động)
- "densucco" -> B12 (bình chữa cháy) + B13 (đèn sự cố/chỉ dẫn thoát nạn)
- "dienpccc" -> B14
- "quy_mo"   -> Form A (kiến trúc) — CHỈ đưa vào danh sách có thể phát hiện
  nếu phiên CHƯA có sẵn dữ liệu quy mô (xem read_and_detect(), tham số
  quy_mo=None/dict) — nếu đã có, KHÔNG hỏi AI phát hiện lại (đã có rồi), chỉ
  dùng dữ liệu đó làm NGỮ CẢNH cho 4 hạng mục kia, giống hệt 4 reader hiện có.

KIẾN TRÚC PROMPT — để giảm rủi ro "prompt quá dài giảm độ chính xác" (đã được
owner cảnh báo trước): 2 quy tắc dùng chung (NHOM_II_MAU_THUAN_CHECKLIST,
KHONG_UOC_LUONG_KHOANG_CACH) vốn đã viết TỔNG QUÁT không nhắc tên hạng mục cụ
thể, nên chỉ đặt 1 LẦN DUY NHẤT ở phần mở đầu dùng chung, KHÔNG lặp lại theo
từng hạng mục như nếu nối thô 5 prompt hiện có lại. Nội dung tiêu chí/special
block của từng hạng mục TÁI DÙNG NGUYÊN VẸN từ các module reader hiện có
(mdc_filler.load_criteria_rows(), ccnuoc_reader._TU_DONG_SCOPE_BLOCK,
densucco_reader._SPECIAL_ID_BLOCKS/_mucdo2_overrides, quymo_reader._A2_A4_TEXT)
— không hardcode lại số liệu/ngưỡng ở đây.
"""

from . import mdc_filler, quy_mo_store
from . import ccnuoc_reader, densucco_reader, quymo_reader
from .ai_reader_common import (
    DOC_CHU_XOAY_VA_KY_HIEU,
    KHONG_UOC_LUONG_KHOANG_CACH,
    NHOM_II_MAU_THUAN_CHECKLIST,
    STANDARD_PHRASES,
    read_and_validate_drawing_json,
    system_prompt_version,
)
from .ai_schema import KHONG_XAC_DINH_SO_HIEU, validate_merged_reader_result

# forms_per_call cua tung hang muc khi da phat hien — KHOP DUNG voi forms_per_call
# da dung o 5 route rieng le hien co (routes/aiho.py) de _handle_read_request
# giu nguyen, KHONG doi don vi "1 form" da thiet lap tu truoc (ccnuoc/densucco
# gop nhieu mau B trong 1 hang muc nen "nang" hon baochay/dienpccc/quy_mo).
CATEGORY_FORMS_PER_CALL = {
    "baochay": 1,
    "ccnuoc": 3,
    "densucco": 2,
    "dienpccc": 1,
    "quy_mo": 1,
}

CATEGORY_LABELS = {
    "baochay": "Báo cháy tự động",
    "ccnuoc": "Chữa cháy bằng nước",
    "densucco": "Đèn sự cố / chỉ dẫn thoát nạn / Bình chữa cháy",
    "dienpccc": "Điện PCCC",
    "quy_mo": "Quy mô công trình",
}

ALL_CATEGORIES = ("baochay", "ccnuoc", "densucco", "dienpccc", "quy_mo")

_DETECTION_HINTS = {
    "baochay": "đầu báo cháy (khói/nhiệt), tủ trung tâm báo cháy, chuông/đèn báo cháy, dây tín hiệu, ký hiệu loop/zone",
    "ccnuoc": "họng nước chữa cháy, trạm bơm chữa cháy, đầu phun sprinkler/drencher, bể nước chữa cháy, đường ống cấp nước chữa cháy",
    "densucco": "đèn chiếu sáng sự cố, đèn chỉ dẫn thoát nạn (exit), bình chữa cháy xách tay/xe đẩy, ký hiệu bình bột/bình khí",
    "dienpccc": "sơ đồ điện, tủ điện PCCC, cáp/dây chống cháy, máy phát điện dự phòng phục vụ PCCC",
    "quy_mo": "mặt bằng kiến trúc tổng thể, mặt cắt, bảng thống kê diện tích/số tầng, thuyết minh kiến trúc",
}


def _fmt_rows(rows):
    return "\n".join(
        f"id={r['id']} | [{r['doi_chieu']}] {r['quy_dinh']} (Căn cứ: {r['khoan_dieu']})"
        for r in rows
    )


def _baochay_block():
    rows_thuong = mdc_filler.load_criteria_rows("thuong")
    rows_dia_chi = mdc_filler.load_criteria_rows("dia_chi")
    return f"""<hang_muc id="baochay">
Tên hạng mục: {CATEGORY_LABELS['baochay']} (MĐC B1/B2). Dấu hiệu nhận diện: {_DETECTION_HINTS['baochay']}.
NẾU phát hiện: trước tiên xác định LOẠI THƯỜNG (zone theo khu vực) hay LOẠI ĐỊA CHỈ (mỗi đầu báo có địa chỉ riêng), rồi CHỈ đối chiếu với ĐÚNG danh sách tiêu chí của loại đã xác định bên dưới — không trả lời cho danh sách của loại còn lại.
--- DANH SÁCH TIÊU CHÍ LOẠI THƯỜNG (MĐC B1) ---
{_fmt_rows(rows_thuong)}
--- DANH SÁCH TIÊU CHÍ LOẠI ĐỊA CHỈ (MĐC B2) ---
{_fmt_rows(rows_dia_chi)}
</hang_muc>"""


def _dienpccc_block():
    rows = mdc_filler.load_criteria_rows("dien_pccc")
    return f"""<hang_muc id="dienpccc">
Tên hạng mục: {CATEGORY_LABELS['dienpccc']} (MĐC B14). Dấu hiệu nhận diện: {_DETECTION_HINTS['dienpccc']}.
--- DANH SÁCH TIÊU CHÍ (MĐC B14) ---
{_fmt_rows(rows)}
</hang_muc>"""


def _ccnuoc_block():
    parts = []
    for f in ccnuoc_reader.FORMS:
        rows = mdc_filler.load_criteria_rows(f["loai"])
        extra = ccnuoc_reader._TU_DONG_SCOPE_BLOCK if f["loai"] == "chua_chay_tu_dong" else ""
        field_note = ' Với mẫu này, thêm field "co_thiet_ke_tu_dong": true|false trong kết quả của đúng mẫu này (xem hướng dẫn riêng ngay dưới).' if f["loai"] == "chua_chay_tu_dong" else ""
        parts.append(f"""  <mau loai="{f['loai']}" mdc_label="{f['mdc_label']}">
  Hệ thống: {f['ten_he_thong']}.{field_note}
{extra}  --- DANH SÁCH TIÊU CHÍ ({f['mdc_label']}) ---
{_fmt_rows(rows)}
  </mau>""")
    return f"""<hang_muc id="ccnuoc">
Tên hạng mục: {CATEGORY_LABELS['ccnuoc']}. Dấu hiệu nhận diện: {_DETECTION_HINTS['ccnuoc']}. Hạng mục này GỘP 3 mẫu đối chiếu riêng biệt (B3/B5/B6) — nếu phát hiện hạng mục này, đối chiếu ĐỦ CẢ 3 mẫu bên dưới (trừ B6 khi không có dấu hiệu hệ tự động — xem hướng dẫn riêng của B6):
{chr(10).join(parts)}
</hang_muc>"""


def _densucco_block(quy_mo):
    overrides = densucco_reader._mucdo2_overrides(quy_mo)
    parts = []
    for f in densucco_reader.FORMS:
        rows = mdc_filler.load_criteria_rows(f["loai"])
        special = densucco_reader._SPECIAL_ID_BLOCKS.get(f["loai"], "") + overrides.get(f["loai"], "")
        parts.append(f"""  <mau loai="{f['loai']}" mdc_label="{f['mdc_label']}">
  Hệ thống: {f['ten_he_thong']}.
{special}  --- DANH SÁCH TIÊU CHÍ ({f['mdc_label']}) ---
{_fmt_rows(rows)}
  </mau>""")
    return f"""<hang_muc id="densucco">
Tên hạng mục: {CATEGORY_LABELS['densucco']}. Dấu hiệu nhận diện: {_DETECTION_HINTS['densucco']}. Hạng mục này GỘP 2 mẫu đối chiếu riêng biệt (B12/B13) — nếu phát hiện hạng mục này, đối chiếu ĐỦ CẢ 2 mẫu bên dưới:
{chr(10).join(parts)}
</hang_muc>"""


def _quy_mo_block():
    return f"""<hang_muc id="quy_mo">
Tên hạng mục: {CATEGORY_LABELS['quy_mo']} (Form A). Dấu hiệu nhận diện: {_DETECTION_HINTS['quy_mo']}.
NẾU phát hiện: trích xuất object "quy_mo" (field "occ" BẮT BUỘC, chọn đúng 1 trong danh sách công năng sau, các field còn lại để null nếu bản vẽ không thể hiện — TUYỆT ĐỐI không suy đoán):
{quymo_reader._fmt_occupations()}
Các field khác trong "quy_mo": floors, basements, semiBasements, areaFloor, totalArea, volume, hFire (chiều cao phục vụ PCCC — Điều 1.4.9 QCVN 06:2022/BXD), kids, seats, hazard (A/B/C/D/E), garaKin ("kin"/"ho"), garaKC12 ("le12"/"gt12"), garaBcl ("I".."V"), garaCapS ("S0".."S3"), pplFloor, extLevel ("thap"/"tb"/"cao"), hanhLangDaiNhat.
Đồng thời trả lời 4 mục sau (ghi đúng nguyên văn "{quymo_reader.KHONG_XAC_DINH_A2_A4}" nếu bản vẽ không đủ thông tin, KHÔNG suy đoán):
{quymo_reader._fmt_a2_a4()}
</hang_muc>"""


_CATEGORY_BLOCK_BUILDERS = {
    "baochay": lambda quy_mo: _baochay_block(),
    "ccnuoc": lambda quy_mo: _ccnuoc_block(),
    "densucco": lambda quy_mo: _densucco_block(quy_mo),
    "dienpccc": lambda quy_mo: _dienpccc_block(),
    "quy_mo": lambda quy_mo: _quy_mo_block(),
}


def _output_schema_snippet(detectable):
    per_cat = []
    if "baochay" in detectable:
        per_cat.append('  "baochay": null hoặc {"loai_he_thong": "thuong"|"dia_chi", "ly_do_nhan_dien": "...", "items": [{"id":2,"noi_dung_thiet_ke":"...","ket_luan":"dat"|"chua_dat"|"chua_the_hien"}], "tong_ket": "...", "kien_nghi": {"I_chua_the_hien":[],"II_chua_thong_nhat":[],"III_chua_phu_hop":[],"IV_de_xuat_bo_sung":[]}},')
    if "ccnuoc" in detectable:
        per_cat.append('  "ccnuoc": null hoặc {"forms": {"tram_bom": {...items/tong_ket/kien_nghi...} , "hong_nuoc": {...}, "chua_chay_tu_dong": {"co_thiet_ke_tu_dong": true|false, ...items/tong_ket/kien_nghi...} }},')
    if "densucco" in detectable:
        per_cat.append('  "densucco": null hoặc {"forms": {"binh_chua_chay": {...items/tong_ket/kien_nghi...}, "den_su_co": {...items/tong_ket/kien_nghi...} }},')
    if "dienpccc" in detectable:
        per_cat.append('  "dienpccc": null hoặc {"items": [...], "tong_ket": "...", "kien_nghi": {...}},')
    if "quy_mo" in detectable:
        per_cat.append('  "quy_mo": null hoặc {"quy_mo": {"occ":"...", ...}, "bang_a2_bao_chay":"...", "bang_a4_bao_chay":"...", "bang_a2_sprinkler":"...", "bang_a4_sprinkler":"..."},')
    return "\n".join(per_cat)


def build_system_prompt(quy_mo):
    """quy_mo: dict neu phien DA co san du lieu quy mo (tu 1 lan doc/nhap tay
    truoc do trong CUNG phien) - khi do KHONG dua "quy_mo" vao danh sach hang
    muc co the phat hien nua (da co roi), chi dung lam NGU CANH cho 4 hang muc
    con lai (giong het 4 reader hien co). None neu phien CHUA co -> "quy_mo"
    la 1 trong 5 hang muc AI co the phat hien tren chinh ban ve nay."""
    detectable = tuple(c for c in ALL_CATEGORIES if c != "quy_mo" or not quy_mo)
    blocks = "\n\n".join(_CATEGORY_BLOCK_BUILDERS[c](quy_mo) for c in detectable)
    labels_list = ", ".join(f'"{c}" ({CATEGORY_LABELS[c]})' for c in detectable)

    prompt = f"""Bạn là kỹ sư PCCC rà soát 1 bản vẽ, đối chiếu với NHIỀU mẫu đối chiếu MĐC cùng lúc.

YÊU CẦU THÊM: Đọc SỐ HIỆU BẢN VẼ ghi trong khung tên (title block) của chính bản vẽ này. Nếu khung tên không có, không rõ, hoặc bản vẽ không thể hiện số hiệu: ghi ĐÚNG NGUYÊN VĂN "{KHONG_XAC_DINH_SO_HIEU}" ở trường "so_hieu_ban_ve" — TUYỆT ĐỐI không suy đoán.

BƯỚC 1 — PHÂN LOẠI (làm TRƯỚC KHI đối chiếu bất kỳ tiêu chí nào): bản vẽ này có thể thuộc 1 hoặc NHIỀU trong {len(detectable)} hạng mục sau: {labels_list}. Với MỖI hạng mục, chỉ đánh dấu là "có xuất hiện" (đưa vào "detected_categories") khi bản vẽ có BẰNG CHỨNG CỤ THỂ (ký hiệu/chú giải/sơ đồ đặc trưng đúng hệ thống đó — xem "Dấu hiệu nhận diện" trong từng khối bên dưới) — TUYỆT ĐỐI KHÔNG suy đoán từ loại công trình hoặc "có thể liên quan". Nếu chỉ thấy dấu hiệu mơ hồ, không đủ chắc chắn: KHÔNG đưa hạng mục đó vào "detected_categories" (bỏ sót còn hơn đoán bừa — người dùng sẽ mất Bộ hồ sơ oan cho hạng mục không thật sự có trên bản vẽ). Bản vẽ hoàn toàn có thể không thuộc hạng mục nào, hoặc thuộc nhiều hạng mục cùng lúc (bản vẽ tổng hợp).

BƯỚC 2 — Với MỖI hạng mục đã đưa vào "detected_categories" ở Bước 1, đối chiếu đầy đủ theo đúng danh sách tiêu chí và hướng dẫn riêng (nếu có) của hạng mục đó dưới đây. Với hạng mục KHÔNG có trong "detected_categories": để giá trị null trong JSON, KHÔNG điền gì cho hạng mục đó.

Với MỖI id trong 1 danh sách tiêu chí (khi trả lời PHẢI giữ nguyên đúng id đó, trả lời ĐỦ cho TẤT CẢ id thuộc mẫu đang đối chiếu, không bỏ sót):
- "noi_dung_thiet_ke": nội dung điền vào cột "Nội dung thiết kế" — ngắn gọn, đúng mạch đối chiếu, nêu số liệu cụ thể NHÌN THẤY trên bản vẽ. Nếu không đủ thông tin: ghi đúng "Chưa thể hiện trên bản vẽ cung cấp".
{STANDARD_PHRASES}
- "ket_luan": "dat" | "chua_dat" | "chua_the_hien" (và "khong_ap_dung" CHỈ dùng cho đúng các id có hướng dẫn riêng chỉ định rõ là mục tuỳ chọn).

{blocks}

BƯỚC 3 — Với MỖI id (thuộc bất kỳ mẫu nào ở Bước 2) có "ket_luan" là "chua_dat" hoặc "chua_the_hien", soạn thêm câu kiến nghị theo đúng văn phong công văn PC07, gắn vào ĐÚNG mẫu (loai) chứa id đó:
- Mở đầu bằng động từ mệnh lệnh phù hợp: "Thể hiện rõ ..." (chua_the_hien), "Bổ sung ..." (thiếu chi tiết/thiết bị/bản vẽ), hoặc "Thuyết minh rõ ..." (cần giải trình).
- Một câu mạch lạc, nêu rõ đối tượng cụ thể + số liệu định lượng của tiêu chuẩn (lấy từ đúng nội dung quy định của id đó).
- Kết câu bằng phần căn cứ trong ngoặc đơn, lấy ĐÚNG Khoản/Điều đã ghi ở id đó — không tự bịa số Điều khác.
- Xếp vào đúng 1 trong 4 nhóm: "chua_the_hien" → nhóm I; "chua_dat" → nhóm III; nhóm II và IV chỉ dùng khi có căn cứ rõ ràng từ chính bản vẽ này (trừ các id đã có hướng dẫn riêng chỉ định rõ nhóm), không cố tạo đủ 4 nhóm.
{NHOM_II_MAU_THUAN_CHECKLIST}
- Nếu mọi id của 1 mẫu đều "dat", để cả 4 mảng kiến nghị của mẫu đó rỗng.

NGUYÊN TẮC BẮT BUỘC (áp dụng cho MỌI hạng mục/mẫu ở trên):
- Chỉ đánh giá dựa trên nội dung THỰC SỰ thể hiện trên bản vẽ được cung cấp. Không suy đoán, không dùng kiến thức chung ngoài bản vẽ.
- Không được bỏ sót bất kỳ id nào thuộc mẫu đang đối chiếu.
{KHONG_UOC_LUONG_KHOANG_CACH}
{DOC_CHU_XOAY_VA_KY_HIEU}

Trả lời DUY NHẤT bằng JSON hợp lệ theo đúng cấu trúc sau, không thêm văn bản nào khác ngoài JSON. Chỉ điền giá trị (không phải null) cho ĐÚNG các hạng mục có trong "detected_categories":
{{
  "detected_categories": [{", ".join(f'"{c}"' for c in detectable)} — chỉ liệt kê những hạng mục THẬT SỰ phát hiện được, có thể rỗng []],
  "so_hieu_ban_ve": "...",
{_output_schema_snippet(detectable)}
}}"""

    if quy_mo:
        prompt += quy_mo_store.format_quy_mo_context(quy_mo)
    return prompt


def _validate_for(quy_mo):
    def _validate(data: dict):
        return validate_merged_reader_result(data, quy_mo_known=bool(quy_mo))
    return _validate


def read_and_detect(file_bytes: bytes, media_type: str, provider, quy_mo: dict = None) -> dict:
    """Gọi AI 1 LẦN DUY NHẤT, trả về dict {detected_categories, so_hieu_ban_ve,
    <cat>: {...}}. Mỗi <cat> present đã qua Pydantic validate (đủ id, đúng enum)
    y hệt mức kiểm tra của 5 reader riêng lẻ — chỉ khác ở chỗ gộp chung 1 lượt gọi."""
    system_prompt = build_system_prompt(quy_mo)
    model = read_and_validate_drawing_json(
        file_bytes, media_type, provider, system_prompt, _validate_for(quy_mo),
        prompt_version=system_prompt_version(system_prompt),
    )
    return model.model_dump()


def _combine_multi_form(cat_data, forms_meta, so_hieu_ban_ve):
    """Dựng lại ĐÚNG shape mà ccnuoc_reader.read_drawing()/densucco_reader.read_drawing()
    vốn đã trả về (forms_out {label,mdc_label,items} + kien_nghi/tong_ket GỘP) từ
    dữ liệu merged_reader (mỗi sub-form chỉ có items/tong_ket/kien_nghi thô) — để
    routes/aiho.py và frontend (renderMdcReal/renderKienNghiReal/itemsForMdcFile)
    dùng lại NGUYÊN VẸN logic hiện có, không cần biết dữ liệu tới từ 1 hay 3 lượt gọi AI."""
    combined_kien_nghi = {"I_chua_the_hien": [], "II_chua_thong_nhat": [], "III_chua_phu_hop": [], "IV_de_xuat_bo_sung": []}
    tong_ket_parts = []
    forms_out = {}
    forms = cat_data.get("forms") or {}
    for meta in forms_meta:
        loai = meta["loai"]
        data = forms.get(loai)
        if not data:
            continue
        # Cung 1 chi dao nghiep vu nhu ccnuoc_reader.read_drawing(): B6 chi xuat
        # MDC khi cong trinh THAT SU thiet ke he tu dong - "co_thiet_ke_tu_dong"
        # (neu co field nay) quyet dinh co loai form nay khoi forms_out hay khong.
        if data.get("co_thiet_ke_tu_dong") is False:
            if data.get("tong_ket"):
                tong_ket_parts.append(meta["ten_he_thong"].capitalize() + ": " + data["tong_ket"])
            continue
        forms_out[loai] = {"label": meta["ten_he_thong"], "mdc_label": meta["mdc_label"], "items": data.get("items", [])}
        kn = data.get("kien_nghi") or {}
        for key in combined_kien_nghi:
            combined_kien_nghi[key].extend(kn.get(key) or [])
        if data.get("tong_ket"):
            tong_ket_parts.append(meta["ten_he_thong"].capitalize() + ": " + data["tong_ket"])
    return {
        "forms": forms_out,
        "tong_ket": " ".join(tong_ket_parts),
        "kien_nghi": combined_kien_nghi,
        "so_hieu_ban_ve": so_hieu_ban_ve,
    }


def finalize_category_result(cat: str, merged_result: dict) -> dict:
    """Chuyển 1 hạng mục trong kết quả read_and_detect() về ĐÚNG shape mà route
    /read-<hạng mục> riêng lẻ hiện có vẫn trả — để tái dùng NGUYÊN VẸN _build_mdc_file()/
    build_*_mdc() và cách frontend hiển thị (không phải viết code hiển thị mới)."""
    so_hieu = merged_result.get("so_hieu_ban_ve", KHONG_XAC_DINH_SO_HIEU)
    cat_data = merged_result.get(cat) or {}

    if cat in ("baochay", "dienpccc", "quy_mo"):
        out = dict(cat_data)
        out["so_hieu_ban_ve"] = so_hieu
        return out

    if cat == "ccnuoc":
        return _combine_multi_form(cat_data, ccnuoc_reader.FORMS, so_hieu)

    if cat == "densucco":
        return _combine_multi_form(cat_data, densucco_reader.FORMS, so_hieu)

    raise ValueError(f"Hạng mục không hợp lệ: {cat}")
