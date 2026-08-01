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

**Quyết định của owner (thay cho gate "kỹ sư PCCC duyệt" ban đầu):** đây là
công cụ trợ lý/hỗ trợ tham khảo, **không có quyền thẩm định, phê duyệt hoặc
đưa ra quyết định chuyên môn cuối cùng** — bỏ hoàn toàn mọi workflow phê
duyệt nội bộ (không cần "kỹ sư PCCC ký duyệt" hay bất kỳ ai duyệt
source/version trước khi merge). Thay vào đó, mọi kết quả rule/AI phải kèm
đúng **cảnh báo thống nhất**:

> "Kết quả từ công cụ chỉ mang tính hỗ trợ tham khảo trong quá trình rà soát
> hồ sơ. Kết luận, thẩm định và trách nhiệm chuyên môn cuối cùng thuộc về kỹ
> sư PCCC."

`rule_set_version` và nguồn quy định (`can_cu`) vẫn được giữ để **truy vết
thông tin** (biết đang đối chiếu theo văn bản/phiên bản nào), nhưng chỉ mang
tính tham khảo — không phải điều kiện chặn merge.

**Trạng thái hiện tại:**
- **Cụm 1 (thẩm định):** đã có sẵn `backend/app/services/tham_dinh.py` +
  `backend/app/routes/tham_dinh.py` (`/api/tham-dinh/occupancies`,
  `/api/tham-dinh/evaluate`) từ trước — port khớp với `evalThamDinh()` trong
  `js/tuvan-so-bo.js`, đã xác nhận bằng 61 golden test.
- **Cụm 2 (hệ thống bắt buộc — QCVN 10:2025/BCA):** đã port
  `backend/app/services/he_thong_bat_buoc.py` (4 hàm:
  `evaluate_bao_chay`/`evaluate_sprinkler`/`evaluate_hong_nuoc`/`evaluate_ngoai_nha`,
  khớp `evalBaoChay`/`evalA3`/`evalSprinkler`/`evalHongNuoc`/`evalNgoaiNha`
  trong JS) + route `/api/he-thong-bat-buoc/evaluate`, xác nhận bằng 145
  golden test.
- Owner quyết định: **giữ nguyên giao diện tính client-side trong giai đoạn
  này** — chưa chuyển frontend sang gọi API cho bất kỳ cụm nào, chưa xoá
  logic JS cũ; backend chỉ đóng vai trò "đối chiếu song song" (golden test),
  chưa phải nguồn duy nhất được frontend gọi tới.
- 2 cụm còn lại (nước, phương tiện) tiếp tục theo đúng hướng này khi được
  yêu cầu — khảo sát, port sang backend có golden test, chưa chuyển
  frontend/xoá JS.

**Công việc**

- Viết API contract cho rule results bằng schema rõ ràng — **cụm thẩm định
  và cụm hệ thống bắt buộc đã có**; 2 cụm còn lại (nước, phương tiện) chưa làm.
- Di chuyển theo từng cụm rule từ `js/tuvan-so-bo.js` vào backend service có
  test; **frontend TẠM THỜI vẫn tính client-side** cho mọi cụm — việc
  "frontend chỉ render API response" hoãn lại tới khi owner xác nhận chuyển đổi.
- Mỗi rule có `rule_set_version`, nguồn, điều kiện đầu vào và test
  dưới/bằng/trên ngưỡng — đã có cho cụm 1 và cụm 2; "ngày hiệu lực" cụ thể
  chưa có (nguồn hiện chỉ trích dẫn tên văn bản chung, vd. "NĐ 105/2025",
  "QCVN 10:2025/BCA"), chỉ mang tính tham khảo thêm khi có, không phải điều
  kiện bắt buộc.
- Chỉ chuyển một cụm mỗi PR: thẩm định -> hệ thống bắt buộc -> nước -> phương tiện.
- Loại bỏ logic JS trùng lặp: **hoãn lại cho mọi cụm**, chỉ làm sau khi owner
  xác nhận chuyển frontend sang gọi API.

**Gate kiểm tra**

