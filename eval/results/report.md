# Evaluation Report — P-194

Báo cáo này tách **target trong PRD** khỏi **actual đã đo**. Clinical ingestion, retrieval, UI và user study chưa được triển khai nên không suy diễn số liệu khi chưa có benchmark.

## 1. Current metrics

| Metric | PRD target | Actual | Status |
|---|---:|---:|---|
| Citation coverage | 100% claim lâm sàng | Chưa đo — clinical generator chưa triển khai | ⏳ |
| Citation correctness | ≥95% test set | Chưa đo — chưa có evaluation set | ⏳ |
| Unsupported serious clinical claims | 0 | Chưa đo — citation validator chưa triển khai | ⏳ |
| Numeric value/unit/time consistency | ≥99% | Chưa đo — structured retrieval chưa triển khai | ⏳ |
| Timeline ordering accuracy | ≥95% | Chưa đo | ⏳ |
| Medication status accuracy | ≥90% | Chưa đo | ⏳ |
| Summary generation latency | <60s MVP | Chưa đo — chỉ có agent skeleton | ⏳ |
| Dashboard/source-panel latency | <2s | Chưa đo — UI chưa triển khai | ⏳ |
| Unauthorized access accepted | 0 | Chưa đo — RBAC chưa triển khai | ⏳ |
| Existing automated tests | N/A | 5 passed, 0 failed | ✅ |

## 2. Automated test results

Command:

```text
pytest tests -q
.....                                                                    [100%]
5 passed in 0.10s
```

Các test hiện tại kiểm tra health endpoint, request validation, agent status và LangGraph state/basic flow. Đây là test skeleton, chưa phải test clinical safety.

## 3. Evaluation plan for MVP

- Tạo cohort 20–50 bệnh nhân MIMIC-IV 3.1 theo tiêu chí trong PRD; không commit raw rows.
- Gắn gold evidence cho timeline, labs, medication status và source lineage.
- Kiểm tra claim-level citation coverage/correctness, numeric consistency và unsupported-claim blocking.
- Tạo các case missing data, conflicting sources, unavailable module và drug-tool timeout.
- Đo p50/p95 latency với dataset đã lập chỉ mục.
- Thực hiện usability study với bác sĩ sau khi có UI; so sánh thời gian rà soát trước/sau, mục tiêu giảm ≥50%.

## 4. User feedback

Chưa thu thập vì UI và clinical workflow chưa triển khai.

| User | Feedback | Rating |
|---|---|---:|
| Chưa có người dùng thử | Chưa thu thập | — |

## 5. Demo status

- Ngày demo: Chưa lên lịch.
- Người tham gia: Chưa cung cấp.
- Live URL: Chưa triển khai.
- Issues đã biết: clinical ingestion, auth/RBAC, retrieval, citation validator, frontend và PDF export chưa có.

## 6. Action items

- [ ] Chốt cohort và tạo ingestion/checksum report.
- [ ] Implement PostgreSQL schema và scoped retrieval tools.
- [ ] Implement claim/citation/numeric validators.
- [ ] Implement auth, patient assignment và audit log.
- [ ] Xây UI review workflow và PDF export.
- [ ] Chạy evaluation set và user study; cập nhật bảng actual bằng số liệu thật.
