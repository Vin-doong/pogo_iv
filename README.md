# Pokemon GO 개체값 리그 랭커 + 일정/메타 통합 도구

Pokemon GO의 개체값(IV) 분석 + PvP 메타 + PvE 카운터 + 게임 일정(레이드/이벤트/알/리서치)을 한 화면에서 보는 Python GUI/CLI 도구입니다.

## 기능

총 13개 탭, **PvP → PvE → 공통** 순으로 정렬(시작 탭 = PvP 분석): **PvP 3 + PvE 4 + 공통 6 (대시보드 1 + 타입 1 + 일정 4)**

## PvP (3개 탭)
- **PvP 분석** — 포켓몬 + IV(공격/방어/HP) 입력 → 각 리그 최적 레벨/순위/CP/스탯곱 + 어필러 등급 자동 판정. 진화 후 CP 미리보기 + 현재 일정상 "입수 경로" 한 줄 표시. **🔍 인게임 검색** 줄에 현재 리그 베스트 IV 검색 문자열(복사 버튼) + **개체값 영향도 안내**(레이드선 무의미·마스터리그만 중요). CLI: `--search <포켓몬> [--league]`
- **PvP 비교** — 두 포켓몬을 IV/Lv/리그별로 나란히 비교 (타입·약점·내성·리그별 점수/순위·추천 무브셋·매치업 배율). 입력 시 자동 갱신. 마지막에 **✦ 종합 판단** — 메타 점수 우위 + 매치업 공격 효율(eDPS) 우위로 "어느 쪽이 더 좋은지" 자동 판정 (정밀 비교는 "PvPoke 매치업으로 열기" 버튼)
- **PvP 메타** — 리그별 상위 순위 + 검색 필터. 상단 라디오로 **개별 메타 ↔ 팀 메타** 토글 (팀 메타 = PvPoke 메타 팀의 8개 역할 슬롯 + 추천 무브셋 + 선택률). 예전 별도 "팀 메타" 탭을 한 탭 안에 통합

## PvE (4개 탭)
- **PvE 카운터** — 보스 → 카운터 TOP N (표시 개수 20/50/100/200/전체 선택). 카운터 순위는 **보스 실제 무브셋 + 공격자 타입 상성**으로 받는 피해(TDO)를 계산해, 보스 기술에 약점/내성인 카운터를 정확히 구분
- **PvE 로켓** — 로켓단 조무래기 카운터 (대사 입력 시 타입 자동 추정) + **로켓 라인업 통합** (보스/간부/조무래기 슬롯별 가능 포켓몬, 색다른 ★ / 획득가능 💎). 라인업 행 클릭 시 같은 탭 아래쪽 카운터 자동 갱신, 더블클릭 시 첫 슬롯 포켓몬으로 좌측 선택
- **PvE 투자** — "뭘 키울까" 가이드. 상단 라디오로 **타입별 딜러 ↔ 내 즐겨찾기 투자** 토글. *타입별 딜러* = 18타입별 범용 PvE 딜러 랭킹(그 타입에 약점인 보스 기준 DPS 순, 메가/그림자/전설 필터). *즐겨찾기 투자* = 보유(★) 포켓몬을 각자의 최고 화력 역할 + 그 타입 내 순위로 평가해 **★★★ 최우선 ~ — 비주력** 투자 등급 부여. CLI: `--attackers <타입>`, `--invest`
- **PvE 다맥** — 다이맥스/거다이맥스 맥스배틀 추천: 최우선 S급 어택커 + 18타입별 추천 어택커(맥스무브 포함) + 탱커(0.5초 평타 기준) + 힐러(HP 기준). 맥스배틀은 일반 레이드와 역학이 달라 별도 큐레이션(출처 GO Hub/doctorpokegogo, 표만 갱신하면 됨). CLI: `--maxtier`

## 공통 (6개 탭)

### 오늘 할 일 (대시보드)
- **오늘 할 일** — 맨 위에 **일일/주간 루틴 체크리스트**(무료 레이드 패스·필드 리서치·선물/반짝교환·버디 하트·체육관 점령·맥스 파티클·데일리 인센스·모험싱크·리서치 돌파·스포트라이트 등). 체크 상태는 저장되며 매일/매주 자동 초기화. 이어서 진행 중/곧 시작 이벤트 + 주목 레이드(5★·메가·엘리트) + **🎯 내 즐겨찾기로 잡는 주목 레이드**(보스별 상성 카운터 후보) + 알·리서치 요약. 맨 아래 **🛒 박스 효율 계산기**(단품 대비 할인율 판정) + **⚛️ 합체/변신 에너지 계산기**(네크로즈마 등, `80+10n` 공식)
- CLI: `--routine`(루틴), `--fusion [꾸러미수]`(합체 에너지)

### 타입 상성
- **타입 상성** — 18×18 풀 매트릭스 (PvP 분석 탭의 약점/내성 요약과 별개로 전체 조회용)

### 게임 일정 (4개 탭)
- **레이드 일정** — 글로벌(LeekDuck) + 한국(pogomate) 통합. 🌐 글로벌 / 🇰🇷 한국만 / ✓ 양쪽 출처 표시
- **이벤트** — 진행 중/예정 이벤트 캘린더 + 보너스/스폰/보스 상세. **이벤트 이름 한글 자동 번역** (커뮤니티 데이/스포트라이트 아워/레이드/맥스 먼데이/GBL 등 규칙 기반)
- **알 부화** — 거리별 풀(1~12km), 색이 다른/모험 모드/지역 한정 필터
- **리서치** — 필드 리서치 태스크 한글 자동 번역 + 보상 포켓몬