- [x] Golden test cho công năng và biên ngưỡng đã chuyển:
      61 test cụm thẩm định (`backend/tests/test_tham_dinh_golden.py`) +
      145 test cụm hệ thống bắt buộc
      (`backend/tests/test_he_thong_bat_buoc_golden.py`), tất cả pass.
- [x] Cảnh báo trách nhiệm chuyên môn thống nhất — hiển thị ở khu vực kết quả
      thẩm định (`js/tuvan-so-bo.js`, phần disclaimer cuối phiếu) và kết quả
      AI đọc bản vẽ (`index.html`, disclaimer tĩnh ngay sau `#aihoResults`).
- [ ] Browser test xác nhận phiếu in/xuất giữ nguyên kết quả trên bộ dữ liệu
      chuẩn — chưa cần thiết ở giai đoạn "đối chiếu song song" (frontend
      chưa đổi hành vi hiển thị); áp dụng khi thật sự chuyển sang gọi API.

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

## Batch 5A — Xác thực email, Bộ hồ sơ và chuyển khoản thủ công

**Mục tiêu:** chuyển mô hình quota "N lượt/ngày" hiện tại sang mô hình
"Bộ hồ sơ" trả trước (credit-based), có xác thực email và nạp thêm bằng
chuyển khoản ngân hàng thủ công — chưa tích hợp cổng thanh toán tự động.

**Chính sách nghiệp vụ (owner quyết định, giữ nguyên khi triển khai)**

- Tài khoản xác thực email lần đầu được đúng **2 Bộ hồ sơ** dùng thử.
- Thay quota theo ngày bằng số dư **"Bộ hồ sơ còn lại"** (bỏ hẳn khái niệm
  hạn mức/ngày hiện tại cho luồng AI đọc bản vẽ).
- Nạp **100.000 VNĐ** được cộng **5 Bộ hồ sơ**, chỉ sau khi admin xác nhận
  đã nhận được chuyển khoản thật.
- Một Bộ hồ sơ = tối đa **5 file bản vẽ** của cùng một công trình/cùng một
  phiên bản, tối đa **7 form MĐC**.
- Mỗi yêu cầu nạp có **mã chuyển khoản riêng** (để đối chiếu); nút "Tôi đã
  chuyển khoản" chỉ chuyển đơn sang trạng thái **chờ xác nhận**, không tự
  động cộng Bộ hồ sơ.
- Chỉ **admin** xem giao dịch ngân hàng thật và bấm xác nhận thủ công mới
  cộng +5 Bộ hồ sơ vào tài khoản.
- Có **ledger/lịch sử** đầy đủ: cấp 2 lượt lúc xác thực email, trừ 1 lượt
  lúc dùng, hoàn lại lượt khi lỗi kỹ thuật (AI/hệ thống lỗi, không phải lỗi
  người dùng), cộng 5 lượt lúc admin xác nhận chuyển khoản.
- Email xác thực dùng **liên kết một lần** (one-time link/token có hạn sử
  dụng) — không gửi mật khẩu qua email trong bất kỳ trường hợp nào.
- **Chưa** tích hợp payOS, VNPAY, webhook hay bất kỳ hình thức tự động đọc
  biến động số dư ngân hàng nào — toàn bộ xác nhận chuyển khoản trong batch
  này là thủ công do admin thực hiện.
- Thông tin tài khoản ngân hàng/mã QR nhận tiền **chỉ cấu hình qua biến môi
  trường** lúc triển khai batch này — không đưa vào source code, docs hay
  git dưới bất kỳ hình thức nào (kể cả ví dụ/placeholder gần giống thật).

**Công việc (khi được duyệt triển khai)**

- Thiết kế schema mới: bảng credit/ledger cho "Bộ hồ sơ" (số dư, lịch sử
  cấp/trừ/hoàn/cộng), bảng yêu cầu nạp tiền (mã chuyển khoản, trạng thái
  chờ/đã xác nhận/từ chối, thời điểm admin xác nhận).
- Xác thực email: sinh token một lần, gửi email, endpoint xác nhận, tự động
  cấp 2 Bộ hồ sơ khi xác thực thành công lần đầu.
- Đổi luồng quota AI đọc bản vẽ: kiểm tra/trừ theo "Bộ hồ sơ còn lại" thay
  vì đếm lượt/ngày; giữ nguyên cơ chế giữ-chỗ nguyên tử đã có ở Batch 1 (áp
  dụng cho đơn vị "Bộ hồ sơ" thay vì "lượt gọi API").
