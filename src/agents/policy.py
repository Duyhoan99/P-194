"""Rule-first task routing and non-clinical safety policy."""

from __future__ import annotations

import re
import unicodedata
from enum import Enum
from typing import Literal

from src.agents.contracts import AgentRequest
from src.agents.retrieval.router import DomainNeed, QueryPlanner, RetrievalPlan

QuestionType = Literal["structured", "notes", "hybrid", "not_allowed", "not_allowed_treatment", "not_allowed_tampering", "not_allowed_interaction", "narrative", "temporal", "mixed"]

_TREATMENT_REQUESTS = (
    "đổi thuốc",
    "ngừng thuốc",
    "nên dùng",
    "nên ngừng",
    "nên đổi",
    "kê đơn",
    "khuyến nghị điều trị",
    "recommend treatment",
    "which medication should",
    "thay thuốc",
    "bớt thuốc",
    "thêm thuốc",
    "tăng liều",
    "giảm liều",
    "chỉnh liều",
    "uống thêm",
    "bỏ thuốc",
    "tiêm thêm",
    "dùng thêm",
    "chuyển sang",
    "phác đồ mới",
    "tự ý",
    "bỏ bớt thuốc",
    "uống bao nhiêu viên",
)
_DATA_TAMPERING_REQUESTS = (
    "xóa hồ sơ",
    "xóa bệnh nhân",
    "sửa chẩn đoán",
    "sửa kết quả",
    "chỉnh sửa kết quả",
    "thay đổi chẩn đoán",
    "delete patient",
    "delete record",
)
_INTERACTION_REQUESTS = (
    "tương tác",
    "interaction",
)
_NOTE_TERMS = (
    "ghi chú",
    "đau ngực",
    "khó thở",
    "hạ đường huyết",
    "triệu chứng",
    "tự khai",
    "note",
    "symptom",
)
_STRUCTURED_TERMS = (
    "hba1c",
    "egfr",
    "glucose",
    "xét nghiệm",
    "liều",
    "thuốc",
    "metformin",
    "dị ứng",
    "trend",
    "bao nhiêu",
)
_PATIENT_TOKEN = re.compile(r"PAT-?\d{3}", re.IGNORECASE)
_PROMPT_OVERRIDE = re.compile(
    r"\b(ignore|disregard|forget|override)\b.{0,48}"
    r"\b(previous|prior|system|developer)\b.{0,32}"
    r"\b(instruction|prompt|message)s?\b",
    re.IGNORECASE,
)


from enum import StrEnum

class RequestCategory(str, Enum):
    SIMPLE = "SIMPLE"              # Chào hỏi, danh tính, lịch sử, văn bản rác/chưa rõ
    CLINICAL = "CLINICAL"          # Tra cứu bệnh án, xét nghiệm, chẩn đoán, thuốc
    NOT_ALLOWED = "NOT_ALLOWED"    # Kê đơn mới, can thiệp sửa đổi bệnh án
    TOOL = "TOOL"                  # Công cụ (hiện danh sách, v.v.)


def remove_accents(text: str) -> str:
    text = unicodedata.normalize('NFD', text)
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn').lower()


def is_gibberish(text: str) -> bool:
    """Phát hiện chuỗi gõ phím thử, từ vô nghĩa, ký tự lặp."""
    raw = text.strip().lower()
    if len(raw) < 2:
        return True
    # Kiểm tra ký tự lặp liên tiếp >= 3 lần (vd: aaaaa, dâdaadadaad, xxx), ngoại trừ số (vd: 1000)
    if re.search(r'([^\d])\1{2,}', raw):
        return True
    # Kiểm tra tỷ lệ nguyên âm/phụ âm hoặc chuỗi không có dấu cách nếu quá dài
    words = raw.split()
    if len(words) == 1 and len(raw) > 12:
        return True
    return False


