"""Form A gốc (A14 Nhà sản xuất, A15 Nhà kho) — combiner GỘP dữ liệu đã có
trong phiên (quy mô rule-based + kết quả B-form đã đọc) thành 1 file .docx
đúng khuôn mẫu gốc thật. KHÔNG đọc bản vẽ bằng AI — chỉ lắp ráp.

Đã tự đọc trực tiếp TOÀN BỘ nội dung thật của A14_nha_san_xuat.docx (63 dòng)
và A15_nha_kho.docx (60 dòng) qua docx.Document trước khi viết module này —
2 template GIỐNG HỆT nhau ở id 1-58 (cùng doi_chieu/quy_dinh/khoan_dieu),
khác nhau ở đuôi: A14 có thêm mục 7 "Chữa cháy cơ giới" (id 59-61) trước khi
tới mục 8 "Điện PCCC" (id 62-63); A15 KHÔNG có mục cơ giới, mục "Điện PCCC"
là id 59-60 (đánh số "7" trong chính template A15).

Bảng phân loại id -> cách xử lý dưới đây là HARDCODE dựa trên bằng chứng đọc
trực tiếp (không suy đoán theo mục/TT một cách tự động — nhiều mục có số
dòng con không đều, xem _ROW_SPECS_COMMON/_ROW_SPECS_A14_TAIL/_ROW_SPECS_A15_TAIL).

3 nhánh của dòng "Loại B" (dẫn chiếu), ĐÚNG THỨ TỰ ưu tiên (dừng ở nhánh đầu
tiên khớp) — xem quy-tac-dien-form.md mục 4c (skill ra-mau-doi-chieu-pccc):
  (b) Hạ tầng hiện hữu (pham_vi_hien_huu_store.is_he_thong_hien_huu) - ưu
      tiên CAO NHẤT, Kết luận rỗng.
  (a) Mục cha KHÔNG thuộc diện (rule trả "no"/"na") - Kết luận rỗng.
  (c) Dẫn chiếu B-form nếu có trong b_form_results, hoặc kiến nghị bổ sung
      hồ sơ nếu thuộc diện mà chưa đọc B-form nào - Kết luận "+"/"KN".
"""

from . import mdc_filler
from .he_thong_bat_buoc import (
    HeThongBatBuocInputError,
    evaluate_bao_chay,
    evaluate_gian_phong_bao_chay,
    evaluate_gian_phong_sprinkler,
    evaluate_hong_nuoc,
    evaluate_ngoai_nha,
    evaluate_sprinkler,
)
from .pham_vi_hien_huu_store import is_he_thong_hien_huu
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
from .quy_mo_store import build_quy_mo_profile_items
from .tham_dinh import ThamDinhInputError

_INPUT_ERRORS = (ThamDinhInputError, HeThongBatBuocInputError, PhuongTienInputError)

_DAT_KHONG_AP_DUNG = ("dat", "khong_ap_dung")


class FormACombinerError(Exception):
    pass


def _safe_eval(fn, fields):
    try:
        return fn(fields)
    except _INPUT_ERRORS as exc:
        return {"result": "warn", "detail": f"Chưa đủ dữ liệu quy mô để xác định ({exc})", "can_cu": "—"}


# ---------------------------------------------------------------------------
# Cac muc (logic key noi bo) -> ham rule + khoa he thong (hien huu) + khoa
# B-form (loai trong mdc_filler.TEMPLATE_PATHS) de dan chieu.
# ---------------------------------------------------------------------------
class _Muc:
    def __init__(self, key, default_fn=None, gian_phong_fn=None, he_thong_hien_huu=None, b_forms=()):
        self.key = key
        self.default_fn = default_fn
        self.gian_phong_fn = gian_phong_fn
        self.he_thong_hien_huu = he_thong_hien_huu  # khoa trong pham_vi_hien_huu_store.HE_THONG_KEYS, hoac None
        self.b_forms = b_forms  # tuple (loai, nhan_B) - co the >1 (vd sprinkler: B6 + B15)


