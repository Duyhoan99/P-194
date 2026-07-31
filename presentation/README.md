# Pitch Deck & Demo Plan — P-194

## Project

**AI Agent hỗ trợ tóm tắt hồ sơ lâm sàng đa nguồn cho bác sĩ**

MIMIC-IV 3.1 đã khử định danh → truy xuất có kiểm soát → timeline và structured summary → citation từng claim → bác sĩ rà soát và phê duyệt.

## Pitch deck outline

1. **Title** — P-194 và tên sản phẩm.
2. **Problem** — Bác sĩ phải đối chiếu nhiều lần nhập viện, labs, diagnoses, procedures, medications và ICU events thủ công.
3. **Solution** — Agent evidence-first tạo bản nháp có citation, hiển thị missing/conflicting data và buộc human review.
4. **MVP scope** — MIMIC-IV 3.1 `hosp`/`icu`; MIMIC-IV-Note và MIMIC-IV-ED là optional, hiện `NOT_LOADED`.
5. **Architecture** — FastAPI + LangGraph + scoped SQL retrieval + PostgreSQL target; xem [ARCHITECTURE.md](../ARCHITECTURE.md).
6. **Safety** — RBAC, patient assignment, claim validator, numeric integrity, audit log và không tự chẩn đoán/điều trị.
7. **Workflow demo** — Login → assigned patient → data availability → Generate → Draft → Source review → Edit → Approve.
8. **Evaluation** — Skeleton test hiện tại `5 passed`; groundedness, latency, user study và clinical benchmark chưa đo.
9. **Current status** — Product/architecture documentation hoàn thành; clinical ingestion, production API và UI chưa triển khai.
10. **Next ask** — Chốt identity provider, LLM terms, drug knowledge source, deployment boundary và clinical governance.

## Team

| Thành viên | Vai trò |
|---|---|
| Đào Trung Hiếu | Team Lead / AI & Backend Architecture |
| Phạm Duy Hoàn | Product Owner / Clinical Workflow |
| Nguyễn Đình Quốc | Prompt Engineer / PM |
| Đặng Hoàng Dũng | Data Engineer / QA |

## Demo script (khi MVP được triển khai)

1. Đăng nhập bằng tài khoản bác sĩ và mở danh sách bệnh nhân được phân công.
2. Chọn `subject_id`, `hadm_id`/`stay_id` và xem data availability (`hosp`, `icu`, optional modules).
3. Bấm **Generate Summary**; hiển thị processing nodes và trace ID nội bộ không lộ chain-of-thought.
4. Mở summary draft: xem timeline, lab trend, medication status, limitations và conflict badges.
5. Bấm citation để mở source panel với dataset/version/module/table/row/time/value.
6. Sửa claim, revalidate citation và kiểm tra rằng claim thiếu nguồn không thể approve.
7. Hoàn thành checklist HITL, approve; chỉ bản approved được xuất PDF chính thức.

## Video checklist

- [ ] Screen recording Login và assigned patient (chưa có UI).
- [ ] Screen recording Generate → Draft (chưa có clinical agent).
- [ ] Citation/source panel (chưa có data ingestion).
- [ ] Review checklist và approved PDF (chưa triển khai).
- [x] Nội dung storyboard và acceptance criteria đã ghi ở trên.

## Assets

Chưa có `pitch_deck.pptx` hoặc `video_demo.mp4`. Không tạo placeholder giả cho các asset này trước khi có UI và MVP workflow chạy được.
