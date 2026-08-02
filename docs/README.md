# Kế hoạch cải thiện PCCC Tools

Đây là bộ tài liệu triển khai cho dự án. Mục tiêu là nâng chất lượng và độ an toàn của sản phẩm mà vẫn giữ kiến trúc vận hành đơn giản:

- Một **Render Web Service** phục vụ cả trang web và Flask API.
- Một **PostgreSQL managed**; ưu tiên Render PostgreSQL để giảm số nhà cung cấp.
- Không dùng Vercel, Supabase, Redis hay worker riêng ở giai đoạn đầu, trừ khi một batch được phê duyệt bổ sung.

## Đọc theo thứ tự

1. [Kiến trúc mục tiêu](01-target-architecture.md)
2. [Các batch triển khai](02-implementation-batches.md)
3. [Quy tắc kiểm thử, review và deploy](03-quality-release-gates.md)
4. [Prompt handoff cho Claude](CLAUDE-HANDOFF-PROMPT.md)
5. [Runbook migration/rollback (từ Batch 2)](04-migration-runbook.md)
6. [Runbook incident — AI provider down, rollback deployment, revoke secret (từ Batch 5)](05-incident-runbook.md)

## Phạm vi hiện tại

Sản phẩm production hiện tại là `index.html` cùng `css/` và `js/`, được Flask phục vụ ở production. `frontend/` là MVP React/Vite tách rời, chưa phải giao diện production. Không được thêm tính năng song song vào cả hai frontend.

Các quy tắc PCCC và kết quả AI có độ nhạy cảm chuyên môn cao. AI chỉ hỗ trợ đọc/trích xuất/tổng hợp; kết luận pháp lý hoặc kỹ thuật phải do rule-based code có nguồn, version và kiểm thử xác định.

## Quy tắc bắt buộc khi triển khai

- Chỉ thực hiện **một batch đã được duyệt** tại một thời điểm.
- Không đổi ngưỡng pháp lý khi chưa có nguồn văn bản chính thức, version hiệu lực và test biên ngưỡng.
- Không deploy production, chạy migration production, đổi secret, xóa dữ liệu, push hoặc tạo PR nếu chưa có lệnh rõ ràng của người duyệt.
- Không thay đổi các file ngoài phạm vi batch; giữ nguyên thay đổi chưa commit của người dùng.
- Mọi thay đổi phải có test tương ứng hoặc ghi rõ lý do chưa thể tự động hóa.
- Sau batch, dừng ở review gate và dùng prompt handoff; không tự làm tiếp batch kế tiếp.