def classify_prompt_category(query: str, patient_id: str = "") -> dict:
    clean_q = query.strip().lower()
    no_accent_q = remove_accents(clean_q)

    # 1. Bắt chuỗi rác / gõ phím linh tinh trước tiên -> Trả về UNCLEAR, không báo cấm
    if is_gibberish(clean_q):
        return {
            "category": RequestCategory.SIMPLE,
            "intent": "unclear_query",
            "reasoning": "Chuỗi ký tự không rõ nghĩa hoặc gõ phím thử.",
        }

    # 2. Nhận diện danh tính người dùng / trò chuyện / khả năng
    identity_keywords = ["tôi là ai", "toi la ai", "tôi là bác sĩ", "toi la bac si", "vai trò của tôi"]
    capability_keywords = ["bạn là ai", "ban la ai", "bạn làm được gì", "khả năng của bạn", "giúp được gì", "chức năng của bạn", "ban lam duoc gi", "ban co the lam gi"]
    greeting_keywords = ["chào", "chao", "hello", "hi", "alo", "hey", "ê", "có ai không", "co ai khong", "buổi sáng", "buổi chiều", "buổi tối", "cảm ơn", "cam on", "thanks", "thank you", "tạm biệt", "tam biet", "bye", "goodbye"]
    words = no_accent_q.split()
    
    if any(kw in clean_q or kw in no_accent_q for kw in identity_keywords):
        return {
            "category": RequestCategory.SIMPLE,
            "intent": "user_identity",
            "reasoning": "Hỏi về danh tính/vai trò của người dùng.",
        }
        
    if any(kw in clean_q or kw in no_accent_q for kw in capability_keywords) or (len(words) <= 7 and any(kw == no_accent_q or kw in words for kw in greeting_keywords)):
        return {
            "category": RequestCategory.SIMPLE,
            "intent": "chit_chat",
            "reasoning": "Trò chuyện ngắn hoặc hỏi về khả năng của hệ thống.",
        }

    # 3. Nhận diện TOÀN DIỆN câu hỏi lịch sử đàm thoại
    history_patterns = [
        "vua hoi", "da hoi", "hoi gi", "nhung gi ben tren", "nhung cau gi", "lich su chat", "nhac lai",
        "câu hỏi trước", "cau hoi truoc"
    ]
    if any(p in no_accent_q for p in history_patterns) and not any(k in no_accent_q for k in ["thuoc", "benh", "xet nghiem"]):
        return {
            "category": RequestCategory.SIMPLE,
            "intent": "chat_history_query",
            "reasoning": "Yêu cầu xem lại lịch sử các câu hỏi trước đó.",
        }

    # 4. Kiểm tra tương tác thuốc (CHỈ BẮT KHI CÓ TÊN THUỐC HOẶC TỪ KHÓA RÕ RÀNG)
    interaction_keywords = ["tuong tac thuoc", "tương tác thuốc", "uong chung duoc khong", "dung chung co sao khong"]
    if any(kw in no_accent_q for kw in interaction_keywords):
        return {
            "category": RequestCategory.SIMPLE,
            "intent": "drug_interaction_unsupported",
            "reasoning": "Hỏi về tương tác thuốc chưa hỗ trợ.",
        }

    # 5. Các vi phạm an toàn y tế nghiêm trọng (Kê đơn, sửa hồ sơ)
    if any(term in clean_q for term in _TREATMENT_REQUESTS) or any(term in no_accent_q for term in _TREATMENT_REQUESTS):
        return {
            "category": RequestCategory.NOT_ALLOWED,
            "intent": "not_allowed_treatment",
            "reasoning": "Hành vi kê đơn, điều chỉnh liều.",
        }

    if any(term in clean_q for term in _DATA_TAMPERING_REQUESTS) or any(term in no_accent_q for term in _DATA_TAMPERING_REQUESTS):
        return {
            "category": RequestCategory.NOT_ALLOWED,
            "intent": "not_allowed_tampering",
            "reasoning": "Hành vi can thiệp trái phép vào hồ sơ bệnh án.",
        }

    # Bắt query danh sách xét nghiệm toàn bộ
    lab_list_keywords = ["tất cả chỉ số", "toàn bộ chỉ số", "các chỉ số", "chỉ số của bệnh nhân", "cụ thể tất cả chỉ số", "danh sách chỉ số", "những chỉ số"]
    if any(kw in clean_q or kw in no_accent_q for kw in lab_list_keywords):
        return {
            "category": RequestCategory.TOOL,
            "domain": "lab",
            "intent": "full_lab_listing",
            "reasoning": "Yêu cầu xem toàn bộ chỉ số xét nghiệm.",
        }

    # 6. Các trường hợp tra cứu lâm sàng thực tế
    return {
        "category": RequestCategory.CLINICAL,
        "intent": "clinical_inquiry",
        "reasoning": "Truy vấn dữ liệu bệnh án thông thường.",
    }


def classify_request(request: AgentRequest) -> QuestionType | dict:
    if request.task_type == "review_generation":
        # Review generation is a server-owned workflow, not a user chat turn.
        return RetrievalPlan(
            task_type="summary",
            needs=[DomainNeed(domain="all")],
            use_structured=True,
            use_semantic=False,
            use_lexical=False,
            retrieval_required=True,
            strict_intent="NONE",
        ).model_dump()

    classified = classify_prompt_category(request.question or "", request.patient_id)
    category = classified.get("category")
    intent = classified.get("intent", "UNKNOWN")

    if category == RequestCategory.NOT_ALLOWED:
        if intent == "not_allowed_treatment":
            return "not_allowed_treatment"
        elif intent == "not_allowed_tampering":
            return "not_allowed_tampering"
        return "not_allowed"

    if category == RequestCategory.SIMPLE:
        if intent == "chat_history_query":
            return RetrievalPlan(
                task_type="conversation_reference",
                strict_intent="NONE",
                extracted_entity="previous_question",
                retrieval_required=False,
            ).model_dump()
        elif intent == "unclear_query":
            return RetrievalPlan(
                task_type="clarification",
                strict_intent="unclear_query",
                extracted_entity="Tôi chưa hiểu câu hỏi. Bạn có thể diễn đạt rõ hơn nội dung cần tra cứu không?",
                retrieval_required=False,
            ).model_dump()
        elif intent == "drug_interaction_unsupported":
            return "not_allowed_interaction"
        else: # user_identity and others
            return RetrievalPlan(
                task_type="conversation",
                strict_intent=intent,
                extracted_entity=intent,
                retrieval_required=False,
            ).model_dump()

    # Category is CLINICAL: Use QueryPlanner to get the validated RetrievalPlan
    planner = QueryPlanner()
    plan = planner.plan(request.question or "")

    # If the plan is out of scope, return not_allowed
    if plan.task_type == "out_of_scope":
        return "not_allowed"

    return plan.model_dump()

