AI Agent hỗ trợ tóm tắt hồ sơ lâm sàng đa nguồn cho bác sĩ

1. Bối cảnh và vấn đề

Hồ sơ của một bệnh nhân thường phân tán qua nhiều lần khám, đợt nhập viện, kết quả xét nghiệm, báo cáo chẩn đoán hình ảnh, đơn thuốc và ghi chú lâm sàng. Trước mỗi lượt khám, bác sĩ phải đọc lại nhiều tài liệu để tái dựng diễn biến bệnh, xác định bệnh nền, thuốc gần đây và xu hướng chỉ số. Quá trình này tốn thời gian, dễ bỏ sót dữ kiện và khó kiểm tra khi các nguồn không thống nhất.

2. Người dùng mục tiêu

Bác sĩ điều trị/chuyên khoa: xem hồ sơ, kiểm tra nguồn, chỉnh sửa và phê duyệt bản tóm tắt.

Quản trị viên: quản lý tài khoản, phân quyền bệnh nhân và audit log.

Bệnh nhân không trực tiếp sử dụng hệ thống trong phạm vi MVP.

3. Giải pháp đề xuất

Xây dựng AI Agent có khả năng lập kế hoạch truy xuất, kết hợp nhiều bảng dữ liệu lâm sàng có cấu trúc, đối chiếu nhiều nguồn, phát hiện dữ liệu thiếu hoặc mâu thuẫn, sau đó tạo bản tóm tắt lâm sàng theo dòng thời gian. Trong MVP hiện tại, agent sử dụng các bảng thuộc MIMIC-IV 3.1; khả năng truy xuất clinical notes bằng RAG được giữ làm hướng mở rộng khi tích hợp thêm MIMIC-IV-Note.

Đầu ra gồm:

Tổng quan và vấn đề lâm sàng chính.

Bệnh nền và tiền sử liên quan.

Thuốc hiện tại/gần đây kèm trạng thái bằng chứng.

Timeline các lần khám và sự kiện quan trọng.

Xu hướng chỉ số xét nghiệm.

Cảnh báo tương tác thuốc từ công cụ chuyên biệt.

Cảnh báo dữ liệu thiếu, không chắc chắn hoặc mâu thuẫn.

Citation liên kết từng nhận định với hồ sơ nguồn.

4. Dữ liệu và công nghệ

Dự án sử dụng MIMIC-IV 3.1 đã khử định danh, gồm hai module hosp và icu. Các nguồn chính bao gồm bệnh nhân và lần nhập viện (patients, admissions, transfers), chẩn đoán và thủ thuật, xét nghiệm (labevents, d_labitems), thuốc (prescriptions, pharmacy, emar, emar_detail), chỉ số OMR và dữ liệu ICU (icustays, chartevents, inputevents, outputevents). Dữ liệu được liên kết chủ yếu bằng subject_id, hadm_id và stay_id.

MIMIC-IV 3.1 được chọn vì đã sửa tính nhất quán itemid của xét nghiệm và loại bỏ các subject_id không tồn tại trong patients. MVP dùng SQL/tool retrieval trên dữ liệu cấu trúc. Clinical-note RAG và dữ liệu ED chuyên biệt chỉ được bổ sung khi có MIMIC-IV-Note/MIMIC-IV-ED; tương tác thuốc sử dụng nguồn tri thức độc lập.

Kiến trúc dự kiến: LangGraph, LLM ngữ cảnh dài, FastAPI, Next.js, PostgreSQL, vector DB tùy chọn, object store và Docker.

5. Phạm vi MVP

Đăng nhập và phân quyền Bác sĩ/Quản trị viên.

Chọn một subject_id trong cohort MIMIC-IV 3.1 đã được nạp và phân quyền.

Sinh bản tóm tắt lâm sàng có cấu trúc.

Citation bắt buộc cho mọi câu chứa dữ kiện lâm sàng.

Panel mở bản ghi nguồn, hiển thị bảng MIMIC, subject_id, hadm_id/stay_id, thời gian, mã mục, giá trị và đơn vị khi có.

Hiển thị dữ liệu thiếu, mâu thuẫn và giới hạn.

Bác sĩ chỉnh sửa, từ chối, yêu cầu tạo lại hoặc phê duyệt.

Lưu phiên bản đã duyệt và lịch sử thao tác.

6. Guardrails bắt buộc

Human-in-the-loop: bản AI tạo luôn ở trạng thái DRAFT; bác sĩ phải rà soát trước khi sử dụng.

Không chẩn đoán/điều trị mới: AI không tự thêm chẩn đoán, kê đơn hay thay đổi phác đồ.

Grounded tuyệt đối: claim không có bằng chứng phải bị loại bỏ hoặc ghi “Không đủ dữ liệu”.

Citation cấp nhận định: mỗi thông tin về bệnh, thuốc, xét nghiệm hoặc lần khám phải có nguồn.

Bảo mật: kiểm soát truy cập theo vai trò và bệnh nhân được phân công; ghi audit log; không đưa dữ liệu MIMIC thô lên GitHub hoặc AI development log công khai; không chia sẻ quyền truy cập dữ liệu restricted.

Minh bạch mâu thuẫn: AI không tự chọn nguồn đúng; bác sĩ là người quyết định cuối cùng.

7. Ngoài phạm vi

Không thay thế đánh giá chuyên môn của bác sĩ.

Không tư vấn trực tiếp cho bệnh nhân.

Không tự động ghi đè hồ sơ chính thức.

Không sử dụng dữ liệu có thể nhận diện; bản demo chỉ dùng MIMIC-IV 3.1 đã khử định danh hoặc dữ liệu mock.

Không để LLM tự suy đoán tương tác thuốc.

Chưa xử lý discharge summary, radiology report dạng văn bản hoặc medication reconciliation từ ED nếu chưa tích hợp thêm MIMIC-IV-Note/MIMIC-IV-ED.

8. Chỉ số thành công

Giảm tối thiểu 50% thời gian đọc lại hồ sơ trong thử nghiệm.

100% câu chứa dữ kiện lâm sàng có citation.

Không có dữ kiện lâm sàng nghiêm trọng không được nguồn hỗ trợ.

Giá trị, đơn vị và thời điểm phải khớp với hồ sơ nguồn.

100% bản tóm tắt được bác sĩ rà soát trước khi phê duyệt.