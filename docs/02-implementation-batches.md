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

## Batch 3 — Canonical API và rule engine — **HOÀN THÀNH**

**Mục tiêu:** một nguồn sự thật cho kết luận rule-based, có truy vết pháp lý.

**Tổng kết (cả 4 cụm đã port, ở chế độ "đối chiếu song song"):**

| Cụm | Service | Route | Golden test | Validation/route test |
|---|---|---|---:|---:|
| 1. Thẩm định | `tham_dinh.py` | `/api/tham-dinh/evaluate` | 61 | 7 |
| 2. Hệ thống bắt buộc | `he_thong_bat_buoc.py` | `/api/he-thong-bat-buoc/evaluate` | 145 | 20 |
| 3. Nước chữa cháy | `nuoc_chua_chay.py` | `/api/nuoc-chua-chay/evaluate` | 64 tra bảng + 6 end-to-end = 70 | 16 |
| 4. Phương tiện | `phuong_tien.py` | `/api/phuong-tien/evaluate` | 52 | 19 |
| **Tổng Batch 3** | | | **328** | **62** |

**Tổng cộng 390 test riêng cho Batch 3** (328 golden/end-to-end + 62 validation route), nằm trong tổng 430 test của toàn bộ backend — `pytest -q` xác nhận **430/430 pass**, không hồi quy.

**Xác nhận "đối chiếu song song" còn nguyên vẹn:**
- `grep` toàn bộ `js/*.js` và `index.html` cho 4 endpoint mới (`api/tham-dinh`, `api/he-thong-bat-buoc`, `api/nuoc-chua-chay`, `api/phuong-tien`) → **0 kết quả** — production chưa gọi bất kỳ route nào trong số này.
- Toàn bộ 12 hàm rule gốc trong `js/tuvan-so-bo.js` (`evalThamDinh`, `evalBaoChay`, `evalSprinkler`, `evalHongNuoc`, `evalNgoaiNha`, `evalNuoc`, `evalPhaDo`, `evalMatNa`, `evalCoGioi`, `evalLoa`, `evalBinh`, `evalDen`) **vẫn còn nguyên**, chưa xoá hàm nào.
- Duy nhất 1 thay đổi hành vi JS production trong cả batch: sửa lỗi mapping `hXepM`→`hXepM2` ở cụm 3 (theo yêu cầu owner, chỉ đổi nguồn dữ liệu đầu vào, không đổi công thức/ngưỡng).

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
- **Cụm 3 (nước chữa cháy sơ bộ — QCVN 06, TCVN 7336:2021, TCVN 14496:2025):**
  đã port `backend/app/services/nuoc_chua_chay.py` (toàn bộ bảng tra + hàm:
  `traBang11`/`traBang12`/`traBang8`/`traSprinkler`/`heSoPsi14496`/
  `tinh14496_1tang`/`tinh14496_nhieutang`/`traBang1_14496`/`evalNuoc` trong
  JS) + route `/api/nuoc-chua-chay/evaluate` — tự gọi 3 hàm cụm 2
  (sprinkler/họng nước/ngoài nhà) để lấy đầu vào, đúng luồng `render()` gốc
  gọi `evalNuoc(d, sp, hn, nn)`. Xác nhận bằng 64 golden test cho các hàm
  tra bảng nội bộ + 6 test end-to-end đối chiếu Vtn/Vnn/Vtd/Vtong/bơm sơ bộ
  tính tay độc lập theo công thức nguồn.
  - **Đã sửa lỗi mapping dữ liệu** (owner yêu cầu sau khi review lần 1,
    không phải "giữ nguyên hành vi cũ"): chế độ "nhiều tầng đầu phun"
    (Điều 6, `tinh14496_nhieutang`) từng đọc nhầm field `hXepM` (field của
    chế độ "1 tầng đầu phun", Điều 5) thay vì `hXepM2` (field riêng mà form
    thực sự thu thập cho chế độ nhiều tầng). Đã sửa đồng bộ ở cả
    `js/tuvan-so-bo.js` (production) và `backend/app/services/nuoc_chua_chay.py`
    — chỉ đổi nguồn dữ liệu đầu vào, không đổi công thức/ngưỡng/kết luận/căn
    cứ quy chuẩn nào (Qi=A×B×n×i, iD theo ngưỡng h≤16m/&gt;16m, Qd=iD×Sd,
    Qs=Qi+Qd giữ nguyên 100%). Có 3 regression test riêng xác nhận: (1) để
    trống hXepM, chỉ nhập hXepM2 vẫn tính được; (2) hXepM và hXepM2 khác giá
    trị thì kết quả theo đúng hXepM2; (3) ngưỡng hXepM2 ≤16m/&gt;16m quyết
    định đúng cường độ phun dưới mái — cộng thêm 1 test end-to-end qua
    `evaluate_nuoc()` xác nhận lỗi không còn xuất hiện khi tính trọn luồng.
  - Phát hiện thêm (không phải bug mapping field, không sửa): nếu nhóm nguy
    cơ cháy (nhomNC) trống khi sprinkler bắt
    buộc phải tính, bản JS gốc sẽ lỗi runtime (truy cập thuộc tính của
    undefined) thay vì báo lỗi rõ ràng — bản port trả về kết quả lỗi mềm
    (không phải ngưỡng/công thức, chỉ là xử lý input thiếu để tránh 500 ở
    route, đúng yêu cầu validation của batch này).
- **Cụm 4 (phương tiện & hạng mục khác — Phụ lục D/E/F/G QCVN 10:2025/BCA,
  TCVN 7435-1:2004, TCVN 13456:2022):** đã port
  `backend/app/services/phuong_tien.py` (6 hàm:
  `evaluate_pha_do`/`evaluate_mat_na`/`evaluate_co_gioi`/`evaluate_loa`/
  `evaluate_binh`/`evaluate_den`, khớp `evalPhaDo`/`evalMatNa`/`evalCoGioi`/
  `evalLoa`/`evalBinh`/`evalDen` trong JS) + route `/api/phuong-tien/evaluate`.
  Xác nhận bằng 52 golden test + 19 test validation route (bổ sung 2 trường
  mới `extLevel` enum và `pplFloor` số nguyên không âm tuỳ chọn).
  - Cụm này khác 3 cụm trước: 2 hàm (`evaluate_binh`, `evaluate_den`) LUÔN
    trả `result="yes"` — không phải quyết định ngưỡng mà tính/liệt kê NỘI
    DUNG cụ thể (số lượng bình chữa cháy theo công thức
    `n=max(ceil(areaFloor/dt), min)`; danh sách vị trí lắp đèn sự cố + ghi
    chú có điều kiện). Golden test cho 2 hàm này kiểm tra đúng công thức/
    ranh giới số học và đúng nội dung xuất hiện theo điều kiện, không phải
    so sánh yes/no như các cụm khác.
  - `evaluate_loa` có 5 điều kiện (TT1, TT2, TT3, TT4, TT6) **độc lập, có
    thể đạt đồng thời** — đã port đúng cơ chế gom nhiều "hit" thay vì
    if/elif loại trừ nhau như các cụm trước.
- Owner quyết định: **giữ nguyên giao diện tính client-side trong giai đoạn
  này** — chưa chuyển frontend sang gọi API cho bất kỳ cụm nào, chưa xoá
  logic JS cũ; backend chỉ đóng vai trò "đối chiếu song song" (golden test),
  chưa phải nguồn duy nhất được frontend gọi tới.
- **Cả 4 cụm của Batch 3 đã port xong** (thẩm định, hệ thống bắt buộc,
  nước chữa cháy, phương tiện) — chưa có cụm nào được frontend gọi tới.

