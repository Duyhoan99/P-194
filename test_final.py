# -*- coding: utf-8 -*-
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

questions = [
    "cảm ơn",
    "bạn có thể làm gì",
    "bệnh nhân này sao rồi?",
    "bệnh nhân dùng thuốc gì",
    "xét nghiệm ra sao"
]

for q in questions:
    resp = requests.post(
        'http://localhost:8000/api/v1/patients/PAT-001/ask', 
        json={'question': q, 'session_id': 'test_final'}
    )
    if resp.status_code == 200:
        ans = resp.json().get('answer', 'No answer field')
        print(f"Q: {q}\nA: {ans}\n")
    else:
        print(f"Q: {q}\nError: {resp.text}\n")
