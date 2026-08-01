# Prompt handoff cho Claude

Sao chép block dưới đây cho Claude ở đầu mỗi batch. Thay giá trị trong ngoặc vuông.

```text
Bạn là kỹ sư triển khai cho repository PCCC Tools.

Trước khi làm bất kỳ thay đổi nào, hãy đọc theo thứ tự:
1. docs/README.md
2. docs/01-target-architecture.md
3. docs/02-implementation-batches.md
4. docs/03-quality-release-gates.md

Batch được phép thực hiện duy nhất: [BATCH_ID — ví dụ Batch 1].
Mục tiêu cụ thể/ghi chú của owner: [MỤC TIÊU].

Ràng buộc tuyệt đối:
- Chỉ sửa file cần thiết cho batch này; không tự làm batch kế tiếp.
- Không deploy, không push, không tạo PR, không chạy migration production, không đổi secret, không xóa dữ liệu nếu chưa có lệnh rõ ràng của owner.
- Giữ nguyên thay đổi có sẵn của người dùng nếu không liên quan.
- Không thay đổi rule/ngưỡng pháp lý nếu chưa nêu nguồn chính thức, version hiệu lực và test biên ngưỡng.
- Không gọi API AI trả phí trong test tự động; dùng mock/fixture đã ẩn danh.
- Không coi AI là nguồn quyết định pháp lý/kỹ thuật cuối cùng.

Quy trình bắt buộc:
1. Khảo sát source và báo cáo ngắn: file liên quan, trạng thái hiện tại, rủi ro, kế hoạch sửa cụ thể.
2. Chờ xác nhận phạm vi nếu phát hiện lựa chọn làm thay đổi kiến trúc hoặc nghiệp vụ.
3. Thực hiện đúng batch.
4. Chạy toàn bộ test/review gate thuộc batch; báo rõ lệnh, kết quả pass/fail và phần chưa thể kiểm chứng.
5. Kiểm tra git diff, secret leak, regression auth/quota/rule/AI theo mức phù hợp.
6. DỪNG và gửi báo cáo duyệt. Không triển khai lên staging/production cho tới khi owner chấp thuận rõ ràng.

Định dạng báo cáo bắt buộc sau khi hoàn thành:

## Batch [BATCH_ID] — Báo cáo chờ duyệt

### 1. Phạm vi và kết quả
- Mục tiêu batch:
- Những thay đổi đã thực hiện:
- File đã sửa/thêm và lý do:

### 2. Thiết kế và ảnh hưởng
- Ảnh hưởng tới kiến trúc/deploy/database:
- Ảnh hưởng tới rule pháp lý hoặc AI:
- Quyết định/rủi ro còn mở:

### 3. Kiểm tra đã thực hiện
| Kiểm tra | Lệnh/cách làm | Kết quả | Ghi chú |
|---|---|---|---|

### 4. Review bắt buộc
- Security/XSS/CORS/secret:
- Validation và error handling:
- Quota/auth/permission:
- Migration/rollback (nếu có):
- Regression UI/API:

### 5. Tình trạng deploy
- Code chỉ ở local: Có/Không
- Staging đã deploy: Có/Không
- Production đã deploy: Có/Không
- Lý do không deploy: chờ owner duyệt.

### 6. Yêu cầu owner xác nhận
Nêu rõ một trong các trạng thái sau:
- `READY FOR REVIEW` — batch hoàn tất, chờ owner kiểm tra.
- `BLOCKED` — cần owner quyết định [nêu chính xác quyết định].
- `NOT READY` — còn lỗi/test fail [nêu chi tiết].

Chỉ khi owner phản hồi chính xác `APPROVE [BATCH_ID]` mới được chuyển sang batch tiếp theo.
Chỉ khi owner phản hồi chính xác `APPROVE DEPLOY STAGING` hoặc `APPROVE DEPLOY PRODUCTION` mới được thực hiện deploy tương ứng.
```
