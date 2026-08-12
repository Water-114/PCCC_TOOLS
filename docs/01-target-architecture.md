# Kiến trúc mục tiêu: đơn giản trước, mở rộng sau

## Quyết định kiến trúc

Giai đoạn đầu duy trì **modular monolith**. Không tách microservice và không đưa frontend lên Vercel.

```text
Browser
  │ HTTPS, cùng domain
  ▼
Render Web Service
  ├─ Flask: static UI, auth, rule engine, API, AI gateway
  └─ Gunicorn
  │ DATABASE_URL
  ▼
Render PostgreSQL
```

Lý do: source phục vụ `index.html`, `css/` và `js/` từ chính Flask (`backend/app/static/`); giữ cùng origin sẽ tránh một lớp CORS, biến môi trường frontend và reverse proxy không cần thiết. Xem `backend/app/__init__.py` và `render.yaml`.

## Thành phần và trách nhiệm

| Thành phần | Trách nhiệm | Không làm |
|---|---|---|
| Static UI (`backend/app/static/index.html`, `js/`, `css/`) | Nhập liệu, hiển thị, upload, UX | Không quyết định rule pháp lý cuối cùng, không giữ secret |
| Flask API | Validation, auth, rate limit, rule engine, quota, AI gateway | Không tin client-side validation |
| PostgreSQL | User, usage, feedback, dữ liệu job/kết quả tối thiểu | Không lưu API key hoặc file bản vẽ dạng BLOB |
| Claude/Gemini | Trích xuất/đối chiếu có cấu trúc từ bản vẽ | Không là nguồn sự thật pháp lý |

## Quyết định frontend

- **`backend/app/static/` là frontend production chính thức và duy nhất** — Flask phục vụ trực tiếp cùng origin với API (route `/`, `/css/<path>`, `/js/<path>`, xem `backend/app/__init__.py`).
- MVP React/Vite (`frontend/`) từng chạy song song (đóng băng, không nhận tính năng mới) đã được **gỡ khỏi source** (Batch 7A) — không được Render build, không được `index.html` import. Lịch sử code vẫn còn trong git nếu cần tham khảo lại.
- Chỉ lập kế hoạch migration sang React/TypeScript nếu thật sự cần, sau khi API contract, rule engine và test ổn định — dự án riêng, không xen vào batch an toàn/vận hành, và không mặc định coi git history của `frontend/` cũ là điểm khởi đầu.

## Quyết định database

- Chuyển từ SQLite sang Render PostgreSQL bằng `DATABASE_URL`; giữ SQLAlchemy + Flask-Migrate.
- Migrations là nguồn sự thật schema; không sửa schema production bằng tay trên dashboard.
- Web service dùng connection pool có giới hạn, `pool_pre_ping`, và không chạy migration đồng thời bởi nhiều instance.
- Giai đoạn đầu chỉ dùng **một database production duy nhất**, không tạo staging riêng — quyết định của chủ dự án (giữ kiến trúc đơn giản, tiết kiệm chi phí ở giai đoạn này). Nếu sau này cần staging, tạo bổ sung theo đúng quy trình batch, không tự ý thêm.

### Trạng thái hiện tại (cập nhật Batch 7A — 2026-08-12)

- Render PostgreSQL production: **`pccc-trolynghiepvu-db`** (region Oregon/US West, cùng region với web service `PCCC-TROLYNGHIEPVU`), đã được owner nâng lên gói **Basic-256mb** (không còn ở gói Free hết hạn) — xác nhận đang là database thật đang phục vụ production.
- Kể từ Batch 5A, production đã chạy nhiều tính năng phụ thuộc schema mới (xác thực email, số dư Bộ hồ sơ, nạp tiền thủ công, thưởng góp ý) — đây là bằng chứng gián tiếp rằng `DATABASE_URL` đã gắn vào web service và các migration liên quan đã được áp dụng tại một thời điểm nào đó trên Postgres thật.
- **Claude Code KHÔNG có quyền truy cập Render Shell nên không thể tự xác nhận** database production hiện có đang ở đúng migration head mới nhất khớp với `backend/migrations/versions/` trong source hay không — theo đúng quy tắc "không khẳng định khi không có bằng chứng trực tiếp". **Đây là việc owner cần tự kiểm tra thủ công** trước khi deploy bất kỳ thay đổi schema mới nào: mở Render Shell cho `PCCC-TROLYNGHIEPVU`, chạy `flask db current` rồi so với `flask db heads`, xem thêm [runbook migration](04-migration-runbook.md).

Supabase là lựa chọn thay thế hợp lệ khi cần đồng thời PostgreSQL, Storage private hoặc Auth managed; nó **không bắt buộc** cho kiến trúc này. Nếu thay đổi sang Supabase sau này, vẫn giữ Flask là API quyết định nghiệp vụ.

## AI ở giai đoạn đơn giản

AI vẫn chạy đồng bộ trong batch đầu, nhưng phải được bao bọc:

- Một lượt AI/user tại một thời điểm; quota reservation phải nguyên tử.
- Request timeout, retry có phân loại lỗi và giới hạn output/cost.
- Validate file theo kích thước, magic bytes, số trang và MIME; không chỉ tin `file.mimetype`.
- Validate chặt JSON AI: schema, enum, đầy đủ id tiêu chí, không có id lạ.
- Ghi nhận provider/model/prompt version/latency/token usage nếu SDK cung cấp.
- Công cụ là trợ lý/hỗ trợ tham khảo — **không có quyền thẩm định, phê duyệt
  hoặc đưa ra quyết định chuyên môn cuối cùng**, và không có workflow phê
  duyệt nội bộ nào chặn việc dùng kết quả (xem quyết định của owner ở
  `docs/02-implementation-batches.md` mục Batch 3). Mọi kết quả rule/AI phải
  kèm đúng cảnh báo thống nhất: *"Kết quả từ công cụ chỉ mang tính hỗ trợ
  tham khảo trong quá trình rà soát hồ sơ. Kết luận, thẩm định và trách
  nhiệm chuyên môn cuối cùng thuộc về kỹ sư PCCC."*

Khi đạt một trong các ngưỡng sau thì mới mở batch kiến trúc bất đồng bộ: p95 AI trên 90 giây, từ 10 job AI/ngày trở lên, có timeout/mất kết quả, hoặc cần nhiều người dùng cùng lúc. Khi đó bổ sung Redis + worker riêng; không làm sớm hơn.

## Bảo mật tối thiểu trước public

- `SECRET_KEY` bắt buộc ở production, không có default dùng được.
- CORS chỉ whitelist domain thật; không dùng `*` cho auth/admin/AI.
- Token không lưu trong `localStorage` nếu còn lỗ hổng XSS; ưu tiên cookie HttpOnly/Secure/SameSite khi cùng domain.
- Không dùng `innerHTML` với dữ liệu người dùng, tên file, Google Sheet hoặc output AI.
- Thêm CSP, HSTS (sau khi HTTPS ổn định), `X-Content-Type-Options`, `Referrer-Policy`.
- `/api/ai/comment`, login, register, feedback và upload đều phải rate-limit.

## Sơ đồ dữ liệu tối thiểu

```text
users ──< usage_log
users ──< feedback

Tương lai khi cần xử lý bất đồng bộ:
users ──< analysis_jobs ──< analysis_artifacts
```

Không thêm `analysis_jobs` trước Batch 5 trừ khi metrics xác nhận cần worker.