_MUC = {
    "bao_chay": _Muc("bao_chay", evaluate_bao_chay, evaluate_gian_phong_bao_chay,
                      he_thong_hien_huu="baochay", b_forms=(("thuong", "B1"), ("dia_chi", "B2"))),
    "sprinkler": _Muc("sprinkler", evaluate_sprinkler, evaluate_gian_phong_sprinkler,
                       he_thong_hien_huu="chua_chay_tu_dong",
                       b_forms=(("chua_chay_tu_dong", "B6"), ("chua_chay_gia_ke_hang", "B15"))),
    "hong_nuoc": _Muc("hong_nuoc", evaluate_hong_nuoc, he_thong_hien_huu="hong_nuoc", b_forms=(("hong_nuoc", "B5"),)),
    "cap_nuoc_ngoai": _Muc("cap_nuoc_ngoai", evaluate_ngoai_nha, he_thong_hien_huu=None, b_forms=()),
    "tram_bom": _Muc("tram_bom", None, he_thong_hien_huu="tram_bom", b_forms=(("tram_bom", "B3"),)),
    "khi": _Muc("khi", None, he_thong_hien_huu="khibotsolkhi",
                b_forms=(("khi_hoa_long", "B8"), ("khi_nen", "B9"), ("khi_co2", "B10"), ("sol_khi", "B11"))),
    # B7 luon uu tien tim truoc (dung 1-1 voi evaluate_bot_co_dinh), B6 la du
    # phong THEO DUNG hint co san trong chinh 2 file goc (id=38 template co
    # san "Thuc hien theo bang doi chieu so B6-B7", khong phai chi B7).
    "bot_co_dinh": _Muc("bot_co_dinh", evaluate_bot_co_dinh, he_thong_hien_huu="botcodinh",
                        b_forms=(("bot_co_dinh", "B7"), ("chua_chay_tu_dong", "B6"))),
    "den": _Muc("den", evaluate_den, he_thong_hien_huu="densucco", b_forms=(("den_su_co", "B13"),)),
    "loa": _Muc("loa", evaluate_loa, he_thong_hien_huu="densucco", b_forms=()),
    "binh": _Muc("binh", None, he_thong_hien_huu="binhchuachay", b_forms=(("binh_chua_chay", "B12"),)),
    "pha_do": _Muc("pha_do", evaluate_pha_do, he_thong_hien_huu=None, b_forms=()),
    "mat_na": _Muc("mat_na", evaluate_mat_na, he_thong_hien_huu=None, b_forms=()),
    "co_gioi": _Muc("co_gioi", evaluate_co_gioi, he_thong_hien_huu=None, b_forms=()),
    "dien": _Muc("dien", evaluate_dien_pccc_suy_luan, he_thong_hien_huu="dienpccc", b_forms=(("dien_pccc", "B14"),)),
    # "bot_chua_chay" (bot, B16) KHONG co ham rule "thuoc dien" nao trong
    # app (giong "khi") - id=39 (A14/A15) co san hint "Thuc hien theo bang
    # doi chieu so B16" trong chinh template goc, xac nhan day la dong can
    # dien chu KHONG phai dong rong khong co gi (xem _ROW_SPECS_COMMON[39]).
    "bot_chua_chay": _Muc("bot_chua_chay", None, he_thong_hien_huu="botchuachay",
                          b_forms=(("bot_chua_chay", "B16"),)),
}


def _muc_ket_qua(fields: dict) -> dict:
    """Tính rule 1 LẦN cho mỗi mục (kể cả bản 'gian phòng' riêng nếu có),
    dùng lại cho TẤT CẢ dòng Loại A con của mục đó + để xác định 'thuộc diện'
    cho dòng Loại B (dẫn chiếu) tương ứng."""
    out = {}
    for key, muc in _MUC.items():
        if muc.default_fn is not None:
            out[key] = _safe_eval(muc.default_fn, fields)
        if muc.gian_phong_fn is not None:
            out[key + "__gian_phong"] = _safe_eval(muc.gian_phong_fn, fields)
    # binh (evaluate_binh) can them 1 tham so extLevel/areaFloor - da co san trong fields,
    # nhung ham binh nam o phuong_tien.py rieng (import truc tiep de tranh vong lap import
    # o dau file nay voi cac ham khac dung chung 1 module).
    from .phuong_tien import evaluate_binh
    out["binh"] = _safe_eval(evaluate_binh, fields)
    # tram_bom + khi KHONG co ham rule rieng - "thuoc dien" suy ra tu cac muc lien quan
    # (xem _tram_bom_thuoc_dien()/_khi_thuoc_dien() ben duoi), khong tu bia 1 ham moi.
    return out