### 공통
- 한글 포켓몬 이름 지원 (그림자/메가/알로라/가라르/히스이/팔데아 폼)
- 즐겨찾기 (★), 창 크기/리그 선택 저장
- **즐겨찾기 백업/복원** — JSON 파일로 내보내기/가져오기 (가져올 때 병합/덮어쓰기 선택)
- **강화 비용 표시** — 현재 레벨 → 목표 레벨까지 필요한 별의모래/사탕/XL사탕 (공식 수치)
- 좌측 포켓몬 검색 (substring + 폼 필터 + 700ms 폴링)
- 스프라이트 자동 캐싱
- 모든 일정 탭에 신선도 라벨 (`갱신: 3시간 전` 같은 형식)
- 모든 트리뷰 컬럼 정렬 (헤딩 클릭) + 스크롤바

## 실행

```bash
# GUI (기본)
python pogo_iv.py

# 대화형 CLI
python pogo_iv.py --cli

# 단발성 조회
python pogo_iv.py 마릴리 0 15 15
python pogo_iv.py "메가 갸라도스" 15 15 15 --max-level 50

# 제일 좋은 개체값 조회 (개체값 없이 이름만)
python pogo_iv.py 마릴리                       # 리그별 최고 개체값(랭크 #1) 표
python pogo_iv.py 마릴리 --league 슈퍼리그      # 슈퍼리그 상위 개체값 목록
python pogo_iv.py 마릴리 --league 슈퍼리그 --top 20
# (대화형에서도 개체값 칸을 비우면 리그별 최고, 리그명을 넣으면 그 리그 상위 목록)

# PvE 투자 가이드
python pogo_iv.py --attackers 불꽃          # 불꽃 타입 범용 PvE 딜러 랭킹 (DPS 순)
python pogo_iv.py --attackers dragon -n 30  # 영문 타입 + 개수 지정
python pogo_iv.py --invest                  # 즐겨찾기 포켓몬의 PvE 투자 우선순위
python pogo_iv.py --routine                 # 매일/주간 챙길 포고 루틴 체크리스트
python pogo_iv.py --maxtier                  # 다이맥스/거다이맥스 배틀 추천 티어
python pogo_iv.py --search 마릴리             # 베스트 개체값 인게임 검색 문자열 (리그별)
python pogo_iv.py --search 마릴리 --league 슈퍼리그
python pogo_iv.py --fusion                   # 합체/변신 에너지 공식·표
python pogo_iv.py --fusion 36                # 보상 꾸러미 36개 → 기대 에너지 추정
```

Windows에서는 `PogoTool.bat`을 더블클릭하여 실행할 수 있습니다. (바탕화면 `PogoTool` 바로가기는 몬스터볼 아이콘으로 생성됨.) 실행 중 창·작업표시줄 아이콘은 `icon.ico`(몬스터볼)를 사용합니다.

## 디스코드 봇 (자연어 인터페이스)

같은 도구를 디스코드에서 자연어로 쓸 수 있다. GUI/CLI 없이 멘션 또는 DM 으로 질문 → Gemini 가 의도 파악 후 적절한 함수 호출 → 답변.

예시:
- `@봇 라프라스 어디서 잡아?` → `find_acquisition` 호출
- `@봇 메가 갸라도스 카운터 10마리` → `top_counters` 호출
- `@봇 슈퍼리그 메타 보여줘` → `league_meta` 호출
- `@봇 마릴리 0 15 15 어때?` → `analyze_pokemon` 호출
- `@봇 오늘 한국 5성 뭐 떠?` → `current_raids(region="kr")` 호출
- `@봇 불꽃 딜러 추천` → `type_attackers` 호출
- `@봇 뭐 키울까?` → `investment_priority`(즐겨찾기 기반) 호출
- `@봇 다이맥스 탱커 추천` → `max_battle_tier` 호출
- `@봇 마릴리 베스트 개체값 검색어` → `search_string` 호출
- `@봇 네크로즈마 합체 에너지 몇 번?` → `fusion_energy` 호출
- `@봇 데일리 루틴 알려줘` → `daily_routine` 호출

### 설치

```bash
pip install -r requirements-bot.txt
```

### 환경 변수 (`.env`)

`.env.example` 을 복사해서 `.env` 로 이름 바꾼 뒤 두 값을 채운다:

