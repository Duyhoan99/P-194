import asyncio
from src.agents.retrieval.router import QueryPlanner

async def main():
    planner = QueryPlanner()
    test_cases = [
        "Bệnh nhân mắc bệnh gì?", # DIAGNOSIS -> DISEASE
        "Thông tin bệnh nhân", # PATIENT_OVERVIEW
        "Chỉ số khám gần nhất?", # LATEST_VITALS -> LATEST_VISIT
        "Tình trạng nào đang không ổn định?", # WARNING_STATUS
        "Có gì bất thường không?", # WARNING_STATUS
        "Buổi khám 10/06/2026", # SPECIFIC_DATE -> VISIT
        "Buổi khám lần trước?", # PREVIOUS_VISIT
        "Thuốc bệnh nhân đang dùng?", # MEDICATION
        "HbA1c thay đổi thế nào?", # HISTORICAL_TREND -> COMPARISON / LAB_RESULT
        "Cho tôi nhiệt độ cơ thể" # SPECIFIC_TEST
    ]
    
    for q in test_cases:
        plan = planner.plan(q)
        print(f"Q: {q}")
        print(f"-> strict_intent: {getattr(plan, 'strict_intent', 'NONE')}")
        print(f"-> task_type: {plan.task_type}")
        if getattr(plan, 'strict_intent', 'NONE') == "SPECIFIC_TEST":
            print(f"-> extracted_entity: {getattr(plan, 'extracted_entity', 'NONE')}")
        print("---")

if __name__ == "__main__":
    asyncio.run(main())
