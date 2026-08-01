# Backend tests — Batch 0

Chạy bộ test (không đụng `backend/app.db` thật, không gọi API AI trả phí):

```bash
cd backend
venv/Scripts/pip install -r requirements-dev.txt
venv/Scripts/pytest -v
```

## Phạm vi

- `test_health.py`, `test_auth.py` — happy path + input cơ bản.
- `test_water.py`, `test_tham_dinh.py` — mỗi file có vài test `test_bug_*`
  **ghi nhận baseline** cho các lỗi validation input đã phát hiện (NaN, số âm,
  input không hợp lệ gây 500) — cố ý pass ở trạng thái hiện tại, KHÔNG sửa
  lỗi ở Batch 0. Khi Batch 1 sửa các lỗi này, các test `test_bug_*` tương ứng
  sẽ đổi sang fail — đó là tín hiệu đúng để cập nhật lại test cho hành vi mới.
- `test_migrations.py` — chạy `flask db upgrade` thật trên 1 file SQLite
  trống mới, xác nhận 2 migration hiện có áp dụng sạch.
- `test_mdc_baseline.py` — ghi số dòng tiêu chí của 6 mẫu MĐC hiện có, không
  gọi AI.

## Baseline KHÔNG thể tự động hoá trong bộ test này

Theo đúng ràng buộc "không gọi API AI trả phí trong test tự động"
(`docs/CLAUDE-HANDOFF-PROMPT.md`), các số liệu sau **không có test tự động**
và cần đo thủ công qua Anthropic Console (mục Usage/Cost — xem hướng dẫn đã
gửi cho owner) khi có nhu cầu:

- Thời gian phản hồi thật của Claude cho từng hạng mục (báo cháy/điện PCCC/
  chữa cháy nước).
- Tỷ lệ lỗi API thật (rate limit, timeout, JSON không hợp lệ) trên lưu lượng
  thật.
- Kích thước response thật (input/output token) trên bản vẽ thật.

Ghi lại các số liệu này (khi đo) vào một tài liệu riêng ngoài bộ test, không
gán cứng vào assertion pytest vì chúng phụ thuộc bản vẽ cụ thể và có thể đổi
theo thời gian.