**Công việc**

- Viết API contract cho rule results bằng schema rõ ràng — **cả 4 cụm đã có**.
- Di chuyển theo từng cụm rule từ `js/tuvan-so-bo.js` vào backend service có
  test; **frontend TẠM THỜI vẫn tính client-side** cho mọi cụm — việc
  "frontend chỉ render API response" hoãn lại tới khi owner xác nhận chuyển đổi.
- Mỗi rule có `rule_set_version`, nguồn, điều kiện đầu vào và test
  dưới/bằng/trên ngưỡng — đã có cho cả 4 cụm; "ngày hiệu lực" cụ thể
  chưa có (nguồn hiện chỉ trích dẫn tên văn bản chung, vd. "NĐ 105/2025",
  "QCVN 10:2025/BCA", "TCVN 14496:2025"), chỉ mang tính tham khảo thêm khi
  có, không phải điều kiện bắt buộc.
- Chỉ chuyển một cụm mỗi PR: thẩm định -> hệ thống bắt buộc -> nước -> phương tiện — **đã xong cả 4**.
- Loại bỏ logic JS trùng lặp: **hoãn lại cho mọi cụm**, chỉ làm sau khi owner
  xác nhận chuyển frontend sang gọi API.

**Gate kiểm tra (đúng phạm vi Batch 3 đã thực hiện — "đối chiếu song song",
không bao gồm chuyển frontend)**

- [x] Golden test cho công năng và biên ngưỡng đã chuyển: **328 golden/
      end-to-end test** (61 cụm thẩm định + 145 cụm hệ thống bắt buộc + 64
      tra bảng và 6 end-to-end cụm nước chữa cháy, gồm 4 test regression cho
      lỗi mapping hXepM/hXepM2 đã sửa + 52 cụm phương tiện), cộng **62 test
      validation route** (7+20+16+19) — tổng **390 test riêng cho Batch 3**,
      tất cả pass trong 430/430 test toàn backend.
- [x] Cảnh báo trách nhiệm chuyên môn thống nhất — hiển thị ở khu vực kết quả
      thẩm định (`js/tuvan-so-bo.js`, phần disclaimer cuối phiếu) và kết quả
      AI đọc bản vẽ (`index.html`, disclaimer tĩnh ngay sau `#aihoResults`).
- [x] Xác nhận "đối chiếu song song": production chưa gọi endpoint nào
      trong 4 endpoint mới (`grep` toàn bộ `js/*.js`/`index.html` → 0 kết
      quả); toàn bộ 12 hàm rule gốc trong `js/tuvan-so-bo.js` vẫn còn nguyên,
      chưa xoá hàm nào.
- [ ] *(N/A cho Batch 3 như đã thực hiện)* Browser test xác nhận phiếu
      in/xuất giữ nguyên kết quả trên bộ dữ liệu chuẩn — gate này chỉ áp
      dụng khi có quyết định **chuyển frontend sang gọi API** (chưa xảy ra,
      chưa được lên lịch cho batch nào) — không phải điều kiện để coi
      Batch 3 là hoàn thành theo phạm vi "đối chiếu song song" đã thống nhất
      với owner trong suốt batch này.

**Việc CHƯA làm (chủ động ngoài phạm vi Batch 3, cần quyết định riêng của
owner ở batch/thời điểm khác):**
- Chuyển `js/tuvan-so-bo.js` sang gọi 4 API mới thay vì tự tính client-side.
- Xoá logic JS trùng lặp (chỉ làm được sau khi đã chuyển frontend và có
  browser test xác nhận kết quả không đổi).
- Bổ sung "ngày hiệu lực" cụ thể cho từng `rule_set_version` (hiện chỉ có
  tên văn bản, không phải điều kiện bắt buộc theo quyết định owner).

## Batch 4 — AI reliability và tính đúng đắn đầu ra — **HOÀN THÀNH**

> Toàn bộ phần thuộc trách nhiệm code/kỹ thuật đã xong. Còn đúng 1 gate **KHÔNG
> phải việc code** — thuộc trách nhiệm nghiệp vụ của owner/kỹ sư PCCC (review
> thủ công 1 bộ bản vẽ thật đã ẩn danh) — xem chi tiết ở mục Gate kiểm tra và
> "Việc CHƯA làm" cuối phần này. Không có việc code nào còn treo.

**Mục tiêu:** AI là trợ lý có kiểm soát, không tạo MĐC sai cấu trúc.

**Tổng kết (2 sub-bước, chia nhỏ theo yêu cầu owner để duyệt từng phần):**

| Sub-bước | Nội dung | Test mới |
|---|---|---:|
| 1 | Pydantic schema, retry-repair schema, `so_hieu_ban_ve`, xuất kiến nghị `.docx` | 35 |
| 2 | Gemini SDK migration, timeout/retry/circuit-breaker, logging, audit demo-vs-AI-thật | 44 |
| **Tổng Batch 4** | | **79** |

**79 test riêng cho Batch 4**, nằm trong tổng **508 test toàn bộ backend** — `pytest -q` xác nhận **508/508 pass**, không hồi quy. `npm run lint` không phát sinh cảnh báo mới.

**Trạng thái hiện tại (từng việc trong mục "Công việc" gốc):**

- **Pydantic model cho từng loại đọc bản vẽ** — `backend/app/services/ai_schema.py` (`ItemResult`, `KienNghi`, `ReaderResult`, `BaoChayReaderResult`).
- **Validate đủ tiêu chí, id chính xác (khớp tuyệt đối — không thiếu, không thừa), enum `dat/chua_dat/chua_the_hien`, giới hạn 3000 ký tự nội dung** — `validate_reader_result()`; cả 2 con số (3000 ký tự, id khớp tuyệt đối) là lựa chọn của tôi, **đã được owner duyệt**.
- **Retry repair tối đa 1 lần khi invalid; sau đó trả lỗi rõ ràng, không sinh MĐC nửa vời** — `ai_reader_common.read_and_validate_drawing_json()`.
- **Ghi provider, model, prompt template version, thời gian, usage** — `ai_reader_common._log_ai_call()`, 1 dòng log/lần gọi AI (kể cả lần repair). Dùng logger chuẩn `logging.getLogger(__name__)`, KHÔNG dùng `current_app.logger` — đã xác nhận bằng thử nghiệm thực tế rằng `current_app` ném `RuntimeError` khi gọi từ trong `ThreadPoolExecutor` (bối cảnh Flask app-context là thread-local, không tự có trong worker thread do executor tạo), mà `ccnuoc_reader` luôn gọi 3 lần AI song song qua `ThreadPoolExecutor` — nếu dùng `current_app.logger` sẽ làm SẬP tính năng chữa cháy nước khi lên production. "Prompt template version" = 12 ký tự đầu sha256 nội dung prompt gốc, tự đổi khi prompt đổi, không cần nhớ bump tay. **"Cost" không ghi được** — cả Claude lẫn Gemini đều không trả giá tiền trong response, chỉ có token usage (đã ghi `input_tokens`/`output_tokens`) — đúng tinh thần "nếu có" của yêu cầu gốc.
- **Timeout/retry backoff/circuit-breaker tối thiểu** — `backend/app/providers/resilience.py`: circuit breaker dùng chung theo tên provider, mở sau 3 lỗi hạ tầng liên tiếp, nghỉ 60s rồi tự "thăm dò" lại. Claude: timeout 870s (giữ nguyên, đã có từ trước) + `max_retries=1` tường minh (SDK `anthropic` tự nhận diện lỗi mạng/429/5xx để retry). Gemini: **timeout 300s + 1 lần retry mạng — hoàn toàn MỚI** (trước đây không có timeout riêng, chỉ dựa vào gunicorn cắt cứng ở 900s).
  - **Quyết định cần bạn biết:** timeout Gemini (300s) thấp hơn Claude (870s) có chủ đích, để giữ biên độ an toàn khi cộng dồn với retry mạng + retry-repair schema (sub-bước 1). Trường hợp xấu nhất về lý thuyết (mọi lớp retry đều rơi đúng lúc timeout tối đa, cực kỳ hiếm) vẫn có thể vượt 900s của gunicorn: Claude ước tính tới ~3480s (2 lần đọc × 2 lần thử mỗi lần × 870s), Gemini ~1200s (2×2×300s). Đây là đánh đổi có chủ đích giữa "đủ thời gian cho hồ sơ thật phức tạp nhất (~150s đo thực tế)" và "giới hạn worst-case" — CHƯA giải quyết triệt để 100% vì retry mạng (sub-bước 2) và retry-repair schema (sub-bước 1) là 2 lớp độc lập, cộng dồn được. Nếu muốn siết chặt hơn (vd. bỏ retry mạng khi 1 lần đã hết đúng timeout, chỉ retry cho lỗi phản hồi nhanh), báo tôi làm thêm — chưa tự quyết định thu hẹp vì ngoài phạm vi "tối thiểu" bạn yêu cầu.
