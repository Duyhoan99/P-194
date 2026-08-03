# Thiết kế sản phẩm hỗ trợ tóm tắt hồ sơ lâm sàng cho triển khai thực tế

**Ngày:** 2026-08-03  
**Trạng thái:** Đã được duyệt để lập implementation plan  
**Phạm vi:** Vertical slice demo dùng dữ liệu synthetic/mock, giữ nguyên hợp đồng cho triển khai dữ liệu bệnh viện

## 1. Mục tiêu

Sản phẩm giúp bác sĩ giảm thời gian đọc lại hồ sơ bệnh nhân qua nhiều lần nhập viện bằng cách truy xuất evidence có cấu trúc, tạo bản tóm tắt lâm sàng dạng draft và cho phép kiểm tra nguồn trước khi phê duyệt.

Sản phẩm không tự chẩn đoán, kê đơn, đề xuất thay đổi điều trị hoặc ghi ngược vào EHR. Bác sĩ được phân công là người quyết định cuối cùng.

Release đầu tiên phải chứng minh được quy trình thực tế end-to-end bằng dữ liệu demo an toàn, đồng thời không tạo ra một contract khác với phiên bản dùng cho dữ liệu bệnh viện.

## 2. Actors và quyền hạn

| Actor | Nhiệm vụ trong release demo | Ranh giới quyền hạn |
|---|---|---|
| Bác sĩ | Xem bệnh nhân được phân công, tạo draft, kiểm tra citation/conflict, chỉnh sửa, từ chối và phê duyệt | Chỉ xem bệnh nhân được phân công; chỉ bác sĩ được phân công được approve |
| Trưởng khoa/bác sĩ kiểm duyệt | Theo dõi chất lượng và áp dụng chính sách review | Không bypass assignment hoặc citation validation |
| Admin | Quản lý tài khoản, vai trò và assignment | Không sửa nội dung lâm sàng thay bác sĩ |
| Data steward | Theo dõi ingestion, lỗi schema, source availability và lineage | Không phê duyệt nội dung lâm sàng |
| Safety/compliance | Xem audit log, version history và các bản chưa được phê duyệt | Read-only với clinical content |
| DevOps/IT | Theo dõi health, lỗi, latency, database, backup và deployment | Không truy cập clinical content ngoài quyền vận hành được cấp |
| Bệnh nhân | Chưa có quyền truy cập trong release đầu | Chỉ xem xét ở giai đoạn sau khi có governance phù hợp |

Demo dùng tài khoản và assignment giả lập. Production phải thay bằng identity provider/SSO và assignment provider đáng tin cậy; không bao giờ dùng user ID, role hoặc assignment do client tự gửi làm bằng chứng phân quyền.

## 3. Phạm vi release demo

### 3.1. Luồng bác sĩ

```text
Login → Assigned patient list → Patient workspace
      → Timeline/labs/evidence → Generate draft
      → Check citations/conflicts → Edit or reject
      → Approve → Audit and export
```

Patient workspace phải hiển thị trạng thái dữ liệu, timeline, laboratory evidence, diagnoses/procedures, missing/conflicting data, limitations và source lineage. Bản tóm tắt luôn hiển thị rõ trạng thái `DRAFT` cho tới khi được approve.

### 3.2. Luồng vận hành

- Admin tạo user, gán role và gán bác sĩ với bệnh nhân.
- Data steward xem ingestion run, module/table availability, checksum/schema error và lineage.
- Safety/compliance xem các state transition, version, reviewer, timestamp và audit result.
- DevOps/IT theo dõi health check, query latency, error rate, database availability và backup status qua công cụ vận hành.

### 3.3. Ngoài phạm vi release đầu

- Bệnh nhân tự truy cập.
- Ghi dữ liệu trở lại EHR.
- Tự động chẩn đoán, kê đơn hoặc khuyến nghị điều trị.
- Clinical notes/RAG khi chưa có nguồn được cấp phép và pipeline tương ứng.
- Drug interaction do LLM tự suy luận.

## 4. Kiến trúc

Hệ thống gồm các lớp có boundary rõ ràng:

1. **Next.js frontend:** các màn hình bác sĩ, admin, data steward và compliance.
2. **Identity and access:** xác thực, role và assignment; demo provider chỉ dành cho test/development.
3. **FastAPI clinical API:** patient, timeline, labs, diagnoses, medications, summary, review, audit và export routes.
4. **Clinical service:** kiểm tra quyền trước khi truy vấn, chuẩn hóa evidence, giữ lineage và map trạng thái/lỗi.
5. **Evidence-first agent:** retrieve → normalize → detect missing/conflict → generate draft → validate claim → attach citation → persist draft.
6. **Data adapters:** `DemoRepository` cho synthetic SQLite và `HospitalRepository` cho PostgreSQL/staging.

`DemoRepository` và `HospitalRepository` phải dùng cùng interface và response schema. Việc thay nguồn dữ liệu không được yêu cầu viết lại frontend, review workflow hoặc citation contract.

Luồng dữ liệu chuẩn:

```text
Actor
  → Authentication/role
  → Assigned patient
  → Clinical API
  → Server-side access check
  → Read-only repository
  → Evidence + source lineage
  → Agent draft
  → Claim/citation validation
  → Human review
  → Approval + audit + export
```

