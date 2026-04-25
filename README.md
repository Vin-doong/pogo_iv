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

### 캐시 정책
- `gamemaster.json`, `rankings-*.json`: 시즌마다 바뀌므로 **7일 경과 시 자동 재다운로드**
- 한국어/기술명 CSV: 거의 바뀌지 않으므로 **90일 경과 시 자동 재다운로드**
- 스프라이트: 한 번 다운로드 후 영구 캐시

## 크레딧

이 도구는 아래 오픈 데이터/프로젝트를 활용합니다.

- [pvpoke](https://github.com/pvpoke/pvpoke) — 포켓몬 GO PvP 시뮬레이터 및 랭킹 데이터
- [PokeAPI](https://github.com/PokeAPI/pokeapi) — 포켓몬 다국어 이름 및 기술 메타데이터
- [Pokémon Showdown](https://play.pokemonshowdown.com/) — 포켓몬 스프라이트 이미지

Pokémon 및 관련 상표는 Nintendo / Game Freak / The Pokémon Company의 자산입니다. 이 프로젝트는 비영리 팬 메이드 도구입니다.

## 요구 사항

- Python 3.10+ (표준 라이브러리만 사용, tkinter 필요)
- 첫 실행 시 인터넷 연결 (데이터 다운로드용)

## 변경 이력

### 2026-04-25
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
