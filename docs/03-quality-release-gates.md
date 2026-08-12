# Quy tắc kiểm thử, review và release

## Ma trận kiểm thử tối thiểu

| Nhóm | Bắt buộc từ batch | Nội dung |
|---|---:|---|
| Unit test backend | 0 | validation, calculator, rule boundary, quota |
| API integration test | 0 | auth, admin permission, error JSON, database test |
| Security regression | 1 | XSS, CORS, rate limit, upload validation, secret config |
| Migration test | 2 | upgrade database production rỗng (không có staging riêng), rollback đã diễn tập trên local trước |
| Golden rule test | 3 | dưới/bằng/trên ngưỡng và căn cứ pháp lý |
| AI contract test | 4 | malformed JSON, thiếu id, provider lỗi, quota race |
| Browser smoke/UAT | 5 | login, hướng dẫn, tính toán, upload, admin, download MĐC |

## Lệnh kiểm tra mục tiêu

Các lệnh chính xác nằm trong README. Chuẩn kỳ vọng (cập nhật Batch 7A — sau
khi hợp nhất frontend production vào `backend/app/static/` và gỡ MVP
React/Vite `frontend/` khỏi source):

```powershell
cd backend
python -m pytest
flask db upgrade

cd ..
npm run lint   # oxlint backend/app/static/js/
```

Test không được gọi provider AI trả phí mặc định; provider phải được mock.
Không còn bước `npm run build` (không có framework nào build static UI —
`backend/app/static/index.html`/`css/`/`js/` được Flask phục vụ trực tiếp,
không qua bước biên dịch).

## Checklist review sau mỗi batch

1. Scope có đúng một batch đã duyệt không?
2. Có file nào ngoài phạm vi bị đổi không?
3. Test mới có chứng minh bug/rủi ro được sửa không?
4. Có regression ở auth, quota, legal rules, admin hay xuất DOCX không?
5. Có secret, dữ liệu thật, log nhạy cảm hay URL database bị commit không?
6. Có thay đổi ngưỡng/công thức pháp lý nào không — nếu có, đã dẫn đúng nguồn văn bản chưa (công cụ không tự phê duyệt, chỉ cần trích dẫn nguồn rõ ràng)?
7. Migration có rollback tương thích không?
8. AI output lỗi có bị chặn trước khi hiển thị/sinh MĐC không?

## Quy tắc release (một database production duy nhất, không có staging)

- Owner quyết định giữ kiến trúc đơn giản: chỉ một PostgreSQL production
  (`pccc-trolynghiepvu-db`), không có staging riêng — xem
  `docs/01-target-architecture.md`.
- Vì không có staging để thử trước, MỌI migration/thay đổi schema phải diễn
  tập kỹ trên local (SQLite hoặc Postgres tạm) trước, và phải có backup
  production xác nhận gần nhất trước khi chạy migration thật — xem
  `docs/04-migration-runbook.md`.
- Chạy migration một lần theo release runbook, sau backup/restore check;
  không chạy migration tự động trên mọi web instance start.
- Dùng health check `/api/health`, smoke test endpoints và kiểm tra logs
  trước khi mở traffic.
- Giữ deployment trước đó để rollback application. Không rollback migration
  phá hủy dữ liệu nếu chưa có runbook được duyệt.

## Điều kiện cấm deploy production

- Còn lỗi P0/P1 chưa được owner chấp nhận rõ ràng.
- Không có backup database gần nhất hoặc migration chưa được diễn tập trên local.
- Test bắt buộc không chạy/pass.
- Có output demo được trình bày như kết quả AI thật.
- `SECRET_KEY`, API key hoặc database URL xuất hiện trong git diff/log.
- Chưa có phê duyệt rõ ràng bằng câu lệnh `APPROVE DEPLOY PRODUCTION` từ người sở hữu dự án.

## Rà soát hiện trạng checklist trên (cập nhật 2026-08-02, chuẩn bị đóng Batch 5)

Rà từng mục dựa trên bằng chứng cụ thể (đọc source/chạy lệnh thật) khi có
thể; khi không tự kiểm tra được (cấu hình/trạng thái thật trên Render
Dashboard, ngoài tầm với của tôi), ghi rõ nguồn là **xác nhận trực tiếp của
owner**, không phải suy luận từ repo. **Cập nhật 2026-08-02: đã nhận lệnh
`APPROVE DEPLOY PRODUCTION` — 0/6 mục còn chặn deploy** (xem mục 6).

1. **Lỗi P0/P1 chưa được owner chấp nhận** — Không có bug tracker chính thức
   trong repo để đối chiếu tuyệt đối. Trong phiên làm việc gần nhất, đã phát
   hiện và **sửa xong** 2 lỗi thật mức nghiêm trọng cao: (a) luồng xác thực
   email chưa từng được nối vào frontend — mọi tài khoản đăng ký mới bị kẹt
   vĩnh viễn ở 0 Bộ hồ sơ (sửa, test, đã push ở commit `c963edb`); (b) bug
   `auth.js` đọc DOM trước khi phần tử mới được parse xong, làm vỡ UI đăng
   nhập (sửa, test, đã push ở commit `e5981a3`). Không biết P0/P1 nào khác
   đang mở — nhưng đây là đánh giá theo phạm vi đã trực tiếp làm việc, **không
   phải một audit toàn ứng dụng từ đầu**, nên không thể coi mục này là "đã rà
   soát đầy đủ", chỉ là "không có gì đang biết là mở".
