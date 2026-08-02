# Runbook incident (Batch 5)

Bổ sung cho [docs/04-migration-runbook.md](04-migration-runbook.md) (chỉ
migration/rollback schema) — file này gồm 4 loại sự cố còn lại theo đúng
phạm vi Batch 5: **AI provider down**, **rollback deployment**, **rollback
migration** (tóm tắt + link), **revoke secret**.

**Chưa từng diễn tập THẬT trên production** cho bất kỳ mục nào dưới đây —
khác với runbook migration (đã diễn tập upgrade/downgrade/upgrade lại trên
SQLite local). Nội dung dưới đây được viết dựa trên tính năng có sẵn của
Render/nhà cung cấp và cách code hiện xử lý lỗi (đọc trực tiếp source, không
đoán) — xem mục "Khoảng trống chưa có" cuối file trước khi coi runbook này là
đủ để owner tự tin xử lý sự cố thật.

## 1. AI provider down (Anthropic hoặc Gemini lỗi hạ tầng)

**Cơ chế tự động đã có** (`backend/app/providers/resilience.py`, từ Batch 4):
circuit breaker per-provider-name (`"claude"`/`"gemini"` tách biệt), lưu
trạng thái **trong bộ nhớ tiến trình** (mất khi restart/redeploy, mỗi worker
gunicorn có breaker riêng — không dùng Redis). Sau **3 lỗi hạ tầng liên tiếp**
(mất kết nối/timeout/5xx — KHÔNG tính lỗi JSON sai hay provider chưa cấu
hình), breaker "mở" và từ chối gọi thêm trong **60 giây** (fail-fast, không
tốn thời gian chờ timeout lần nữa), sau đó tự cho 1 lượt "thăm dò" — không
cần thao tác thủ công để reset.

**Phân biệt 2 loại lỗi khi xem log/response:**
- **API key sai/hết hạn/hết quota** → route trả **503**, message "provider
  chưa cấu hình" (`ProviderNotConfigured`, `backend/app/providers/base.py`)
  — xảy ra ngay từ request đầu tiên, KHÔNG đợi đủ 3 lần mới báo. Kiểm tra
  dashboard nhà cung cấp (Anthropic Console / Google AI Studio) xác nhận key
  còn hiệu lực và còn quota.
- **Lỗi hạ tầng tạm thời** (mất kết nối/timeout/5xx từ phía provider) → route
  trả **502**, message `"Lỗi gọi máy chủ AI ('<provider>') — vui lòng thử lại
  sau."` (`backend/app/routes/aiho.py:129`); nếu breaker đã mở, message cụ
  thể hơn: `"Provider '<tên>' vừa lỗi kết nối N lần liên tiếp — tạm ngừng gọi
  thêm khoảng N giây..."` (`CircuitBreakerOpen`).

**Mitigation thủ công nếu 1 provider down kéo dài** (không tự phục hồi sau
vài phút): đổi biến môi trường `AI_PROVIDER` trên Render Dashboard (Web
Service → Environment) từ `claude` sang `gemini` hoặc ngược lại, rồi để
Render tự restart service khi lưu biến môi trường. **Lưu ý quan trọng**:
frontend (`js/ai-doc-ho-so.js`) hiện **không có UI chọn provider** — luôn
dùng đúng provider mặc định phía backend (`AI_PROVIDER`), nên đổi biến này là
**cách duy nhất** để chuyển hướng traffic sang provider còn lại; không có
cách chuyển theo từng request từ phía người dùng.

**Phát hiện sự cố:** hiện KHÔNG có alerting tự động — chỉ phát hiện qua
người dùng báo lỗi hoặc chủ động xem Render Dashboard → Logs, tìm dòng
`Loi goi provider` hoặc response 502/503 lặp lại.

## 2. Rollback deployment (bản deploy mới gây lỗi)

1. Vào Render Dashboard → chọn Web Service `PCCC-TROLYNGHIEPVU` → tab
   "Events" (hoặc "Deploys") → chọn bản deploy **trước đó** (đã chạy ổn) →
   dùng tính năng **"Rollback"**. Nếu không có nút Rollback trực tiếp: dùng
   "Manual Deploy" → chọn đúng commit SHA cũ cần quay lại.
2. **Cảnh báo bắt buộc kiểm tra trước khi rollback**: nếu bản deploy lỗi đi
   kèm 1 migration schema MỚI đã chạy (`flask db upgrade`), rollback CODE
   không tự rollback SCHEMA — code cũ có thể không tương thích với schema
   mới hơn. Phải rollback migration TRƯỚC (mục 3 dưới đây), rồi mới rollback
   code, trừ khi chắc chắn migration đó chỉ thêm cột nullable/index (an toàn
   cho code cũ chạy cùng schema mới).
3. Sau khi rollback: gọi `GET /api/health`, xác nhận
   `{"status":"ok","database":"ok"}`; thử nhanh 1-2 luồng chính (đăng nhập,
   1 tính năng công cụ tính toán) trước khi coi là xong.
4. Giữ lại bản deploy lỗi trong lịch sử Render (không xoá) để điều tra
   nguyên nhân sau — không cần rollback gấp nếu lỗi không ảnh hưởng người
   dùng đang hoạt động (đánh giá theo mức độ, không rollback theo phản xạ).

