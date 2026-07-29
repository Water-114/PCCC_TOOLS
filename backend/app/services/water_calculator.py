"""Tinh dung tich be nuoc chua chay: V = Q x t x 60 (doi phut -> giay), tong 3 nhom.

Port tu index.html (form frm-nuoc, dong ~2284-2301): hong nuoc trong nha,
chua chay tu dong (sprinkler/drencher), cap nuoc ngoai nha. Khong bao gom
module kho ke cao (TCVN 14496) - de danh phase sau.
"""


def calculate_water_tank(payload: dict) -> dict:
    htn_n = float(payload.get("htn_n") or 0)
    htn_q = float(payload.get("htn_q") or 0)
    htn_t = float(payload.get("htn_t") or 0)

    sp_q = float(payload.get("sp_q") or 0)
    sp_t = float(payload.get("sp_t") or 0)

    nn_q = float(payload.get("nn_q") or 0)
    nn_t = float(payload.get("nn_t") or 0)

    q_tn = htn_n * htn_q
    v_tn = q_tn * htn_t * 60
    v_sp = sp_q * sp_t * 60
    v_nn = nn_q * nn_t * 60
    v_tong = v_tn + v_sp + v_nn

    if v_tong <= 0:
        raise ValueError(
            "Chưa nhập đủ dữ liệu cho hệ thống nào — nhập ít nhất 1 hệ thống "
            "có lưu lượng và thời gian > 0."
        )

    return {
        "hong_nuoc_trong_nha": {
            "q_tia": htn_q,
            "so_tia": htn_n,
            "q_tong": round(q_tn, 2),
            "thoi_gian_phut": htn_t,
            "the_tich_lit": round(v_tn, 1),
            "the_tich_m3": round(v_tn / 1000, 2),
        },
        "chua_chay_tu_dong": {
            "q": sp_q,
            "thoi_gian_phut": sp_t,
            "the_tich_lit": round(v_sp, 1),
            "the_tich_m3": round(v_sp / 1000, 2),
        },
        "cap_nuoc_ngoai_nha": {
            "q": nn_q,
            "thoi_gian_phut": nn_t,
            "the_tich_lit": round(v_nn, 1),
            "the_tich_m3": round(v_nn / 1000, 2),
        },
        "tong": {
            "the_tich_lit": round(v_tong, 1),
            "the_tich_m3": round(v_tong / 1000, 2),
        },
    }