- **Bỏ output demo khỏi luồng AI thật / gắn nhãn không thể nhầm lẫn** — rà toàn bộ `js/ai-doc-ho-so.js`: `renderResultTable()` trước đây dùng 1 ternary dùng chung fallback, khiến 1 hạng mục "AI thật" (có trong `REAL_CATEGORIES`) có thể ngầm hiện nội dung minh hoạ (`SLOT_MOCK`) dưới đúng nhãn "AI thật" nếu `realResults[slot]` vì lý do gì đó chưa kịp ghi nhận — đã tách hẳn 2 nhánh, hạng mục AI thật không còn đường nào chạm tới `SLOT_MOCK` nữa (kể cả khi thiếu kết quả, hiện rõ "Chưa có kết quả phân tích thật" thay vì minh hoạ). Xoá luôn 3 entry demo chết (baochay/ccnuoc/dienpccc) trong `SLOT_MOCK` — nay không còn cách nào đọc tới. `collectRealSections()`/`collectFailedRealSlots()` (dùng cho khối MĐC/kiến nghị) đã rà lại — vốn AN TOÀN từ trước (không có fallback sang mock), không cần sửa.
- **Chuyển Gemini SDK legacy sang SDK được nhà cung cấp hỗ trợ hiện tại** — `google-generativeai` (Google đã khai tử: dừng hỗ trợ 2025-08-31, deprecated hẳn 2025-11-30) → `google-genai` (SDK chính thức hiện tại, bản 2.16.0). Viết lại toàn bộ `gemini_provider.py`; hành vi output không đổi (vẫn trả JSON text để `ai_reader_common` parse) — xác nhận bằng 14 test regression (mock `google.genai.Client` hoàn toàn, không gọi Gemini thật).

**Gate kiểm tra**

- [x] Fixture output malformed/missing id bị chặn — `test_ai_schema.py` (10 test).
- [x] Test MĐC: đúng số dòng, không tự điền "Đạt" khi model trả enum sai — validate thất bại (kể cả enum sai) → `AIReaderError` rõ ràng, KHÔNG build MĐC — `test_ai_reader_retry_repair.py`.
- [x] Test không có API key — `test_aiho_read_routes.py::test_no_api_key_returns_503_with_clean_message`.
- [x] Test provider timeout — `test_aiho_read_routes.py::test_provider_timeout_returns_502_without_leaking_internals` + `test_circuit_breaker_open_returns_502_with_breaker_message`.
- [x] Test quota exhausted — `test_aiho_read_routes.py::test_quota_exhausted_returns_429_without_calling_ai_again`.
- [x] Test partial result chữa cháy nước — `test_aiho_read_routes.py::test_ccnuoc_partial_result_when_one_form_fails` + `test_ccnuoc_partial_result_mdc_files_flag_failed_form`.
- [ ] **[VIỆC CỦA OWNER — KHÔNG PHẢI VIỆC CODE]** Review bằng ít nhất một bộ bản vẽ đã được ẩn danh và được kỹ sư PCCC đối chiếu thủ công — đây là bước nghiệp vụ đòi hỏi bản vẽ thật + đánh giá chuyên môn của kỹ sư PCCC, không thể tự động hoá hay thực hiện bằng code. Toàn bộ hạ tầng kỹ thuật (schema, validate, retry, timeout, logging, test) đã sẵn sàng để owner/kỹ sư PCCC thực hiện review này bất kỳ lúc nào có bản vẽ phù hợp — không phải việc đang thiếu code, chỉ đang chờ owner thực hiện.

**Việc CHƯA làm (không phải code — chờ owner quyết định/thực hiện riêng):**
- Gate "kỹ sư PCCC đối chiếu thủ công" nêu trên — việc nghiệp vụ của owner, không phải khoảng trống kỹ thuật.
- Rủi ro cộng dồn timeout worst-case (retry mạng × retry-repair schema) nêu trên — đã giới hạn thực tế nhưng chưa airtight tuyệt đối ở trường hợp cực xấu lý thuyết.
- Chưa gỡ package `google-generativeai` khỏi venv cục bộ (chỉ đổi `requirements.txt`) — không ảnh hưởng gì (không còn file nào import), chỉ là dọn dẹp không bắt buộc.

## Batch 5A — Xác thực email, Bộ hồ sơ và chuyển khoản thủ công — **HOÀN THÀNH (5/5 sub-bước)**

**Mục tiêu:** chuyển mô hình quota "N lượt/ngày" hiện tại sang mô hình
"Bộ hồ sơ" trả trước (credit-based), có xác thực email và nạp thêm bằng
chuyển khoản ngân hàng thủ công — chưa tích hợp cổng thanh toán tự động.

**Tiến độ — Sub-bước 1 (schema + xác thực email cấp Bộ hồ sơ, KHÔNG đổi luồng
quota AI đọc bản vẽ đang chạy thật):**

- **Schema mới** (`backend/app/models.py`): `User.email_verified_at` (null =
  chưa xác thực — kể cả tài khoản đăng ký trước Batch 5A, KHÔNG có migration
  backfill nào set cột này), `CreditLedger` (ledger đầy đủ — số dư luôn tính từ
  `SUM(delta)`, không có cột số dư rời rạc để tránh 2 nguồn lệch nhau;
  `backend/app/services/credits.py` khai báo sẵn cả 5 loại giao dịch
  `CREDIT_REASON_*` dù sub-bước này chỉ tạo ra được loại
  `email_verification`), `EmailVerificationToken` (chỉ lưu sha256 hash của
  token, không lưu bản rõ), `TopupRequest` (**tạo schema trước, chưa route nào
  dùng tới** — đúng phạm vi sub-bước 1).
