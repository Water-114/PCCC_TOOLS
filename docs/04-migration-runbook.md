# Runbook migration/rollback (Batch 2)

Áp dụng từ Batch 2: `startCommand` trong `render.yaml` **không còn tự chạy
`flask db upgrade`** lúc web instance khởi động (tránh nhiều instance cùng
chạy migration đồng thời khi scale > 1 instance — xem `docs/01-target-architecture.md`
và `docs/03-quality-release-gates.md`). Từ giờ, migration là một bước thủ công,
tách riêng, chạy **một lần** trước khi mở traffic cho code phụ thuộc schema mới.

## Trước khi migrate lần đầu sang PostgreSQL production

Dự án chỉ dùng một database production duy nhất (`pccc-trolynghiepvu-db`),
không có staging riêng — nên bước này chính là lần chạy thật đầu tiên,
không có môi trường staging để thử trước.

1. Xác nhận đã có backup/snapshot gần nhất của database (Render Postgres có
   backup tự động theo plan — kiểm tra tab "Backups" của database trên
   Dashboard trước khi migrate lần đầu có ý nghĩa, tức là sau khi đã có dữ
   liệu thật).
2. Xác nhận `DATABASE_URL` trên web service đang trỏ đúng database
   `pccc-trolynghiepvu-db` — dán nhầm có thể migrate nhầm database.
3. Chạy migration qua **Render Shell** (Dashboard → chọn web service →
   tab "Shell"), KHÔNG chạy migration bằng cách sửa `startCommand` tạm thời:

   ```bash
   flask db upgrade
   ```

4. Xác nhận thành công:

   ```bash
   flask db current
   ```

   Kết quả phải khớp đúng revision mới nhất trong `backend/migrations/versions/`.
5. Chỉ sau khi bước 3–4 thành công mới deploy/restart code phụ thuộc schema mới.

## Rollback (khi migration mới gây lỗi)

1. Xác định revision muốn quay lại (xem `flask db history` hoặc tên file
   trong `backend/migrations/versions/`).
2. Chạy qua Render Shell:

   ```bash
   flask db downgrade <revision_id_muon_quay_ve>
   ```

3. Với các migration chỉ thêm cột nullable hoặc thêm index (như migration
   `9ba0353a8591` và `7269076b80f2`), downgrade an toàn — không mất dữ liệu
   cột/bảng khác. Với migration xoá cột/bảng trong tương lai, PHẢI có backup
   trước khi downgrade vì downgrade không tự khôi phục dữ liệu đã xoá.
4. Sau khi downgrade, rollback luôn code đang chạy về bản tương thích với
   revision đó (deploy trước đó trên Render — dùng tính năng "Rollback" của
   Render hoặc redeploy commit cũ).

## Đã diễn tập (local, SQLite, không phải production)

- `flask db upgrade` từ revision `9ba0353a8591` lên `7269076b80f2`: thành công.
- `flask db downgrade` về `9ba0353a8591` rồi `flask db upgrade` lại lên
  `7269076b80f2`: thành công, không lỗi.
- **Chưa diễn tập trên PostgreSQL thật** — migration `flask db upgrade` đầu
  tiên trên `pccc-trolynghiepvu-db` (production, không có staging riêng) sẽ
  là lần chạy thật đầu tiên trên Postgres; cần thực hiện đúng theo checklist
  "Trước khi migrate lần đầu" ở trên, có xác nhận rõ ràng của chủ dự án
  trước khi chạy.

## Lỗi cần biết trước

- Vì `startCommand` không còn `flask db upgrade`, nếu deploy service trỏ vào
  một database PostgreSQL **hoàn toàn trống** (chưa migrate lần nào) thì mọi
  API cần database sẽ lỗi (bảng chưa tồn tại). Bắt buộc chạy `flask db upgrade`
  qua Render Shell **trước** lần đầu tiên trỏ `DATABASE_URL` sang Postgres.
