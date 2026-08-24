"""Regenerate fresh multi-source reviews for all demo patients via the live API."""
import urllib.request
import json

PATIENTS = ['PAT-001', 'PAT-002', 'PAT-003', 'PAT-004', 'PAT-005', 'PAT-006']

for pid in PATIENTS:
    payload = json.dumps({'profile_versions': ['type_2_diabetes@1.0.0'], 'language': 'vi'}).encode()
    req = urllib.request.Request(
        f'http://127.0.0.1:8000/api/v1/patients/{pid}/reviews/generate',
        data=payload,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-Clinician-ID': 'dr_demo_01'
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
            cit_types = set()
            for sec in data.get('sections', []):
                for clm in sec.get('claims', []):
                    for c in clm.get('citations', []):
                        cit_types.add(c.get('source_type'))
            print(f'{pid} v{data.get("version")}: citation types = {sorted(cit_types)}')
    except Exception as e:
        print(f'{pid}: ERROR - {e}')

print('\nAll done!')