- **Xác thực email** (`backend/app/services/email_verification.py` +
  `backend/app/services/mailer.py` + route `POST /api/auth/send-verification-email`
  (cần đăng nhập, 409 nếu đã xác thực) và `POST /api/auth/verify-email` (public
  — token tự chứng minh danh tính, không cần đăng nhập)): token ngẫu nhiên
  (`secrets.token_urlsafe`), hạn 24 giờ, dùng 1 lần (đánh dấu `used_at` ngay
  khi tìm thấy hợp lệ, cùng transaction với việc cấp credit). Cấp đúng 2 Bộ hồ
  sơ khi `email_verified_at` đang `None` lúc xác thực thành công; nếu đã có
  giá trị từ trước thì KHÔNG cấp lại — chặn kép 2 lớp (route trả 409 khi bấm
  gửi lại nếu đã xác thực, và bản thân hàm xác nhận cũng tự kiểm tra
  `email_verified_at` trước khi cấp, không phụ thuộc riêng lớp route).
  Gửi lại email xác thực sẽ huỷ token cũ CHƯA dùng của cùng tài khoản (lựa
  chọn của tôi, chưa được bạn xác nhận riêng — nếu muốn giữ nhiều link cùng
  sống song song thì báo tôi bỏ dòng huỷ này).
- **Gửi email** (`backend/app/services/mailer.py`): SMTP thuần (`smtplib`),
  cấu hình hoàn toàn qua biến môi trường mới (`SMTP_HOST`/`SMTP_PORT`/
  `SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_FROM_EMAIL`, đã thêm vào
  `backend/.env.example` với giá trị RỖNG, không có ví dụ gần giống thật nào).
  Nếu `SMTP_HOST` rỗng: KHÔNG gửi thật, chỉ log cảnh báo — để đăng ký/xác thực
  vẫn chạy được lúc dev/test chưa có SMTP thật.
- **Migration Alembic** `33a95593a87d_add_email_verification_credit_ledger_...py`
  — đã chạy thử thật upgrade → downgrade → upgrade lại trên SQLite local (file
  tạm, không đụng `backend/app.db` thật), xác nhận sạch cả 2 chiều; khoá lại
  bằng test tự động `test_batch_5a_migration_downgrades_and_reupgrades_cleanly`.
- **62 test mới** (8 email_verification service + 5 credits service + 3 mailer
  + 9 route xác thực + 1 migration round-trip mới, cộng các test hiện có được
  giữ nguyên) — `pytest -q` xác nhận **534/534 test backend pass**, không hồi
  quy. `npm run lint` không đổi (không sửa file JS nào ở sub-bước này).
- **Lỗi thật phát hiện và sửa trong lúc làm:** so sánh `expires_at` (đọc từ DB)
  với thời điểm hiện tại bị `TypeError: can't compare offset-naive and
  offset-aware datetimes` trên SQLite — SQLite không giữ được `tzinfo` qua
  `DateTime(timezone=True)` dù lúc ghi luôn là giờ UTC có tzinfo (Postgres
  production giữ đúng, chỉ SQLite dev/test bị mất) — đã thêm hàm chuẩn hoá
  `_as_aware_utc()` coi datetime "naive" đọc lại là UTC trước khi so sánh; có
  test riêng khoá lại hành vi hết hạn để không tái diễn.
- **KHÔNG đổi** (đúng phạm vi sub-bước 1, theo yêu cầu): luồng quota AI đọc
  bản vẽ vẫn 100% theo "lượt/ngày" cũ đang chạy thật; chưa có trang nạp tiền;
  chưa có trang admin xác nhận; chưa đổi giới hạn 5 file/7 form MĐC; chưa đổi
  thông báo UI "Chú ý trước khi sử dụng"; `register()` KHÔNG tự động gửi email
  xác thực (người dùng phải tự gọi `send-verification-email` — quyết định của
  tôi để tránh đổi hành vi `register()` hiện có, có thể đổi lại nếu bạn muốn
  tự động gửi ngay lúc đăng ký).

**Tiến độ — Sub-bước 2 (đổi luồng AI đọc bản vẽ sang "Bộ hồ sơ" qua khái niệm
"phiên", theo đúng thiết kế đã trình bày và được duyệt trước khi code):**

- **Thiết kế đã duyệt trước khi code** (5 điểm, xem hội thoại): 1 lần bấm
  "Bắt đầu phân tích" = 1 phiên, tự đóng ngay sau khi các hạng mục xong, không
  cộng dồn qua nhiều lượt bấm khác nhau; double-click/2 tab → trả về phiên
  đang mở (idempotent); timeout phiên bị bỏ quên = 60 phút; đổi hiển thị quota
  ở 2 vị trí + thêm dòng phụ giải thích 5 file/7 form; giới hạn 5 file/7 form
  là validate phòng ngừa cho tương lai (UI hiện tại đúng 3 hạng mục cố định,
  không bao giờ chạm ngưỡng thật).
- **Schema mới**: `HoSoSession` (`backend/app/models.py`) — `status`
  (`open`/`closed_used`/`closed_refunded`), `files_used`/`forms_used`/
  `success_count`, `ledger_entry_id` (trỏ đúng dòng `-1` lúc mở phiên).
  Migration `4ca63b0c73f2_add_ho_so_session...py`, đã chạy thật upgrade →
  downgrade → upgrade lại trên SQLite local (file tạm), khoá lại bằng test
  `test_batch_5a_ho_so_session_migration_downgrades_and_reupgrades_cleanly`.
- **`backend/app/services/ho_so_session.py`** (logic nghiệp vụ, tái dùng ý
  tưởng "giữ chỗ nguyên tử" của Batch 1 nhưng ở cấp phiên): `open_session()`
  trừ ngay 1 Bộ hồ sơ (ghi `CreditLedger` delta=-1) cùng transaction với tạo
  phiên; idempotent nếu đang có phiên `open` chưa hết hạn; tự lazy-đóng (dùng
  hoặc hoàn tuỳ `success_count`) phiên cũ nếu đã quá 60 phút trước khi mở
  phiên mới. `reserve_slot()` kiểm tra + tăng `files_used`/`forms_used` TRƯỚC
  khi gọi AI (chặn sớm nếu vượt 5/7, không tốn 1 lần gọi AI cho yêu cầu chắc
  chắn bị từ chối) — KHÔNG rollback nếu AI sau đó lỗi kỹ thuật (giữ đơn giản,
  UI hiện tại không có đường nào "thử lại đúng hạng mục trong cùng phiên").
  `close_session()` giữ nguyên nếu `success_count > 0`, hoàn `+1` nếu bằng 0;
  idempotent (gọi lại với phiên đã đóng không lỗi, không hoàn 2 lần).
- **`backend/app/routes/aiho.py`**: `_handle_read_request()` bỏ hẳn
  `_reserve_usage_slot`/`_finalize_usage`/`UsageLog` (Batch 1) khỏi luồng đọc
  bản vẽ — nhận `session_id` (form field), xác nhận phiên thuộc đúng user +
  đang mở + còn hạn, kiểm tra giới hạn qua `reserve_slot()` rồi mới gọi AI.
  Response mỗi hạng mục nay có `ho_so: {session_id, files_used, forms_used,
  max_files, max_forms}` thay cho `quota` cũ. 2 route mới: `POST
  /api/aiho/session/open` (trả 429 kèm `bo_ho_so_con_lai` nếu hết Bộ hồ sơ) và
  `POST /api/aiho/session/close`. **`/api/ai/comment` (tính năng khác, quota
  riêng `AI_COMMENT_API_NAME`) hoàn toàn KHÔNG bị đụng tới.**
- **`_user_payload()` (`routes/auth.py`)**: đổi field `quota` (lượt/ngày cũ)
  thành `bo_ho_so: {con_lai}` — dùng chung cho response `register`/`login`/`me`.
