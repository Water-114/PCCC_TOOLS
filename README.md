# PCCC_TOOLS — Hướng dẫn PCCC (Demo MVP)

APP HƯỚNG DẪN VẤN ĐÁP PCCC

## Kế hoạch cải thiện

Tài liệu triển khai theo kiến trúc đơn giản (Render Web Service + PostgreSQL managed), các batch test/review và prompt handoff cho Claude nằm tại [docs/README.md](docs/README.md). Đọc bộ tài liệu này trước khi thực hiện thay đổi lớn hoặc deploy.

Dự án gồm 2 phần chạy song song:

- **`index.html`** (thư mục gốc) — trang chính đang dùng thật, đầy đủ 5 mục: Hướng dẫn thiết kế và lập phiếu hướng dẫn sơ bộ, Công cụ tính toán, **AI kiểm tra hồ sơ** (đã gắn AI thật cho hạng mục "Báo cháy tự động", có đăng nhập + giới hạn lượt/ngày), Thư viện pháp luật, AI trợ lý.
- **`admin.html`** (thư mục gốc) — trang quản trị riêng: đăng nhập bằng tài khoản `role=admin`, xem thống kê tổng số tài khoản/lượt gọi API/góp ý, danh sách user kèm lượt còn lại, bảng góp ý.
- **`backend/`** — Flask API phục vụ cả 2 trang trên: tính nước chữa cháy, AI gateway (Claude/Gemini), đăng nhập/đăng ký, AI đọc bản vẽ báo cháy (có giới hạn quota), góp ý, thống kê quản trị. Có database SQLite (`backend/app.db`, không commit) qua SQLAlchemy + Flask-Migrate.
- **`frontend/`** — React + Vite, một MVP tách riêng (2 tính năng: tính nước chữa cháy, diện thẩm định Phụ lục III) — **đã đóng băng**: không nhận tính năng mới, không deploy độc lập, chỉ giữ lại để tham khảo. `index.html` (root static UI) là giao diện production chính thức duy nhất.

## Đăng nhập & giới hạn lượt dùng (tính năng AI đọc bản vẽ)

Chỉ tính năng "AI đọc bản vẽ" (hạng mục Báo cháy tự động, trong tab "AI kiểm tra hồ sơ") yêu cầu đăng nhập — các công cụ khác dùng tự do. Mỗi tài khoản được **5 lượt/ngày** (đổi số ở `AIHO_DAILY_QUOTA` trong `backend/.env`, cần khởi động lại backend sau khi đổi). Đăng ký mở tự do (email + mật khẩu ≥ 6 ký tự).

Tạo tài khoản admin đầu tiên (để dùng `admin.html`):
```bash
cd backend
source venv/Scripts/activate
export FLASK_APP=app:create_app   # PowerShell: $env:FLASK_APP="app:create_app"
flask create-admin <email> <mat_khau>
```
Chạy lại lệnh này với email đã có sẵn để đổi mật khẩu/nâng quyền admin cho tài khoản đó.

## Chạy backend (Flask)

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env           # rồi điền ANTHROPIC_API_KEY / GEMINI_API_KEY nếu đã có
export FLASK_APP=app:create_app
flask db upgrade                # tạo/migrate database (chỉ cần chạy khi có migration mới)
python run.py                  # chạy tại http://localhost:5000
```

Chưa có API key vẫn chạy được — các endpoint tính toán hoạt động bình thường, riêng `/api/ai/comment` và `/api/aiho/read-baochay` sẽ trả lỗi rõ ràng "Chưa cấu hình ... API_KEY" thay vì crash (vẫn tính 1 lượt quota vì đã thực sự cố gọi AI).

Mở `index.html`/`admin.html` qua server tĩnh (không mở trực tiếp bằng `file://`) để các lệnh gọi API chạy đúng, ví dụ: `python -m http.server 8080` tại thư mục gốc, rồi truy cập `http://127.0.0.1:8080/index.html`.

## Chạy test (Batch 0 — baseline)

```bash
cd backend
venv/Scripts/pip install pytest==8.3.4   # hoặc: pip install -r requirements-dev.txt (cần sẵn PostgreSQL build tools nếu build psycopg2-binary từ source)
venv/Scripts/pytest -v                    # không đụng backend/app.db thật, không gọi API AI trả phí
```

Chi tiết phạm vi test: [backend/tests/README.md](backend/tests/README.md).

Lint cho `js/*.js` (root static UI — tách biệt hoàn toàn `frontend/`):

```bash
npm install
npm run lint
```

## Chạy frontend (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, mặc định http://localhost:5000
npm run dev            # chạy tại http://localhost:5173
```

## Khuyến nghị trước khi dùng làm demo công khai / thương mại hoá

- Không commit `.env`/API key/`app.db` (đã gitignore) — khi deploy thật dùng secret manager của platform và đổi `SECRET_KEY` thật.
- Quota (5 lượt/ngày) mới chặn tính năng AI đọc bản vẽ — `/api/ai/comment` (bên MVP React) chưa có giới hạn, cân nhắc thêm nếu public.
- Dùng số liệu mẫu khi demo công khai, không dùng dữ liệu hồ sơ khách hàng thật.
- Trước khi thương mại hoá: chuyển dần các bảng tra QCVN/TCVN khác thành rule-based code thay vì để AI tự suy luận, để đảm bảo độ tin cậy cho hồ sơ pháp lý.
- SQLite hiện đủ dùng cho quy mô demo — khi nhiều người dùng thật hơn, đổi `DATABASE_URL` sang Postgres/Supabase (không cần sửa code, chỉ đổi connection string).