- Giới hạn 1 Bộ hồ sơ: tối đa 5 file bản vẽ/tối đa 7 form MĐC — validate ở
  cả frontend và backend.
- Trang/luồng "Nạp thêm Bộ hồ sơ": tạo yêu cầu nạp với mã riêng, hiển thị
  thông tin chuyển khoản (đọc từ biến môi trường), nút "Tôi đã chuyển khoản"
  chỉ đổi trạng thái sang chờ.
- Trang admin: danh sách yêu cầu nạp đang chờ, nút xác nhận thủ công (cộng
  5 Bộ hồ sơ + ghi ledger), nút từ chối.
- Trang người dùng: xem số dư Bộ hồ sơ còn lại + lịch sử ledger.

**Gate kiểm tra**

- Test: xác thực email cấp đúng 2 Bộ hồ sơ, không cấp lại lần 2 nếu xác
  thực lại.
- Test: dùng hết Bộ hồ sơ → chặn đúng, không cho âm số dư.
- Test: hoàn lượt đúng khi lỗi kỹ thuật, không hoàn khi lỗi do người dùng
  (vd. file sai định dạng).
- Test: chỉ admin mới gọi được endpoint xác nhận chuyển khoản; user thường
  bị chặn (403).
- Test: xác nhận chuyển khoản 2 lần cho cùng 1 yêu cầu không cộng 2 lần
  (idempotent).
- Review: không có thông tin ngân hàng/QR nào xuất hiện trong git diff/log/docs.
- Review: giới hạn 5 file/7 form MĐC được validate ở backend, không chỉ ở
  frontend (client có thể bị bypass).

## Batch 5 — UAT và release readiness

**Mục tiêu:** đưa production (một PostgreSQL production duy nhất —
`pccc-trolynghiepvu-db`, không có staging riêng, xem
`docs/01-target-architecture.md`) qua kiểm thử có kiểm soát trước khi thật sự
mở cho người dùng, và quyết định có cần tăng độ phức tạp (worker/Redis) hay
không.

**Công việc**

- Gắn `DATABASE_URL` vào web service, chạy `flask db upgrade` trên
  `pccc-trolynghiepvu-db` theo đúng `docs/04-migration-runbook.md` (backup
  trước, xác nhận `flask db current` sau) — đóng 4 gate còn treo từ Batch 2.
- Thiết lập monitoring lỗi, structured logging, health/readiness check
  (`/api/health` đã kiểm tra kết nối database thật từ Batch 2).
- Chạy smoke test và UAT theo checklist ngay trên production (vì không có
  staging riêng) — thực hiện ở khung giờ kiểm soát được, trước khi mời
  người dùng thật, và có kế hoạch rollback nhanh nếu phát hiện lỗi; đo
  p50/p95 AI và tỷ lệ lỗi.
- Lập runbook incident: AI provider down, rollback deployment, rollback
  migration (đã có runbook migration cơ bản, bổ sung phần incident khác),
  revoke secret.
- Quyết định có cần Redis/worker theo ngưỡng trong kiến trúc mục tiêu hay
  không (xem `docs/01-target-architecture.md` mục "AI ở giai đoạn đơn giản").

**Gate kiểm tra**

- 4 gate còn treo từ Batch 2 (migration Postgres thật, smoke test, restart
  không mất dữ liệu, review backup/rollback) đã pass.
- Không có lỗi P0/P1 mở.
- Security checklist pass và secret không xuất hiện trong repository/log.
- UAT được người nghiệp vụ ký xác nhận.
- Người sở hữu dự án phê duyệt deploy production bằng văn bản rõ ràng.

## Batch 6 — Tùy chọn: AI worker bất đồng bộ

Chỉ mở khi Batch 5 xác nhận cần thiết. Bổ sung một queue và một Render Background Worker; không thay đổi rule engine hoặc UI ngoài flow trạng thái job.

**Gate kiểm tra:** idempotency, retry, resume sau restart, job timeout, không tạo hai lượt quota/cost cho một job, tải song song giới hạn.
