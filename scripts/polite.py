"""예의 있게 가져오기: 모든 수집 스크립트는 이것만 쓴다.
- 민간 이벤트·공모전 모음 사이트(BLOCKED)는 아예 열지 않는다(데이터베이스권·저작권).
- 호스트마다 robots.txt를 먼저 읽고, 막힌 경로는 열지 않는다(robots.txt를 못 읽으면 그 호스트는 열지 않는다).
- 같은 호스트에는 최소 DELAY초 간격(robots.txt의 Crawl-delay가 더 길면 그걸 따른다).
표준 라이브러리만 쓴다(GitHub Actions에서 그대로 돈다)."""
import threading, time, urllib.request
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

UA = 'eventjup-bot/1.0 (+https://9yurrr.github.io/eventjup-data/)'
DELAY = 2.0
MAX_BYTES = 5_000_000
# 민간 모음 사이트: 후보 찾기용으로도 쓰지 않는다. 주소가 이 도메인이면 수집·등록 모두 거부.
BLOCKED = ('supertoday', 'haebom', 'wevity.com', 'thinkcontest.com', 'linkareer.com', 'contestkorea.com',
           'allforyoung.com', 'campuspick.com', 'eventhouse', 'events.kr', 'detizen.com', 'gongmo',
           'aifilmcontests', 'aicallsheet', 'holaworld', 'bhuntr.com')


class Blocked(Exception):
    pass


def blocked_domain(url):
    host = urlsplit(url).netloc.lower()
    return any(b in host for b in BLOCKED)


_robots, _last, _lock = {}, {}, threading.Lock()


def _rules(scheme, host):
    key = f'{scheme}://{host}'
    if key not in _robots:
        rp = RobotFileParser()
        try:
            req = urllib.request.Request(f'{key}/robots.txt', headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                rp.parse(r.read(200_000).decode('utf-8', 'replace').splitlines())
        except urllib.error.HTTPError as e:
            # robots.txt가 없으면(4xx) 전부 허용이 표준, 서버 오류(5xx)면 보수적으로 전부 금지
            rp.parse([] if 400 <= e.code < 500 else ['User-agent: *', 'Disallow: /'])
        except OSError:
            rp.parse(['User-agent: *', 'Disallow: /'])
        _robots[key] = rp
    return _robots[key]


def fetch(url):
    if blocked_domain(url):
        raise Blocked(f'모음 사이트라 열지 않음: {url}')
    p = urlsplit(url)
    with _lock:
        rp = _rules(p.scheme, p.netloc)
    if not rp.can_fetch(UA, url):
        raise Blocked(f'robots.txt가 막은 경로: {url}')
    wait = max(DELAY, float(rp.crawl_delay(UA) or 0))
    with _lock:  # 호스트별 간격 맞추기
        gap = wait - (time.time() - _last.get(p.netloc, 0))
        if gap > 0:
            time.sleep(gap)
        _last[p.netloc] = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ko'})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('응답이 5MB를 넘음')
    return raw


if __name__ == '__main__':  # 자체 점검: python scripts/polite.py
    assert blocked_domain('https://www.wevity.com/?c=find') and not blocked_domain('https://www.korea.kr/')
    for u in ('https://rss.blog.naver.com/kfdazzang.xml', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCixQ1UCmPoS2IEyJ4GeHjRA'):
        p = urlsplit(u)
        print(u[:60], '허용' if _rules(p.scheme, p.netloc).can_fetch(UA, u) else '막힘')
    try:
        fetch('https://www.wevity.com/')
    except Blocked as e:
        print('OK', e)
