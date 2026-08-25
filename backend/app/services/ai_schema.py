"""Pydantic schema cho kết quả AI đọc bản vẽ (Batch 4, sub-bước 1) — validate
cấu trúc JSON AI trả về (đủ tiêu chí/id đúng, enum kết luận hợp lệ, giới hạn
độ dài nội dung) TRƯỚC khi dùng để điền MĐC/kiến nghị, tránh dữ liệu nửa vời
lọt qua mà không bị phát hiện.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import mdc_filler
from .tham_dinh import OCCUPATIONS as _OCCUPATIONS

MAX_NOI_DUNG_LEN = 3000
KHONG_XAC_DINH_SO_HIEU = "Không xác định được số hiệu bản vẽ"
_VALID_OCC_IDS = {o["id"] for o in _OCCUPATIONS}

# "khong_ap_dung": mục TUỲ CHỌN (vd bình bột/bình khí tự động treo) mà công
# trình không thiết kế — KHÔNG phải thiếu sót, khác "chua_the_hien" (đáng lẽ
# phải có nhưng bản vẽ chưa thể hiện). Cột "Kết luận" trong MĐC để TRỐNG cho
# giá trị này (xem routes/aiho.py _answers_from_items(), mdc_filler.fill_docx()).
KetLuan = Literal["dat", "chua_dat", "chua_the_hien", "khong_ap_dung"]


class SchemaValidationError(Exception):
    """Lỗi validate schema hoặc thiếu/thừa id — dùng để kích hoạt retry-repair."""


class ItemResult(BaseModel):
    id: int
    noi_dung_thiet_ke: str = Field(max_length=MAX_NOI_DUNG_LEN)
    ket_luan: KetLuan


class KienNghi(BaseModel):
    I_chua_the_hien: List[str] = Field(default_factory=list)
    II_chua_thong_nhat: List[str] = Field(default_factory=list)
    III_chua_phu_hop: List[str] = Field(default_factory=list)
    IV_de_xuat_bo_sung: List[str] = Field(default_factory=list)


class ReaderResult(BaseModel):
    items: List[ItemResult]
    tong_ket: str = ""
    kien_nghi: KienNghi
    so_hieu_ban_ve: str = KHONG_XAC_DINH_SO_HIEU


class BaoChayReaderResult(ReaderResult):
    loai_he_thong: Literal["thuong", "dia_chi"]
    ly_do_nhan_dien: str = ""


class KhiBotSolKhiReaderResult(ReaderResult):
    """Rieng cho khibotsolkhi_reader.py (B8-B11: chua chay bang khi/sol-khi —
    B7 bot co dinh CO Y khong nam trong pham vi nay, xem docstring dau file
    khibotsolkhi_reader.py) - AI phai tu xac dinh DUNG 1 trong 4 he thong
    (khi_hoa_long/khi_nen/khi_co2/sol_khi) truoc khi doi chieu, giong het
    pattern loai_he_thong cua BaoChayReaderResult (thuong/dia_chi) - 4 nhanh
    thay vi 2."""
    he_thong: Literal["khi_hoa_long", "khi_nen", "khi_co2", "sol_khi"]
    ly_do_nhan_dien: str = ""


class ChuaChayTuDongReaderResult(ReaderResult):
    """Riêng cho mẫu B6 (chữa cháy tự động bằng nước/bọt) trong ccnuoc_reader.py
    — AI phải tự xác định công trình CÓ thiết kế hệ sprinkler/drencher hay
    không trước khi đối chiếu (chỉ đạo nghiệp vụ của owner). Không có default —
    bắt buộc AI trả lời rõ ràng, không được bỏ sót."""
    co_thiet_ke_tu_dong: bool


class GiaKeHangReaderResult(ReaderResult):
    """Riêng cho gia_ke_hang_reader.py (B15: chữa cháy tự động giá kệ hàng,
    TCVN 14496:2025) — KHÁC KhiBotSolKhiReaderResult ở chỗ 2 nhánh dùng CHUNG
    1 template/1 bộ id cố định (không chọn template theo nhánh) — AI vẫn phải
    trả lời ĐỦ mọi id, chỉ đánh dấu "khong_ap_dung" cho id thuộc nhánh không
    chọn (xem gia_ke_hang_reader._EXPECTED_IDS, không lọc theo "nhanh")."""
    nhanh: Literal["mot_tang", "nhieu_tang"]
    ly_do_nhan_dien: str = ""


class BotChuaChayReaderResult(ReaderResult):
    """Riêng cho bot_chua_chay_reader.py (B16: chữa cháy bằng bột, TCVN
    13877-2:2023) — cùng kiểu "1 template, 2 nhánh loại id" như
    GiaKeHangReaderResult ở trên."""
    nhanh: Literal["the_tich", "be_mat"]
    ly_do_nhan_dien: str = ""


class QuyMoFields(BaseModel):
    """Dữ liệu quy mô công trình (hạng mục "Quy mô", Form A) — dùng ĐÚNG tên
    field mà tham_dinh.py/he_thong_bat_buoc.py/phuong_tien.py đã dùng (occ,
    floors, totalArea, hFire...) để truyền THẲNG vào các evaluate_*() có sẵn,
    không cần lớp chuyển đổi tên field nào (tránh bug lệch tên). Lưu vào
    HoSoSessionQuyMo (quy_mo_store.py) để 4 reader khác (baochay/dienpccc/
    ccnuoc/densucco) tái dùng qua get_quy_mo(session_id), không cần AI đoán
    lại quy mô mỗi lần."""
    occ: str
    floors: Optional[int] = None
    basements: Optional[int] = None
    semiBasements: Optional[int] = None
    areaFloor: Optional[float] = None
    totalArea: Optional[float] = None
    volume: Optional[float] = None
    hFire: Optional[float] = None  # chieu cao PCCC (Dieu 1.4.9 QCVN 06:2022/BXD)
    kids: Optional[int] = None
    seats: Optional[int] = None
    hazard: Optional[Literal["A", "B", "C", "D", "E"]] = None
    garaKin: Optional[Literal["kin", "ho"]] = None
    garaKC12: Optional[Literal["le12", "gt12"]] = None
    garaBcl: Optional[Literal["I", "II", "III", "IV", "V"]] = None
    garaCapS: Optional[Literal["S0", "S1", "S2", "S3"]] = None
    pplFloor: Optional[int] = None
    extLevel: Optional[Literal["auto", "thap", "tb", "cao"]] = None
    hanhLangDaiNhat: Optional[float] = None  # rieng cho evaluate_bien_tam_thap (phuong_tien.py)
    chieuCaoKeHang: Optional[float] = None  # chieu cao sap xep hang hoa tren gia do/ke hang, m — phuc vu goi y form B15 (TCVN 14496:2025) sau nay
    coBeXangDauNgoaiTroi: Optional[bool] = None  # co be chua xang dau/dung moi de chay ngoai troi khong — can cu ap dung B7 (TCVN 5307:2009)

    @field_validator("occ")
    @classmethod
    def _occ_hop_le(cls, v):
        if v not in _VALID_OCC_IDS:
            raise ValueError(f"Công năng không hợp lệ: '{v}'.")
        return v


class ScanQuyMoFields(BaseModel):
    """Y HET QuyMoFields nhung TOAN BO field deu Optional (ke ca "occ") — dung
    RIENG cho scan_quymo_reader.py (Luot 0, quy_mo_store.py Phan A): ban ve
    bao chay/ccnuoc co the cho biet floors/totalArea ma KHONG the hien ro
    cong nang, khong duoc ep AI phai doan "occ" chi de qua validation nhu
    QuyMoFields (occ bat buoc) dang lam cho quymo_reader.py (doc dung ban ve
    kien truc, luon co occ ro rang)."""
    occ: Optional[str] = None
    floors: Optional[int] = None
    basements: Optional[int] = None
    semiBasements: Optional[int] = None
    areaFloor: Optional[float] = None
    totalArea: Optional[float] = None
    volume: Optional[float] = None
    hFire: Optional[float] = None
    kids: Optional[int] = None
    seats: Optional[int] = None
    hazard: Optional[Literal["A", "B", "C", "D", "E"]] = None
    garaKin: Optional[Literal["kin", "ho"]] = None
    garaKC12: Optional[Literal["le12", "gt12"]] = None
    garaBcl: Optional[Literal["I", "II", "III", "IV", "V"]] = None
    garaCapS: Optional[Literal["S0", "S1", "S2", "S3"]] = None
    pplFloor: Optional[int] = None
    extLevel: Optional[Literal["auto", "thap", "tb", "cao"]] = None
    hanhLangDaiNhat: Optional[float] = None
    chieuCaoKeHang: Optional[float] = None
    coBeXangDauNgoaiTroi: Optional[bool] = None

    @field_validator("occ")
    @classmethod
    def _occ_hop_le_neu_co(cls, v):
        if v is not None and v not in _VALID_OCC_IDS:
            raise ValueError(f"Công năng không hợp lệ: '{v}'.")
        return v


class ScanQuyMoResult(BaseModel):
    """Kết quả "Lượt 0" (quét nhẹ quy mô, KHÔNG chạy đủ checklist tiêu chí kỹ
    thuật) — xem scan_quymo_reader.py. tim_thay=False khi bản vẽ không có
    thông tin quy mô nào (thay vì AI tự bịa để có giá trị)."""
    tim_thay: bool
    quy_mo: Optional[ScanQuyMoFields] = None
    so_hieu_ban_ve: str = KHONG_XAC_DINH_SO_HIEU


class QuyMoReaderResult(BaseModel):
    """Schema RIÊNG cho quymo_reader.py — KHÔNG kế thừa ReaderResult vì Form A
    không có danh sách items[] theo id như 4 reader kia (đa số dòng "Đối
    tượng trang bị" điền bằng evaluate_*() có sẵn, không cần AI — xem
    quy_mo_store.py). AI CHỈ làm 2 việc: trích quy mô có cấu trúc, và đọc 2
    tiêu chí không có rule sẵn (Bảng A.2 "hạng mục/khu vực", Bảng A.4 "thiết
    bị" — cả báo cháy lẫn chữa cháy tự động)."""
    quy_mo: QuyMoFields
    bang_a2_bao_chay: str
    bang_a4_bao_chay: str
    bang_a2_sprinkler: str
    bang_a4_sprinkler: str
    so_hieu_ban_ve: str = KHONG_XAC_DINH_SO_HIEU

    @field_validator("bang_a2_bao_chay", "bang_a4_bao_chay", "bang_a2_sprinkler", "bang_a4_sprinkler")
    @classmethod
    def _khong_qua_dai(cls, v):
        if len(v) > MAX_NOI_DUNG_LEN:
            raise ValueError(f"Nội dung vượt quá {MAX_NOI_DUNG_LEN} ký tự.")
        return v


def validate_quy_mo_reader_result(data: dict) -> QuyMoReaderResult:
    """Validate rieng cho QuyMoReaderResult - khong co khai niem 'expected_ids'
    nhu validate_reader_result() vi khong co items[] theo id."""
    if not isinstance(data, dict):
        raise SchemaValidationError("Kết quả trả về không phải một JSON object.")
    try:
        return QuyMoReaderResult.model_validate(data)
    except ValidationError as exc:
        raise SchemaValidationError(f"JSON trả về không đúng cấu trúc yêu cầu: {exc}") from exc


def validate_scan_quy_mo_result(data: dict) -> ScanQuyMoResult:
    """Validate rieng cho ScanQuyMoResult (Luot 0, quet nhe) - tuong tu
    validate_quy_mo_reader_result() nhung khac model."""
    if not isinstance(data, dict):
        raise SchemaValidationError("Kết quả trả về không phải một JSON object.")
    try:
        return ScanQuyMoResult.model_validate(data)
    except ValidationError as exc:
        raise SchemaValidationError(f"JSON trả về không đúng cấu trúc yêu cầu: {exc}") from exc


def validate_reader_result(data: dict, expected_ids, model_cls=ReaderResult):
    """Parse JSON thô qua Pydantic model_cls, rồi kiểm tra 'items' khớp ĐÚNG bộ id
    kỳ vọng (không thiếu, không thừa). Raise SchemaValidationError với thông báo
    cụ thể (dùng làm nội dung phản hồi lỗi cho AI khi retry) nếu thất bại ở bước nào.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError("Kết quả trả về không phải một JSON object.")

    try:
        model = model_cls.model_validate(data)
    except ValidationError as exc:
        raise SchemaValidationError(f"JSON trả về không đúng cấu trúc yêu cầu: {exc}") from exc

    got_ids = {item.id for item in model.items}
    expected = set(expected_ids)
    missing = expected - got_ids
    extra = got_ids - expected
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"thiếu id: {sorted(missing)}")
        if extra:
            parts.append(f"có id không tồn tại trong danh sách tiêu chí: {sorted(extra)}")
        raise SchemaValidationError(
            "Danh sách 'items' không khớp đủ danh sách id yêu cầu — " + "; ".join(parts) + "."
        )

    return model


# ---------------------------------------------------------------------------
# "Đính 1 bản vẽ — AI tự nhận diện nhiều hạng mục" (merged_reader.py) — validate
# phần khung ngoài (detected_categories/so_hieu_ban_ve) bằng Pydantic, rồi
# validate NỘI DUNG từng hạng mục bằng ĐÚNG validate_reader_result()/
# validate_quy_mo_reader_result() ở trên (tái dùng nguyên vẹn, không viết lại
# logic kiểm tra id đầy đủ cho từng mẫu).
# ---------------------------------------------------------------------------
MergedCategory = Literal["baochay", "ccnuoc", "densucco", "dienpccc", "quy_mo"]

_CCNUOC_SUBFORMS = (("tram_bom", ReaderResult), ("hong_nuoc", ReaderResult), ("chua_chay_tu_dong", ChuaChayTuDongReaderResult))
_DENSUCCO_SUBFORMS = (("binh_chua_chay", ReaderResult), ("den_su_co", ReaderResult))


class MergedTopLevel(BaseModel):
    """Chỉ validate khung ngoài — nội dung từng hạng mục validate riêng bên dưới."""
    model_config = ConfigDict(extra="allow")
    detected_categories: List[MergedCategory] = Field(default_factory=list)
    so_hieu_ban_ve: str = KHONG_XAC_DINH_SO_HIEU


class _MergedResultWrapper:
    """Không phải Pydantic model thật — chỉ giả lập đúng interface .model_dump()
    mà read_and_validate_drawing_json()/các hàm read_drawing() của reader khác
    kỳ vọng ở giá trị trả về của validate_fn(), để tái dùng được callsite hiện
    có (merged_reader.read_and_detect()) mà không cần đổi chữ ký chung."""

    def __init__(self, data: dict):
        self._data = data

    def model_dump(self, **_kwargs):
        return self._data


def _validate_sub_or_raise(data: dict, key: str, expected_ids, model_cls) -> dict:
    sub = data.get(key)
    if not isinstance(sub, dict):
        raise SchemaValidationError(f"'{key}' có trong detected_categories nhưng thiếu dữ liệu tương ứng.")
    model = validate_reader_result(sub, expected_ids, model_cls)
    return model.model_dump()


def validate_merged_reader_result(data: dict, quy_mo_known: bool = False):
    """quy_mo_known: True nếu phiên ĐÃ có sẵn dữ liệu quy mô (không mời AI phát
    hiện lại 'quy_mo' nữa — xem merged_reader.build_system_prompt())."""
    if not isinstance(data, dict):
        raise SchemaValidationError("Kết quả trả về không phải một JSON object.")

    try:
        top = MergedTopLevel.model_validate(data)
    except ValidationError as exc:
        raise SchemaValidationError(f"JSON trả về không đúng cấu trúc yêu cầu: {exc}") from exc

    allowed = {c for c in ("baochay", "ccnuoc", "densucco", "dienpccc", "quy_mo") if c != "quy_mo" or not quy_mo_known}
    detected = list(dict.fromkeys(top.detected_categories))  # giữ thứ tự, bỏ trùng
    invalid = set(detected) - allowed
    if invalid:
        raise SchemaValidationError(
            f"'detected_categories' chứa hạng mục không hợp lệ hoặc không được phép ở lượt này: {sorted(invalid)}."
        )

    out = {"detected_categories": detected, "so_hieu_ban_ve": top.so_hieu_ban_ve}

    if "baochay" in detected:
        sub = data.get("baochay")
        if not isinstance(sub, dict):
            raise SchemaValidationError("'baochay' có trong detected_categories nhưng thiếu dữ liệu.")
        ids_thuong = {r["id"] for r in mdc_filler.load_criteria_rows("thuong")}
        ids_dia_chi = {r["id"] for r in mdc_filler.load_criteria_rows("dia_chi")}
        expected = ids_dia_chi if sub.get("loai_he_thong") == "dia_chi" else ids_thuong
        out["baochay"] = validate_reader_result(sub, expected, BaoChayReaderResult).model_dump()

    if "dienpccc" in detected:
        ids_dien = {r["id"] for r in mdc_filler.load_criteria_rows("dien_pccc")}
        out["dienpccc"] = _validate_sub_or_raise(data, "dienpccc", ids_dien, ReaderResult)

    if "ccnuoc" in detected:
        sub = data.get("ccnuoc")
        if not isinstance(sub, dict) or not isinstance(sub.get("forms"), dict):
            raise SchemaValidationError("'ccnuoc' có trong detected_categories nhưng thiếu 'forms'.")
        forms_out = {}
        for loai, model_cls in _CCNUOC_SUBFORMS:
            expected = {r["id"] for r in mdc_filler.load_criteria_rows(loai)}
            forms_out[loai] = _validate_sub_or_raise(sub["forms"], loai, expected, model_cls)
        out["ccnuoc"] = {"forms": forms_out}

    if "densucco" in detected:
        sub = data.get("densucco")
        if not isinstance(sub, dict) or not isinstance(sub.get("forms"), dict):
            raise SchemaValidationError("'densucco' có trong detected_categories nhưng thiếu 'forms'.")
        forms_out = {}
        for loai, model_cls in _DENSUCCO_SUBFORMS:
            expected = {r["id"] for r in mdc_filler.load_criteria_rows(loai)}
            forms_out[loai] = _validate_sub_or_raise(sub["forms"], loai, expected, model_cls)
        out["densucco"] = {"forms": forms_out}

    if "quy_mo" in detected:
        sub = data.get("quy_mo")
        if not isinstance(sub, dict):
            raise SchemaValidationError("'quy_mo' có trong detected_categories nhưng thiếu dữ liệu.")
        out["quy_mo"] = validate_quy_mo_reader_result(sub).model_dump()

    return _MergedResultWrapper(out)