Không cho frontend truy cập trực tiếp database. Agent không được tự sinh SQL tự do; retrieval chỉ dùng query/tool allow-list và parameterized filters.

## 5. Trạng thái nghiệp vụ và an toàn

Trạng thái summary:

```text
NOT_STARTED → GENERATING → DRAFT
DRAFT → NEEDS_REVISION → DRAFT
DRAFT → REJECTED
DRAFT → APPROVED → EXPORTED
```

Quy tắc bắt buộc:

- Chỉ bác sĩ được phân công mới được approve.
- Claim không có citation hợp lệ bị loại hoặc hiển thị là không đủ dữ liệu.
- Conflict không được AI tự chọn nguồn đúng; phải giữ trạng thái unresolved và hiển thị limitation.
- Draft chưa approve không được xuất như tài liệu chính thức.
- Mỗi lần generate, edit, regenerate, reject, approve và export tạo một audit event.
- Original AI draft và các phiên bản bác sĩ chỉnh sửa được lưu tách biệt.
- Log lỗi không chứa raw clinical value, secret, token, prompt hoặc SQL parameter.

## 6. Xử lý lỗi

| Tình huống | Hành vi hệ thống |
|---|---|
| Bệnh nhân không được phân công | `403`, không gọi repository, ghi audit event |
| Scope/hadm/stay không hợp lệ | `422`, không trả evidence ngoài scope |
| Nguồn chưa được nạp | `PARTIAL` hoặc `NOT_LOADED`, hiển thị warning rõ ràng |
| Không có bản ghi phù hợp | `EMPTY`, không suy diễn dữ liệu |
| Database unavailable | `503`, không lộ SQL hoặc giá trị clinical |
| Query timeout | `504`, kèm trace ID để tra cứu |
| Claim validation thất bại | Không persist bản approved; giữ draft và hiển thị lỗi citation |
| Authentication chưa cấu hình | Fail closed; không cho clinical access |

Mọi response clinical và lỗi đều có correlation/trace ID nhưng không chứa dữ liệu nhạy cảm không cần thiết.

## 7. Kiểm thử và tiêu chí nghiệm thu

### 7.1. Kiểm thử kỹ thuật

- Unit test cho schema, access control, citation validator và state transition.
- API test cho từng role và route.
- Security test cho unassigned patient, unrelated encounter/ICU stay và client-supplied identity.
- Integration test từ synthetic dataset → API → agent → review → export.
- Failure test cho thiếu bảng, timeout, database error và dữ liệu mâu thuẫn.
- Regression test khi thay `DemoRepository` bằng `HospitalRepository`.
- Ruff, full pytest, `git diff --check` và smoke test không in clinical values.

### 7.2. Tiêu chí release demo

- Bác sĩ hoàn tất được toàn bộ quy trình từ mở hồ sơ đến phê duyệt bằng dữ liệu demo.
- 100% clinical request đi qua server-side authorization.
- 100% claim trong bản approved có citation hợp lệ.
- 100% bản approved có reviewer và timestamp.
- Unauthorized access bị chặn và được audit.
- Không có raw patient data, secret hoặc restricted excerpt trong repository/log.
- Actor vận hành xem được trạng thái hệ thống mà không cần bypass clinical permission.

### 7.3. Tiêu chí chuyển sang dữ liệu thật

- Có PostgreSQL production adapter và migration/index được review.
- Có SSO/OIDC, assignment provider và patient-identity mapping được bệnh viện phê duyệt.
- Có ingestion pipeline tái lập, checksum/schema/foreign-key validation và rollback.
- Có retention, backup, restore, incident response và audit access policy.
- Có đánh giá với bác sĩ về thời gian hoàn tất, khả năng kiểm tra nguồn và tỷ lệ chỉnh sửa draft.
- Có clinical governance sign-off cho reviewer credential, approval policy và unresolved conflict policy.

## 8. Thứ tự triển khai

1. Review và tích hợp branch clinical backend vào `main`.
2. Hoàn thiện summary generation, claim/citation validation, review/version và audit persistence.
3. Xây frontend vertical slice cho bác sĩ.
4. Thêm màn hình tối thiểu cho admin, data steward và safety/compliance.
5. Chạy end-to-end demo với synthetic data và kiểm thử bảo mật.
6. Chuyển adapter sang PostgreSQL staging và kết nối auth sandbox.
7. Chạy pilot có kiểm soát với dữ liệu bệnh viện sau khi hoàn tất governance và đánh giá.

## 9. Quyết định thiết kế

- Demo phải giữ nguyên API/schema của production.
- SQLite chỉ dành cho local/test; production chọn PostgreSQL rõ ràng, không fallback âm thầm.
- Human approval là state transition ở backend, không phải nút UI đơn thuần.
- Citation là entity/contract first-class, không chỉ là link cuối đoạn.
- Retrieval có cấu trúc là đường evidence chính; RAG là phần mở rộng có điều kiện.
- Product success được đo bằng thời gian và chất lượng review của bác sĩ, không chỉ bằng chất lượng câu trả lời của LLM.