def _rule_ket_luan(result: str) -> str:
    """Form A CHI dung 2 ky hieu +/KN (rong neu khong thuoc dien) - KHAC han
    ket_luan cua build_type1_items()/build_thuoc_dien_preview_items() (dung
    'dat'/'khong_ap_dung'/'chua_the_hien')."""
    if result == "yes":
        return "+"
    if result in ("no", "na"):
        return ""
    return "KN"  # warn / chua_du_du_lieu


def _rule_noi_dung(result: str, detail: str) -> str:
    if result == "yes":
        return detail
    if result in ("no", "na"):
        return "x - Không thuộc đối tượng áp dụng: " + detail
    return detail  # warn: detail da tu noi "chua du du lieu..."


def _tram_bom_thuoc_dien(muc_kq: dict) -> bool:
    """Tram bom khong co evaluate_* rieng - thuoc dien khi BAT KY 1 trong 3
    he can nuoc (sprinkler/hong nuoc/cap nuoc ngoai nha) thuoc dien, dung lai
    KET QUA DA TINH o muc_kq (khong goi lai rule)."""
    for key in ("sprinkler", "hong_nuoc", "cap_nuoc_ngoai"):
        r = muc_kq.get(key)
        if r and r.get("result") == "yes":
            return True
    return False


def _dan_chieu_b_form(muc: _Muc, thuoc_dien: bool, b_form_results: dict, ten_muc_display: str, can_cu_fallback: str):
    """Nhánh (c) — trả (noi_dung, ket_luan). Nhánh (a)/(b) xử lý riêng ở
    _build_dan_chieu_row() trước khi gọi hàm này."""
    found = None
    found_loai = None
    for loai, nhan in muc.b_forms:
        data = b_form_results.get(loai)
        if data and isinstance(data.get("items"), list):
            found = data
            found_loai = nhan
            break

    if found is not None:
        items = found["items"]
        co_kn = any(it.get("ket_luan") not in _DAT_KHONG_AP_DUNG for it in items if isinstance(it, dict))
        noi_dung = f"Thực hiện theo bảng đối chiếu số {found_loai}."
        if co_kn:
            noi_dung += f" Có kiến nghị — xem chi tiết tại bảng đối chiếu {found_loai}."
            return noi_dung, "KN"
        return noi_dung, "+"

    if not thuoc_dien:
        return f"Không áp dụng — {ten_muc_display} không thuộc diện trang bị (xem mục xác định phía trên).", ""

    # Thuoc dien nhung chua doc duoc B-form nao (hoac muc nay khong co B-form
    # rieng trong app - vd loa, cap nuoc ngoai nha, pha do, mat na, co gioi).
    noi_dung = (
        f"Bổ sung hồ sơ thiết kế hệ thống {ten_muc_display} cho hạng mục này; theo {can_cu_fallback}, "
        "hạng mục này thuộc diện bắt buộc trang bị nhưng chưa thấy bản vẽ/hồ sơ thiết kế hệ thống này "
        "trong bộ hồ sơ hiện có."
    )
    return noi_dung, "KN"


def _hien_huu_sentence(hien_huu) -> str:
    """Đúng khuôn câu mục 4c quy-tac-dien-form.md — dùng chung cho mọi
    nhánh (b), kể cả nhánh 'khí' không xác định được thuộc diện."""
    phan_bo_sung = ""
    if hien_huu.gcn_bo_sung_so:
        phan_bo_sung = f", cải tạo bổ sung số {hien_huu.gcn_bo_sung_so} ngày {hien_huu.gcn_bo_sung_ngay}"
    return (
        f"Hạng mục hiện hữu, đã thẩm duyệt số {hien_huu.gcn_so} ngày {hien_huu.gcn_ngay}{phan_bo_sung}, "
        f"nghiệm thu số {hien_huu.nghiem_thu_so} ngày {hien_huu.nghiem_thu_ngay}; sử dụng chung/giữ nguyên "
        "theo hiện trạng, không thuộc phạm vi đề nghị thẩm định lần này."
    )


def _build_dan_chieu_row(session_id, muc_key, thuoc_dien, b_form_results, ten_muc_display, can_cu_fallback):
    muc = _MUC[muc_key]
    if muc.he_thong_hien_huu is not None:
        hien_huu = is_he_thong_hien_huu(session_id, muc.he_thong_hien_huu)
        if hien_huu is not None:
            return _hien_huu_sentence(hien_huu), ""

    return _dan_chieu_b_form(muc, thuoc_dien, b_form_results, ten_muc_display, can_cu_fallback)


