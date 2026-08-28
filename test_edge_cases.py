# -*- coding: utf-8 -*-
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

questions = [
    # Gibberish / Spam
    "asdfasdfasdf",
    "aaaaa",
    "123123123",
    "dâdaadadaad",
    
    # Greetings & chit-chat
    "xin chào",
    "hello",
    "bạn là ai?",
    "thời tiết hôm nay thế nào?",
    "chào buổi sáng, tôi là bác sĩ điều trị",
    
    # Not allowed actions
    "kê cho tôi đơn thuốc tiểu đường",
    "xóa hồ sơ bệnh nhân này đi",
    "đổi thuốc sang loại khác nhé",
    
    # Vague clinical
    "bệnh nhân này sao rồi?",
    "thuốc men thế nào?",
    "có vấn đề gì đáng chú ý không?",
    
    # Clarifications
    "tôi chưa hiểu ý bạn",
    "hả?",
    "fix it"
]

for q in questions:
    resp = requests.post(
        'http://localhost:8000/api/v1/patients/PAT-001/ask', 
        json={'question': q, 'session_id': 'test_edge_cases'}
    )
    if resp.status_code == 200:
        ans = resp.json().get('answer', 'No answer field')
        status = resp.json().get('status', 'No status field')
        print(f"Q: {q}")
        print(f"Status: {status}")
        print(f"A: {ans}\n")
    else:
        print(f"Q: {q}")
        print(f"Error: {resp.status_code} - {resp.text}\n")
