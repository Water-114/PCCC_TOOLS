# Các batch cải thiện

Mỗi batch phải được triển khai độc lập, test/review xong rồi dừng chờ duyệt. Không gộp batch để "tiện tay".

## Batch 0 — Baseline và khung kiểm thử

**Mục tiêu:** tạo điểm xuất phát lặp lại được trước khi đổi behavior.

**Công việc**

- Xác định root static UI là production UI; đánh dấu `frontend/` là MVP đóng băng trong README.
- Thêm pytest, cấu trúc `backend/tests/`, fixture Flask test client và database test tách biệt.
- Thêm test cho health, auth input cơ bản, water calculator và thẩm định.
- Thêm script kiểm tra JS root, lint frontend và kiểm tra migration.
- Ghi nhận baseline: thời gian AI, lỗi API, kích thước response, số tiêu chí MĐC.

**Không làm:** không đổi ngưỡng pháp lý, UI lớn, schema production hay deploy.

**Gate kiểm tra**

- `pytest` chạy ổn định, không dùng database production.
- `npm run lint` pass.
- Các test tái hiện lỗi đã phát hiện: số âm/NaN ở water và số không hợp lệ ở thẩm định.
- Review xác nhận test chạy được trên máy mới theo README.

## Batch 1 — Security và validation bắt buộc

**Mục tiêu:** đóng các rủi ro public nghiêm trọng mà không đổi nghiệp vụ.

**Công việc**

- Validation server-side cho mọi số: parse lỗi -> 400; finite; range; không âm khi phù hợp.
- Chuẩn hóa error response JSON; không trả stack trace hoặc exception SDK cho client.
- Bắt buộc production `SECRET_KEY`, CORS allowlist, security headers.
- Rate limit cho register/login/feedback/AI comment/upload; `/api/ai/comment` yêu cầu auth và quota.
- Sửa stored/reflected XSS: thay `innerHTML` bằng DOM API/text escaping cho feedback, email, file name, output AI và thư viện.
- Đặt `MAX_CONTENT_LENGTH`, kiểm tra magic bytes/MIME upload, giới hạn số trang/ảnh trước gọi AI.

**Gate kiểm tra**

- Test API âm/NaN/string trả 400, không còn 500.
- Test quota và rate limit; test concurrent quota reservation.
- Regression test payload chứa HTML không thực thi trong admin/kết quả AI.
- Manual review CORS và response headers từ local server.

## Batch 2 — PostgreSQL và deploy readiness

**Mục tiêu:** thay SQLite để dữ liệu bền vững khi deploy Render.

**Quyết định của owner (thay cho kế hoạch "staging" ban đầu):** chỉ tạo **một
Render PostgreSQL production** — `pccc-trolynghiepvu-db` — không tạo database
staging riêng ở giai đoạn này, để giữ kiến trúc đơn giản và tiết kiệm chi phí.
Xem `docs/01-target-architecture.md` mục "Trạng thái hiện tại".

**Công việc**

- ~~Tạo Render PostgreSQL staging~~ → Tạo Render PostgreSQL **production**
  (`pccc-trolynghiepvu-db`, region Oregon) qua Dashboard — **đã xong**, trạng
  thái Available. Chưa cấu hình `DATABASE_URL` trên web service.
- Review migration Alembic hiện có, thêm index cần thiết cho usage query —
  **đã xong** (composite index `ix_usage_log_user_api_created`).
- Tối ưu query admin: pagination, tránh N+1 `count_usage_today`, giới hạn
  feedback/users trả về — **đã xong**.
- Cấu hình SQLAlchemy pool và health check database — **đã xong**.
- Tách lệnh migration khỏi web startup; tạo runbook migration/rollback —
  **đã xong**, xem [docs/04-migration-runbook.md](04-migration-runbook.md).
- Bổ sung `.env.example` hoàn chỉnh theo local/production — **đã xong**.

**Gate kiểm tra — TRẠNG THÁI: CHƯA PASS, còn lại cho giai đoạn deploy sau**

- [x] `flask db upgrade` / `downgrade` / `upgrade` lại chạy đúng trên SQLite
      local (diễn tập rollback) — đã xác nhận trong Batch 2.
- [ ] `flask db upgrade` chạy trên `pccc-trolynghiepvu-db` (Postgres production)
      lúc còn rỗng — **chưa thực hiện**, chờ owner xác nhận từng bước theo
      `docs/04-migration-runbook.md`.