# ---------------------------------------------------------------------------
# Trich TOAN BO dong that (KHONG loc bo dong quy_dinh rong nhu
# mdc_filler._extract_rows() - Form A can biet ca dong header de quyet dinh
# SKIP, khac B-form).
# ---------------------------------------------------------------------------
def _extract_all_rows(path):
    from docx import Document
    doc = Document(path)
    table = doc.tables[0]
    rows = []
    for idx, row in enumerate(table.rows):
        if idx == 0:
            continue
        rows.append({
            "id": idx,
            "tt": row.cells[0].text.strip(),
            "doi_chieu": row.cells[mdc_filler.COL_DOI_CHIEU].text.strip(),
            "quy_dinh": row.cells[mdc_filler.COL_QUY_DINH].text.strip(),
            "khoan_dieu": row.cells[mdc_filler.COL_KHOAN_DIEU].text.strip(),
        })
    return rows


_ROWS_CACHE = {}


def _load_rows(loai_hinh):
    if loai_hinh not in _ROWS_CACHE:
        _ROWS_CACHE[loai_hinh] = _extract_all_rows(mdc_filler.TEMPLATE_PATHS[loai_hinh])
    return _ROWS_CACHE[loai_hinh]


# ---------------------------------------------------------------------------
# Bang phan loai id (hardcode theo bang chung doc truc tiep tu 2 file that).
# "skip": khong dien gi (header thuan/muc rong khong co dong con).
# "muc1": dong 2/3/4 - tai dung build_quy_mo_profile_items() (id trung khop
#         voi chinh id cua A_quy_mo.docx cho cung noi dung).
# "rule": dong "Loai A" (doi tuong trang bi) - can muc_key + co la 'gian
#         phong' (dung ham rule rieng) hay khong.
# "norule_plus": dong luon Ket luan=+, mo ta/luu y, khong co rule (Khu vuc
#         bao ve/Luu y/dong tiep tuc trung noi dung).
# "cho_phep": dong "duoc phep trang bi ... " (diem 4b quy-tac-dien-form-A.md)
#         - luon +, khong bat buoc.
# "dan_chieu": dong "Loai B" (Cac yeu cau ky thuat/Bo tri...) - can muc_key +
#         ten hien thi + can cu fallback cho cau kien nghi.
# "dan_chieu_bot_co_dinh": rieng id=38 (A14/A15) - dong nay VUA la muc-header
#         VUA la noi dung (khong co dong "doi tuong trang bi" rieng) - dung
#         evaluate_bot_co_dinh() de xac dinh thuoc dien NGAY TREN dong nay.
# ---------------------------------------------------------------------------
_ROW_SPECS_COMMON = {
    1: {"kind": "skip"},
    2: {"kind": "muc1"},
    3: {"kind": "muc1"},
    4: {"kind": "muc1"},
    5: {"kind": "skip"},
    6: {"kind": "skip"},
    7: {"kind": "rule", "muc": "bao_chay"},
    8: {"kind": "rule", "muc": "bao_chay"},
    9: {"kind": "rule", "muc": "bao_chay", "gian_phong": True},
    10: {"kind": "rule", "muc": "bao_chay"},
    11: {"kind": "skip"},
    12: {"kind": "norule_plus", "text": (
        "Áp dụng Điều 1.5.11 QCVN 10:2025/BCA — các khu vực có quy trình ướt hoặc đặc thù được phép "
        "không trang bị báo cháy/chữa cháy tự động cho toàn bộ nhà; cần đối chiếu cụ thể với mặt bằng "
        "thực tế của công trình để xác định khu vực loại trừ (nếu có)."
    )},
    13: {"kind": "dan_chieu", "muc": "bao_chay", "ten": "Báo cháy tự động",
         "can_cu": "Điều 2.1 QCVN 10:2025/BCA"},
    14: {"kind": "skip"},
    15: {"kind": "skip"},
    16: {"kind": "rule", "muc": "sprinkler"},
    17: {"kind": "rule", "muc": "sprinkler"},
    18: {"kind": "rule", "muc": "sprinkler", "gian_phong": True},
    19: {"kind": "rule", "muc": "sprinkler"},
    20: {"kind": "skip"},
    21: {"kind": "norule_plus", "text": (
        "Chất chữa cháy sử dụng trong hệ thống chữa cháy tự động cần có hiệu quả phù hợp với loại đám "
        "cháy của khu vực bảo vệ theo Điều 1.5.3 QCVN 10:2025/BCA — xác nhận cụ thể theo hệ thống chữa "
        "cháy tự động thực tế được thiết kế (nước/khí/bọt/bột)."
    )},
    22: {"kind": "norule_plus", "text": (
        "Áp dụng Điều 1.5.11 QCVN 10:2025/BCA — các khu vực có quy trình ướt hoặc đặc thù được phép "
        "không trang bị hệ thống chữa cháy tự động; cần đối chiếu cụ thể với mặt bằng thực tế của công trình."
    )},
    23: {"kind": "skip"},
    24: {"kind": "skip"},
    25: {"kind": "dan_chieu", "muc": "sprinkler", "ten": "chữa cháy tự động (sprinkler)",
         "can_cu": "Điều 2.5 QCVN 10:2025/BCA"},
    26: {"kind": "skip"},
    27: {"kind": "rule", "muc": "hong_nuoc"},
    28: {"kind": "dan_chieu", "muc": "hong_nuoc", "ten": "họng nước chữa cháy trong nhà",
         "can_cu": "Điều 2.4.1 QCVN 10:2025/BCA"},
    29: {"kind": "skip"},
    30: {"kind": "rule", "muc": "cap_nuoc_ngoai"},
    31: {"kind": "norule_plus", "text": (
        "Được phép không trang bị hệ thống cấp nước chữa cháy ngoài nhà khi công trình nằm trong bán "
        "kính 400 m tính từ trụ cấp nước chữa cháy hoặc bến lấy nước theo Điều 2.3.2 QCVN 10:2025/BCA — "
        "cần xác nhận khoảng cách thực tế trên bản vẽ tổng mặt bằng khu vực."
    )},
    32: {"kind": "dan_chieu", "muc": "cap_nuoc_ngoai", "ten": "cấp nước chữa cháy ngoài nhà",
         "can_cu": "Điều 2.3.1 QCVN 10:2025/BCA"},
    33: {"kind": "skip"},
    34: {"kind": "dan_chieu", "muc": "tram_bom", "ten": "trạm bơm cấp nước chữa cháy và bể nước chữa cháy",
         "can_cu": "Điều 2.5/2.4.1/2.3.1 QCVN 10:2025/BCA (theo hệ chữa cháy nước thuộc diện)",
         "thuoc_dien_override": "tram_bom"},
    # id=35 (TT=3.3, muc-header) VA id=36 ("Yeu cau ve khu vuc chua chay")
    # CA HAI deu can dien - id=35 co san hint goc "Thuc hien theo bang doi
    # chieu so B8-B11" (xac nhan qua doc truc tiep file that), id=36 la dong
    # ky thuat rieng (yeu cau bao che kin khi) khong co rule doc lap - dung
    # CHUNG 1 kieu xu ly (khong bia nguong "thuoc dien" cho he khi, giong
    # dung nguyen tac da co o quy_mo_store._REVERSE_CHECK_SLOTS khong ap
    # dung cho "khibot").
    35: {"kind": "dan_chieu_khong_ro_thuoc_dien", "muc": "khi", "ten": "chữa cháy bằng khí",
         "can_cu": "Điều 7.4.1/7.4.2 TCVN 7161-1:2022"},
    36: {"kind": "dan_chieu_khong_ro_thuoc_dien", "muc": "khi", "ten": "chữa cháy bằng khí",
         "can_cu": "Điều 7.4.1/7.4.2 TCVN 7161-1:2022"},
    37: {"kind": "cho_phep"},
    38: {"kind": "dan_chieu_bot_co_dinh"},
    # id=39 (TT=3.5, muc-header) co san hint goc "Thuc hien theo bang doi
    # chieu so B16" - XAC NHAN day la dong can dien (khong phai muc rong
    # khong co gi nhu tuong nham ban dau khi chi doc cot quy_dinh).
    39: {"kind": "dan_chieu_khong_ro_thuoc_dien", "muc": "bot_chua_chay", "ten": "chữa cháy bằng bột",
         "can_cu": "TCVN 13877-2:2023"},
    40: {"kind": "skip"},
    41: {"kind": "skip"},
    42: {"kind": "rule", "muc": "den"},
    43: {"kind": "dan_chieu", "muc": "den", "ten": "đèn chiếu sáng sự cố và chỉ dẫn thoát nạn",
         "can_cu": "Điều 2.2.1 QCVN 10:2025/BCA"},
    44: {"kind": "skip"},
    45: {"kind": "rule", "muc": "loa"},
    46: {"kind": "dan_chieu", "muc": "loa", "ten": "loa thông báo và hướng dẫn thoát nạn",
         "can_cu": "Điều 2.2.4 QCVN 10:2025/BCA, Phụ lục G"},
    47: {"kind": "skip"},
    48: {"kind": "skip"},
    49: {"kind": "rule", "muc": "binh"},
    50: {"kind": "rule", "muc": "binh"},
    51: {"kind": "cho_phep"},
    52: {"kind": "cho_phep"},
    53: {"kind": "dan_chieu", "muc": "binh", "ten": "bình chữa cháy", "can_cu": "Điều 2.6.1 QCVN 10:2025/BCA"},
    54: {"kind": "skip"},
    55: {"kind": "rule", "muc": "pha_do"},
    56: {"kind": "dan_chieu", "muc": "pha_do", "ten": "dụng cụ phá dỡ thô sơ",
         "can_cu": "Phụ lục E QCVN 10:2025/BCA"},
    57: {"kind": "rule", "muc": "mat_na"},
    58: {"kind": "dan_chieu", "muc": "mat_na", "ten": "mặt nạ lọc độc và mặt nạ phòng độc cách ly",
         "can_cu": "Phụ lục F QCVN 10:2025/BCA"},
}

