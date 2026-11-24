"""발굴 결과(JSON 배열 파일)를 검사해 src/data/manual.json에 합친다.
사용: python scripts/merge_found.py found.json [found2.json ...]
검사: 필수 칸, https 링크, 마감 안 지남, 금지 키워드(앱인토스 정책), id·url 중복."""
import json, os, re, sys, datetime

ROOT = os.path.join(os.path.dirname(__file__), '..')
_r = os.path.join(os.path.dirname(__file__), '..')
# 데이터 저장소(eventjup-data)에선 맨 위 manual.json, 앱 폴더에선 src/data/manual.json
MANUAL = os.path.join(_r, 'manual.json') if os.path.exists(os.path.join(_r, 'manual.json')) else os.path.join(_r, 'src', 'data', 'manual.json')
TODAY = datetime.date.today().isoformat()
# 앱인토스 출시 불가: 가상자산·금융상품·도박·앱 설치 유도
BANNED = re.compile(r'(코인|가상자산|NFT|에어드롭|airdrop|crypto|토큰|대출|카드\s?발급|계좌\s?개설|보험\s?가입|카지노|도박|베팅|앱\s?설치|설치\s?필수)', re.I)

ANSWERISH = re.compile(r'정답\s*근거|정답\s*[은는:=]|답\s*[:=]|정답\s*\d|댓글\s*문구\s*[:=]')

rows = json.load(open(MANUAL, encoding='utf-8'))
ids = {r['id'] for r in rows}
urls = {r['url'] for r in rows}
added, rejected = [], []

for path in sys.argv[1:]:
    for o in json.load(open(path, encoding='utf-8')):
        o.pop('answer', None); o.pop('comments', None)  # 정답·댓글 문구는 싣지 않는다(부정 응모 조장 방지)
        why = None
        if not all(o.get(k) for k in ('id', 'axis', 'title', 'host', 'url', 'end_at')):
            why = '필수 칸 없음'
        elif o['axis'] not in ('event', 'contest'):
            why = 'axis 이상'
        elif not str(o['url']).startswith('https://'):
            why = 'https 아님'
        elif o['end_at'] < TODAY:
            why = '마감 지남'
        elif BANNED.search(' '.join([o['title'], o.get('what', ''), ' '.join(o.get('summary') or []) if isinstance(o.get('summary'), list) else str(o.get('summary', ''))])):
            why = '정책 금지 키워드'
        elif o['id'] in ids or o['url'] in urls:
            why = '중복'
        if why:
            rejected.append((o.get('title', '?'), why))
            continue
        if isinstance(o.get('summary'), str):
            o['summary'] = [x.strip() for x in re.split(r'(?<=[.다])\s+', o['summary']) if x.strip()][:3]
        # 요약 문장에 섞인 정답·정답 근거도 버린다(2026-11-24 공공 퀴즈 3건에서 발견)
        o['summary'] = [x for x in (o.get('summary') or []) if not ANSWERISH.search(x)]
        o.setdefault('conditions', [])
        o.setdefault('minutes', 5)
        o.setdefault('what', '')
        rows.append(o)
        ids.add(o['id'])
        urls.add(o['url'])
        added.append(o['title'])

json.dump(rows, open(MANUAL, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'추가 {len(added)}건 / 제외 {len(rejected)}건')
for t, w in rejected:
    print(' 제외:', w, '|', t)