2. **Backup database / migration diễn tập local** — PASS, đã cập nhật sau
   xác nhận trực tiếp của owner (2026-08-02): đánh giá trước đó của tôi ("chưa
   gắn `DATABASE_URL`") chỉ dựa trên đọc `render.yaml` trong repo — **sai**,
   vì `DATABASE_URL` production được gắn **thủ công trực tiếp trên Render
   Dashboard** theo đúng chủ đích bảo mật (không commit vào `render.yaml`),
   nên tôi không thể tự thấy được qua git. Owner xác nhận: đã gắn
   `DATABASE_URL` và chạy `flask db upgrade` **thật thành công** trên
   `pccc-trolynghiepvu-db` production cùng ngày, `flask db current` trả về
   đúng revision mới nhất (`4ca63b0c73f2`, head), và `/api/health` trả về
   `database: ok` trên chính production thật (không phải local) — trong lúc
   xử lý một sự cố production ngoài phạm vi các commit của tôi. Migration
   local trước đó (SQLite, upgrade/downgrade/upgrade lại) vẫn đúng như đã ghi
   ở `docs/04-migration-runbook.md`; nay đã có thêm xác nhận migration THẬT
   trên Postgres production.
3. **Test bắt buộc không chạy/pass** — PASS. Vừa chạy lại xác nhận:
   `pytest -q` → 617/617 pass; `npm run lint` → sạch (chỉ còn các cảnh báo cũ
   không liên quan, đã biết từ trước).
4. **Output demo trình bày như kết quả AI thật** — PASS theo đúng thiết kế:
   3 hạng mục (Báo cháy tự động, Chữa cháy bằng nước, Điện PCCC) gọi AI thật;
   các hạng mục còn lại vẫn minh hoạ nhưng được ghi rõ ràng ngay trong UI
   (`index.html`, phần giới thiệu tab AIHO: "...các hạng mục còn lại vẫn
   đang minh hoạ, chưa đọc bản vẽ thật") — không trình bày như kết quả thật.
5. **`SECRET_KEY`/API key/database URL trong git diff/log** — PASS. Đã quét
   lại **toàn bộ lịch sử git** (`git log --all -p`) tìm pattern API key thật
   (`sk-ant-api03-...`, `AIzaSy...`) và giá trị gán trực tiếp cho
   `SECRET_KEY`/`ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`SMTP_PASSWORD`/chuỗi
   kết nối Postgres có mật khẩu thật — 0 kết quả thật, chỉ có đúng 1 dòng ví
   dụ minh hoạ rõ ràng là giả trong `.env.example`
   (`postgres://user:password@dpg-xxxxxxxx-...`). Không có file `.env`/
   credentials nào từng được commit trong lịch sử.
6. **Phê duyệt `APPROVE DEPLOY PRODUCTION`** — **PASS**. Nhận đúng câu lệnh
   này từ người sở hữu dự án ngày 2026-08-02.

**Kết luận cập nhật: 0/6 mục còn chặn deploy.** Lưu ý: mục 1 (P0/P1) vẫn chỉ
là "không biết gì đang mở trong phạm vi đã làm việc", không phải một audit
toàn ứng dụng — owner chấp nhận rủi ro này khi phê duyệt. Phê duyệt deploy
**không đồng nghĩa** các việc còn lại của Batch 5 (monitoring/alerting tự
động, UAT hình thức đầy đủ có chữ ký) đã xong — xem `docs/02-implementation-batches.md`
mục Batch 5.

Xem thêm [docs/05-incident-runbook.md](05-incident-runbook.md) (mới, Batch 5)
cho runbook incident bổ sung (AI provider down, rollback deployment, revoke
secret) — phần "Lập runbook incident" của Batch 5.

## Dữ liệu và trách nhiệm chuyên môn

- Không tải bản vẽ/hồ sơ khách hàng thật lên staging hay môi trường AI test nếu chưa có quyền xử lý dữ liệu.
- Dùng fixture đã ẩn danh cho automation.
- Công cụ là trợ lý/hỗ trợ tham khảo, không có quyền thẩm định/phê duyệt hồ
  sơ — mọi kết quả rule và AI phải kèm đúng cảnh báo thống nhất (xem
  `docs/01-target-architecture.md` mục "AI ở giai đoạn đơn giản" và
  `docs/02-implementation-batches.md` mục Batch 3): *"Kết quả từ công cụ chỉ
  mang tính hỗ trợ tham khảo trong quá trình rà soát hồ sơ. Kết luận, thẩm
  định và trách nhiệm chuyên môn cuối cùng thuộc về kỹ sư PCCC."* Kỹ sư PCCC
  là người dùng cuối chịu trách nhiệm phê duyệt hồ sơ thật để sử dụng chính
  thức — không phải một bước duyệt nội bộ trước khi merge code.
