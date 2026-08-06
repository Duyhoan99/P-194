---
title: "State Management"
description: "Định nghĩa State schema cho LangGraph agent"
weight: 1
---

## State Schema

State là "bộ nhớ" của agent, truyền giữa các nodes. Dưới đây là state thực tế của Clinical Agent (`src/clinical/agent.py`):

```python
from typing import TypedDict
from src.clinical.schemas import AccessContext, ClinicalQuery, ClinicalResponse, EvidenceRecord
from src.clinical.summary_schemas import ClinicalSummaryDraft, ValidationReport

class AgentState(TypedDict, total=False):
    context: AccessContext                  # Thông tin phân quyền, trace_id
    query: ClinicalQuery                    # Scope truy vấn lâm sàng (bệnh nhân, đợt nhập viện)
    responses: tuple[ClinicalResponse, ...] # Phản hồi thô từ các module retrieval
    evidence: list[EvidenceRecord]          # Danh sách chứng cứ đã được chuẩn hóa
    draft: ClinicalSummaryDraft             # Bản nháp tóm tắt lâm sàng (kết quả của generate_node)
    validation: ValidationReport            # Báo cáo kiểm tra citation từ validate_node
```

## Nguyên tắc thiết kế State

### 1. Dùng TypedDict

```python
# ✅ TỐT — TypedDict cho state
class AgentState(TypedDict, total=False):
    query: ClinicalQuery
    draft: ClinicalSummaryDraft

# ❌ TỆ — Không dùng Pydantic BaseModel làm LangGraph state
class AgentState(BaseModel):
    query: ClinicalQuery  # LangGraph mong đợi TypedDict
```

### 2. total=False cho optional fields

```python
class AgentState(TypedDict, total=False):
    context: AccessContext       # Input ban đầu (cùng với query)
    query: ClinicalQuery         # Input ban đầu
    draft: ClinicalSummaryDraft  # Optional — chỉ có sau khi qua generate_node
```

### 3. Chỉ thêm fields thực sự cần thiết cho workflow

- Mỗi field đại diện cho dữ liệu được truyền giữa các nodes hoặc dùng để quyết định hướng đi trong graph.
- Không dùng state như "trash can" chứa mọi thứ (ví dụ: không lưu credentials, api keys vào state).
- Nên sử dụng Pydantic models (như `ClinicalSummaryDraft`, `EvidenceRecord`) làm kiểu dữ liệu bên trong `TypedDict` để tận dụng validate.

### 4. Pattern cập nhật State

```python
# Mỗi node chỉ return một dictionary chứa các fields nó cần thay đổi
def _generate_node(self, state: AgentState) -> dict[str, ClinicalSummaryDraft]:
    query = state["query"]
    evidence = state["evidence"]
    
    # ... logic tạo bản nháp ...
    draft = self._structured_llm.invoke(messages)
    
    # Chỉ update field "draft" trong state
    return {"draft": draft}
```