- **Frontend**: `js/ai-doc-ho-so.js` — `cta` click handler nay `await` gọi
  `/session/open` (giữ `session_id` trong biến JS cục bộ của lượt chạy đó)
  TRƯỚC KHI bắn 3 fetch hạng mục song song (mỗi fetch thêm `session_id` vào
  `FormData`), gọi `/session/close` ngay trong `finishUp()` sau khi tất cả đã
  settle. Bỏ nhánh `429` cũ trong xử lý per-hạng-mục (không còn route nào trả
  429 nữa — chỉ `/session/open` trả 429). `updateCta()` + `js/auth.js` (dòng
  trạng thái đăng nhập trên nav) đổi hiển thị "còn X/Y lượt đọc bản vẽ hôm
  nay" → "còn N Bộ hồ sơ (mỗi Bộ hồ sơ tối đa 5 file bản vẽ, 7 form MĐC)".
  `A.setUserQuota`/`updateQuotaDisplay` đổi tên thành `A.setUserBoHoSo`/
  `updateBoHoSoDisplay` cho đúng ngữ nghĩa mới.
- **Test**: 17 test mới (`test_ho_so_session_service.py`, unit test trực tiếp
  cho `ho_so_session.py`) + viết lại toàn bộ `test_aiho_read_routes.py` cho
  luồng phiên (8 → 15 test) + viết lại `test_quota_concurrency.py` cho
  `open_session()` (1 → 2 test, thay cho `_reserve_usage_slot` đã gỡ) + 1 test
  migration mới — tổng bộ test tăng từ 534 lên **560/560 pass**, chạy lại 3
  lần liên tiếp không phát sinh flaky. `npm run lint` không phát sinh cảnh
  báo mới.
- **2 lỗi thật phát hiện và sửa trong lúc làm** (cả 2 đều từ test concurrency
  mới, KHÔNG phải lỗi trong code nghiệp vụ):
  1. `test_quota_concurrency.py` (bản viết lại) thỉnh thoảng báo
     `DetachedInstanceError`/`database is locked` ngẫu nhiên khi chạy 20 luồng
     đồng thời. Nguyên nhân: Flask-SQLAlchemy 3.x scope session theo `id()`
     của app-context — tạo/huỷ nhiều app context dồn dập ở nhiều luồng mà
     không giữ tham chiếu sống có thể khiến Python tái sử dụng cùng 1 địa chỉ
     bộ nhớ cho 2 app context KHÁC NHAU ở 2 luồng (id() trùng do garbage
     collect), khiến 2 luồng vô tình dùng chung 1 scoped session. Xác nhận
     bằng thực nghiệm (không giữ tham chiếu: lỗi ~1/5 lần; giữ tham chiếu:
     sạch 10/10 lần) — đã sửa TRONG TEST (giữ tham chiếu app context sống
     suốt vòng đời luồng), không phải lỗi ở `ho_so_session.py`.
  2. Nhân tiện phát hiện `_build_engine_options()` cho SQLite chưa từng đặt
     `connect_args={"timeout": ...}` — mặc định driver chỉ chờ ngắn trước khi
     báo "database is locked" khi nhiều request cùng xếp hàng qua `BEGIN
     IMMEDIATE` (Batch 1). Đã thêm `timeout: 30` giây — cải thiện chịu tải
     đồng thời thật, không chỉ riêng cho test. `test_config.py` cập nhật theo.
- **KHÔNG đổi** (đúng phạm vi sub-bước 2): chưa có trang nạp tiền/admin xác
  nhận; chưa đổi giới hạn form MĐC ở nơi khác; chưa đổi thông báo UI "Chú ý
  trước khi sử dụng"; trang quản trị (`quan-tri.js`/`admin.py`) hoàn toàn
  KHÔNG bị đụng — vẫn dùng `daily_quota`/`UsageLog` cũ y nguyên, NHƯNG cột
  "used_today" của nó cho AIHO trên trang admin sẽ **không còn tăng nữa** kể
  từ sub-bước này (vì `aiho.py` không còn ghi `UsageLog` cho luồng đọc bản vẽ)
  — số liệu cũ vẫn xem được, chỉ đóng băng, không phải lỗi. **Cần bạn biết**
  nếu trang admin đó vẫn đang được dùng để theo dõi mức sử dụng AIHO thực tế.

**Tiến độ — Sub-bước 3 (route nạp tiền + xác nhận/từ chối admin — CHỈ backend,
chưa có UI/HTML thật):**

- **State machine 3 trạng thái** (đã sửa lại theo đúng yêu cầu, sau khi bạn
  chỉnh 1 bản nháp đầu gộp sai thành 1 bước):
  `cho_chuyen_khoan` (vừa tạo, nháp — **CHƯA vào hàng đợi admin**) →
  `cho_xac_nhan` (user tự bấm "Tôi đã chuyển khoản") →
  `da_xac_nhan` | `tu_choi` (admin quyết định, trạng thái cuối). `status` đổi
  default sang `'cho_chuyen_khoan'` — chỉ là default Python-side của
  SQLAlchemy (`default=`, không phải `server_default`), không cần migration
  riêng cho việc này.
- **Đổi tên cột trung lập**: `TopupRequest.confirmed_at`/`confirmed_by_admin_id`
  → `reviewed_at`/`reviewed_by_admin_id` (dùng chung cho cả xác nhận LẪN từ
  chối, không thiên về "confirmed"). Vì bảng chưa deploy/chưa có dữ liệu thật,
  đã sửa THẲNG vào migration `33a95593a87d` hiện có (không tạo migration mới)
  — đã chạy lại `flask db migrate` để xác nhận **không còn lệch (drift)** giữa
  `models.py` và migration sau khi đổi tên, và chạy upgrade thật trên SQLite
  tạm để xác nhận đúng 2 cột mới tồn tại, 2 cột cũ không còn.
- **Biến môi trường ngân hàng** (`BANK_ACCOUNT_NUMBER`/`BANK_ACCOUNT_NAME`/
  `BANK_NAME`/`BANK_QR_URL`, thêm vào `config.py` + `.env.example` — **giá trị
  RỖNG**, không có ví dụ/placeholder gần giống thật nào). Đã rà toàn bộ diff
  bằng grep tên các ngân hàng phổ biến — xác nhận sạch, không lộ thông tin nào.
- **`backend/app/services/topup.py`**: `_generate_reference_code()` sinh mã
  dạng `BHS-XXXXXXXX` (bỏ ký tự dễ nhầm 0/O/1/I/L, kiểm tra unique trước khi
  dùng). `bank_transfer_info()` raise `BankInfoNotConfigured` rõ ràng nếu
  thiếu bất kỳ biến bắt buộc nào (số TK/tên chủ TK/ngân hàng — QR là tuỳ
  chọn) — KHÔNG trả chuỗi rỗng ra UI như thể đó là thông tin thật.
  `create_topup_request()` tạo với trạng thái `cho_chuyen_khoan`.
  `confirm_transfer(request_id, user_id)` — hàm MỚI, chỉ chính chủ yêu cầu gọi
  được (khác user hoặc không tồn tại đều coi là "không tìm thấy" — không lộ
  sự tồn tại của yêu cầu người khác), chuyển sang `cho_xac_nhan`, KHÔNG cộng
  gì. `confirm_topup_request()`/`reject_topup_request()` giờ CHỈ hợp lệ khi
  đang `cho_xac_nhan` — cả `cho_chuyen_khoan` (user chưa xác nhận đã chuyển
  khoản) lẫn trạng thái cuối kia đều bị chặn rõ ràng; cả 2 vẫn idempotent khi
  gọi lại đúng trạng thái đích (không ghi ledger thêm, không cộng/đảo 2 lần).
