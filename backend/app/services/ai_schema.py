"""Pydantic schema cho kết quả AI đọc bản vẽ (Batch 4, sub-bước 1) — validate
cấu trúc JSON AI trả về (đủ tiêu chí/id đúng, enum kết luận hợp lệ, giới hạn
độ dài nội dung) TRƯỚC khi dùng để điền MĐC/kiến nghị, tránh dữ liệu nửa vời
lọt qua mà không bị phát hiện.
"""

from typing import List, Literal

from pydantic import BaseModel, Field, ValidationError

MAX_NOI_DUNG_LEN = 3000
KHONG_XAC_DINH_SO_HIEU = "Không xác định được số hiệu bản vẽ"

KetLuan = Literal["dat", "chua_dat", "chua_the_hien"]


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