## 3. Rollback migration

Đã có runbook đầy đủ ở
**[docs/04-migration-runbook.md](04-migration-runbook.md)** — không lặp lại
ở đây. Tóm tắt nhanh: xác định revision cần quay về (`flask db history`),
chạy `flask db downgrade <revision>` qua Render Shell (KHÔNG qua sửa
`startCommand`), với migration xoá cột/bảng PHẢI có backup xác nhận trước
khi downgrade (downgrade không tự khôi phục dữ liệu đã xoá).

## 4. Revoke secret (lộ SECRET_KEY/API key/mật khẩu SMTP/DB)

**Quy tắc chung, áp dụng cho MỌI loại secret bên dưới**: nếu secret thật đã
từng xuất hiện trong git (commit, kể cả đã xoá ở commit sau) — coi như đã lộ
**vĩnh viễn** (lịch sử git vẫn còn), PHẢI revoke/rotate tại nguồn (nhà cung
cấp), không chỉ xoá khỏi code. Danh sách secret hiện có (`backend/.env.example`,
`render.yaml`) và nơi xử lý từng loại:

| Secret | Nơi cấu hình thật | Cách revoke/rotate |
|---|---|---|
| `ANTHROPIC_API_KEY` | Render Dashboard → Environment (`sync: false` trong `render.yaml`, không lưu giá trị thật trong repo) | Anthropic Console → revoke key cũ → tạo key mới → cập nhật Render Dashboard |
| `GEMINI_API_KEY` | Render Dashboard → Environment | Google AI Studio/Cloud Console → xoá/tạo lại key → cập nhật Render Dashboard |
| `SECRET_KEY` (ký token đăng nhập) | Render tự sinh (`generateValue: true` trong `render.yaml`) | Đổi giá trị thủ công trên Render Dashboard (hoặc yêu cầu Render generate lại). **Hệ quả**: đổi `SECRET_KEY` làm MỌI token đăng nhập đã phát hành hết hiệu lực NGAY LẬP TỨC — toàn bộ người dùng đang đăng nhập bị đăng xuất, phải đăng nhập lại. Cân nhắc thông báo trước nếu không phải phản ứng khẩn cấp với lộ secret thật. |
| `SMTP_USERNAME`/`SMTP_PASSWORD` | Render Dashboard → Environment | Đổi mật khẩu ứng dụng (app password) tại nhà cung cấp SMTP đang dùng → cập nhật Render Dashboard |
| `DATABASE_URL` (chứa mật khẩu Postgres) | Render Dashboard → Environment, giá trị lấy từ database `pccc-trolynghiepvu-db` → tab "Info" | Render Postgres → đổi mật khẩu qua Render Dashboard (nếu tính năng khả dụng theo plan) hoặc liên hệ Render support → cập nhật `DATABASE_URL` trên web service sau khi đổi → **bắt buộc test lại `/api/health`** ngay sau đổi vì service sẽ mất kết nối DB tới khi cập nhật xong |
| `BANK_ACCOUNT_NUMBER`/`BANK_ACCOUNT_NAME`/`BANK_NAME`/`BANK_QR_URL` | Render Dashboard → Environment | Không phải "secret" theo nghĩa credential, nhưng vẫn nhạy cảm (thông tin nhận tiền thật) — nếu bị lộ sai ý muốn (vd dán nhầm vào chỗ công khai), sửa lại giá trị đúng trên Render Dashboard; không cần "revoke" như API key |

Sau khi rotate bất kỳ secret nào: redeploy/restart service để áp dụng giá trị
mới (đổi env var trên Render thường tự trigger restart), rồi xác nhận lại
đúng luồng liên quan (vd đổi `ANTHROPIC_API_KEY` → thử 1 lượt đọc bản vẽ thật
qua provider Claude).

## Khoảng trống chưa có (để owner biết rõ, không giả vờ đã đủ)

- **Chưa có structured logging tập trung** ngoài log mặc định của Render
  (chỉ xem qua Render Dashboard → Logs, không có công cụ tổng hợp/tìm kiếm
  log riêng).
- **Chưa có alerting tự động** (không có Sentry/PagerDuty hay tương đương) —
  phát hiện sự cố hiện hoàn toàn dựa vào theo dõi thủ công hoặc người dùng
  báo lỗi trực tiếp.
- **Chưa diễn tập THẬT** rollback deployment, revoke secret, hay chuyển
  `AI_PROVIDER` trên chính Render production — toàn bộ runbook này viết dựa
  trên tính năng Render/nhà cung cấp đã biết và cách code xử lý lỗi (đọc
  source trực tiếp), CHƯA có lần chạy thử thật nào để xác nhận từng bước
  đúng thao tác/đúng tên nút trên UI Render (giao diện nhà cung cấp có thể
  đổi khác thời điểm viết runbook này).
- **Circuit breaker mất trạng thái khi restart/redeploy** và không chia sẻ
  giữa các gunicorn worker (in-memory, per-process) — nếu chạy nhiều worker,
  một worker có thể đang "mở breaker" trong khi worker khác vẫn gọi bình
  thường; đây là giới hạn đã biết của thiết kế đơn giản (không dùng Redis),
  không phải lỗi cần sửa gấp trong Batch 5.
