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

Các lệnh chính xác được thêm vào README khi Batch 0 hoàn thành. Chuẩn kỳ vọng:

```powershell
cd backend
python -m pytest
flask db upgrade

cd ../frontend
npm run lint
npm run build
```

Root static UI cần có thêm script kiểm tra cú pháp tất cả file trong `js/`. Test không được gọi provider AI trả phí mặc định; provider phải được mock.

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
