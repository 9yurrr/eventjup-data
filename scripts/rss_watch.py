"""공식 계정 RSS 감시: feeds.txt의 블로그·유튜브 새 글 중 이벤트로 보이는 것만 candidates.json에 모은다.
후보일 뿐이다 — manual.json에 넣기 전에 원 게시물을 열어 마감·경품·참여 방법을 확인한다(CLAUDE.md 3번 규칙).

  python scripts/rss_watch.py          # 후보 갱신 (최근 DAYS일, manual.json에 이미 있는 URL 제외)
  python scripts/rss_watch.py --seed   # manual.json의 블로그 아이디·유튜브 채널을 feeds.txt에 추가하고 끝

feeds.txt 한 줄: blog:<네이버 아이디> | yt:<채널 ID UC...> | https://...(그 밖의 RSS). # 뒤는 메모.
표준 라이브러리만 쓴다(GitHub Actions에서 그대로 돈다)."""
import json, re, sys, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDS, MANUAL, OUT = ROOT / 'feeds.txt', ROOT / 'manual.json', ROOT / 'candidates.json'
DAYS = 7
KST = timezone(timedelta(hours=9))
UA = {'User-Agent': 'Mozilla/5.0 (compatible; eventjup-rss/1.0)', 'Accept-Language': 'ko'}
# 제목·요약에 이 중 하나가 있으면 후보. 너무 넓으면 여기서 줄인다.
HIT = re.compile(r'이벤트|EVENT|추첨|경품|증정|퀴즈|QUIZ|설문|공모|기프티콘|상품권|당첨|댓글 남기|구독자', re.I)
# 결과 발표·지난 이벤트 안내는 뺀다.
SKIP = re.compile(r'당첨자 발표|당첨자 안내|당첨자 공지|결과 발표|발표 안내|수상작|마감되었|종료되었|종료 안내')
YT = 'http://www.youtube.com/xml/schemas/2015'
ATOM = 'http://www.w3.org/2005/Atom'


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def feed_url(line):
    kind, _, v = line.partition(':')
    if kind == 'blog':
        return f'https://rss.blog.naver.com/{v}.xml', f'https://blog.naver.com/{v}'
    if kind == 'yt':
        return f'https://www.youtube.com/feeds/videos.xml?channel_id={v}', f'https://www.youtube.com/channel/{v}'
    return line, line


def strip(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()


def parse(raw):
    """(제목, 링크, 시각, 요약, 출처이름) 목록. RSS 2.0(네이버)·Atom(유튜브) 둘 다."""
    root = ET.fromstring(raw)
    out = []
    if root.tag == 'rss':
        src = strip(root.findtext('channel/title'))
        for it in root.iter('item'):
            try:
                when = parsedate_to_datetime(it.findtext('pubDate'))
            except (TypeError, ValueError):
                continue
            link = re.sub(r'\?.*$', '', it.findtext('link') or '')  # 네이버 링크의 ?fromRss... 꼬리 제거
            out.append((strip(it.findtext('title')), link, when, strip(it.findtext('description'))[:200], src))
    else:
        src = strip(root.findtext(f'{{{ATOM}}}title'))
        for e in root.iter(f'{{{ATOM}}}entry'):
            when = datetime.fromisoformat(e.findtext(f'{{{ATOM}}}published'))
            link = e.find(f'{{{ATOM}}}link').get('href')
            desc = e.findtext('.//{http://search.yahoo.com/mrss/}description') or ''
            out.append((strip(e.findtext(f'{{{ATOM}}}title')), link, when, strip(desc)[:200], src))
    return out


def lines():
    return [l.split('#')[0].strip() for l in FEEDS.read_text(encoding='utf-8').splitlines() if l.split('#')[0].strip()]


def seed():
    have = set(lines())
    rows = json.loads(MANUAL.read_text(encoding='utf-8'))
    new = []
    for x in rows:
        u = x.get('url', '')
        m = re.match(r'https://(?:m\.)?blog\.naver\.com/([A-Za-z0-9_-]+)/\d+', u)
        if m and f'blog:{m.group(1)}' not in have:
            new.append((f'blog:{m.group(1)}', x.get('host', '')))
        elif re.match(r'https://(www\.)?youtube\.com/watch|https://youtu\.be/', u):
            try:  # 영상 페이지에서 채널 ID를 찾는다
                c = re.search(rb'"channelId":"(UC[\w-]{22})"', fetch(u))
            except OSError:
                c = None
            if c and f'yt:{c.group(1).decode()}' not in have:
                new.append((f'yt:{c.group(1).decode()}', x.get('host', '')))
        have.update(k for k, _ in new)
    with FEEDS.open('a', encoding='utf-8') as f:
        for k, host in new:
            f.write(f'{k}  # {host}\n')
    print(f'feeds.txt +{len(new)}건 (전체 {len(have)})')


def run():
    known = {x.get('url', '').rstrip('/') for x in json.loads(MANUAL.read_text(encoding='utf-8'))}
    since = datetime.now(KST) - timedelta(days=DAYS)

    def one(line):
        url, home = feed_url(line)
        try:
            return line, home, parse(fetch(url)), None
        except Exception as e:  # 피드 하나가 죽어도 나머지는 돈다
            return line, home, [], f'{type(e).__name__}: {e}'[:120]

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, lines()))
    cands, errors, empty = [], [], []
    for line, home, items, err in res:
        if err:
            errors.append({'feed': line, 'error': err})
            continue
        if not items:
            empty.append(line)  # 아이디가 틀렸거나 비공개 — 정리 대상
        for title, link, when, desc, src in items:
            text = f'{title} {desc}'
            if when < since or link.rstrip('/') in known or not HIT.search(text) or SKIP.search(title):
                continue
            cands.append({'title': title, 'url': link, 'posted': when.astimezone(KST).strftime('%Y-%m-%d %H:%M'),
                          'source': src or home, 'feed': line, 'snippet': desc})
    cands.sort(key=lambda c: c['posted'], reverse=True)
    OUT.write_text(json.dumps({'updated': datetime.now(KST).strftime('%Y-%m-%d %H:%M'), 'days': DAYS, 'feeds': len(res),
                               'candidates': cands, 'empty_feeds': empty, 'errors': errors},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'피드 {len(res)}개 → 후보 {len(cands)}건, 빈 피드 {len(empty)}, 오류 {len(errors)}')


if __name__ == '__main__':
    seed() if '--seed' in sys.argv else run()
