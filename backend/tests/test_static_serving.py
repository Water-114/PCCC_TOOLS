"""Batch 7A — Flask phải phục vụ đúng giao diện production đã hợp nhất vào
backend/app/static/ (trước đây nằm ở thư mục gốc repo: index.html, css/, js/).
Không kiểm tra nội dung UI (đã có kiểm chứng qua Playwright thủ công ở các
batch trước) — chỉ khoá lại đúng 3 route serve_index/serve_css/serve_js trả về
200 với đúng file thật trên đĩa, và 404 rõ ràng cho file không tồn tại (không
lộ file khác trong repo qua đường dẫn tuỳ ý)."""

import os
import re

STATIC_ROOT = os.path.join(os.path.dirname(__file__), "..", "app", "static")

ALL_JS_FILES = [
    "ai-doc-ho-so.js",
    "ai-giang-day.js",
    "auth.js",
    "cong-cu-tinh-toan.js",
    "nav.js",
    "quan-tri.js",
    "thu-vien.js",
    "tuvan-so-bo.js",
    "utils.js",
]


def test_serve_index_returns_200_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<html" in resp.data.lower()


def test_serve_css_returns_200(client):
    resp = client.get("/css/styles.css")
    assert resp.status_code == 200
    assert resp.content_length > 0


def test_serve_every_main_js_file_returns_200(client):
    for filename in ALL_JS_FILES:
        resp = client.get(f"/js/{filename}")
        assert resp.status_code == 200, filename
        assert resp.content_length > 0, filename


def _script_src_js_files_in_index_html() -> set:
    index_path = os.path.join(STATIC_ROOT, "index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    return set(re.findall(r'<script\s+src="js/([^"]+\.js)"', content))


def test_static_root_matches_index_html_script_tags():
    """So sanh 2 chieu ALL_JS_FILES (danh sach test khoa cung) voi danh sach
    that <script src="js/...js"> doc dong tu index.html - ca 2 chieu deu phai
    fail neu lech: index.html them file JS moi ma ALL_JS_FILES chua liet ke
    (thieu kiem tra 200 cho file moi), hoac ALL_JS_FILES con ten file da bi
    go khoi index.html (test 200 cho file khong con duoc dung nua)."""
    real_files = _script_src_js_files_in_index_html()
    expected_files = set(ALL_JS_FILES)
    missing_from_test = real_files - expected_files
    stale_in_test = expected_files - real_files
    assert not missing_from_test, f"index.html co script JS moi chua duoc them vao ALL_JS_FILES: {missing_from_test}"
    assert not stale_in_test, f"ALL_JS_FILES con ten file JS khong con duoc index.html dung toi: {stale_in_test}"


def test_serve_css_404_for_nonexistent_file(client):
    resp = client.get("/css/does-not-exist.css")
    assert resp.status_code == 404


def test_serve_js_404_for_nonexistent_file(client):
    resp = client.get("/js/does-not-exist.js")
    assert resp.status_code == 404


def test_serve_js_cannot_escape_static_js_dir_via_path_traversal(client):
    """Flask/Werkzeug tu chan '..' trong <path:filename> converter, nhung khoa
    lai bang test ro rang - dam bao khong the doc backend/.env qua route nay."""
    resp = client.get("/js/../../.env")
    assert resp.status_code in (400, 404)
    assert b"ANTHROPIC_API_KEY" not in resp.data
    assert b"SECRET_KEY" not in resp.data
