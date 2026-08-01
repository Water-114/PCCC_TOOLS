# Quy tắc kiểm thử, review và release

## Ma trận kiểm thử tối thiểu

| Nhóm | Bắt buộc từ batch | Nội dung |
|---|---:|---|
| Unit test backend | 0 | validation, calculator, rule boundary, quota |
| API integration test | 0 | auth, admin permission, error JSON, database test |
| Security regression | 1 | XSS, CORS, rate limit, upload validation, secret config |
| Migration test | 2 | upgrade database staging rỗng, rollback đã diễn tập |
| Golden rule test | 3 | dưới/bằng/trên ngưỡng và căn cứ pháp lý |
| AI contract test | 4 | malformed JSON, thiếu id, provider lỗi, quota race |
| Browser smoke/UAT | 5 | login, tư vấn, tính toán, upload, admin, download MĐC |

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
6. Có thay đổi pháp lý nào cần kỹ sư PCCC duyệt không?
7. Migration có rollback tương thích không?
8. AI output lỗi có bị chặn trước khi hiển thị/sinh MĐC không?

## Quy tắc deploy staging

- Staging và production dùng database khác nhau, secret khác nhau, domain khác nhau.
- Chạy migration một lần theo release runbook, sau backup/restore check; không chạy migration tự động trên mọi web instance start.
- Dùng health check `/api/health`, smoke test endpoints và kiểm tra logs trước khi mở traffic.
- Giữ deployment trước đó để rollback application. Không rollback migration phá hủy dữ liệu nếu chưa có runbook được duyệt.

## Điều kiện cấm deploy production

- Còn lỗi P0/P1 chưa được owner chấp nhận rõ ràng.
- Không có backup database gần nhất hoặc migration chưa được diễn tập trên staging.
- Test bắt buộc không chạy/pass.
- Có output demo được trình bày như kết quả AI thật.
- `SECRET_KEY`, API key hoặc database URL xuất hiện trong git diff/log.
- Chưa có phê duyệt rõ ràng bằng câu lệnh `APPROVE DEPLOY PRODUCTION` từ người sở hữu dự án.

## Dữ liệu và trách nhiệm chuyên môn

- Không tải bản vẽ/hồ sơ khách hàng thật lên staging hay môi trường AI test nếu chưa có quyền xử lý dữ liệu.
- Dùng fixture đã ẩn danh cho automation.
- Kết quả rule và AI phải có disclaimer; chỉ kỹ sư PCCC có thẩm quyền mới phê duyệt hồ sơ để sử dụng chính thức.
