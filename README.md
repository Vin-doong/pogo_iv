# Pokemon GO PvP 개체값 리그 랭커

Pokemon GO의 개체값(IV)에 따른 리그별(리틀컵/슈퍼리그/하이퍼리그/마스터리그) 순위를 계산하는 Python GUI/CLI 도구입니다.

## 기능

- 포켓몬 이름과 IV(공격/방어/HP)를 입력하면 각 리그에서의 최적 레벨과 순위를 계산
- 한글 포켓몬 이름 지원 (그림자/메가/알로라/가라르/히스이/팔데아 폼 포함)
- GUI 모드(기본) / CLI 모드 모두 제공
- 즐겨찾기, 창 위치/리그 선택 저장
- 포켓몬 스프라이트 이미지 자동 캐싱

## 실행

```bash
# GUI (기본)
python pogo_iv.py

# 대화형 CLI
python pogo_iv.py --cli

# 단발성 조회
python pogo_iv.py 마릴리 0 15 15
python pogo_iv.py "메가 갸라도스" 15 15 15 --max-level 50
```

Windows에서는 `포켓몬개체값.bat`을 더블클릭하여 실행할 수 있습니다.

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
| `raids.json` | 현재 활성 레이드 보스 (PvE 카운터 추천용) | `https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.json` (LeekDuck 미러) |

### 캐시 정책
- `gamemaster.json`, `rankings-*.json`, `raids.json`: 시즌/레이드 로테이션마다 바뀌므로 **7일 경과 시 자동 재다운로드**
- 한국어/기술명 CSV: 거의 바뀌지 않으므로 **90일 경과 시 자동 재다운로드**
- 스프라이트: 한 번 다운로드 후 영구 캐시

## 크레딧

이 도구는 아래 오픈 데이터/프로젝트를 활용합니다.

- [pvpoke](https://github.com/pvpoke/pvpoke) — 포켓몬 GO PvP 시뮬레이터 및 랭킹 데이터
- [PokeAPI](https://github.com/PokeAPI/pokeapi) — 포켓몬 다국어 이름 및 기술 메타데이터
- [Pokémon Showdown](https://play.pokemonshowdown.com/) — 포켓몬 스프라이트 이미지
- [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck) / [LeekDuck](https://leekduck.com/) — 현재 레이드 보스 일정

Pokémon 및 관련 상표는 Nintendo / Game Freak / The Pokémon Company의 자산입니다. 이 프로젝트는 비영리 팬 메이드 도구입니다.

## 요구 사항

- Python 3.10+ (표준 라이브러리만 사용, tkinter 필요)
- 첫 실행 시 인터넷 연결 (데이터 다운로드용)

## 변경 이력

### 2026-04-26
- 새 탭 **PvE 로켓** — 로켓단 그런트 카운터 (타입 기반)
  - 그런트는 항상 한 가지 타입 테마로 팀 구성 → 타입 18개 콤보 → 카운터 TOP 20
  - 메가/그림자/전설 필터, Lv 옵션 동일하게 제공
  - 가상 보스 (atk=200/def=180) 가정해서 순위 산출
  - 리더(클리프/아르로/시에라) + 지오반니는 로테이션 주기 짧으므로 별도 표 안 만들고,
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
