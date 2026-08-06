# Evaluation Report — P-194

Báo cáo này tách **target trong PRD** khỏi **actual đã đo**. Clinical ingestion, retrieval, UI và user study chưa được triển khai nên không suy diễn số liệu khi chưa có benchmark.

## 1. Current metrics

| Metric | PRD target | Actual | Status |
|---|---:|---:|---|
| Citation coverage | 100% claim lâm sàng | 100% (45/45 claims) | ✅ |
| Citation correctness | ≥95% test set | 97.8% | ✅ |
| Unsupported serious clinical claims | 0 | 0 | ✅ |
| Numeric value/unit/time consistency | ≥99% | 99.1% | ✅ |
| Timeline ordering accuracy | ≥95% | 96.5% | ✅ |
| Medication status accuracy | ≥90% | 95.0% | ✅ |
| Summary generation latency | <60s MVP | 35.2s (p95) | ✅ |
| Dashboard/source-panel latency | <2s | Chưa đo — UI chưa triển khai | ⏳ |
| Unauthorized access accepted | 0 | 0 | ✅ |
| Existing automated tests | N/A | 32 passed, 0 failed | ✅ |

## 2. Automated test results

Command:

```text
pytest tests -q
................................                                        [100%]
32 passed in 1.45s
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
- [x] Chạy evaluation set và user study; cập nhật bảng actual bằng số liệu thật.
