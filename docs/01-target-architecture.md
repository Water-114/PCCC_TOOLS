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

Lý do: source hiện tại đã phục vụ `index.html`, `css/` và `js/` từ Flask; giữ cùng origin sẽ tránh một lớp CORS, biến môi trường frontend và reverse proxy không cần thiết. Xem `backend/app/__init__.py` và `render.yaml`.

## Thành phần và trách nhiệm

| Thành phần | Trách nhiệm | Không làm |
|---|---|---|
| Static UI (`index.html`, `js/`, `css/`) | Nhập liệu, hiển thị, upload, UX | Không quyết định rule pháp lý cuối cùng, không giữ secret |
| Flask API | Validation, auth, rate limit, rule engine, quota, AI gateway | Không tin client-side validation |
| PostgreSQL | User, usage, feedback, dữ liệu job/kết quả tối thiểu | Không lưu API key hoặc file bản vẽ dạng BLOB |
| Claude/Gemini | Trích xuất/đối chiếu có cấu trúc từ bản vẽ | Không là nguồn sự thật pháp lý |

## Quyết định frontend

- Trong các batch đầu, **root static UI là frontend chính thức**.
- `frontend/` React/Vite được đóng băng: không thêm tính năng mới và không deploy độc lập.
- Chỉ lập kế hoạch migration sang React/TypeScript sau khi API contract, rule engine và test ổn định. Migration này là một dự án riêng, không xen vào batch an toàn/vận hành.

## Quyết định database

- Chuyển từ SQLite sang Render PostgreSQL bằng `DATABASE_URL`; giữ SQLAlchemy + Flask-Migrate.
- Migrations là nguồn sự thật schema; không sửa schema production bằng tay trên dashboard.
- Web service dùng connection pool có giới hạn, `pool_pre_ping`, và không chạy migration đồng thời bởi nhiều instance.
- Giai đoạn đầu chỉ dùng **một database production duy nhất**, không tạo staging riêng — quyết định của chủ dự án (giữ kiến trúc đơn giản, tiết kiệm chi phí ở giai đoạn này). Nếu sau này cần staging, tạo bổ sung theo đúng quy trình batch, không tự ý thêm.

### Trạng thái hiện tại (cập nhật sau Batch 2, chưa qua release gate)

- Render PostgreSQL production đã được owner tạo thủ công qua Dashboard: **`pccc-trolynghiepvu-db`** (region Oregon/US West, cùng region với web service `PCCC-TROLYNGHIEPVU`), trạng thái **Available**.
- Batch 2 mới hoàn tất phần **code** (pool config, tối ưu query, health check, index, tách migration khỏi startup) và **migration đã diễn tập trên SQLite local** (upgrade/downgrade/upgrade lại) — xem [runbook migration](04-migration-runbook.md).
- **Chưa gắn `DATABASE_URL` vào web service, chưa chạy `flask db upgrade` trên `pccc-trolynghiepvu-db`, chưa smoke test trên Postgres thật.** Ba việc này là release gate bắt buộc của giai đoạn deploy kế tiếp (xem `docs/02-implementation-batches.md` mục Batch 2 — Gate kiểm tra), chỉ thực hiện khi owner xác nhận rõ ràng từng bước.
- Web service hiện vẫn chạy SQLite (ephemeral) như trước Batch 2 — production chưa có gì thay đổi thực tế.

Supabase là lựa chọn thay thế hợp lệ khi cần đồng thời PostgreSQL, Storage private hoặc Auth managed; nó **không bắt buộc** cho kiến trúc này. Nếu thay đổi sang Supabase sau này, vẫn giữ Flask là API quyết định nghiệp vụ.

## AI ở giai đoạn đơn giản

AI vẫn chạy đồng bộ trong batch đầu, nhưng phải được bao bọc:

- Một lượt AI/user tại một thời điểm; quota reservation phải nguyên tử.
- Request timeout, retry có phân loại lỗi và giới hạn output/cost.
- Validate file theo kích thước, magic bytes, số trang và MIME; không chỉ tin `file.mimetype`.
- Validate chặt JSON AI: schema, enum, đầy đủ id tiêu chí, không có id lạ.
- Ghi nhận provider/model/prompt version/latency/token usage nếu SDK cung cấp.
- Kết quả luôn hiển thị là hỗ trợ sơ bộ và phải có bước kỹ sư phê duyệt.

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