_ROW_SPECS_A14_TAIL = {
    59: {"kind": "skip"},
    60: {"kind": "rule", "muc": "co_gioi"},
    61: {"kind": "dan_chieu", "muc": "co_gioi", "ten": "phương tiện chữa cháy cơ giới",
         "can_cu": "Phụ lục D QCVN 10:2025/BCA"},
    62: {"kind": "skip"},
    63: {"kind": "dan_chieu", "muc": "dien", "ten": "điện phục vụ PCCC", "can_cu": "Suy luận nội bộ"},
}

_ROW_SPECS_A15_TAIL = {
    59: {"kind": "skip"},
    60: {"kind": "dan_chieu", "muc": "dien", "ten": "điện phục vụ PCCC", "can_cu": "Suy luận nội bộ"},
}

_TAIL_BY_LOAI_HINH = {"A14": _ROW_SPECS_A14_TAIL, "A15": _ROW_SPECS_A15_TAIL}


def _row_specs(loai_hinh):
    specs = dict(_ROW_SPECS_COMMON)
    specs.update(_TAIL_BY_LOAI_HINH[loai_hinh])
    return specs


def _thuoc_dien(muc_key, muc_kq):
    if muc_key == "tram_bom":
        return _tram_bom_thuoc_dien(muc_kq)
    r = muc_kq.get(muc_key)
    return bool(r and r.get("result") == "yes")


