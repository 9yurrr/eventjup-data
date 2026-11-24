"""발굴 결과(JSON 배열 파일)를 검사해 manual.json에 합친다.
사용: python scripts/merge_found.py found.json [found2.json ...]
      python scripts/merge_found.py --retag      # 기존 항목 전체에 조건 태그만 다시 붙임
      python scripts/merge_found.py --audit      # 태그 + 기존 항목 전체 원문 복사 검사
검사: 필수 칸, https, 민간 모음 사이트 주소 거부, 마감, 금지 키워드(앱인토스 정책), 중복,
      원문 복사(summary가 공식 페이지 문장을 20자 이상 그대로 옮겼으면 그 줄을 버림),
      정답·정답 근거 문장 삭제, 조건 태그 자동 분류(참가비·현장 참석·본인인증·지역 제한)."""
import json, os, re, sys, datetime, html

sys.path.insert(0, os.path.dirname(__file__))
import polite  # noqa: E402

_r = os.path.join(os.path.dirname(__file__), '..')
# 데이터 저장소(eventjup-data)에선 맨 위 manual.json, 앱 폴더에선 src/data/manual.json
MANUAL = os.path.join(_r, 'manual.json') if os.path.exists(os.path.join(_r, 'manual.json')) else os.path.join(_r, 'src', 'data', 'manual.json')
TODAY = datetime.date.today().isoformat()
# 앱인토스 출시 불가: 가상자산·금융상품·도박·앱 설치 유도
BANNED = re.compile(r'(코인|가상자산|NFT|에어드롭|airdrop|crypto|토큰|대출|카드\s?발급|계좌\s?개설|보험\s?가입|카지노|도박|베팅|앱\s?설치|설치\s?필수)', re.I)
ANSWERISH = re.compile(r'정답\s*근거|정답\s*[은는:=]|답\s*[:=]|정답\s*\d|댓글\s*문구\s*[:=]')
# 조건 태그 자동 분류. (태그, 찾을 말). 앱 SNS 필터(구독·댓글·팔로우·좋아요·태그·공유 필요)와 겹치지 않는 이름만 쓴다.
TAGS = [
    ('참가비 있음', re.compile(r'참가비|응모비|출품료|등록비|entry fee|registration fee', re.I)),
    ('현장 참석 필요', re.compile(r'현장\s?(참석|방문|참여|발표)|오프라인\s?(행사|참석|본선|발표)|대면|본선\s?발표|시상식\s?참석|in[- ]person|on-?site', re.I)),
    ('본인인증 필요', re.compile(r'본인\s?인증\s?(필요|필수|후)|휴대폰\s?인증|실명\s?인증|PASS\s?인증')),
    ('지역 제한', re.compile(r'(시민|도민|구민|군민|주민)만|(거주|재학|재직)(자|중인)\s?(만|한정|대상)|관내\s?(거주|소재)')),
]
NEG = re.compile(r'(본인\s?인증|참가비|출품료|응모비)\S{0,3}\s*(X|없|불필요|무료|free)|no (entry|registration) fee|free to enter', re.I)


def texts(o):
    s = o.get('summary') or []
    return ' '.join([o.get('title', ''), o.get('what', ''), ' '.join(s if isinstance(s, list) else [str(s)]), ' '.join(o.get('conditions') or [])])


def retag(o):
    t = texts(o)
    conds = list(o.get('conditions') or [])
    for tag, rx in TAGS:
        if tag in conds or not rx.search(t):
            continue
        if tag in ('본인인증 필요', '참가비 있음') and NEG.search(t):
            continue
        conds.append(tag)
    o['conditions'] = conds
    return o


def norm(s):
    return re.sub(r'\s+', '', s)


def copied_lines(o):
    """공식 페이지 본문과 20자 이상 똑같이 겹치는 summary 줄. 페이지를 못 열면(robots·로그인 등) 검사 생략."""
    try:
        page = polite.fetch(o['url']).decode('utf-8', 'replace')
    except Exception:
        return [], False
    body = norm(html.unescape(re.sub(r'<(script|style)[\s\S]*?</\1>|<[^>]+>', ' ', page)))
    bad = []
    for line in o.get('summary') or []:
        n = norm(line)
        if any(n[i:i + 20] in body for i in range(0, max(1, len(n) - 19))) and len(n) >= 20:
            bad.append(line)
    return bad, True


def main(paths):
    rows = json.load(open(MANUAL, encoding='utf-8'))
    ids, urls = {r['id'] for r in rows}, {r['url'] for r in rows}
    added, rejected, trimmed, unchecked = [], [], [], 0
    for path in paths:
        for o in json.load(open(path, encoding='utf-8')):
            for k in ('answer', 'comments', 'image', 'image_url', 'poster', 'thumbnail'):
                o.pop(k, None)  # 정답·댓글 문구, 남의 포스터·배너 이미지는 싣지 않는다
            why = None
            if not all(o.get(k) for k in ('id', 'axis', 'title', 'host', 'url', 'end_at')):
                why = '필수 칸 없음'
            elif o['axis'] not in ('event', 'contest'):
                why = 'axis 이상'
            elif not str(o['url']).startswith('https://'):
                why = 'https 아님'
            elif polite.blocked_domain(o['url']):
                why = '민간 모음 사이트 주소'
            elif o['end_at'] < TODAY:
                why = '마감 지남'
            elif BANNED.search(texts(o)):
                why = '정책 금지 키워드'
            elif o['id'] in ids or o['url'] in urls:
                why = '중복'
            if why:
                rejected.append((o.get('title', '?'), why))
                continue
            if isinstance(o.get('summary'), str):
                o['summary'] = [x.strip() for x in re.split(r'(?<=[.다])\s+', o['summary']) if x.strip()][:3]
            o['summary'] = [x for x in (o.get('summary') or []) if not ANSWERISH.search(x)]
            bad, checked = copied_lines(o)
            unchecked += not checked
            if bad:
                o['summary'] = [x for x in o['summary'] if x not in bad]
                trimmed.append((o['title'], len(bad)))
            o.setdefault('conditions', [])
            o.setdefault('minutes', 5)
            o.setdefault('what', '')
            rows.append(retag(o))
            ids.add(o['id'])
            urls.add(o['url'])
            added.append(o['title'])
    if not paths or '--retag' in sys.argv:
        rows = [retag(o) for o in rows]
    if '--audit' in sys.argv:  # 기존 항목 전체 원문 복사 검사(느림: 호스트마다 2초 간격)
        for o in rows:
            bad, checked = copied_lines(o)
            unchecked += not checked
            if bad:
                o['summary'] = [x for x in o['summary'] if x not in bad]
                trimmed.append((o['title'], len(bad)))
    json.dump(rows, open(MANUAL, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'추가 {len(added)}건 / 제외 {len(rejected)}건 / 원문 복사 줄 삭제 {len(trimmed)}건 / 복사 검사 못 함 {unchecked}건')
    for t, w in rejected:
        print(' 제외:', w, '|', t)
    for t, n in trimmed:
        print(f' 복사 줄 {n}개 삭제 |', t)


if __name__ == '__main__':
    main([a for a in sys.argv[1:] if not a.startswith('--')])
