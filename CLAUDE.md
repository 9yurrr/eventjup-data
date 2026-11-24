# eventjup-data

「이벤트줍」 앱(앱인토스 미니앱)이 열릴 때 받아 가는 이벤트·공모전 목록이다.
앱은 https://9yurrr.github.io/eventjup-data/manual.json 을 읽는다. 이 저장소의 main에 올라간 manual.json이 곧 사용자 화면이다.
한국어로 일한다.

## 항목 형식 (manual.json 배열 한 칸)
{"id":"ev-..."|"ct-...", "axis":"event"|"contest", "title", "host", "what"(경품/상금 한 줄, 1등 경품을 앞에), "prize_value"(최고 경품 1개 원화 숫자, 모르면 생략), "minutes"(예상 소요분), "conditions":["본인인증 X","로그인 X","이름·휴대폰 입력","구독 필요","댓글 필요","팔로우 필요","해외 참가 가능","영어","AI 허용" 등], "end_at":"YYYY-MM-DD", "announce_at"(확인 시), "summary":["최대 3줄"], "url"(주최 측 공식 페이지)}
앱은 conditions로 필터를 나눈다: "~ 필요"(구독·댓글·팔로우·좋아요·태그·공유)가 있으면 SNS 참여, "해외"가 들어가면 해외.

## 주간 갱신 순서
1. `python scripts/prune_expired.py` — 마감 지난 항목 삭제.
2. 매달 반복되는 공공 퀴즈 확인: 국회예산정책처 재정퀴즈(https://www.nabo.go.kr/ko/fiscalQuiz/quiz.do?key=2507040020), KOSIS 퀴즈(https://kosis.kr/eventLink.jsp), 지표누리 퀴즈(https://www.index.go.kr/unity/potal/Event.do). 새 달 회차가 열렸으면 새 id로 추가. 정답·댓글 문구는 절대 싣지 않는다(answer·comments 칸 금지, 부정 응모 조장 방지) — summary에는 참여 방법만.
3. 새 항목 발굴 — 세 갈래를 각각 서브에이전트(Agent 도구, 병렬)로 돌린다:
   (a) 국내 기업·공공기관·지자체 경품 이벤트(퀴즈·설문·투표)와 상금 있는 일반인 공모전
   (b) 유튜브 구독·댓글, 인스타·블로그 SNS 경품 이벤트(공식 원 게시물만)
   (c) 한국에서 참가 가능한 해외 대회·경품(Devpost, Kaggle 등, 공식 Official Rules에 한국 또는 worldwide 명시, 참가비 없음). 1USD=1,400원 환산, prize_value는 1등 상금.
   공통 규칙(서브에이전트 프롬프트에 그대로 넣는다): 마감이 오늘 이후일 것. 모음 사이트(슈퍼투데이·이벤트하우스·events.kr·링커리어·위비티 등)는 후보 찾기용으로만 쓰고, 반드시 주최 측 공식 페이지를 직접 열어(WebFetch/WebSearch) 마감·경품·참여 방법을 확인한 것만 남긴다. 공식 페이지를 열어 확인하지 못한 항목은 넣지 않는다. 제외: 앱 설치 필수, 구매·영수증 필수, 금융상품(대출·카드·보험·계좌) 가입, 코인·가상자산·NFT·에어드롭, 도박·경륜·경정·복권 등 사행성, 참가비, 특정 지역 주민·직군 한정, 미국 거주자 한정. 정보를 지어내지 말고 확인 못 한 필드는 뺀다. 어떤 폼 제출·로그인·댓글·구독도 하지 않고 개인정보를 입력하지 않는다. 결과는 위 형식의 JSON 배열로 반환. 이미 있는 항목(id·title 목록을 함께 준다)은 다시 찾지 않는다.
   매번 먼저 훑을 공식 출처(서브에이전트 프롬프트에 함께 준다. 목록 페이지가 안 열리면 기존 항목 URL 형식을 참고해 검색으로 찾는다):
   - 모두의 공모전·설문 modu.go.kr (상세 형식: https://modu.go.kr/fron/jdgmn/jdgmnView.do?menu_id=393&qustnr_id=...)
   - 대한민국 구석구석 Fun이벤트 korean.visitkorea.or.kr (상세 형식: /detail/event_detail.do?cotid=...)
   - 보건복지부 홍보 갤러리 https://www.mohw.go.kr/gallery.es?mid=a10314000000&bid=0015 , 한국소비자원 kca.go.kr, 서울시 내 손안에 서울 news.seoul.go.kr·mediahub.seoul.go.kr/missions
   - Devpost(devpost.com 공개 API), DrivenData, Kaggle — 해외(c)
   네이버 블로그: WebFetch는 blog.naver.com을 못 연다. Bash로 연다 —
     검색(최신순): curl -s -A 'Mozilla/5.0 (iPhone)' "https://m.search.naver.com/search.naver?where=m_blog&nso=so:dd&query=<URL인코딩 검색어>" | grep -o 'https://m.blog.naver.com/[A-Za-z0-9_]*/[0-9]*' | sort -u
     본문: curl -s -A 'Mozilla/5.0 (iPhone)' "https://m.blog.naver.com/<아이디>/<글번호>" 후 태그 제거해서 읽는다.
     검색어 예: "공식 블로그 이웃추가 이벤트", "댓글 이벤트 기프티콘 추첨", "퀴즈 이벤트 정답 댓글" + 이번 달. 기관·기업 공식 블로그(아이디가 기관/브랜드) 원 게시물만 넣고, 개인 블로그의 소개 글은 후보 찾기용으로만 쓴다. manual.json의 url은 https://blog.naver.com/<아이디>/<글번호> 형식으로 적는다.
   인스타그램은 로그인이 필요해 클라우드에서는 열지 않는다(로컬 보조 작업이 맡는다).
4. 각 결과를 임시 JSON 파일로 저장하고 `python scripts/merge_found.py <파일들>` 로 합친다(필수 칸·https·마감·정책 금지어·중복 검사). 넣기 전에 직접 훑어서 정답이 적힌 요약, 총상금을 prize_value에 넣은 것 등은 고친다.
5. `python -c "import json;json.load(open('manual.json',encoding='utf-8'))"` 로 JSON이 깨지지 않았는지 확인한다.
6. manual.json만 커밋해서 main에 push한다. 커밋 메시지: `data: YYYY-MM-DD 주간 갱신 (+추가 -삭제)`. 다른 파일은 고치지 않는다.

마지막 보고: 삭제 건수, 추가 건수(이벤트/공모전, 국내/SNS/해외), 제외한 후보와 이유 상위 5개, 이번 주 마감 임박 상위 5건.