- [ ] Smoke test register/login/quota/admin/feedback trên PostgreSQL
      production thật (sau khi gắn `DATABASE_URL` và migrate) — **chưa
      thực hiện**.
- [ ] Restart web service không làm mất dữ liệu (chỉ kiểm chứng được sau khi
      `DATABASE_URL` đã trỏ Postgres) — **chưa thực hiện**.
- [ ] Review backup, quyền truy cập database và rollback migration trước khi
      deploy thật — **chưa thực hiện**.

Bốn gate còn lại là điều kiện bắt buộc trước khi coi Batch 2 là "deploy
readiness" thật sự, không chỉ là "code readiness". Không tự ý đánh dấu pass
các gate này nếu chưa thực sự chạy trên `pccc-trolynghiepvu-db`.

## Batch 3 — Canonical API và rule engine

**Mục tiêu:** một nguồn sự thật cho kết luận rule-based, có truy vết pháp lý.

**Công việc**

- Viết API contract cho water/thẩm định/rule results bằng schema rõ ràng.
- Di chuyển theo từng cụm rule từ `js/tuvan-so-bo.js` vào backend service có test; frontend chỉ render API response.
- Mỗi rule phải có `rule_set_version`, nguồn, ngày hiệu lực, điều kiện đầu vào và test dưới/bằng/trên ngưỡng.
- Chỉ chuyển một cụm mỗi PR: thẩm định -> hệ thống bắt buộc -> nước -> phương tiện.
- Loại bỏ logic JS trùng lặp chỉ sau khi endpoint tương ứng đã qua regression test.

**Gate kiểm tra**

- Golden test cho mọi công năng và biên ngưỡng đã chuyển.
- Kỹ sư PCCC duyệt source/version của rule trước merge.
- Browser test xác nhận phiếu in/xuất giữ nguyên kết quả trên bộ dữ liệu chuẩn.

## Batch 4 — AI reliability và tính đúng đắn đầu ra

**Mục tiêu:** AI là trợ lý có kiểm soát, không tạo MĐC sai cấu trúc.

**Công việc**

- Định nghĩa JSON Schema/Pydantic model cho từng loại đọc bản vẽ.
- Validate đủ tiêu chí, id chính xác, enum `dat/chua_dat/chua_the_hien`, giới hạn độ dài nội dung.
- Khi invalid: retry repair tối đa một lần; sau đó trả lỗi rõ ràng, không sinh MĐC nửa vời.
- Ghi provider, model, prompt template version, thời gian, usage/cost nếu có.
- Cài timeout/retry backoff/circuit-breaker tối thiểu; bỏ output demo khỏi luồng "AI thật" hoặc gắn nhãn không thể nhầm lẫn.
- Chuyển Gemini SDK legacy sang SDK được nhà cung cấp hỗ trợ, kèm regression test provider adapter.

**Gate kiểm tra**

- Fixture output malformed/missing id bị chặn.
- Test MĐC: đúng số dòng, không tự điền "Đạt" khi model trả enum sai.
- Test không có API key, provider timeout, quota exhausted, partial result chữa cháy nước.
- Review bằng ít nhất một bộ bản vẽ đã được ẩn danh và được kỹ sư PCCC đối chiếu thủ công.

## Batch 5 — Release staging và quyết định worker

**Mục tiêu:** phát hành staging an toàn và chỉ tăng độ phức tạp khi có dữ liệu.

**Công việc**

- Deploy staging trên Render Web Service + Render PostgreSQL.
- Thiết lập env tách biệt, monitoring lỗi, structured logging, health/readiness check.
- Chạy smoke test và UAT theo checklist; đo p50/p95 AI và tỷ lệ lỗi.
- Lập runbook incident: AI provider down, rollback deployment, rollback migration, revoke secret.
- Quyết định có cần Redis/worker theo ngưỡng trong kiến trúc mục tiêu hay không.

**Gate kiểm tra**

- Không có lỗi P0/P1 mở.
- Security checklist pass và secret không xuất hiện trong repository/log.
- UAT được người nghiệp vụ ký xác nhận.
- Người sở hữu dự án phê duyệt deploy production bằng văn bản rõ ràng.

## Batch 6 — Tùy chọn: AI worker bất đồng bộ

Chỉ mở khi Batch 5 xác nhận cần thiết. Bổ sung một queue và một Render Background Worker; không thay đổi rule engine hoặc UI ngoài flow trạng thái job.

**Gate kiểm tra:** idempotency, retry, resume sau restart, job timeout, không tạo hai lượt quota/cost cho một job, tải song song giới hạn.
