import asyncio
from src.agents.retrieval.router import QueryPlanner

async def main():
    planner = QueryPlanner()
    test_cases = [
        "Tình trạng nào đang không ổn định?",
        "Thông tin của bệnh nhân",
        "HbA1c của bệnh nhân",
        "Bệnh nhân đang dùng thuốc gì?",
        "Lần khám gần nhất thế nào?",
        "Huyết áp bao nhiêu?",
        "Bệnh nhân bị bệnh gì?",
        "Chỉ số nào đang cảnh báo?",
        "Gfgdfg sdfsdf" # UNKNOWN test
    ]
    
    for q in test_cases:
        plan = planner.plan(q)
        print(f"Q: {q}")
        print(f"-> strict_intent: {getattr(plan, 'strict_intent', 'NONE')}")
        print(f"-> task_type: {plan.task_type}")
        print("---")

if __name__ == "__main__":
    asyncio.run(main())
