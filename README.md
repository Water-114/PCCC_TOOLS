# Tư vấn PCCC — Demo MVP

Bản demo MVP chuyển từ trang tĩnh `index.html` sang kiến trúc tách lớp:

- **frontend/** — React + Vite (UI)
- **backend/** — Flask (API thuần)
- **AI gateway** ở backend, có provider abstraction để đổi qua lại giữa **Claude** và **Gemini**
- **Chưa dùng database** ở giai đoạn demo này (Supabase để dành cho giai đoạn thương mại hoá sau)

Tính năng demo: **Tính dung tích bể nước chữa cháy** (V = Q × t, QCVN 06 / TCVN 7336) — tính deterministic ở Flask, sau đó có nút gọi AI (Claude/Gemini) để diễn giải kết quả bằng ngôn ngữ tự nhiên. AI chỉ diễn giải, không tự quyết định số liệu kỹ thuật.

`index.html` ở thư mục gốc là bản tĩnh cũ, giữ lại để tham khảo — không còn được cập nhật.

## Chạy backend (Flask)

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env           # rồi điền ANTHROPIC_API_KEY / GEMINI_API_KEY nếu đã có
python run.py                  # chạy tại http://localhost:5000
```

Chưa có API key vẫn chạy được — các endpoint tính toán hoạt động bình thường, riêng `/api/ai/comment` sẽ trả lỗi rõ ràng "Chưa cấu hình ... API_KEY" thay vì crash.

## Chạy frontend (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL, mặc định http://localhost:5000
npm run dev            # chạy tại http://localhost:5173
```

## Khuyến nghị trước khi dùng làm demo công khai / thương mại hoá

- Không commit `.env`/API key (đã gitignore) — khi deploy thật dùng secret manager của platform.
- Thêm rate-limit cho `/api/ai/comment` để tránh phát sinh chi phí bất ngờ khi gọi Claude/Gemini.
- Dùng số liệu mẫu khi demo công khai, không dùng dữ liệu hồ sơ khách hàng thật.
- Trước khi thương mại hoá: chuyển dần các bảng tra QCVN/TCVN khác thành rule-based code thay vì để AI tự suy luận, để đảm bảo độ tin cậy cho hồ sơ pháp lý.
- Khi cần lưu dữ liệu (lịch sử tính toán, tài khoản người dùng): thêm Supabase Postgres qua SQLAlchemy + Alembic, giữ nguyên service layer/provider abstraction hiện có.
