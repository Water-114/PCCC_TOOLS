# PCCC_TOOLS — Hướng dẫn PCCC (Demo MVP)

APP HƯỚNG DẪN VẤN ĐÁP PCCC

## Kế hoạch cải thiện

Tài liệu triển khai theo kiến trúc đơn giản (Render Web Service + PostgreSQL managed), các batch test/review và prompt handoff cho Claude nằm tại [docs/README.md](docs/README.md). Đọc bộ tài liệu này trước khi thực hiện thay đổi lớn hoặc deploy.

## Kiến trúc

Một service Flask duy nhất phục vụ cả API lẫn giao diện — không còn frontend tách riêng:

- **`backend/app/static/`** — giao diện production duy nhất (`index.html` + `css/` + `js/`), gồm 5 mục chính: Hướng dẫn thiết kế và lập phiếu hướng dẫn sơ bộ, Công cụ tính toán, **AI kiểm tra hồ sơ** (đọc bản vẽ bằng AI thật, có đăng nhập + số dư "Bộ hồ sơ"), Thư viện pháp luật, AI trợ lý. Trang **Quản trị** (đăng nhập bằng tài khoản `role=admin`: thống kê tài khoản/lượt gọi API/góp ý, xác nhận nạp tiền...) nằm trong **cùng `index.html`** (tab riêng), không phải trang HTML tách biệt.
- **`backend/`** — Flask API + phục vụ luôn static UI ở trên: tính nước chữa cháy, AI gateway (Claude/Gemini), đăng nhập/đăng ký + xác thực email, AI đọc bản vẽ (nhiều hạng mục PCCC, có quản lý số dư "Bộ hồ sơ"), nạp tiền thủ công, góp ý + thưởng góp ý, thống kê quản trị. Database qua SQLAlchemy + Flask-Migrate (SQLite cho dev local, PostgreSQL cho production).

Trước đây có một MVP React + Vite (`frontend/`) chạy song song — đã đóng băng và **gỡ khỏi source** (không được Render build, không được `index.html` import). Lịch sử code vẫn còn trong git nếu cần tham khảo lại; không thêm framework/hosting mới để thay thế.

## Chính sách "Bộ hồ sơ" (tính năng AI đọc bản vẽ)

Chỉ tính năng **AI kiểm tra hồ sơ** yêu cầu đăng nhập — các công cụ khác (tính nước, phiếu hướng dẫn sơ bộ...) dùng tự do. Số dư được tính bằng đơn vị **"Bộ hồ sơ"** (không dùng "credit"/"lượt đọc" khi nói với người dùng):

- Mỗi tài khoản được **01 Bộ hồ sơ dùng thử** một lần, cấp ngay sau khi xác thực email lần đầu (đăng ký mở tự do: email + mật khẩu ≥ 6 ký tự).
- Nạp **100.000đ** được cộng **02 Bộ hồ sơ**, chỉ sau khi admin xác nhận đã nhận được chuyển khoản thủ công (không tích hợp cổng thanh toán tự động).
- Góp ý cho **05 Bộ hồ sơ hoàn thành** được cộng thêm **01 Bộ hồ sơ**.
- Một Bộ hồ sơ = tối đa 5 file bản vẽ, tối đa 7 form MĐC của cùng một công trình/phiên.
- Ngoài số dư Bộ hồ sơ, còn một hạn mức phụ **`AIHO_DAILY_QUOTA`** (mặc định 5 lượt gọi AI/ngày/tài khoản, đổi ở `backend/.env`, cần khởi động lại backend sau khi đổi) — lớp chặn chi phí bổ sung, không thay thế số dư Bộ hồ sơ.

Tạo tài khoản admin đầu tiên (để dùng tab **Quản trị** trong `index.html`):
```bash
cd backend
source venv/Scripts/activate
export FLASK_APP=app:create_app   # PowerShell: $env:FLASK_APP="app:create_app"
flask create-admin <email> <mat_khau>
```
Chạy lại lệnh này với email đã có sẵn để đổi mật khẩu/nâng quyền admin cho tài khoản đó.

## Chạy backend (Flask) — phục vụ cả API và giao diện

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env           # rồi điền ANTHROPIC_API_KEY / GEMINI_API_KEY nếu đã có
export FLASK_APP=app:create_app
flask db upgrade                # tạo/migrate database (chỉ cần chạy khi có migration mới)
python run.py                  # chạy tại http://127.0.0.1:5000
```

Chưa có API key vẫn chạy được — các endpoint tính toán hoạt động bình thường, riêng `/api/ai/comment` và các route `/api/aiho/read-*` sẽ trả lỗi rõ ràng "Chưa cấu hình ... API_KEY" thay vì crash (không tính vào số dư Bộ hồ sơ vì chưa thực sự gọi AI).

Mở **http://127.0.0.1:5000/** — Flask phục vụ trực tiếp `index.html`/`css/`/`js/` từ `backend/app/static/`, không cần server tĩnh riêng, không mở bằng `file://`.

## Chạy test (backend)

```bash
cd backend
venv/Scripts/pip install pytest==8.3.4   # hoặc: pip install -r requirements-dev.txt (cần sẵn PostgreSQL build tools nếu build psycopg2-binary từ source)
venv/Scripts/pytest -v                    # không đụng backend/app.db thật, không gọi API AI trả phí
```

Chi tiết phạm vi test: [backend/tests/README.md](backend/tests/README.md).

Lint cho giao diện (`backend/app/static/js/*.js`):

```bash
npm install
npm run lint
```

## Khuyến nghị trước khi dùng làm demo công khai / thương mại hoá

- Không commit `.env`/API key/`app.db` (đã gitignore) — khi deploy thật dùng secret manager của platform và đổi `SECRET_KEY` thật.
- Thông tin tài khoản ngân hàng nhận chuyển khoản (`BANK_ACCOUNT_NUMBER`/`BANK_ACCOUNT_NAME`/`BANK_NAME`) chỉ cấu hình qua biến môi trường, không hardcode/commit dưới bất kỳ hình thức nào.
- Dùng số liệu mẫu khi demo công khai, không dùng dữ liệu hồ sơ khách hàng thật.
- Trước khi thương mại hoá: chuyển dần các bảng tra QCVN/TCVN khác thành rule-based code thay vì để AI tự suy luận, để đảm bảo độ tin cậy cho hồ sơ pháp lý.
- SQLite chỉ dùng cho local development/test. Production dùng Render PostgreSQL (`pccc-trolynghiepvu-db`, qua `DATABASE_URL` — không cần sửa code, chỉ đổi connection string, xem `docs/01-target-architecture.md`).
