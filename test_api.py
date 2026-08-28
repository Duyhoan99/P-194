# -*- coding: utf-8 -*-
import requests
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

questions = [
    "Tình trạng bệnh nhân này như thế nào?",
    "Bệnh nhân này tên là gì?",
    "Bệnh nhân đã được kê những loại thuốc nào?"
]

for q in questions:
    resp = requests.post(
        'http://localhost:8000/api/v1/patients/PAT-001/ask', 
        json={'question': q, 'session_id': 'test_session_2'}
    )
    print(f"Q: {q}")
    print(f"A: {resp.json().get('answer')}\n")