- **GEMINI_API_KEY** — [Google AI Studio](https://aistudio.google.com/apikey) 에서 발급. 무료 티어 (Gemini 2.5 Flash, 1,500 RPD, 신용카드 불필요)
- **DISCORD_BOT_TOKEN** — [Discord Developer Portal](https://discord.com/developers/applications) → New Application → Bot → Reset Token. **MESSAGE CONTENT INTENT** 토글 ON 필수
- (선택) **ALLOWED_CHANNEL_IDS** — 특정 채널에서만 응답시키려면 콤마 구분 ID

### 실행

```bash
python bot.py
```

봇이 응답하려면 서버에 초대돼있어야 한다. OAuth2 URL Generator 에서 `bot` + `applications.commands` 스코프 + `Send Messages`/`Read Message History`/`Embed Links` 권한으로 초대 링크 생성.

### Gemini 무료 티어 한도

- 1분당 15회 요청, 1일 1,500회 요청, 분당 100만 토큰
- 봇 1회 응답 ≒ Gemini 1~2 호출 → 개인+친구 사용에는 충분
- 프롬프트/응답은 모델 학습에 사용될 수 있음 (포켓몬 데이터만 다루므로 무관)

## 데이터 출처

이 도구는 아래 공개 데이터 소스에서 파일을 자동으로 다운로드해 로컬에 캐싱합니다.

| 데이터 | 용도 | URL |
|--------|------|-----|
| `gamemaster.json` | 포켓몬 종족값/기술 정보 (pvpoke 기준) | `https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster.json` (fallback: `https://pvpoke.com/data/gamemaster.json`) |
| `rankings-{500,1500,2500,10000}.json` | 리그별 메타 랭킹 | `https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/all/overall/rankings-{cap}.json` |
| `korean_names.csv` | 포켓몬 다국어(한글) 이름 | `https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv` |
| `moves.csv` | 기술 메타데이터 | `https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/moves.csv` |
| `move_names.csv` | 기술 다국어(한글) 이름 | `https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/move_names.csv` |
| `sprites/*.png` | 포켓몬 스프라이트 이미지 | `https://play.pokemonshowdown.com/sprites/gen5/{name}.png` |
| `raids.json` | 글로벌 활성 레이드 보스 | `https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.json` (LeekDuck 미러, 10분 갱신) |
| `kr_raids.json` | 한국 활성 레이드 보스 (스크래핑) | `https://pogomate.com/raids` (한국 일정, 정규식 파싱) |
| `events.json` | 이벤트 일정 (커뮤니티 데이/스포트라이트/Max Monday 등) | `https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json` |
| `eggs.json` | 거리별 알 부화 풀 | `https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/eggs.json` |
| `research.json` | 필드 리서치 태스크/보상 | `https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/research.json` |
| `rocket_lineups.json` | GO 로켓단 보스/간부/조무래기 라인업 | `https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/rocketLineups.json` |
| `team_meta-{cup_id}-{cap}.json` | 리그별 메타 팀 슬롯 (8개 역할 + 추천 포켓몬) | `https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/training/teams/{cup_id}/{cap}.json` |

### 캐시 정책
- `gamemaster.json`, `rankings-*.json`, `eggs.json`, `team_meta-*.json`: **7일 경과 시 자동 재다운로드**
- `raids.json`, `kr_raids.json`, `events.json`, `research.json`, `rocket_lineups.json`: 자주 바뀜 → **1일 경과 시 자동 재다운로드**
- 한국어/기술명 CSV: 거의 안 바뀜 → **90일 경과 시 자동 재다운로드**
- 스프라이트: 한 번 다운로드 후 영구 캐시
- 각 일정 탭의 [갱신] 버튼은 만료 무시하고 즉시 다운로드

## 크레딧

이 도구는 아래 오픈 데이터/프로젝트를 활용합니다.

- [pvpoke](https://github.com/pvpoke/pvpoke) — 포켓몬 GO PvP 시뮬레이터, 랭킹 데이터, 메타 팀 슬롯 데이터
- [PokeAPI](https://github.com/PokeAPI/pokeapi) — 포켓몬 다국어 이름 및 기술 메타데이터
- [Pokémon Showdown](https://play.pokemonshowdown.com/) — 포켓몬 스프라이트 이미지
- [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck) / [LeekDuck](https://leekduck.com/) — 글로벌 레이드/이벤트/알/리서치 일정
- [pogomate.com](https://pogomate.com/) — 한국 레이드 일정 (지역 차이 보완)

Pokémon 및 관련 상표는 Nintendo / Game Freak / The Pokémon Company의 자산입니다. 이 프로젝트는 비영리 팬 메이드 도구입니다.

## 요구 사항

- Python 3.10+ (표준 라이브러리만 사용, tkinter 필요)
- 첫 실행 시 인터넷 연결 (데이터 다운로드용)

## 변경 이력

### 2026-06-20
- **이벤트 이름 한글화 — 규칙 기반 번역기 추가** (`_translate_event_name`)
  - 리서치 태스크 번역과 같은 방식(정규식 규칙 + 포켓몬명 자동 변환)으로 이벤트 제목을 한글화
  - 패턴: 커뮤니티 데이 / 스포트라이트 아워 / N성·메가·그림자 레이드 / 레이드 데이·아워·위크엔드 / 맥스 먼데이(다이맥스·거다이맥스) / 갈림길(Choose Your Path) / GBL 리그·시즌 키워드 치환
  - 예: `Frigibax Community Day` → `드니차 커뮤니티 데이`, `Necrozma in 5-star Raid Battles` → `5성 레이드: 네크로즈마`, `Celesteela and Kartana Raid Hour` → `철화구야 · 종이신도 레이드 아워`
  - 이벤트 탭(이름 컬럼) + 오늘 할 일 대시보드 양쪽 적용. 패턴/포켓몬 없는 일회성 제목은 영문 유지(정직한 fallback)
  - `EVENT_TYPE_KO` 에 `choose-your-path`→갈림길, `max-mondays`→맥스 먼데이 보강

### 2026-06-19
- **탭 정리 (14 → 11) + 신규 기능 3종**
  - **제거**: PvP IV검색 / PvP CP→IV / PvE DPS — 사용 빈도 낮은 탭 정리 (관련 함수·UI 일괄 제거, 385줄 감소)
  - **PvP 메타 + 팀 메타 통합** — 별도였던 두 탭을 한 탭 안 라디오 토글(개별 메타 ↔ 팀 메타)로 합침. `team_meta_tab` 을 `meta_tab` 내부 컨테이너 프레임 자식으로 재구성
  - **신규: 즐겨찾기 백업/복원** — `_export_favorites`(파일로 저장) / `_import_favorites`(파일에서 가져오기, 병합·덮어쓰기 선택). 데이터 갱신 버튼 옆 버튼 2개
  - **신규: 강화 비용 표시** — 현재→목표 레벨 별의모래/사탕/XL사탕 누적 비용. `POWER_UP_COST` 테이블을 공식 수치(Bulbapedia 교차검증)로 교체 (기존 부정확한 값 수정, 40→50 = 모래 250,000 / XL 296)
  - **신규: 오늘 할 일 대시보드** — 진행 중/곧 시작 이벤트 + 주목 레이드(5★·메가·엘리트) + 알·리서치 요약 타임라인. `notebook.insert(6, …)` 로 레이드 일정 앞 배치

### 2026-06-18
- **안정성/정확도 보강**
  - **데이터 갱신 경쟁 상태 제거** — 워커 스레드는 디스크 다운로드만(`download_all_data` + `compute_leagues`, 전역 `LEAGUES` 비변형), 인메모리 재구성은 메인 스레드에서. `refresh_in_flight` 플래그로 버튼·Ctrl-R 중복 실행 차단
  - **봇 크래시 수정** — Gemini 응답에서 non-text 파트 섞일 때 `ValueError` 나던 것을 파트별 텍스트 결합으로 수정. `inspect.signature` 기반 `_clean_args` 로 미지의 인자 필터링·int 강제. `_last_request` 프루닝, 전송 루프 `discord.HTTPException` 가드
  - **카운터 정확도** — `attacker_dps_vs` 에 `boss_base_atk` 파라미터 추가(보스 실제 공격 종족값 반영), `sid_to_pokemon` 딕셔너리로 선형 스캔 3곳 제거

### 2026-05-25
- **IV 랭킹 기본 최대 레벨 51 → 50 으로 변경** (PvPoke·pvpivs·pokemongo-get 등 주요 사이트와 동일 기준)
  - 원인: 기존엔 Best Buddy 보너스(+1 레벨) 가 적용된 Lv51 을 캡으로 잡고 있어서, 최적 레벨이 캡 부근인 포켓몬 (예: 탱탱겔 하이퍼리그) 의 rank 1 IV 가 타 사이트와 달라지는 경우 발생
    - 탱탱겔 UL: 기존 (4,15,13) Lv51 → **(6,14,15) Lv50** (PvPoke 와 일치)
    - 플라제스 같이 최적 레벨이 캡 한참 아래인 포켓몬은 동일 (Lv29 → 그대로)
  - 신규 모듈 상수 `DEFAULT_MAX_LEVEL = 50.0`, `DEFAULT_MAX_IDX = 98` 도입, `_get_ranking_for` / 역방향 IV검색 캐시가 이걸 사용
  - CLI `--max-level` 기본값 51 → 50, help 문구에 Best Buddy 시 `--max-level 51` 안내 추가
  - Best Buddy 실제로 만든 포켓몬은 사용자가 `--max-level 51` 로 직접 지정

### 2026-05-20
- **레이드 일정 탭 — "데이터 업데이트" 누를 때 이전 보스 누적 표시 버그 수정**
  - 원인: `_populate_raid_sched()` 만 다른 `_populate_*` 함수들과 달리 트리 clear 없이 `insert` 만 수행 → `do_data_refresh` 가 두 번째로 호출하면 기존 행 위에 새 행이 쌓여 옛 보스가 같이 보임
  - 수정: 함수 진입부에 `get_children() → delete` 추가 (다른 populate 들과 동일한 패턴)
  - 다른 모든 Treeview 갱신 함수 (refresh_meta/compare/counters/pve_dps/rocket/reverse/team_meta, _populate_events/eggs/research/rocket, fast/charged/summary/cp_tree) 는 이미 clear-before-insert 패턴이라 영향 없음

### 2026-05-19
- **데이터 업데이트 버튼 — 진짜 "전체 갱신" 으로 수정**
  - 기존: gamemaster/랭킹/일정 파일은 force 다운로드했지만 **뷰는 일부만 갱신** (메타·레이드 보스 콤보) → 일정/이벤트/알/리서치/로켓 탭은 탭 전환 또는 개별 갱신 버튼 누르기 전까지 옛 데이터 표시
  - 수정: `do_data_refresh` 가 다운로드 후 **모든 탭 뷰 + 신선도 라벨** 일괄 갱신
    - 일정 4탭 (`_populate_*` + `_update_*_fresh`): 레이드/이벤트/알/리서치
    - PvE/PvP 탭 (`refresh_*`): 카운터·DPS·로켓·메타·비교·역검색·팀 메타
  - 팀 메타 (`training/teams/all/{cap}.json`) 도 빌트인 4리그 모두 force 다운로드 추가 (기존엔 누락)
  - 갱신 중 좌측 하단 라벨이 "⟳ 갱신 중…" 으로 표시, 완료 후 다이얼로그 + 신선도 라벨 갱신
- **신규 탭: PvP 비교** (PvP 분석 다음, idx=1)
  - 두 포켓몬을 IV/Lv/리그별로 나란히 비교. 좌우 LabelFrame 패널 + 공유 리그 콤보 + 비교 표 (항목 / A / B 3컬럼 Treeview)
  - 표시 항목: 종족값 · 타입 · 약점/내성 · 리그별 (Lv·CP·SP, 메타 순위, IV순위, 베스트대비) — 빌트인 4리그 모두 · 선택 리그의 추천 무브셋 (PvPoke `rankings.moveset`) · A 무브 → B 매치업 / B 무브 → A 매치업 (배율 + 💥/🛡 강조)
  - 모든 입력(검색·IV 스핀박스·Lv 콤보·리그)에 `trace_add` + 180ms 디바운스 → 자동 갱신
  - 하단 "PvPoke 매치업으로 열기" 버튼 → `https://pvpoke.com/battle/{cap}/{sidA}/{sidB}/11/` (1실드)
  - **✦ 종합 판단** (선택 리그 기준 2행 + 참고 노트):
    - 메타 점수 우위: PvPoke 점수 차 1.0pt 이상 시 "← 우세", 이내면 "(비슷)"
    - 매치업 공격 효율 우위: 양쪽 eDPS 비율이 ±10% 밖이면 "← 유리", 이내면 "(비슷)" — 동일 baseline(boss_cpm=0.79) 사용한 상대 비교
    - 참고 노트: 무브 회전·실드·스왑 어드밴티지는 휴리스틱 한계, 정밀 시뮬은 PvPoke 권장 명시
  - 재사용: `analyze_pokemon`, `best_moveset_vs`, `TYPE_CHART`, `TYPE_KO`, `prettify_move`, `make_searchable_combo`
  - 탭 수 13 → 14 (PvP 그룹이 5 → 6)
  - 보정: `team_meta_tab` insert 인덱스 4 → 5 (PvP 비교 추가로 한 칸 밀림)

### 2026-05-17
- **PvP 분석 탭에 "입수" 라인 추가** — 포켓몬 선택 시 현재 일정상 어디서 잡힐 수 있는지 한 줄로 표시
  - 알(거리·어드벤처싱크·색이 다른) / 레이드(티어·CP 범위·🇰🇷 한국 한정) / 필드 리서치(번역된 태스크) / 로켓 라인업(따까리 타입·간부·지오반시)
  - **사전 진화 단계까지 거슬러 검색** — 예: 라프라스 자체는 알/레이드에 없어도 진화 전 단계가 알에 있으면 "(사전 진화 라프라스) 🥚 10km" 표시
  - 신규 헬퍼 `find_acquisition_for_sid(target_sid, gm, eggs, raids, rocket, research, sid_to_display)` — `get_family_chain` + `find_boss_pokemon` 재활용으로 이름·메가·그림자·지역폼 매칭 일관성 보장
  - info_stack `<Configure>` 바인딩으로 wraplength 동적 조정 (창 너비 따라 줄바꿈)

### 2026-05-14
- **PvE 로켓 탭 통합 (로켓 라인업 + 카운터 분석 하나로)**
  - 같은 영역(GO 로켓단)을 두 탭으로 나누는 게 비효율 → 단일 탭 안에 라인업 표(상단) + 컨트롤(중단) + 카운터(하단)
  - 라인업 표 행 클릭 시 NPC 의 type 자동으로 PvE 로켓 타입 콤보에 설정 + 카운터 즉시 갱신 (별도 더블클릭/탭 전환 불필요)
  - 더블클릭은 여전히 첫 슬롯 포켓몬을 좌측에서 선택 (PvP 분석에서 보고 싶을 때)
  - 탭 수 14 → 13 으로 복귀
- **신규 데이터: ScrapedDuck rocketLineups.json** (26명: 보스 1 + 간부 3 + 조무래기 22)
  - 컬럼: 등급/NPC/타입/슬롯 1·2·3/색다른 가능
  - 슬롯 내 포켓몬마다 `★` = 색이 다른 가능, `💎` = 전투 후 획득 가능
  - 필터: 전체 / 보스 / 간부 / 조무래기 / 색이다른 가능만
  - 영문 NPC 한글 매핑 (Cliff→클리프, Arlo→알로, Sierra→시에라, Giovanni→보스 지오반니, "Fire-type Female Grunt"→"불꽃타입 조무래기 (여)" 등)
  - 1일 캐시, 신선도 라벨, 컬럼 정렬, 스크롤바
- **PvP 팀 메타: 추천 무브에 획득 카테고리 prefix 추가**
  - `★ 너클` = 엘리트 TM, `🎉 머드샷` = 커뮤니티 데이, `⚔ 신성한불꽃` = 레이드 데이
  - PvP 분석 탭의 `SPECIAL_MOVE_SOURCE` + `move_acquisition` 재활용 (큐레이션 매핑)
  - 헤더에 범례 표시

### 2026-05-13
- **신규 일정 탭 4종** — 게임 정보 통합:
  - **레이드 일정** — 글로벌(LeekDuck) + 한국(pogomate) 동시 표시. 5성/메가/그림자 그룹, 한국 한정 보스(예: 전수목)는 파란 배경. 더블클릭 시 PvE 카운터로 이동
  - **이벤트** — 진행/예정 필터, 커뮤니티 데이 스폰/레이드 보스/보너스 상세
  - **알 부화** — 거리별 풀(1~12km), 색이 다른/모험/선물/지역 한정 태그
  - **리서치** — 영문 태스크 → 한글 자동 번역 (정규식 39개 패턴, 현재 ScrapedDuck 데이터 100% 커버). 컬럼 토글로 영문 원문 병기 가능
- **한국 레이드 통합** — pogomate.com 스크래핑으로 Niantic 지역 한정 일정 반영. 출처 표시(🌐 글로벌 / 🇰🇷 한국 / ✓ 양쪽). 영문 슬러그 → ScrapedDuck 호환 영문명 변환 헬퍼 추가
- **PvP 팀빌더 교체** — 자체 시너지 매트릭스 도구를 **PvP 팀 메타** 로 교체:
  - PvPoke `training/teams/{cup}/{cap}.json` 사용
  - 리그별 8개 역할 슬롯 + 후보 포켓몬 + 무브셋 + 선택률 표시
  - 25% 이상 선택률은 노란색 강조
  - slot/synergies 영문 → 한글 매핑 (Tank→탱커, Flex→자유 슬롯, Charm→차밍 페어리, Anti-Flying→대 비행 등)
- **거래/강화 탭 제거** — 단순 계산기, 사용 빈도 낮음. 모듈 레벨 `TRADE_IV_FLOORS`/`LUCKY_TRADE_FLOOR`/`TRADE_DUST_*`/`trade_iv_distribution` 함수도 제거
- **PvE 다이맥스 탭 제거** — 자동 데이터 소스(ScrapedDuck/LeekDuck/Serebii/pogomate)가 진행 중 다이맥스 보스를 신뢰성 있게 제공 못 함. 다이맥스 분석은 PvE 카운터에서 가능
- **PvE 카운터: 표시 개수 콤보 추가** — 20/50/100/200/전체 선택 가능 (기존 20 고정)
- **PvE 카운터: 모드 라디오 제거** — 보스 데이터에 맥스 배틀 보스가 없어 모드 전환 무의미
- **데이터 신선도 라벨** — 모든 일정 탭 헤더에 `갱신: N시간 전` 표시. 1일 미만 회색, 1~7일 주황, 7일+ 빨강. `_freshness_label` 헬퍼
- **다단계 코드 정리** — 트리뷰 4개에 스크롤바 + 컬럼 정렬(`_sort_tree` 공용 헬퍼, CP 범위는 max 기준) 일괄 추가, 알 부화 거리 `1 km` → `1km` 공백 정리
- **신규 사용자 디폴트 창 크기** — `1360x840` → `1500x920`, minsize `1280x740` → `1360x800` (기존 사용자는 settings.json 우선)
- **레이드 캐시 주기** — 7일 → 1일 (매주 바뀌므로). 이벤트/리서치도 1일
- **탭 순서 정리** — PvP(5) → 타입 상성 → PvE(3) → 일정(4) = 총 13개. `notebook.insert` 로 팀 메타를 PvP 그룹으로 재배치
- **어필 등급 표시** — `appraisal_label(ivs)` 함수 추가, PvP 분석 결과에 자동 prefix (`★★★★ 합 45/45 · 100% Hundo` 등)
- **진화 체인 CP 미리보기** — IV+Lv 입력 시 진화 후 CP 자동 계산해 표시
- **LRU 랭킹 캐시** — 최근 8종 `rank_all` 결과 보관, 왔다갔다 재계산 방지
- **검색 성능** — `search_cache` (norm/sid/category/length 사전 정규화) + 700ms 폴링 + 180ms 디바운스로 4096종 substring 검색 즉응성 확보

### 2026-05-01
- 좌측 리스트에서 포켓몬 클릭 시 **PvP 분석 탭으로 자동 전환**
  - 다른 탭(타입 상성/PvP 메타/거래/팀빌더 등)에 있어도 클릭한 종의 분석을 바로 볼 수 있음
  - 단, 좌측 종을 직접 활용하는 PvE 탭(PvE DPS, "임의 보스" 모드의 PvE 카운터)에 있을 때는
    그 탭에서 머무르며 갱신 — 비교 작업 중 흐름이 끊기지 않게
- **PvP 메타 탭의 행 단일 클릭** 으로도 PvP 분석 점프 — 기존엔 더블클릭/Enter 만 작동했음
- **버그 픽스**: 진화 체인에서 메가/그림자 폼 링크 클릭 시 좌측 카테고리 체크박스가 꺼져있으면
  해당 폼이 리스트에 없어 선택 실패 → 타입/IV/기술 표가 갱신 안 되던 문제. 클릭 시 해당
  카테고리(메가/그림자/일반) 를 자동 활성화하도록 수정
- **버그 픽스**: 일부 진화 후 종(트리토돈/실버디 등)이 PvPoke gamemaster 에서 `family.parent`
  필드가 누락되어 `(단일종 · 진화 없음)` 으로 표시되던 문제. 모든 종의 `family.evolutions` 를
  역인덱스해 부모를 보강하도록 `get_family_chain` 수정 (gastrodon←shellos, silvally←type_null
  등 자동 복원)
- **버그 픽스**: PvPoke gamemaster 의 `family.parent` 가 실제 부모와 다른 종을 가리키는 9개
  비대칭 케이스 (carkol→boltund 오인, raticate→rattata_alolan 오인, mothim/burmy 변종
  꼬임, 다루마카/조로아 갈/히수이 변종, 피카츄_shaymin 등) 수정.
  - parent 클레임을 양방향 검증 — `parent.evolutions` 에 자기 자신이 들어있을 때만 신뢰,
    아니면 evo_to_parent 로 fallback
  - 영향: 카르콜 → 진화 체인 `석탄가나 → 카르코키 → 카르코나` 정상 표시 (이전엔 무관한 야먼/
    펄스멍이 표시됨), 라이라이쿤 → `라이라이 → 라이라이쿤` (이전엔 알로라 변종으로 우회),
    갈가드 → `갈따라 → 갈가드` (갈라르 변종 체인) 등

### 2026-04-26
- **PvE 로켓 탭의 간부/지오반니 도우미 섹션 제거** — 활용도 낮다고 판단해 단순화
  - 버튼 클릭이 PvE 카운터 탭의 체크박스 1번 누르는 것과 가치가 같았고, 라인업 정보는 어차피
    외부 사이트 (LeekDuck/포케토리 등) 가 더 잘 관리하므로 도구 안에 두는 의미 약함
  - 대신 "특정 포켓몬 카운터는 PvE 카운터 탭의 좌측 선택 모드 활용" 한 줄 안내만 남김
- **검색 가능 콤보박스** — `make_searchable_combo` 헬퍼 추가, 주요 콤보들에 적용
  - 타이핑하면 dropdown 항목이 substring 매치로 자동 필터링
  - 빈 입력 시 전체 목록 복원, 매칭 0건이면 전체로 fallback
  - 적용된 콤보:
    - **시즌 컵** (16개+ 옵션)
    - **PvE 카운터 보스** (현재 16종, 일정 따라 50+ 까지 확장 가능)
    - **PvE 카운터 날씨** (8개)
    - **PvE DPS 타겟 타입** (19개)
    - **PvE DPS 날씨** (8개)
    - **PvE 로켓 조무래기 대사** (Entry → Combobox 변경, 19개 캐논 대사 dropdown + 키워드 검색)
    - **PvE 로켓 조무래기 타입** (18개)
  - 짧은 콤보 (Lv 4종)는 그대로 readonly 유지
- **다이맥스 도감 강화** — 어떤 포켓몬이 필요한지 한눈에 파악 가능
  - 새 컬럼 **주요 약점** — 각 종의 1.6× 이상 약점 타입 4개를 배수와 함께 표시
    (예: 이상해꽃 → "불꽃(1.60×) 얼음(1.60×) 비행(1.60×) 에스퍼(1.60×)")
  - 표 아래 **카운터 미리보기 패널** — 행 선택 시 해당 종의 카운터 TOP 6 즉시 표시
    (속공+차지 무브셋 + eDPS 포함, 맥스 배틀 보스 가정으로 boss CPM 1.0 적용)
  - 더블클릭 → 기존 PvE 카운터 탭 전체 분석 (동작 유지)
- **한국 PoGO 정식 용어 점검**:
  - `그런트` → `조무래기` (모든 코드/주석/UI 라벨 일괄)
  - `리더` → `간부` (클리프/아르로/시에라)
  - `지오반니` → `보스 지오반니`
- 새 탭 **PvE 로켓** — 로켓단 조무래기 카운터 (타입 기반)
  - 조무래기는 항상 한 가지 타입 테마로 팀 구성 → 타입 18개 콤보 → 카운터 TOP 20
  - **대사 입력 → 타입 자동 추정** — 배틀 전 대사 (또는 일부 키워드: "바다", "짜릿", "얼려" 등)
    입력 시 타입 자동 선택되고 카운터 즉시 갱신
    - 18개 타입 전부 매핑 (출처: namu.wiki / poketory.com 교차검증)
    - "특수 조무래기" (잠만보 등 멀티타입) 도 인식해서 안내
  - 메가/그림자/전설 필터, Lv 옵션 동일하게 제공
  - 가상 보스 (atk=200/def=180) 가정해서 순위 산출
  - 간부(클리프/아르로/시에라) + 보스 지오반니는 로테이션 주기 짧으므로 별도 표 안 만들고,
    PvE 카운터 탭의 "좌측 선택 포켓몬을 보스로" 모드를 활용하라고 안내
- **다이맥스 풀 31종 → 61종 확장** — 사실 PoGO 의 "맥스 배틀 / 파워스폿" 풀 전체 반영
  - PokeMiners `BREAD_POKEMON_SCALING_SETTINGS` 기준 (실제 배포된 보스 풀, 진화 전 단계 + 전설 새/비스트 + 갈라르 스타터 풀라인 + 우라오스 일격/연격 등)
  - 거다이맥스(GMax) 가능 종 12개는 ★ 표시 유지
- **공격자 Lv 콤보 추가** — PvE 카운터 + PvE DPS 탭에 Lv 40/45/50/51 선택
  - IV 는 의도적으로 15·15·15 고정 (PvE 에선 IV 영향 ~0.3%, 레벨이 진짜 변수)
- **영문 잔존 한글화 일괄 픽스**:
  - 메타랭킹 폼 변형 (큐레무 화이트, 게노세크트 드라이브 4종, 케르디오 각오폼 등) — `build_sid_display_full` 헬퍼 추가로 dedupe 된 폼들 보충
  - 기술명 36개 추가 (히든파워 18타입, 테크노버스터/오라휠 폼별, 토네/볼트/랜드/러브로스 영물 폼 무브 등)
  - 다이맥스 도감 한글 누락 (갈가부기·마휘핑·대왕끼리동) — released=False 종도 보충 맵으로 표시
  - "Shadow Alolan Marowak" 같은 복합 prefix 보스 매칭 (region + shadow 동시)
  - 단일 타입 포켓몬 디테일 뷰의 `[불꽃 / none]` 표시 → `none` 필터링
- **레이드 카운터 강화**:
  - 모드 라디오 추가: `일반 레이드 / 맥스 배틀` (맥스는 보스 CPM 1.0 으로 단단함 반영)
  - 6마리 라인업 낙관 클리어 시간 추정 표시
  - 보스 정보/콤보 한글 표시명 (이미 적용됨, 보강)
- **다이맥스 도감 → PvE 카운터 점프**:
  - 행 더블클릭 시 좌측 포켓몬 자동 선택 + "직접 보스로" 모드 ON + PvE 카운터 탭 전환
- **알려진 한계 표기**: PvE DPS / 카운터 탭에 "DPS 절대값은 PvP 소스 기반이라 보수적, 순위는 정확" caveat 표시
  - 향후 pogoapi.net `fast_moves.json`/`charged_moves.json` 연동으로 PvE 정확도 개선 예정 (별도 작업)
- 탭 구조 정리 — 8개 탭에 prefix 도입: `PvP 분석 / PvP 메타 / PvP IV검색 / PvP CP→IV / 타입 상성 / PvE 카운터 / PvE DPS / PvE 다이맥스`
- 새 탭 **PvE DPS** — 선택한 포켓몬의 학습 가능한 모든 (속공×차지) 무브셋을 eDPS 정렬 표로 표시
  - 타겟 방어 타입 / 날씨 옵션, ★ = 엘리트/레거시 무브
  - 좌측 포켓몬 변경 시 자동 갱신
- 새 탭 **PvE 다이맥스** — Pokemon GO Max Battle 가능 31종 도감
  - 한글 이름 / 타입 / 거다이맥스(GMax) 가능 여부 / 종족값 / 추천 맥스 무브 (STAB)
  - 데이터: PokeMiners GAME_MASTER 기반 손큐레이션 (신규 출시 시 `DYNAMAX_POOL` 에 추가)
- **레이드 보스 한글화** — 콤보박스/보스 정보가 영문이던 것을 한글 표시명으로 (예: "[5★] Tapu Koko" → "[5★] 카푸꼬꼬꼭")
- 새 탭 **레이드 카운터** (PvE) 추가 — PvP 전용 도구에서 PvE 영역으로 확장
  - 현재 활성 레이드 보스 자동 로드 (ScrapedDuck / LeekDuck 미러, 7일 캐시)
  - 보스 선택 → 타입/약점 자동 표시 + 카운터 TOP 20 (eDPS 기준)
  - 무브셋 자동 최적화: 모든 (속공 × 차지) 조합 시뮬레이션 후 최고 eDPS 선택
  - 날씨 부스트 옵션 (맑음/비/구름조금/흐림/바람/눈/안개)
  - 공격자 풀 필터: 메가 / 그림자 / 전설·환상 / 즐겨찾기만
  - "좌측 선택 포켓몬을 보스로" 모드 — 레이드 일정 외 임의 보스에 대해 미리 카운터 분석
- PvE DPS 엔진: Lv50 / 15·15·15 가정, PoGO 표준 공식 (`floor(0.5·Power·Atk/Def·STAB·Eff·Weather)+1`)
  - 사이클 DPS = (N속공 + 1차지) / 사이클시간, eDPS = √(DPS·TDO)
  - 그림자 1.2× 공/0.83× 방, 메가는 baseStats 자체 반영
  - PvPoke `released:false` 항목 자동 제외 (eternamax 등 미출시 종 카운터 노출 방지)

### 2026-04-25
- 검색 리스트에 **분류 필터** 추가 — `일반 / 그림자 / 메가` 체크박스로 보고 싶은 폼만 표시
  - 그림자(451종) / 메가(48종) 가 일반(1041종) 과 섞여 보이던 문제 해소
  - 설정에 저장되어 다음 실행 시 유지
  - PvP 데이터 소스(pvpoke gamemaster) 에 다이맥스/거다이맥스는 없음 — 별도 도구로 분리 검토 중
- 리그 선택 UI: 단일 콤보박스 → **하이브리드** (4개 빌트인 리그 라디오 + 시즌 컵 콤보)
  - 자주 쓰는 리틀/슈퍼/하이퍼/마스터 항상 클릭 한 번
  - 시즌 컵은 별도 드롭다운 (선택 시 라디오 자동 해제)
- "IV로 포켓몬 찾기" 탭에 IV 입력 필드 복원 (Tab 1 과 var 공유 → 양방향 동기화)
  - 이전 변경에서 Tab 3 입력 필드를 모두 제거했더니 "IV가 동작 안 한다" 로 보였던 이슈
- IV 입력 시 현재 활성 탭이 IV로 포켓몬 찾기면 그쪽도 자동 갱신
- **버그 픽스**: TYPE_CHART 중복 정의로 포켓몬 디테일 뷰의 약점/내성 표시가 조용히 깨져 있던 것 수정
- 약점/내성 라벨을 PoGO 실제 배수로 정확화 (2.56× / 1.6× / 0.625× / 0.39×↓)
- 사용성 개선:
  - 리그 단축키 `1~9` → `Alt+1~9` (검색창/IV 입력에서 숫자가 가로채지지 않도록)
  - 검색창에서 `↓ ↑` 화살표 → 리스트박스 즉시 네비게이션 + 자동 선택
  - 검색 결과 0건 시 안내 문구 표시 (`'XX' 검색 결과 없음 — 다른 단어로 시도`)
  - 즐겨찾기 카운트 라벨 실시간 갱신 (이전엔 재시작해야 보였음)
  - 스프라이트 없을 때 `이미지 없음` 플레이스홀더 표시
  - 최소 창 크기 1100×700 → 1280×740 (4열 역검색 탭이 충분히 보이도록)
- "IV로 포켓몬 찾기" 탭 효율 개선:
  - 중복 IV 입력 제거 → Tab 1 의 `내 개체값` 공유 (한 번만 입력)
  - 해당 탭 전환 시 자동으로 결과 갱신 (수동 `찾기` 버튼 불필요)
- 새 탭 **타입 상성표** 추가 — 18×18 PoGO PvP 데미지 배율 매트릭스 (1.6× / 1× / 0.625× / 0.39×) 색상 코딩
  - 외부 의존 없이 tkinter Label 그리드로 렌더 (PIL 불필요)
- 리그 4개 → **동적 17개+** 로 확장. 빌트인 4개 오픈 리그(리틀/슈퍼/하이퍼/마스터) 외에
  `gamemaster.formats` 에서 시즌 컵을 자동 로드 (마스터 프리미어, 봄/판타지/바이유/주문/캐치/지가르데 크로노 등)
  - 리그 선택 UI 라디오 버튼 → 콤보박스 (다수 리그 수용)
  - 키보드 1~9 단축키는 앞쪽 9개 리그만 매핑, 나머지는 콤보박스로 선택
  - PvPoke 가 랭킹을 공개하지 않은 컵(404) 은 자동으로 드롭다운에서 제거
  - 역검색 탭은 4개 빌트인 리그 한정 (시즌 컵까지 나란히 두면 가독성 저하)
- 기술 표 `⚡` 컬럼을 `획득` 컬럼으로 교체 — `커뮤데이` / `레이드` / `엘리트 TM` / 공란(일반 학습) 으로 세분화 표시
  - 큐레이팅된 `SPECIAL_MOVE_SOURCE` 매핑: 1~8세대 풀/불꽃/물 스타터 9삼각형, 이브이 8진화체 CD 무브, 레이드 데이 시그니처 (루기아/칠색조/뮤츠/레쿠쟈) 등
- 사용자 표시 문자열 `섀도우` → `그림자` (한국 포고 공식 표기)
  - 입력 alias `섀도우/쉐도우/섀도` 는 호환용으로 유지
- CLI 결과 헤더에 한글 표시명 사용 (`Mewtwo (Shadow)` → `그림자 뮤츠`)

### 2026-04-24
- 메타 랭킹 탭 전체 표시 + 검색 필터 추가
- 폼 한글화 + 메타 순위 컬럼 + 데이터 라벨 정리