- **Route user** (`backend/app/routes/topup.py`, blueprint mới
  `/api/topup/*`): `POST /request` (cần đăng nhập, giới hạn 10/giờ, tạo
  `cho_chuyen_khoan`), `POST /<id>/confirm-transfer` (nút "Tôi đã chuyển
  khoản" — route RIÊNG theo đúng lựa chọn mục 2, chỉ đổi trạng thái, không
  cộng gì), `GET /ledger` (số dư + tối đa 200 dòng lịch sử ledger gần nhất,
  mới nhất trước).
- **Route admin** (thêm vào `routes/admin.py` — dùng đúng `@admin_required`
  có sẵn): `GET /topup-requests` (mặc định chỉ hiện `cho_xac_nhan` — đơn còn
  `cho_chuyen_khoan` sẽ KHÔNG xuất hiện; xem tất cả kể cả nháp qua
  `?status=all`), `POST /topup-requests/<id>/confirm` (cộng đúng
  `credits_to_grant` — hiện luôn là 5 — ghi `CreditLedger` reason=
  `topup_confirmed`), `POST /topup-requests/<id>/reject`.
- **Đăng ký blueprint mới** trong `app/__init__.py`, kèm thêm `/api/topup/*`
  vào danh sách CORS mở rộng cho dev local (cùng nhóm với aiho/auth/admin/
  feedback — sót bước này thì gọi từ frontend dev local sẽ bị CORS chặn).
- **48 test** (đã viết lại toàn bộ 3 file test cho khớp state machine 3 trạng
  thái + tên cột mới, cộng test mới cho `confirm_transfer` và cho đúng yêu
  cầu "đơn `cho_chuyen_khoan` không hiện trong danh sách admin"):
  `test_topup_service.py` (21, unit trực tiếp) + `test_topup_routes.py` (13,
  route user, gồm cả `confirm-transfer`) + `test_admin_topup_routes.py` (12,
  route admin, gồm 403 cho user thường, 400 khi thao tác sai trạng thái, và
  test riêng xác nhận nháp không lọt vào danh sách mặc định lẫn `?status=all`
  vẫn thấy đủ). `pytest -q` xác nhận **603/603 test backend pass** (từ 560),
  chạy lại 3 lần liên tiếp không phát sinh flaky. `npm run lint` không đổi.
- **1 lỗi thật phát hiện khi viết test (không phải lỗi nghiệp vụ)**: 3 test
  route ban đầu bị `sqlite3.OperationalError: cannot start a transaction
  within a transaction` — nguyên nhân do chính tôi viết dư 1 lớp
  `with app.app_context():` lồng bên trong test, trong khi fixture `app`
  (conftest.py) đã tự mở sẵn 1 app context bao trọn cả hàm test — lồng thêm
  1 lớp nữa khiến tầng "BEGIN IMMEDIATE" (Batch 1) bị gọi 2 lần trên cùng 1
  transaction. Đã sửa (bỏ lớp `with` dư) — lỗi ở cách viết test, không phải
  ở `services/topup.py`.
- **KHÔNG làm** (đúng phạm vi sub-bước 3): chưa có UI/HTML thật cho trang nạp
  tiền và trang admin (chỉ route backend); chưa đổi thông báo "Chú ý trước
  khi sử dụng"; chưa làm feedback bonus (5 góp ý hoàn thành +1 lượt hướng
  dẫn) — 3 việc này đều nằm ngoài phạm vi sub-bước này theo đúng yêu cầu.

**Tiến độ — Sub-bước 4 (UI thật cho luồng "Bộ hồ sơ" — chỉ sửa root
`index.html`/`js/*.js`, KHÔNG đụng `frontend/` vì đó là MVP đóng băng):**

- **Khu vực "Bộ hồ sơ" trong tab "AI kiểm tra hồ sơ"** (`index.html` — section
  mới `#topupSection`, đặt ngay đầu tab, trước "BƯỚC 1"): số dư hiện tại, nút
  "Nạp thêm Bộ hồ sơ", nút "Xem lịch sử". Logic trong `js/ai-doc-ho-so.js`
  (cùng file đã có sẵn `getToken`/`BACKEND_BASE`/`currentUser`, không tạo file
  JS mới để tránh khai báo trùng các biến dùng chung này).
- **Đúng 2 bước theo state machine backend** — nút "Tôi đã chuyển khoản" CHỈ
  xuất hiện SAU khi `POST /api/topup/request` đã tạo yêu cầu thành công (hiện
  cùng lúc với mã giao dịch + thông tin ngân hàng lấy nguyên văn từ response,
  KHÔNG hardcode giá trị nào trong code): tạo yêu cầu (`cho_chuyen_khoan`) →
  bấm nút riêng gọi `POST /api/topup/<id>/confirm-transfer` (`cho_xac_nhan`)
  → card cập nhật thành "Đã ghi nhận — đang chờ admin đối chiếu...".
- **Lịch sử ledger**: nút "Xem lịch sử" gọi `GET /api/topup/ledger`, hiện
  bảng (thời gian/loại/thay đổi/số dư sau/ghi chú, `reason` dịch sang tiếng
  Việt qua 1 bảng ánh xạ cố định), luôn tải lại mới mỗi lần mở (không cache)
  để không hiện dữ liệu cũ sau khi admin vừa xác nhận ở nơi khác.
- **Trang admin** (`index.html` — section mới trong `#adminDashboard`,
  `js/quan-tri.js`): bảng `GET /api/admin/topup-requests` (dùng nguyên default
  `cho_xac_nhan` — đúng "danh sách đang chờ"), nút Xác nhận/Từ chối mỗi dòng.
  Bấm nút nào **khoá cả 2 nút trong dòng đó ngay lập tức** trước khi gọi API
  (tránh double-click gọi lại — backend đã idempotent nhưng UI vẫn khoá rõ
  ràng theo đúng yêu cầu), rồi tải lại toàn bộ dashboard sau khi xong (dòng
  biến mất khỏi danh sách vì không còn khớp filter mặc định).
- **Cập nhật nội dung "Chú ý trước khi sử dụng"** đúng chính sách thật: 2 Bộ
  hồ sơ miễn phí khi xác thực email, nạp 100.000đ được thêm 5 Bộ hồ sơ (xác
  nhận thủ công). Nhân tiện sửa thêm 2 chỗ chữ cũ khác cũng nhắc tới hạn mức
  "lượt/ngày" đã lỗi thời (mô tả đầu trang tab AIHO, và câu giới thiệu trong
  modal đăng nhập) — không nằm trong 1 câu yêu cầu cụ thể nhưng cùng loại
  chữ sai chính sách, để lại sẽ mâu thuẫn với nội dung vừa sửa.
- **Đã tự bấm thử luồng thật trên trình duyệt** (không chỉ báo cáo bằng chữ)
  — dựng Flask thật trên 1 SQLite tạm riêng (KHÔNG đụng `backend/app.db`
  thật), cấu hình biến môi trường ngân hàng bằng giá trị test rõ ràng giả
  (`...-TEST`/`TEST DEMO`, chỉ tồn tại trong biến môi trường phiên chạy thử,
  không ghi vào bất kỳ file nào), dùng Playwright (cài tạm qua
  `npm install --no-save`, gỡ lại sau khi xong — không đổi `package.json`)
  điều khiển Chromium thật đi hết luồng: đăng ký user mới → số dư 0 → tạo yêu
  cầu nạp (hiện đúng mã giao dịch + thông tin ngân hàng test) → bấm "Tôi đã
  chuyển khoản" → đăng nhập admin → thấy đúng yêu cầu trong danh sách chờ →
  bấm Xác nhận → dòng biến mất khỏi danh sách chờ → đăng nhập lại user gốc →
  số dư hiện đúng **5** → xem lịch sử thấy đúng dòng "Nạp tiền được xác nhận
  +5". Không có lỗi console trong suốt quá trình. Đã dọn sạch: tắt server
  test, xoá DB tạm, gỡ Playwright — không có gì sót lại ngoài đúng các file
  `index.html`/`js/ai-doc-ho-so.js`/`js/quan-tri.js` đã sửa.
