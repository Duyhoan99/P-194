# 📁 BỘ DỮ LIỆU DEMO DÀNH CHO BÁC SĨ & BAN GIÁM KHẢO (P-194)

Thư mục này chứa **toàn bộ các tệp tin dữ liệu mẫu** được phân chia sẵn theo từng kịch bản demo cụ thể để bạn dễ dàng kéo thả, không bị nhầm lẫn khi trình bày trước Ban Giám khảo.

---

## 📂 1. KỊCH BẢN 1: BỆNH NHÂN CÓ SẴN (RÀ SOÁT & ĐỐI SOÁT ĐA NGUỒN)
> **Đường dẫn thư mục:** `BO_DU_LIEU_DEMO/1_DEMO_BENH_NHAN_CO_SAN_DOI_SOAT_NGUON/`

| Tên File | Bệnh nhân | Mục đích Demo & Thao tác |
|---|---|---|
| `1_PAT-001_Don_Thuoc_Amlodipine_Metformin.pdf` | **PAT-001** (Nguyễn Demo An) | **Test đối soát đa nguồn:** Kéo thả vào bệnh nhân `PAT-001` để xem AI gộp thuốc thông minh, giữ nguyên liều `5 MG`, `500 MG` và gắn cả 2 huy hiệu `[⚡ FHIR]` + `[📄 PDF]`. |
| `2_PAT-001_Ket_Qua_Xet_Nghiem_HbA1c.pdf` | **PAT-001** (Nguyễn Demo An) | **Test diễn tiến xét nghiệm:** Tải lên để đối chiếu kết quả HbA1c và Glucose qua các lần khám. |
| `3_PAT-003_Don_Thuoc_Xung_Dot_Lieu_Metformin_850mg.pdf` | **PAT-003** (Phạm Văn Bình) | **Test phát hiện mâu thuẫn:** Tải vào `PAT-003`, mở tab **"Đối soát Mâu thuẫn"** để thấy AI cảnh báo xung đột liều thuốc giữa bệnh viện (500mg) và đơn ngoài (850mg). |

---

## 📂 2. KỊCH BẢN 2: TIẾP NHẬN BỆNH NHÂN HOÀN TOÀN MỚI 100%
> **Đường dẫn thư mục:** `BO_DU_LIEU_DEMO/2_DEMO_BENH_NHAN_MOI_HOAN_TOAN/`

| Tên File | Loại tài liệu | Mục đích Demo & Thao tác |
|---|---|---|
| `1_Phieu_Kham_Va_Don_Thuoc_Le_Hoang_Long.pdf` | **File PDF Đơn thuốc scan** | **Zero-shot Onboarding:** Vào trang **"Hồ sơ"** (`/case-files`) $\rightarrow$ Kéo thả file này $\rightarrow$ Chọn `➕ Tạo mới hồ sơ bệnh nhân...` $\rightarrow$ Đặt tên `Lê Hoàng Long` $\rightarrow$ AI tự động tạo hồ sơ, sinh SOAP và phác đồ điều trị! |
| `2_Anh_Scan_Ket_Qua_Xet_Nghiem_OCR.jpg` | **Ảnh chụp kết quả xét nghiệm** | **Test OCR hình ảnh:** Tải ảnh chụp điện thoại vào hồ sơ bệnh nhân để chứng minh AI có thể đọc và trích xuất chỉ số xét nghiệm từ ảnh chụp thực tế. |
| `3_Ho_So_Dien_Tu_FHIR_R4.json` | **Bản ghi chuẩn FHIR R4** | **Test tích hợp dữ liệu số:** Tệp JSON chuẩn quốc tế FHIR Bundle chứa đầy đủ chẩn đoán, thuốc và lịch sử khám. |

---

## 🚀 3. TÓM TẮT LUỒNG THAO TÁC 3 BƯỚC CHO NGƯỜI DEMO:

1. **Bước 1 (Màn 1):** Mở bệnh nhân `PAT-001`, chỉ vào 2 badge `[⚡ FHIR]` và `[📄 PDF]` để chứng minh đối soát chéo không bịa đặt thông tin.
2. **Bước 2 (Màn 2):** Vào `/case-files`, kéo thả file `1_Phieu_Kham_Va_Don_Thuoc_Le_Hoang_Long.pdf` để tạo bệnh nhân mới trong 3 giây.
3. **Bước 3 (Cao trào):** Bấm **"Hướng dẫn chăm sóc"** ➔ Ký tên bác sĩ ➔ Xuất PDF và **mời Giám khảo quét mã QR** nghe giọng đọc dặn dò tiếng Việt!
