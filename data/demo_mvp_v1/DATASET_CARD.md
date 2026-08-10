# Clinical Review Copilot - MVP Demo Dataset

## Cảnh báo

**DỮ LIỆU GIẢ LẬP PHỤC VỤ DEMO - KHÔNG PHẢI HỒ SƠ Y TẾ THẬT**

## Phiên bản

- Dataset: `demo_mvp_v1`
- Sinh tại: `2026-08-10T12:00:00+07:00`
- Generator: `scripts/generate_demo_mvp_data.py`
- Dữ liệu hoàn toàn synthetic; không chứa hồ sơ hoặc định danh người thật.

## Phạm vi

- 6 bệnh nhân synthetic mắc đái tháo đường type 2.
- Một số ca có tăng huyết áp hoặc bệnh thận mạn.
- 18 tài liệu lâm sàng; mỗi bệnh nhân có xét nghiệm, thuốc và ghi chú tái khám.
- Mọi PDF hiển thị tên bệnh, mã SNOMED CT và ngày bắt đầu được ghi nhận.
- FHIR R4 JSON Bundle, PDF có text, PDF scan/PNG/JPEG và gold JSON/JSONL.
- Không hỗ trợ hoặc chứa CSV.

## Tình huống

- Timeline và xu hướng HbA1c/eGFR.
- Thay đổi tần suất Metformin.
- Mâu thuẫn liều thuốc giữa FHIR và PDF.
- OCR sạch, ảnh nghiêng, ảnh mờ và trường cần xác minh.
- Dữ liệu thiếu, câu hỏi không có bằng chứng và câu hỏi ngoài phạm vi.
- Prompt injection nằm trong tài liệu phải được xem là nội dung không đáng tin, không phải chỉ dẫn.
- Review generated/stale/version conflict/approved-only memory và PDF.

## Nhiễu thực tế có kiểm soát

- Xét nghiệm không liên quan xen giữa chỉ số mục tiêu.
- Kết quả sơ bộ `entered-in-error` cạnh kết quả cuối.
- Bản ghi đến muộn có effective time và issued time khác nhau.
- Thuốc lịch sử, thuốc tự khai chưa xác minh và thuốc hiện tại trong cùng hồ sơ.
- Phủ định, triệu chứng không chắc chắn và tiền sử gia đình trong ghi chú.
- Boilerplate, chuyển phòng, mã thanh toán và metadata hành chính.
- Mâu thuẫn có chủ đích giữa FHIR và PDF; hệ thống phải cảnh báo thay vì tự chọn một nguồn.

## Quy tắc sử dụng

- Không dùng dữ liệu này để chẩn đoán, kê đơn hoặc điều trị.
- Không thay đổi file nguồn sau khi đã ghi checksum; tạo phiên bản dataset mới nếu cần.
- Mọi claim hiển thị như fact phải trỏ tới evidence ID tồn tại.
- OCR confidence thấp phải chuyển `needs_verification`.