- **1 hạn chế nhỏ đã biết, không phải lỗi**: card "đang chờ admin xác nhận"
  ở phía user không tự làm mới khi admin xác nhận ở tab/máy khác trong lúc
  đang mở — chỉ cập nhật đúng khi có hành động mới (bấm lại "Xem lịch sử",
  chuyển tab rồi quay lại). Số dư ở đầu trang (nav) và bảng lịch sử vẫn luôn
  đúng/mới nhất vì lấy trực tiếp từ `/api/auth/me`/`/api/topup/ledger` — chỉ
  riêng cái card đó giữ nguyên nội dung lúc hiện ra, không polling.
- **KHÔNG làm** (đúng phạm vi sub-bước 4): không đổi `backend/`; không đụng
  `frontend/` (MVP đóng băng); chưa làm feedback bonus (5 góp ý +1 lượt).

**Tiến độ — Sub-bước 5 (feedback bonus — 5 góp ý hoàn thành +1 lượt hướng dẫn,
sub-bước cuối cùng của Batch 5A):**

- **Khảo sát trước khi code, đúng yêu cầu dừng lại nếu chưa rõ**: đọc
  `routes/feedback.py` + `js/ai-doc-ho-so.js` xác nhận nút "GÓP Ý" bật sau
  `finishUp()` ở CẢ nhánh AI thật lẫn nhánh demo thuần (không mở phiên nào),
  và payload gửi lên `/api/feedback` không mang `session_id` nào — nghĩa là
  góp ý hiện tại KHÔNG gắn cứng được với đúng 1 `HoSoSession` cụ thể. Đây là
  điểm chưa đủ rõ để tự quyết — đã dừng lại hỏi qua 3 phương án; bạn chọn
  **"Giới hạn theo số phiên thật đã dùng"**: số góp ý "hoàn thành" =
  `min(tổng góp ý feature='aiho_bo_ho_so' của user, tổng HoSoSession
  status='closed_used' của user)` — không cần thêm cột/migration, không cần
  sửa frontend để gửi `session_id`.