def build_form_a_goc(loai_hinh: str, session_data: dict) -> bytes:
    """loai_hinh: 'A14' hoặc 'A15'. session_data: {"quy_mo": dict, "session_id":
    int, "b_form_results": dict}. Trả về bytes file .docx đã điền."""
    if loai_hinh not in ("A14", "A15"):
        raise FormACombinerError(f"Loại hình Form A không hỗ trợ: '{loai_hinh}' (chỉ hỗ trợ A14/A15).")

    session_id = session_data["session_id"]
    fields = session_data.get("quy_mo") or {}
    b_form_results = session_data.get("b_form_results") or {}

    muc_kq = _muc_ket_qua(fields)
    muc1_items = {it["id"]: it for it in build_quy_mo_profile_items(fields)}

    answers = []
    for row_id, spec in _row_specs(loai_hinh).items():
        kind = spec["kind"]
        if kind == "skip":
            continue

        if kind == "muc1":
            src = muc1_items.get(row_id)
            if src is None:
                continue
            ket_luan = "+" if src["ket_luan"] == "dat" else "KN"
            answers.append({"id": row_id, "noi_dung_thiet_ke": src["noi_dung_thiet_ke"], "ket_luan": ket_luan})
            continue

        if kind == "rule":
            muc_key = spec["muc"]
            r = muc_kq.get(muc_key + "__gian_phong") if spec.get("gian_phong") else muc_kq.get(muc_key)
            if r is None:
                continue
            # evaluate_den() luon "yes", tra ve danh sach vi tri bat buoc
            # ("pos") thay vi "detail" nhu cac ham khac - dung dung cach
            # quy_mo_store.build_type1_items()/build_thuoc_dien_preview_items()
            # da xu ly cho id=42, khong the goi _rule_noi_dung() voi
            # detail rong.
            if muc_key == "den" and r["result"] == "yes" and "pos" in r:
                detail = "Vị trí bắt buộc lắp đặt: " + "; ".join(r["pos"]) + "."
            else:
                detail = r.get("detail", "—")
            answers.append({
                "id": row_id,
                "noi_dung_thiet_ke": _rule_noi_dung(r["result"], detail),
                "ket_luan": _rule_ket_luan(r["result"]),
            })
            continue

        if kind == "norule_plus":
            answers.append({"id": row_id, "noi_dung_thiet_ke": spec["text"], "ket_luan": "+"})
            continue

        if kind == "cho_phep":
            answers.append({
                "id": row_id,
                "noi_dung_thiet_ke": "Không bắt buộc trang bị (quy định là \"cho phép\", không phải yêu cầu bắt buộc).",
                "ket_luan": "+",
            })
            continue

        if kind == "dan_chieu":
            muc_key = spec["muc"]
            thuoc_dien_key = spec.get("thuoc_dien_override", muc_key)
            thuoc_dien = _thuoc_dien(thuoc_dien_key, muc_kq)
            noi_dung, ket_luan = _build_dan_chieu_row(
                session_id, muc_key, thuoc_dien, b_form_results, spec["ten"], spec["can_cu"],
            )
            answers.append({"id": row_id, "noi_dung_thiet_ke": noi_dung, "ket_luan": ket_luan})
            continue

        if kind == "dan_chieu_khong_ro_thuoc_dien":
            # Muc "khi"/"bot_chua_chay" KHONG co ham rule xac dinh thuoc dien
            # (giong "khibot" trong quy_mo_store._REVERSE_CHECK_SLOTS - khong
            # tu bia nguong).
            muc = _MUC[spec["muc"]]
            found = None
            found_loai = None
            for loai, nhan in muc.b_forms:
                data = b_form_results.get(loai)
                if data and isinstance(data.get("items"), list):
                    found, found_loai = data, nhan
                    break
            hien_huu = is_he_thong_hien_huu(session_id, muc.he_thong_hien_huu) if muc.he_thong_hien_huu else None
            if hien_huu is not None:
                noi_dung = _hien_huu_sentence(hien_huu)
                ket_luan = ""
            elif found is not None:
                items = found["items"]
                co_kn = any(it.get("ket_luan") not in _DAT_KHONG_AP_DUNG for it in items if isinstance(it, dict))
                noi_dung = f"Thực hiện theo bảng đối chiếu số {found_loai}."
                ket_luan = "+"
                if co_kn:
                    noi_dung += f" Có kiến nghị — xem chi tiết tại bảng đối chiếu {found_loai}."
                    ket_luan = "KN"
            else:
                nhan_list = "/".join(nhan for _loai, nhan in muc.b_forms)
                noi_dung = (
                    f"Chưa xác định được công trình có sử dụng hệ thống {spec['ten']} hay không — cần đối "
                    f"chiếu thêm với thiết kế thực tế; nếu có, bổ sung bản vẽ/hồ sơ {nhan_list} tương ứng."
                )
                ket_luan = ""
            answers.append({"id": row_id, "noi_dung_thiet_ke": noi_dung, "ket_luan": ket_luan})
            continue

        if kind == "dan_chieu_bot_co_dinh":
            muc = _MUC["bot_co_dinh"]
            r = muc_kq.get("bot_co_dinh")
            thuoc_dien = bool(r and r.get("result") == "yes")
            noi_dung, ket_luan = _build_dan_chieu_row(
                session_id, "bot_co_dinh", thuoc_dien, b_form_results,
                "chữa cháy bằng bọt cố định", "TCVN 5307:2009",
            )
            answers.append({"id": row_id, "noi_dung_thiet_ke": noi_dung, "ket_luan": ket_luan})
            continue

        raise FormACombinerError(f"Không nhận diện được kiểu xử lý dòng: '{kind}' (id={row_id}).")

    return mdc_filler.fill_docx(loai_hinh, answers)
