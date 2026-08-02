"""Pydantic schema cho kết quả AI đọc bản vẽ (Batch 4, sub-bước 1) — validate
cấu trúc JSON AI trả về (đủ tiêu chí/id đúng, enum kết luận hợp lệ, giới hạn
độ dài nội dung) TRƯỚC khi dùng để điền MĐC/kiến nghị, tránh dữ liệu nửa vời
lọt qua mà không bị phát hiện.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

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


class ChuaChayTuDongReaderResult(ReaderResult):
    """Riêng cho mẫu B6 (chữa cháy tự động bằng nước/bọt) trong ccnuoc_reader.py
    — AI phải tự xác định công trình CÓ thiết kế hệ sprinkler/drencher hay
    không trước khi đối chiếu (chỉ đạo nghiệp vụ của owner). Không có default —
    bắt buộc AI trả lời rõ ràng, không được bỏ sót."""
    co_thiet_ke_tu_dong: bool


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

    @field_validator("occ")
    @classmethod
    def _occ_hop_le(cls, v):
        if v not in _VALID_OCC_IDS:
            raise ValueError(f"Công năng không hợp lệ: '{v}'.")
        return v


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
