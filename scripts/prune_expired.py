"""마감 지난 항목을 manual.json에서 지운다(예시 sample 항목은 유지). 사용: python scripts/prune_expired.py"""
import json, os, datetime
_r = os.path.join(os.path.dirname(__file__), '..')
# 데이터 저장소(eventjup-data)에선 맨 위 manual.json, 앱 폴더에선 src/data/manual.json
p = os.path.join(_r, 'manual.json') if os.path.exists(os.path.join(_r, 'manual.json')) else os.path.join(_r, 'src', 'data', 'manual.json')
today = datetime.date.today().isoformat()
rows = json.load(open(p, encoding='utf-8'))
keep = [r for r in rows if r.get('sample') or not r.get('end_at') or r['end_at'] >= today]
json.dump(keep, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'삭제 {len(rows) - len(keep)}건, 남음 {len(keep)}건')