- **`backend/app/services/feedback_bonus.py`** (module mới, đúng pattern
  "route mỏng, logic ở services" của `credits.py`/`ho_so_session.py`):
  `maybe_grant_feedback_bonus(user_id)` — tính `eligible = min(total_feedback,
  total_real_sessions)`, số mốc đáng lẽ đã đạt = `eligible // 5`, so với số
  lần đã thực sự cấp thưởng (đếm trực tiếp từ `CreditLedger
  reason=feedback_bonus` — nguồn sự thật duy nhất, không lưu "lần kiểm tra
  trước" ở đâu khác) — cấp thêm 1 Bộ hồ sơ đúng khi số mốc đáng lẽ đạt vượt số
  đã cấp. Cách tính lại từ đầu mỗi lần (thay vì so before/after) để không bỏ
  sót mốc nếu `total_real_sessions` tăng lên giữa 2 lần góp ý mà không có sự
  kiện nào xảy ra đúng lúc vượt mốc — lỗi tôi tự phát hiện ở bản nháp đầu
  trước khi viết code, không phải bug đã xảy ra thật.
- **`routes/feedback.py`**: sau khi lưu `Feedback`, gọi
  `maybe_grant_feedback_bonus()` CHỈ khi đã đăng nhập (`user` khác None) VÀ
  đúng `feature='aiho_bo_ho_so'` (nhãn cũ như `aiho_baochay` không tính — chỉ
  nhãn này được frontend hiện tại gửi lên, xác nhận bằng grep). Response thêm
  field `bonus_granted` (bool) để frontend biết hiện câu chữ nào.
- **Câu chữ chính thức** (đã chốt sẵn từ trước, dùng nguyên văn):
  - `index.html` — thêm dòng tĩnh trong `#feedbackModal`, ngay dưới câu hỏi
    đánh giá: *"Góp ý cho 05 Bộ hồ sơ hoàn thành để nhận thêm 01 lượt hướng
    dẫn cho 01 Bộ hồ sơ."* (luôn hiện, không điều kiện — lời mời chung).
  - `js/ai-doc-ho-so.js` — `feedbackSubmitBtn` handler đọc `bonus_granted` từ
    response JSON: nếu `true`, banner xác nhận (`showFeedbackConfirm`) hiện
    đúng câu *"Anh/chị đã hoàn thành 05 góp ý. Hệ thống đã cộng thêm 01 lượt
    hướng dẫn cho 01 Bộ hồ sơ vào tài khoản của anh/chị."* thay cho câu cảm ơn
    mặc định, đồng thời gọi `A.refreshMe()` để số dư Bộ hồ sơ trên nav/section
    cập nhật ngay không cần tải lại trang.
- **17 test mới** (`test_feedback_bonus_service.py` — 9 test gọi thẳng
  `maybe_grant_feedback_bonus()`: đúng mốc 5 mới cộng, không cộng lặp cho góp
  ý thứ 6/7, đúng mốc 10 cộng lần 2, bị giới hạn bởi số phiên thật khi ít hơn
  số góp ý và ngược lại, luồng demo thuần (0 phiên thật) không bao giờ đủ
  điều kiện, nhãn `feature` khác không được tính; `test_feedback_bonus_routes.py`
  — 4 test qua HTTP xác nhận response `bonus_granted` đúng ở từng góp ý 1-5,
  không cộng lặp ở góp ý 6, góp ý ẩn danh không lỗi và không bao giờ cộng).
  `pytest -q` xác nhận **615/615 test backend pass** (từ 603), không hồi quy.
  `npm run lint` không phát sinh cảnh báo mới (các warning `no-unused-vars`
  hiện có trong `utils.js`/`quan-tri.js`/`tuvan-so-bo.js` có từ trước, không
  liên quan tới thay đổi sub-bước này).
- **KHÔNG làm** (đúng phạm vi sub-bước 5, và đây là mảnh cuối của Batch 5A):
  không thêm cột/migration mới; không sửa frontend để gửi `session_id` kèm
  góp ý (theo đúng phương án đã chọn); không đổi luồng góp ý ẩn danh (vẫn nhận
  bình thường, chỉ không bao giờ được tính vào thưởng).

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
- Góp ý đủ **5 Bộ hồ sơ đã hoàn thành** được cộng thêm **1 lượt hướng dẫn
  cho 1 Bộ hồ sơ**. Câu chữ chính thức (dùng khi triển khai thật ở batch này):
  - Lời mời góp ý: *"Góp ý cho 05 Bộ hồ sơ hoàn thành để nhận thêm 01 lượt
    hướng dẫn cho 01 Bộ hồ sơ."*
  - Khi đủ điều kiện: *"Anh/chị đã hoàn thành 05 góp ý. Hệ thống đã cộng
    thêm 01 lượt hướng dẫn cho 01 Bộ hồ sơ vào tài khoản của anh/chị."*
  **Đã triển khai đủ** ở sub-bước 5 (xem "Tiến độ — Sub-bước 5" phía trên) —
  cơ chế đếm góp ý hoàn thành + cộng lượt thật trên server đã chạy, câu chữ
  đã hiện đúng chỗ trong luồng góp ý.

**Công việc (khi được duyệt triển khai)**

- [x] Thiết kế schema mới: bảng credit/ledger cho "Bộ hồ sơ" (số dư, lịch sử
  cấp/trừ/hoàn/cộng), bảng yêu cầu nạp tiền (mã chuyển khoản, trạng thái
  chờ/đã xác nhận/từ chối, thời điểm admin xác nhận) — **sub-bước 1**, xem
  chi tiết ở "Tiến độ" phía trên. Bảng yêu cầu nạp tiền mới có schema, CHƯA
  có route dùng tới.
- [x] Xác thực email: sinh token một lần, gửi email, endpoint xác nhận, tự động
  cấp 2 Bộ hồ sơ khi xác thực thành công lần đầu — **sub-bước 1**.
- [x] Đổi luồng quota AI đọc bản vẽ: kiểm tra/trừ theo "Bộ hồ sơ còn lại" thay
  vì đếm lượt/ngày; giữ nguyên cơ chế giữ-chỗ nguyên tử đã có ở Batch 1 (áp
  dụng cho đơn vị "Bộ hồ sơ" — qua khái niệm "phiên" gộp nhiều lần gọi AI —
  thay vì "lượt gọi API") — **sub-bước 2**.
- [x] Giới hạn 1 Bộ hồ sơ: tối đa 5 file bản vẽ/tối đa 7 form MĐC — validate ở
  backend (chặn thật, không thể bypass) — **sub-bước 2**. Chưa có validate
  riêng ở frontend (xem giải thích ở gate kiểm tra bên dưới — UI hiện tại
  không thể chạm ngưỡng này nên chưa cần chặn sớm phía client).
- [x] Luồng "Nạp thêm Bộ hồ sơ", đủ cả backend (sub-bước 3) lẫn UI thật
  (sub-bước 4): tạo yêu cầu nạp với mã riêng (trạng thái nháp
  `cho_chuyen_khoan`), hiển thị thông tin chuyển khoản (đọc từ biến môi
  trường, không hardcode), nút riêng "Tôi đã chuyển khoản" (`confirm_transfer`,
  chuyển sang `cho_xac_nhan`, lúc này mới vào hàng đợi admin) — đúng 2 bước
  như policy gốc, đã tự bấm thử trên trình duyệt thật (xem "Tiến độ — Sub-bước
  4").
- [x] Route + trang admin: danh sách yêu cầu nạp đang chờ, xác nhận thủ công
  (cộng 5 Bộ hồ sơ + ghi ledger), từ chối — **sub-bước 3 (route) + sub-bước 4
  (UI trong tab Quản trị)**, nút khoá ngay lúc bấm tránh double-click.
- [x] Trang xem số dư Bộ hồ sơ còn lại + lịch sử ledger — **sub-bước 3
  (route) + sub-bước 4 (UI trong tab AI kiểm tra hồ sơ)**.
- [x] Feedback bonus: đủ 5 góp ý hoàn thành (giới hạn theo số phiên Bộ hồ sơ
  thật đã dùng) cộng thêm 1 Bộ hồ sơ, hiện đúng 2 câu chữ chính thức ở luồng
  góp ý — **sub-bước 5**.

**Gate kiểm tra**

- [x] Test: xác thực email cấp đúng 2 Bộ hồ sơ, không cấp lại lần 2 nếu xác
  thực lại — **sub-bước 1**: `test_email_verification_service.py` +
  `test_auth_email_verification_routes.py` (17 test), cộng test riêng cho
  token hết hạn/token dùng 1 lần/tài khoản cũ chưa xác thực (không nằm trong
  danh sách gate gốc nhưng thuộc yêu cầu cụ thể của sub-bước 1).
- [x] Test: dùng hết Bộ hồ sơ → chặn đúng, không cho âm số dư — **sub-bước 2**:
  `test_open_session_raises_insufficient_credits_when_balance_zero` +
  `test_concurrent_session_open_when_zero_balance_never_grants_any` (kể cả
  dưới tải đồng thời).
- [x] Test: hoàn lượt đúng khi lỗi kỹ thuật — **sub-bước 2**:
  `test_close_session_with_no_success_refunds` +
  `test_closing_session_with_zero_successes_refunds_credit`. **Diễn giải cần
  bạn biết**: ở cấp phiên (khác cấp từng lần gọi AI của policy gốc), quy tắc
  thực tế là "hoàn nếu phiên có 0 lần đọc thành công" — KHÔNG phân biệt lý do
  cụ thể (lỗi kỹ thuật hay lỗi định dạng file người dùng), vì nếu chưa từng
  gọi AI thành công thì chưa phát sinh chi phí thật nào, hợp lý để hoàn dù
  nguyên nhân là gì. Nếu bạn muốn phân biệt chặt hơn (vd. lỗi định dạng file
  của người dùng thì KHÔNG hoàn dù toàn phiên thất bại), báo tôi làm thêm.
- [x] Test: chỉ admin mới gọi được endpoint xác nhận chuyển khoản; user thường
  bị chặn (403) — **sub-bước 3**: `test_confirm_requires_admin` +
  `test_reject_requires_admin` + `test_list_topup_requests_requires_admin`
  (dùng đúng `@admin_required` có sẵn từ Batch 2, không tự viết cơ chế mới).
- [x] Test: xác nhận chuyển khoản 2 lần cho cùng 1 yêu cầu không cộng 2 lần
  (idempotent) — **sub-bước 3**: `test_confirm_twice_does_not_grant_twice` +
  `test_admin_confirm_twice_does_not_grant_twice`. Cộng thêm (ngoài gate gốc,
  hợp lý cần khoá lại): từ chối 1 yêu cầu đã xác nhận / xác nhận 1 yêu cầu đã
  từ chối đều bị chặn rõ ràng (không tự đảo ngược ledger).
- [x] Test: đúng góp ý thứ 5 (Bộ hồ sơ đã hoàn thành) mới cộng +1 lượt hướng dẫn,
  không cộng lặp lại cho góp ý thứ 6, 7... trước khi đủ chu kỳ 5 tiếp theo —
  **sub-bước 5**: `test_bonus_granted_at_exactly_5`,
  `test_no_double_grant_for_feedback_6_and_7`, `test_second_milestone_at_10`
  (`test_feedback_bonus_service.py`) + xác nhận lại qua HTTP thật ở
  `test_feedback_bonus_routes.py`.
- [x] Review: không có thông tin ngân hàng/QR nào xuất hiện trong git diff/log/docs
  — **sub-bước 3**: đã grep toàn bộ diff theo tên các ngân hàng phổ biến,
  xác nhận sạch; `.env.example`/`config.py` chỉ khai tên 4 biến
  `BANK_ACCOUNT_NUMBER`/`BANK_ACCOUNT_NAME`/`BANK_NAME`/`BANK_QR_URL`, giá
  trị rỗng.
- [x] Review: giới hạn 5 file/7 form MĐC được validate ở backend, không chỉ ở
  frontend — **sub-bước 2**: `ho_so_session.reserve_slot()` (backend, chặn
  thật, không thể bypass qua client) + `test_file_cap_exceeded_returns_400`/
  `test_form_cap_exceeded_returns_400`. Frontend hiện KHÔNG có validate riêng
  cho 2 giới hạn này (chỉ hiện thông báo lỗi trả về từ backend nếu vượt) — vì
  UI hiện tại đúng 3 hạng mục cố định không bao giờ chạm ngưỡng thật (xem
  điểm 5 thiết kế đã duyệt), nên chưa cần chặn sớm phía client cho trường hợp
  không thể xảy ra; sẽ thêm validate frontend thật khi có hạng mục mới khiến
  ngưỡng này chạm được trong luồng UI bình thường.

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
