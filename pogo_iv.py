#!/usr/bin/env python3
"""Pokemon GO PvP 개체값 리그 랭커.

기본 실행 = GUI (검색 셀렉트박스)
CLI 사용:
  python pogo_iv.py --cli                           # 대화형 CLI
  python pogo_iv.py 마릴리 0 15 15                   # 단발성
  python pogo_iv.py "메가 갸라도스" 15 15 15 --max-level 50
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from collections import namedtuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

GAMEMASTER_URLS = [
    "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster.json",
    "https://pvpoke.com/data/gamemaster.json",
]
KOREAN_CSV_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv"
MOVES_CSV_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/moves.csv"
MOVE_NAMES_CSV_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/move_names.csv"
RANKINGS_URL_TEMPLATE = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/{cup_id}/overall/rankings-{cap}.json"
SPRITE_URL_BASE = "https://play.pokemonshowdown.com/sprites/gen5"
SCRAPEDUCK_RAIDS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.json"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_GM = os.path.join(SCRIPT_DIR, "gamemaster.json")
CACHE_KO = os.path.join(SCRIPT_DIR, "korean_names.csv")
CACHE_MOVES = os.path.join(SCRIPT_DIR, "moves.csv")
CACHE_MOVE_NAMES = os.path.join(SCRIPT_DIR, "move_names.csv")
CACHE_RAIDS = os.path.join(SCRIPT_DIR, "raids.json")
SPRITE_DIR = os.path.join(SCRIPT_DIR, "sprites")
FAVORITES_PATH = os.path.join(SCRIPT_DIR, "favorites.json")
SETTINGS_PATH = os.path.join(SCRIPT_DIR, "settings.json")

# gamemaster / rankings 는 시즌마다 바뀜 → 7일 지나면 자동 재다운로드
# 한국어/기술명 CSV 는 거의 안 바뀜 → 90일
DATA_MAX_AGE_DAYS = 7
STATIC_MAX_AGE_DAYS = 90

SHOWDOWN_VARIANT_TRANSFORMS = [
    ("_mega_x",    "-megax"),
    ("_mega_y",    "-megay"),
    ("_mega",      "-mega"),
    ("_alolan",    "-alola"),
    ("_alola",     "-alola"),
    ("_galarian",  "-galar"),
    ("_galar",     "-galar"),
    ("_hisuian",   "-hisui"),
    ("_hisui",     "-hisui"),
    ("_paldean",   "-paldea"),
    ("_paldea",    "-paldea"),
]

League = namedtuple("League", "name cup_id cap")

# 항상 표시되는 4개 오픈 리그 (PvPoke `rankings/all/...` 사용)
_BUILTIN_LEAGUES = [
    League("리틀컵",     "all", 500),
    League("슈퍼리그",   "all", 1500),
    League("하이퍼리그", "all", 2500),
    League("마스터리그", "all", None),
]

# (cup_id, cp_cap) → 한글 표시명. PvPoke gamemaster.formats[].cup 를 키로 사용.
# 매핑 없으면 formats[].title (영문) 그대로 표시.
CUP_KO = {
    # 마스터리그 변형
    ("premier",          10000): "마스터리그 프리미어",
    ("classic",          10000): "마스터리그 클래식",
    ("battlefrontiermaster", 10000): "배틀프론티어 (마스터)",
    # 하이퍼리그 변형
    ("classic",          2500):  "하이퍼리그 클래식",
    ("premier",          2500):  "하이퍼리그 프리미어",
    ("bfretro",          2500):  "UL Retro 컵",
    # 슈퍼리그 변형
    ("classic",          1500):  "슈퍼리그 클래식",
    ("premier",          1500):  "슈퍼리그 프리미어",
    # 시즌 컵 (1500)
    ("spring",           1500):  "봄 컵",
    ("fantasy",          1500):  "판타지 컵",
    ("bayou",            1500):  "바이유 컵",
    ("spellcraft",       1500):  "주문 컵",
    ("equinox",          1500):  "춘추분 컵",
    ("maelstrom",        1500):  "마엘스트롬 컵",
    ("catch",            1500):  "캐치 컵",
    ("electric",         1500):  "전기 컵",
    ("jungle",           1500):  "정글 컵",
    ("chrono",           1500):  "지가르데 크로노 컵",
    # 챔피언십/특수
    ("naic2026",         1500):  "NAIC 2026 컵",
    ("laic2025remix",    1500):  "LAIC 2025 리믹스",
    ("championshipseries", 1500): "P!P 챔피언십 컵",
}

# 런타임 채워짐 (init_leagues 호출 후)
LEAGUES: list[League] = list(_BUILTIN_LEAGUES)


def init_leagues(gm):
    """gamemaster.formats 에서 리그 목록을 동적으로 빌드. 빌트인 4개 + 시즌 컵."""
    seen = {(lg.cup_id, lg.cap) for lg in _BUILTIN_LEAGUES}
    # 빌트인 'all'/cap 과 동일한 풀인 cup_id 는 중복 (e.g. 'little' @ 500 == 'all' @ 500)
    SKIP_CUPS = {("little", 500)}
    extras = []
    for f in gm.get("formats", []):
        cup = f.get("cup")
        cp = f.get("cp")
        if not cup or not cp or cup in ("all", "custom"):
            continue
        key = (cup, cp)
        if key in seen or key in SKIP_CUPS:
            continue
        seen.add(key)
        ko = CUP_KO.get(key, f.get("title", cup))
        extras.append(League(ko, cup, cp))
    LEAGUES.clear()
    LEAGUES.extend(_BUILTIN_LEAGUES)
    LEAGUES.extend(extras)
    return LEAGUES

KOREAN_VARIANT_PREFIXES = [
    ("그림자", "_shadow"),  # 한국 포고 공식 표기
    ("섀도우", "_shadow"),  # 영문 음차 (구버전 호환)
    ("쉐도우", "_shadow"),
    ("섀도",   "_shadow"),
    ("메가",   "_mega"),
    ("알로라", "_alolan"),
    ("가라르", "_galarian"),
    ("히스이", "_hisuian"),
    ("팔데아", "_paldean"),
]

REGIONAL_VARIANTS = [
    ("alolan",   "알로라"),
    ("alola",    "알로라"),
    ("galarian", "가라르"),
    ("galar",    "가라르"),
    ("hisuian",  "히스이"),
    ("hisui",    "히스이"),
    ("paldean",  "팔데아"),
    ("paldea",   "팔데아"),
]

MEGA_VARIANTS = [
    ("mega_x", ("메가", " X")),
    ("mega_y", ("메가", " Y")),
    ("mega",   ("메가", "")),
]

# 폼 suffix → 한국 포고 공식/통용 표기
FORM_KO = {
    # 피카츄 코스튬 (PvP 의미 없지만 표시용)
    "5th_anniversary": "5주년",
    "flying":          "플라잉",
    "horizons":        "호라이즌",
    "kariyushi":       "카리유시",
    "libre":           "리브레",
    "pop_star":        "팝스타",
    "rock_star":       "록스타",
    "shaymin":         "쉐이미 스카프",
    # 캐스퐁 · 도롱충이 · 체리꼬 (베이스와 동일 능력치 → 기본 숨김)
    "rainy":     "비",
    "snowy":     "눈",
    "sunny":     "맑음",
    "overcast":  "흐림",
    "plant":     "풀나무",
    "sandy":     "모래땅",
    "trash":     "쓰레기",
    # 켄타로스 (팔데아 폼)
    "aqua":    "물",
    "blaze":   "불꽃",
    "combat":  "격투",
    # 이벤트/갑옷 뮤츠
    "armored": "아머드",
    # 가이오가/그란돈 원시회귀
    "primal":  "원시",
    # 테오키스
    "attack":  "어택",
    "defense": "디펜스",
    "speed":   "스피드",
    # 로토무
    "fan":    "스카이",
    "frost":  "프로스트",
    "heat":   "히트",
    "mow":    "커트",
    "wash":   "워시",
    # 디아루가/펄기아/기라티나/쉐이미
    "origin":  "오리진폼",
    "altered": "어나더폼",
    "land":    "랜드폼",
    "sky":     "스카이폼",
    # 불비달마
    "standard":          "노말폼",
    "galarian_standard": "가라르 노말폼",
    # 토네로스/볼트로스/랜드로스/러브로스
    "incarnate": "화신폼",
    "therian":   "영물폼",
    # 큐레무
    "black": "블랙",
    "white": "화이트",
    # 케르디오
    "ordinary": "평상시폼",
    "resolute": "각오폼",
    # 메로엣타
    "aria":  "보이스폼",
    # 게노세크트 카세트
    "burn":  "바닥",
    "chill": "아이스",
    "douse": "물",
    "shock": "번개",
    # 암/수
    "female": "암컷",
    "male":   "수컷",
    # 킬가르도
    "shield": "실드폼",
    # 호바귀/펌킨인 사이즈
    "average": "보통 사이즈",
    "large":   "큰 사이즈",
    "small":   "작은 사이즈",
    "super":   "특대 사이즈",
    # 지가르데
    "10":       "10% 폼",
    "complete": "퍼펙트 폼",
    # 후파
    "unbound": "해방",
    # 춤추새
    "baile":   "이글이글스타일",
    "pau":     "찰싹찰싹스타일",
    "pom_pom": "팡파카스타일",
    "sensu":   "둥실둥실스타일",
    # 루가루암
    "dusk":     "황혼의 모습",
    "midday":   "한낮의 모습",
    "midnight": "한밤중의 모습",
    # 네크로즈마
    "dawn_wings": "날개의 모습",
    "dusk_mane":  "갈기의 모습",
    # 모르페코
    "full_belly": "배부른 모양",
    # 자시안/자마젠타
    "crowned_sword":  "검왕",
    "crowned_shield": "방패왕",
    "hero":           "용맹",
    # 우라오스
    "rapid_strike":  "연격의 태세",
    "single_strike": "일격의 태세",
    # 싸리용
    "curly":    "컬리 모양",
    "droopy":   "드로피 모양",
    "stretchy": "스트레치 모양",
    # 페르시온
    "b": "B폼",
}

# 강화 비용: idx (= (level-1)*2) → (별의모래, 사탕, XL사탕) per power-up (+0.5 level)
# idx 0 = L1.0→1.5, idx 78 = L40.0→40.5, ...
# Pokémon GO 공식 비용표 (2024 기준)
POWER_UP_COST = [
    # L1→10: 200 dust, 1 candy (idx 0~17, 18칸)
    *([(200, 1, 0)] * 18),
    # L10→15: 400 dust, 1 candy (idx 18~27, 10칸)
    *([(400, 1, 0)] * 10),
    # L15→20: 600 dust, 1 candy (idx 28~37)
    *([(600, 1, 0)] * 10),
    # L20→25: 1300 dust, 2 candy (idx 38~47)
    *([(1300, 2, 0)] * 10),
    # L25→30: 2000 dust, 3 candy (idx 48~57)
    *([(2000, 3, 0)] * 10),
    # L30→35: 2500 dust, 4 candy (idx 58~67)
    *([(2500, 4, 0)] * 10),
    # L35→40: 3000 dust, 6 candy (idx 68~77)
    *([(3000, 6, 0)] * 10),
    # L40→41: 5000, 10, 10  (idx 78~79)
    (5000, 10, 10), (5000, 10, 10),
    # L41→42: 6500, 10, 10  (idx 80~81)
    (6500, 10, 10), (6500, 10, 10),
    # L42→43: 8000, 12, 12
    (8000, 12, 12), (8000, 12, 12),
    # L43→44: 9500, 15, 15
    (9500, 15, 15), (9500, 15, 15),
    # L44→45: 11000, 15, 15
    (11000, 15, 15), (11000, 15, 15),
    # L45→46: 12500, 17, 17
    (12500, 17, 17), (12500, 17, 17),
    # L46→47: 14000, 17, 17
    (14000, 17, 17), (14000, 17, 17),
    # L47→48: 15500, 20, 20
    (15500, 20, 20), (15500, 20, 20),
    # L48→49: 17000, 20, 20
    (17000, 20, 20), (17000, 20, 20),
    # L49→50: 18500, 25, 25
    (18500, 25, 25), (18500, 25, 25),
    # L50→51 (보통 도달 불가, 안전망)
    (20000, 25, 25), (20000, 25, 25),
]

# PoGO 타입 상성 배수 (메인 시리즈와 다름)
CPM = [
    0.094, 0.135137432, 0.16639787, 0.192650919, 0.21573247, 0.236572661,
    0.25572005, 0.273530381, 0.29024988, 0.306057377, 0.3210876, 0.335445036,
    0.34921268, 0.362457751, 0.37523559, 0.387592406, 0.39956728, 0.411193551,
    0.4225, 0.432926419, 0.44310755, 0.453059958, 0.4627984, 0.472336083,
    0.48168495, 0.4908558, 0.4998465, 0.508687064, 0.51739395, 0.525970221,
    0.5343543, 0.542750551, 0.5507927, 0.558830906, 0.5665005, 0.574365365,
    0.5822789, 0.590043681, 0.5974, 0.604824944, 0.6121573, 0.619399365,
    0.6265671, 0.633644533, 0.64065295, 0.6475876, 0.65443563, 0.661214,
    0.667934, 0.674577537, 0.6811649, 0.687680648, 0.69414365, 0.70054287,
    0.7068842, 0.713169531, 0.7193991, 0.725568, 0.7317, 0.734741009,
    0.7377695, 0.740785574, 0.74378943, 0.746781211, 0.74976104, 0.752729087,
    0.75568551, 0.758630368, 0.76156384, 0.764486215, 0.76739717, 0.770297266,
    0.7731865, 0.776064962, 0.77893275, 0.781790055, 0.784637, 0.787473578,
    0.7903, 0.792803968, 0.79530001, 0.797800015, 0.80030001, 0.802800015,
    0.80530001, 0.807800015, 0.81030001, 0.812800015, 0.81530001, 0.817800015,
    0.82030001, 0.822800015, 0.82530001, 0.827800015, 0.83030001, 0.832800015,
    0.83530001, 0.837800015, 0.8403, 0.842800015, 0.84529999,
]


# ----- data loading -----

def _download(url, dest):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (pogo_iv.py)",
        "Accept": "application/json, text/csv, text/plain",
    })
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def _file_age_days(path):
    if not os.path.exists(path):
        return float("inf")
    import time
    return (time.time() - os.path.getmtime(path)) / 86400.0


def _is_stale(path, max_age_days):
    return _file_age_days(path) > max_age_days


def _format_age(path):
    if not os.path.exists(path):
        return "(없음)"
    import time
    from datetime import datetime
    mt = os.path.getmtime(path)
    return datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")


def _ensure_file(path, downloader, label, max_age_days, force=False):
    """파일이 없거나 오래되었으면 다운로드. downloader는 (path)→None 함수."""
    if not force and not _is_stale(path, max_age_days):
        return True
    try:
        print(f"{label} 다운로드 중... ({'갱신' if os.path.exists(path) else '최초'})")
        downloader(path)
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def _gm_downloader(dest):
    last = None
    for url in GAMEMASTER_URLS:
        try:
            _download(url, dest)
            return
        except Exception as e:
            last = e
    raise last or RuntimeError("게임마스터 다운로드 실패")


def load_gamemaster(force=False):
    ok = _ensure_file(CACHE_GM, _gm_downloader, "게임마스터", DATA_MAX_AGE_DAYS, force)
    if not ok and not os.path.exists(CACHE_GM):
        raise RuntimeError("게임마스터를 가져올 수 없습니다 (오프라인?)")
    with open(CACHE_GM, encoding="utf-8") as f:
        return json.load(f)


def load_korean_dex_map(force=False):
    """dex 번호 → 한글 베이스 이름."""
    _ensure_file(CACHE_KO, lambda p: _download(KOREAN_CSV_URL, p),
                 "한글 이름", STATIC_MAX_AGE_DAYS, force)
    if not os.path.exists(CACHE_KO):
        return {}
    dex_to_ko = {}
    with open(CACHE_KO, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 3 and row[1] == "3":  # language_id 3 = Korean
                try:
                    dex_to_ko[int(row[0])] = row[2].strip()
                except ValueError:
                    pass
    return dex_to_ko


def _ranking_cache_path(cup_id, c):
    """'all' (오픈 리그) 은 기존 파일명 유지, 그 외엔 cup_id 포함."""
    if cup_id == "all":
        return os.path.join(SCRIPT_DIR, f"rankings-{c}.json")
    return os.path.join(SCRIPT_DIR, f"rankings-{cup_id}-{c}.json")


def load_league_rankings(cup_id, cap, force=False):
    """PvPoke overall rankings for (cup_id, cap). score-desc sorted."""
    c = cap if cap is not None else 10000
    path = _ranking_cache_path(cup_id, c)
    url = RANKINGS_URL_TEMPLATE.format(cup_id=cup_id, cap=c)
    _ensure_file(path, lambda p: _download(url, p),
                 f"리그 랭킹 {cup_id}/{c}", DATA_MAX_AGE_DAYS, force)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"랭킹 파일 파싱 실패 ({cup_id}/{c}): {e}")
        return []


def load_raid_bosses(force=False):
    """ScrapedDuck (LeekDuck mirror) 의 현재 레이드 보스 목록.
    각 항목: {name, tier, types, image, ...}. 12h 마다 자동 갱신.
    """
    _ensure_file(CACHE_RAIDS, lambda p: _download(SCRAPEDUCK_RAIDS_URL, p),
                 "현재 레이드 보스", DATA_MAX_AGE_DAYS, force)
    if not os.path.exists(CACHE_RAIDS):
        return []
    try:
        with open(CACHE_RAIDS, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"raids.json 파싱 실패: {e}")
        return []


def refresh_all_data():
    """모든 시즌별 데이터 강제 재다운로드. gm 갱신 후 LEAGUES 재구성."""
    gm = load_gamemaster(force=True)
    init_leagues(gm)
    load_korean_dex_map(force=True)
    load_move_ko_map(force=True)
    load_raid_bosses(force=True)
    for lg in LEAGUES:
        load_league_rankings(lg.cup_id, lg.cap, force=True)


def data_status():
    """[(label, path, age_days), ...] — 각 데이터 파일 현황."""
    items = [("게임마스터", CACHE_GM), ("한글 이름", CACHE_KO),
             ("기술 한글", CACHE_MOVE_NAMES)]
    for lg in LEAGUES:
        c = lg.cap if lg.cap is not None else 10000
        items.append((f"랭킹·{lg.name}", _ranking_cache_path(lg.cup_id, c)))
    return [(label, path, _file_age_days(path)) for label, path in items]


def load_favorites():
    if not os.path.exists(FAVORITES_PATH):
        return set()
    try:
        with open(FAVORITES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("species", []))
    except Exception:
        return set()


def save_favorites(species_set):
    try:
        with open(FAVORITES_PATH, "w", encoding="utf-8") as f:
            json.dump({"species": sorted(species_set)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"즐겨찾기 저장 실패: {e}")


def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"설정 저장 실패: {e}")


MOVE_KO_OVERRIDES = {
    # PokeAPI 한글 번역 누락 보완
    "gigaton-hammer":   "거대망치",
    "tera-blast":       "테라버스트",
    "trailblaze":       "길트기",
    "armor-cannon":     "아머캐논",
    "bitter-blade":     "비터블레이드",
    "ceaseless-edge":   "가시덤불칼",
    "stone-axe":        "돌도끼",
    "wave-crash":       "파도타기박치기",
    "collision-course": "충돌코스",
    "electro-drift":    "번개자국",
    "spicy-extract":    "매운추출",
    "psyshield-bash":   "사이코실드 부수기",
    "ivy-cudgel":       "덩굴몽둥이",
    "blood-moon":       "블러드문",
    "matcha-gotcha":    "말차 찹찹",
    "super-power":      "괴력",
    "superpower":       "괴력",
    "chilling-water":   "냉수",
    "triple-axel":      "트리플악셀",
    "scale-shot":       "스케일샷",
    "double-iron-bash": "아이언헤드",
    "snipe-shot":       "스나이퍼샷",
    "v-create":         "V제너레이트",
    "sacred-fire":      "성스러운불꽃",
    "psystrike":        "싸이키네시스",
    "mystical-fire":    "매지컬 불꽃",
    "origin-pulse":     "근원의파동",
    "precipice-blades": "단애의검",
    "spacial-rend":     "아공절단",
    "roar-of-time":     "시간의포효",
    "behemoth-blade":   "거신참",
    "behemoth-bash":    "거신돌격",
    "astral-barrage":   "유성난무",
    "rage-fist":        "분노의주먹",
    "weather-ball-fire": "웨더볼 (불꽃)",
    "weather-ball-water": "웨더볼 (물)",
    "weather-ball-ice":  "웨더볼 (얼음)",
    "weather-ball-rock": "웨더볼 (바위)",
    "weather-ball-normal": "웨더볼",
    "weather-ball":      "웨더볼",
    # 9세대 / 신규 무브
    "aqua-step":         "아쿠아스텝",
    "torch-song":        "토치송",
    "flower-trick":      "플라워트릭",
    # 폼 변형 무브 (PvPoke 가 form 별로 분리)
    "techno-blast-burn":    "테크노버스터 (불꽃)",
    "techno-blast-chill":   "테크노버스터 (얼음)",
    "techno-blast-douse":   "테크노버스터 (물)",
    "techno-blast-shock":   "테크노버스터 (전기)",
    "techno-blast-normal":  "테크노버스터",
    "aura-wheel-dark":      "오라휠 (악)",
    "aura-wheel-electric":  "오라휠 (전기)",
    "hydro-pump-blastoise": "하이드로펌프 (거북왕)",
    "water-gun-fast-blastoise": "물대포 (거북왕)",
    "aegislash-charge-air-slash":  "에어슬래시 (블레이드폼)",
    "aegislash-charge-psycho-cut": "사이코커터 (블레이드폼)",
    # 토네/볼트/랜드/러브로스 영물 폼 무브
    "bleakwind-storm":   "블리자드스톰",
    "sandsear-storm":    "샌드스톰",
    "springtide-storm":  "스프링스톰",
    "wildbolt-storm":    "썬더스톰",
    # 히든파워 18타입 (각 타입별)
    "hidden-power-bug":      "히든파워 (벌레)",
    "hidden-power-dark":     "히든파워 (악)",
    "hidden-power-dragon":   "히든파워 (드래곤)",
    "hidden-power-electric": "히든파워 (전기)",
    "hidden-power-fighting": "히든파워 (격투)",
    "hidden-power-fire":     "히든파워 (불꽃)",
    "hidden-power-flying":   "히든파워 (비행)",
    "hidden-power-ghost":    "히든파워 (고스트)",
    "hidden-power-grass":    "히든파워 (풀)",
    "hidden-power-ground":   "히든파워 (땅)",
    "hidden-power-ice":      "히든파워 (얼음)",
    "hidden-power-normal":   "히든파워",
    "hidden-power-poison":   "히든파워 (독)",
    "hidden-power-psychic":  "히든파워 (에스퍼)",
    "hidden-power-rock":     "히든파워 (바위)",
    "hidden-power-steel":    "히든파워 (강철)",
    "hidden-power-water":    "히든파워 (물)",
}

TYPE_KO = {
    "normal": "노말", "fire": "불꽃", "water": "물", "electric": "전기",
    "grass": "풀", "ice": "얼음", "fighting": "격투", "poison": "독",
    "ground": "땅", "flying": "비행", "psychic": "에스퍼", "bug": "벌레",
    "rock": "바위", "ghost": "고스트", "dragon": "드래곤", "dark": "악",
    "steel": "강철", "fairy": "페어리",
}

# 18타입 상성표 (공격 → 방어). PoGO PvP 배율: 1.6 / 1.0 / 0.625 / 0.390625.
# 1.0 (보통) 인 조합은 dict 에서 생략.
TYPES_ORDER = ["normal", "fire", "water", "electric", "grass", "ice",
               "fighting", "poison", "ground", "flying", "psychic", "bug",
               "rock", "ghost", "dragon", "dark", "steel", "fairy"]

SE = 1.6        # super effective
NVE = 0.625     # not very effective
IMM = 0.390625  # double resist (PoGO 는 면역도 더블 저항으로 처리)

TYPE_CHART = {
    "normal":   {"rock": NVE, "ghost": IMM, "steel": NVE},
    "fire":     {"fire": NVE, "water": NVE, "grass": SE, "ice": SE, "bug": SE,
                 "rock": NVE, "dragon": NVE, "steel": SE},
    "water":    {"fire": SE, "water": NVE, "grass": NVE, "ground": SE, "rock": SE, "dragon": NVE},
    "electric": {"water": SE, "electric": NVE, "grass": NVE, "ground": IMM,
                 "flying": SE, "dragon": NVE},
    "grass":    {"fire": NVE, "water": SE, "grass": NVE, "poison": NVE, "ground": SE,
                 "flying": NVE, "bug": NVE, "rock": SE, "dragon": NVE, "steel": NVE},
    "ice":      {"fire": NVE, "water": NVE, "grass": SE, "ice": NVE, "ground": SE,
                 "flying": SE, "dragon": SE, "steel": NVE},
    "fighting": {"normal": SE, "ice": SE, "poison": NVE, "flying": NVE, "psychic": NVE,
                 "bug": NVE, "rock": SE, "ghost": IMM, "dark": SE, "steel": SE, "fairy": NVE},
    "poison":   {"grass": SE, "poison": NVE, "ground": NVE, "rock": NVE, "ghost": NVE,
                 "steel": IMM, "fairy": SE},
    "ground":   {"fire": SE, "electric": SE, "grass": NVE, "poison": SE, "flying": IMM,
                 "bug": NVE, "rock": SE, "steel": SE},
    "flying":   {"electric": NVE, "grass": SE, "fighting": SE, "bug": SE, "rock": NVE,
                 "steel": NVE},
    "psychic":  {"fighting": SE, "poison": SE, "psychic": NVE, "dark": IMM, "steel": NVE},
    "bug":      {"fire": NVE, "grass": SE, "fighting": NVE, "poison": NVE, "flying": NVE,
                 "psychic": SE, "ghost": NVE, "dark": SE, "steel": NVE, "fairy": NVE},
    "rock":     {"fire": SE, "ice": SE, "fighting": NVE, "ground": NVE, "flying": SE,
                 "bug": SE, "steel": NVE},
    "ghost":    {"normal": IMM, "psychic": SE, "ghost": SE, "dark": NVE},
    "dragon":   {"dragon": SE, "steel": NVE, "fairy": IMM},
    "dark":     {"fighting": NVE, "psychic": SE, "ghost": SE, "dark": NVE, "fairy": NVE},
    "steel":    {"fire": NVE, "water": NVE, "electric": NVE, "ice": SE, "rock": SE,
                 "steel": NVE, "fairy": SE},
    "fairy":    {"fire": NVE, "fighting": SE, "poison": NVE, "dragon": SE, "dark": SE,
                 "steel": NVE},
}

# ----- PvE: 레이드 카운터 추천용 데이터 / DPS 엔진 -----
# 레이드 보스 별 CPM (티어별 고정값). 보스의 effective Def 계산에 사용.
# 출처: GamePress / Pokebattler 공식 raid CPM
# T5/메가/엘리트/그림자는 모두 동일 cpm (0.5793) 사용 — 일반 강화 cpm 과 다른 별도 보스 cpm
RAID_TIER_CPM = {
    "1": 0.6,
    "3": 0.7,
    "5": 0.5793,
    "mega": 0.5793,
    "shadow": 0.5793,
    "elite": 0.5793,
    "max": 1.0,  # 맥스 배틀 보스는 훨씬 단단함 (근사치)
}

# 날씨 → 부스트 받는 타입들 (1.2x 데미지)
WEATHER_BOOSTS = {
    "sunny":   {"fire", "grass", "ground"},
    "rainy":   {"water", "electric", "bug"},
    "partly_cloudy": {"normal", "rock"},
    "cloudy":  {"fairy", "fighting", "poison"},
    "windy":   {"dragon", "flying", "psychic"},
    "snow":    {"ice", "steel"},
    "fog":     {"dark", "ghost"},
}

WEATHER_KO = {
    "sunny": "맑음/매우더움", "rainy": "비", "partly_cloudy": "구름조금",
    "cloudy": "흐림", "windy": "바람", "snow": "눈", "fog": "안개",
    "none": "(없음)",
}

# Pokemon GO 맥스 배틀 / 파워스폿 사용 가능 종 (2026-04 기준)
# PokeMiners GAME_MASTER 의 BREAD_POKEMON_SCALING_SETTINGS (실제 배포된 풀) 기반.
# (PvPoke speciesId, has_gmax_form). 진화 전 단계는 1성 맥스, 최종진화는 3-6성 맥스 보스.
DYNAMAX_POOL = [
    # ── Gen 1 ─────────────────────────────────────────────────────────
    ("bulbasaur",   False), ("ivysaur",     False), ("venusaur",    True),
    ("charmander",  False), ("charmeleon",  False), ("charizard",   True),
    ("squirtle",    False), ("wartortle",   False), ("blastoise",   True),
    ("caterpie",    False), ("metapod",     False), ("butterfree",  True),
    ("krabby",      False), ("kingler",     True),
    ("machop",      False), ("machoke",     False), ("machamp",     True),
    ("gastly",      False), ("haunter",     False), ("gengar",      True),
    ("chansey",     False),
    ("lapras",      True),
    ("snorlax",     True),
    # 1세대 전설 새
    ("articuno",    False), ("zapdos",      False), ("moltres",     False),
    # ── Gen 2 — 전설 비스트 ──────────────────────────────────────────
    ("raikou",      False), ("entei",       False), ("suicune",     False),
    # ── Gen 3 — 메탕 라인 ────────────────────────────────────────────
    ("beldum",      False), ("metang",      False), ("metagross",   False),
    # ── Gen 5 ─────────────────────────────────────────────────────────
    ("pidove",      False), ("tranquill",   False), ("unfezant",    False),
    ("drilbur",     False), ("excadrill",   False),
    ("darumaka",    False), ("darmanitan_standard", False),
    ("cryogonal",   False),
    # ── Gen 7 ─────────────────────────────────────────────────────────
    ("passimian",   False),
    # ── Gen 8 (갈라르) ───────────────────────────────────────────────
    ("skwovet",     False), ("greedent",    False),
    ("wooloo",      False), ("dubwool",     False),
    ("grookey",     False), ("thwackey",    False), ("rillaboom",   True),
    ("scorbunny",   False), ("raboot",      False), ("cinderace",   True),
    ("sobble",      False), ("drizzile",    False), ("inteleon",    True),
    ("toxel",       False), ("toxtricity",  True),
    ("falinks",     False),
    ("kubfu",       False),
    ("urshifu_single_strike", True),  # 일격
    ("urshifu_rapid_strike",  True),  # 연격
    # ── Special ──────────────────────────────────────────────────────
    ("eternatus_eternamax", False),  # 6성 전용 보스
]

# 18 타입 → Max Move 한글명 (Sword/Shield 한국어판 기준)
MAX_MOVE_KO = {
    "normal":   "러시",     "fire":     "플레어",
    "water":    "워터",     "electric": "선더",
    "grass":    "플랜츠",   "ice":      "블리자드",
    "fighting": "너클",     "poison":   "포이즌",
    "ground":   "어스",     "flying":   "에어",
    "psychic":  "마인드",   "bug":      "버그",
    "rock":     "록",       "ghost":    "고스트",
    "dragon":   "드래곤",   "dark":     "다크",
    "steel":    "스틸",     "fairy":    "페어리",
}

# ScrapedDuck 의 보스 이름 → PvPoke speciesId 변환 규칙
_BOSS_NAME_PREFIXES = [
    ("Mega ",     "_mega"),
    ("Primal ",   "_mega"),  # 그라에/카이오 프라이멀은 PvPoke 에 없을 수 있음
    ("Alolan ",   "_alolan"),
    ("Galarian ", "_galarian"),
    ("Hisuian ",  "_hisuian"),
    ("Paldean ",  "_paldean"),
    ("Shadow ",   "_shadow"),
]


def _boss_name_to_sid(name):
    """ScrapedDuck 보스 이름 → PvPoke speciesId 후보들 (우선순위 순).
    "Shadow Alolan Marowak" 같은 복합 prefix 도 처리 (shadow + region/mega)."""
    n = name.strip()
    suffixes = []
    # 복합 prefix 반복 적용 (예: "Shadow Alolan Marowak" → shadow + alolan)
    while True:
        matched = False
        for prefix, suf in _BOSS_NAME_PREFIXES:
            if n.startswith(prefix):
                n = n[len(prefix):]
                suffixes.append(suf)
                matched = True
                break
        if not matched:
            break
    # Mega Charizard X / Y → charizard_mega_x / _mega_y
    if "_mega" in suffixes:
        if n.endswith(" X"):
            n = n[:-2]
            suffixes = [s if s != "_mega" else "_mega_x" for s in suffixes]
        elif n.endswith(" Y"):
            n = n[:-2]
            suffixes = [s if s != "_mega" else "_mega_y" for s in suffixes]
    base = n.lower().replace(".", "").replace("'", "").replace("-", "_").replace(" ", "_")
    # 후보 우선순위: (1) 모든 suffix 적용, (2) shadow 만 우선, (3) base only
    candidates = []
    if suffixes:
        # PvPoke 는 region 먼저 + shadow 마지막 순으로 sid 구성
        # (예: marowak_alolan_shadow). 우선 region/mega 다음에 shadow.
        ordered = [s for s in suffixes if s != "_shadow"] + \
                  [s for s in suffixes if s == "_shadow"]
        candidates.append(base + "".join(ordered))
        # shadow 만 단독으로도 시도 (region 없는 케이스 대비)
        if "_shadow" in suffixes:
            candidates.append(base + "_shadow")
    candidates.append(base)
    return candidates


def find_boss_pokemon(boss_name, gm):
    """보스 이름 → PvPoke pokemon 엔트리 (없으면 None)."""
    by_sid = {p["speciesId"]: p for p in gm["pokemon"]}
    for sid in _boss_name_to_sid(boss_name):
        if sid in by_sid:
            return by_sid[sid]
    return None


def _move_damage(power, atk_eff, def_eff, move_type, atk_types, def_types,
                 weather_boosted, stab_mult=1.2, weather_mult=1.2):
    """PoGO PvE 데미지 공식: floor(0.5 * Power * Atk/Def * STAB * Eff * Weather) + 1"""
    if not power:
        return 0.0
    stab = stab_mult if move_type in atk_types else 1.0
    eff = 1.0
    for d in def_types:
        if d and d != "none":
            eff *= TYPE_CHART.get(move_type, {}).get(d, 1.0)
    weather = weather_mult if weather_boosted else 1.0
    return int(0.5 * power * (atk_eff / def_eff) * stab * eff * weather) + 1


def _combo_dps(fast_dmg, fast_cd_s, fast_egain, charged_dmg, charged_cd_s, charged_ecost):
    """속공 + 차지 조합의 평균 DPS. 1 사이클 = N×속공 + 1×차지 (N = ceil(에너지/얻는량))."""
    if fast_cd_s <= 0:
        return 0.0
    if charged_ecost <= 0 or fast_egain <= 0 or charged_cd_s <= 0:
        return fast_dmg / fast_cd_s
    n = -(-charged_ecost // fast_egain)  # ceil(ec/eg)
    cycle_dmg = n * fast_dmg + charged_dmg
    cycle_time = n * fast_cd_s + charged_cd_s
    return cycle_dmg / cycle_time if cycle_time > 0 else 0.0


def attacker_dps_vs(attacker, fast, charged, boss_types,
                    boss_cpm=0.79, boss_base_def=180, weather=None,
                    attacker_level=50):
    """공격자 1마리 × (속공, 차지) 조합 → DPS / TDO / eDPS.
    attacker: PvPoke pokemon 엔트리. fast/charged: gamemaster moves 엔트리.
    boss_types: 보스 타입 list (소문자, 'none' 허용).
    weather: 날씨 string (부스트 계산), None 이면 부스트 없음.
    """
    base = attacker.get("baseStats", {})
    sid = attacker.get("speciesId", "")
    is_shadow = sid.endswith("_shadow")
    atk_mult = 1.2 if is_shadow else 1.0
    cpm_idx = min(int(round((attacker_level - 1.0) * 2)), len(CPM) - 1)
    cpm = CPM[cpm_idx]
    atk_eff = (base.get("atk", 0) + 15) * cpm * atk_mult
    def_eff = (base.get("def", 0) + 15) * cpm / (1.2 if is_shadow else 1.0)
    hp = int((base.get("hp", 0) + 15) * cpm)

    # 레이드 보스 effective Def: GamePress 공식은 base_def 만 사용 (+15 IV 가산 없음)
    boss_def_eff = boss_base_def * boss_cpm
    atk_types = [t for t in attacker.get("types", []) if t and t != "none"]

    boosted_types = WEATHER_BOOSTS.get(weather, set()) if weather else set()
    fast_dmg = _move_damage(fast.get("power", 0), atk_eff, boss_def_eff,
                            fast.get("type", ""), atk_types, boss_types,
                            fast.get("type", "") in boosted_types)
    charged_dmg = _move_damage(charged.get("power", 0), atk_eff, boss_def_eff,
                               charged.get("type", ""), atk_types, boss_types,
                               charged.get("type", "") in boosted_types)
    dps = _combo_dps(fast_dmg, fast.get("cooldown", 1000) / 1000.0,
                     fast.get("energyGain", 0),
                     charged_dmg, charged.get("cooldown", 500) / 1000.0,
                     charged.get("energy", 0))
    # TDO 근사: HP * DPS / 보스가 1초당 우리에게 입히는 추정데미지
    # 단순화: 보스 base atk 대비 우리 def 비율 사용. 정확도 보다는 ranking 보조용.
    boss_atk_assumed = boss_base_def * 1.5  # 대략 atk ≈ def * 1.5
    incoming_dps = max(1.0, boss_atk_assumed * boss_cpm / def_eff * 35.0)
    survival_s = hp / incoming_dps
    tdo = dps * survival_s
    edps = (dps * tdo) ** 0.5 if tdo > 0 else 0.0
    return {"dps": dps, "tdo": tdo, "edps": edps,
            "fast_dmg": fast_dmg, "charged_dmg": charged_dmg, "hp": hp}


def best_moveset_vs(attacker, boss_types, moves_by_id, boss_cpm=0.79,
                    boss_base_def=180, weather=None, attacker_level=50):
    """공격자의 모든 (속공×차지) 조합 중 eDPS 최고 무브셋 반환."""
    fasts = (attacker.get("fastMoves") or []) + (attacker.get("eliteMoves") or [])
    chargeds = (attacker.get("chargedMoves") or []) + (attacker.get("eliteMoves") or [])
    best = None
    for fid in fasts:
        f = moves_by_id.get(fid)
        if not f or f.get("energyGain", 0) <= 0:
            continue
        for cid in chargeds:
            c = moves_by_id.get(cid)
            if not c or c.get("energy", 0) <= 0:
                continue
            r = attacker_dps_vs(attacker, f, c, boss_types,
                                boss_cpm, boss_base_def, weather, attacker_level)
            if best is None or r["edps"] > best["edps"]:
                best = {**r, "fast_id": fid, "charged_id": cid,
                        "fast_type": f.get("type", ""), "charged_type": c.get("type", "")}
    return best


def top_counters(boss, gm, moves_by_id, n=20, weather=None,
                 include_shadow=True, include_mega=True,
                 include_legendary=True, attacker_level=50,
                 favorites_only=None, force_boss_cpm=None):
    """보스 → 카운터 TOP N. boss = pokemon 엔트리 (또는 dict with 'types','baseStats').
    favorites_only: set of speciesIds to restrict to (None = 전체).
    force_boss_cpm: 지정 시 티어 추정 무시하고 이 CPM 사용 (예: 맥스 배틀 1.0)."""
    boss_types = [t for t in boss.get("types", []) if t and t != "none"]
    boss_base_def = boss.get("baseStats", {}).get("def", 180)
    boss_sid = boss.get("speciesId", "")
    if force_boss_cpm is not None:
        boss_cpm = force_boss_cpm
    elif "_mega" in boss_sid:
        boss_cpm = RAID_TIER_CPM["mega"]
    else:
        boss_cpm = RAID_TIER_CPM["5"]

    results = []
    for p in gm.get("pokemon", []):
        sid = p.get("speciesId", "")
        if sid == boss_sid:
            continue  # 자기 자신 제외
        if p.get("released") is False:
            continue  # PvPoke 가 미출시로 표시한 종 (eternamax, primal 등) 제외
        if not include_shadow and sid.endswith("_shadow"):
            continue
        if not include_mega and sid.endswith(("_mega", "_mega_x", "_mega_y")):
            continue
        if favorites_only is not None and sid not in favorites_only:
            continue
        if not include_legendary:
            tags = p.get("tags") or []
            if "legendary" in tags or "mythical" in tags:
                continue
        bm = best_moveset_vs(p, boss_types, moves_by_id, boss_cpm,
                             boss_base_def, weather, attacker_level)
        if bm is None:
            continue
        results.append({"sid": sid, "pokemon": p, **bm})
    results.sort(key=lambda r: r["edps"], reverse=True)
    return results[:n]


# (species_base_id, move_id) → 획득 경로. PvPoke 의 eliteMoves 는 단일 boolean 이라
# "커뮤데이/레이드/일반 엘리트 TM" 을 구분하지 못하므로, 신뢰도 높은 항목만
# 직접 큐레이팅. 등록되지 않은 elite 항목은 "엘리트 TM" 으로 표시된다.
SPECIAL_MOVE_SOURCE = {
    # ─── 커뮤니티 데이 시그니처 기술 (CD 진화 시 학습 / 이후 엘리트 TM 필요) ─────
    # 풀 스타터 — 마기라스 → 프렌지 플랜트
    ("venusaur",   "FRENZY_PLANT"): "cd",
    ("meganium",   "FRENZY_PLANT"): "cd",
    ("sceptile",   "FRENZY_PLANT"): "cd",
    ("torterra",   "FRENZY_PLANT"): "cd",
    ("serperior",  "FRENZY_PLANT"): "cd",
    ("chesnaught", "FRENZY_PLANT"): "cd",
    ("decidueye",  "FRENZY_PLANT"): "cd",
    ("rillaboom",  "FRENZY_PLANT"): "cd",
    # 불꽃 스타터 → 블래스트 번
    ("charizard",  "BLAST_BURN"): "cd",
    ("typhlosion", "BLAST_BURN"): "cd",
    ("blaziken",   "BLAST_BURN"): "cd",
    ("infernape",  "BLAST_BURN"): "cd",
    ("emboar",     "BLAST_BURN"): "cd",
    ("delphox",    "BLAST_BURN"): "cd",
    ("incineroar", "BLAST_BURN"): "cd",
    ("cinderace",  "BLAST_BURN"): "cd",
    # 물 스타터 → 하이드로 캐논
    ("blastoise",  "HYDRO_CANNON"): "cd",
    ("feraligatr", "HYDRO_CANNON"): "cd",
    ("swampert",   "HYDRO_CANNON"): "cd",
    ("empoleon",   "HYDRO_CANNON"): "cd",
    ("samurott",   "HYDRO_CANNON"): "cd",
    ("greninja",   "HYDRO_CANNON"): "cd",
    ("primarina",  "HYDRO_CANNON"): "cd",
    # 단일 라인 CD 시그니처
    ("metagross",  "METEOR_MASH"):    "cd",  # 메탕 CD (2019.03)
    ("mamoswine",  "ANCIENT_POWER"):  "cd",  # 꾸꾸리 CD (2019.02)
    ("haxorus",    "BREAKING_SWIPE"): "cd",  # 압치 CD (2023.09)
    ("altaria",    "MOONBLAST"):      "cd",  # 파비코리 CD (2019.04)
    ("gardevoir",  "SYNCHRONOISE"):   "cd",  # 랄토스 CD (2020.08)
    ("gallade",    "SYNCHRONOISE"):   "cd",  # 랄토스 CD
    ("garchomp",   "EARTH_POWER"):    "cd",  # 딥상어동 CD (2022.06)
    ("ampharos",   "DRAGON_PULSE"):   "cd",  # 메리프 CD (2018.04)
    ("togekiss",   "AURA_SPHERE"):    "cd",  # 토게틱 CD (2025.05)
    ("kingdra",    "WATER_GUN"):      "cd",  # 쏘드라 CD (2020.05)
    ("charizard",  "DRAGON_BREATH"):  "cd",  # 파이리 CD 클래식 (2024.05)
    # 이브이 + 진화체 시그니처 (이브이 CD 2018.08 + 2022.08 주말 이벤트)
    ("eevee",    "LAST_RESORT"): "cd",
    ("vaporeon", "LAST_RESORT"): "cd",
    ("vaporeon", "SCALD"):       "cd",
    ("jolteon",  "LAST_RESORT"): "cd",
    ("jolteon",  "ZAP_CANNON"):  "cd",
    ("flareon",  "LAST_RESORT"): "cd",
    ("flareon",  "SUPER_POWER"): "cd",
    ("espeon",   "LAST_RESORT"): "cd",
    ("espeon",   "SHADOW_BALL"): "cd",
    ("umbreon",  "LAST_RESORT"): "cd",
    ("umbreon",  "PSYCHIC"):     "cd",
    ("leafeon",  "LAST_RESORT"): "cd",
    ("leafeon",  "BULLET_SEED"): "cd",
    ("glaceon",  "LAST_RESORT"): "cd",
    ("glaceon",  "WATER_PULSE"): "cd",
    ("sylveon",  "LAST_RESORT"): "cd",
    ("sylveon",  "PSYSHOCK"):    "cd",
    # ─── 레이드 데이 / EX 레이드 / 특별 이벤트 시그니처 ──────────────────────
    ("lugia",    "AEROBLAST"):      "raid",  # 레이드 데이 (2018.03)
    ("ho_oh",    "SACRED_FIRE"):    "raid",  # 레이드 데이 (2018.08)
    ("mewtwo",   "PSYSTRIKE"):      "raid",  # EX 레이드 (2018.09)
    ("mewtwo",   "SHADOW_BALL"):    "raid",  # 한정 레이드 (2017.12)
    ("rayquaza", "DRAGON_ASCENT"):  "raid",  # 유료 스페셜 리서치
    ("rayquaza", "BREAKING_SWIPE"): "raid",  # 레이드 아워 (2023.05)
}

ACQ_LABEL = {
    "cd":      "커뮤데이",
    "raid":    "레이드",
    "elite":   "엘리트 TM",
    "regular": "",
}


def _species_base(sid):
    """speciesId 에서 _shadow / _mega / _mega_x / _mega_y 접미사를 떼어 기본형 반환."""
    while True:
        for suf in ("_shadow", "_mega_x", "_mega_y", "_mega"):
            if sid.endswith(suf):
                sid = sid[:-len(suf)]
                break
        else:
            return sid


def move_acquisition(pokemon, move_id, elite_set):
    """주어진 (포켓몬, 기술) 의 획득 경로 분류 → 'cd' / 'raid' / 'elite' / 'regular'."""
    base = _species_base(pokemon.get("speciesId", ""))
    cat = SPECIAL_MOVE_SOURCE.get((base, move_id))
    if cat:
        return cat
    if move_id in elite_set:
        return "elite"
    return "regular"


def load_move_ko_map(force=False):
    """PvPoke/PokeAPI 슬러그 ('mud-shot') → 한글 기술명 ('머드 샷')."""
    for cache, url, label in (
        (CACHE_MOVES, MOVES_CSV_URL, "기술 리스트"),
        (CACHE_MOVE_NAMES, MOVE_NAMES_CSV_URL, "기술 한글명"),
    ):
        _ensure_file(cache, lambda p, u=url: _download(u, p),
                     label, STATIC_MAX_AGE_DAYS, force)
        if not os.path.exists(cache):
            return dict(MOVE_KO_OVERRIDES)

    id_to_slug = {}
    with open(CACHE_MOVES, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 2:
                try:
                    id_to_slug[int(row[0])] = row[1]
                except ValueError:
                    pass

    slug_to_ko = {}
    with open(CACHE_MOVE_NAMES, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 3 and row[1] == "3":  # Korean
                try:
                    slug = id_to_slug.get(int(row[0]))
                    if slug:
                        slug_to_ko[slug] = row[2].strip()
                except ValueError:
                    pass
    slug_to_ko.update(MOVE_KO_OVERRIDES)
    return slug_to_ko


def prettify_move(move_id, ko_map=None):
    if ko_map:
        slug = move_id.lower().replace("_", "-")
        if slug in ko_map:
            return ko_map[slug]
    return " ".join(w.capitalize() for w in move_id.split("_"))


def sprite_variants_for(pokemon):
    """Showdown sprite 파일명 후보 (변형형 → 베이스 fallback)."""
    sid = (pokemon.get("speciesId") or "").lower()
    if not sid:
        return []

    # 1) 변형 포함 이름 (charizard_mega_y → charizard-megay)
    s1 = sid
    for k, v in SHOWDOWN_VARIANT_TRANSFORMS:
        s1 = s1.replace(k, v)
    s1 = s1.replace("_shadow", "").replace("_", "")

    # 2) 변형 접미사 제거 + underscore flatten (그림자/변형 → 베이스)
    base = sid
    for k, _ in SHOWDOWN_VARIANT_TRANSFORMS:
        if base.endswith(k):
            base = base[: -len(k)]
            break
    if base.endswith("_shadow"):
        base = base[: -len("_shadow")]
    s2 = base.replace("_", "")

    # 3) 코스프레/커스텀 폼은 첫 단어만 (pikachu_libre → pikachu)
    first_part = sid.split("_")[0]

    seen, results = set(), []
    for n in (s1, s2, first_part):
        if n and n not in seen:
            seen.add(n)
            results.append(n)
    return results


def get_sprite_path(pokemon):
    """캐시된 PNG 경로 반환. 없으면 다운로드 시도. 실패 시 None."""
    os.makedirs(SPRITE_DIR, exist_ok=True)
    for name in sprite_variants_for(pokemon):
        local = os.path.join(SPRITE_DIR, f"{name}.png")
        if os.path.exists(local):
            if os.path.getsize(local) > 0:
                return local
            os.remove(local)  # 0바이트 불량 캐시
        try:
            _download(f"{SPRITE_URL_BASE}/{name}.png", local)
            if os.path.getsize(local) > 0:
                return local
            os.remove(local)
        except Exception:
            # 다음 후보 (base dex)로 fallback
            continue
    return None


def get_family_chain(gm, species_id):
    """선택 포켓몬의 진화 단계 리스트 (단계별 sid 묶음).
    예: squirtle → [['squirtle'], ['wartortle'], ['blastoise']]
        eevee    → [['eevee'], ['vaporeon','jolteon',...]]
    변형(그림자/메가)일 경우 해당 변형의 family 우선, 없으면 베이스로.
    """
    by_sid = {p.get("speciesId"): p for p in gm["pokemon"]}
    p = by_sid.get(species_id)
    fam = p.get("family") if p else None

    # family 없으면 변형 suffix를 단계별로 벗겨내며 베이스 sid로 fallback
    if not fam:
        base = species_id
        stripped = False
        if base.endswith("_shadow"):
            base = base[: -len("_shadow")]; stripped = True
        for key, _pair in MEGA_VARIANTS:
            if base.endswith("_" + key):
                base = base[: -(len(key) + 1)]; stripped = True; break
        for key, _kor in REGIONAL_VARIANTS:
            if base.endswith("_" + key):
                base = base[: -(len(key) + 1)]; stripped = True; break
        if stripped and base in by_sid and by_sid[base].get("family"):
            p = by_sid[base]
            fam = p["family"]
            species_id = base
        if not fam:
            return []

    # Walk back to root
    root = species_id
    visited = {root}
    while True:
        pr = by_sid.get(root, {}).get("family", {}) or {}
        parent = pr.get("parent")
        if not parent or parent not in by_sid or parent in visited:
            break
        visited.add(parent)
        root = parent

    # BFS forward
    stages = [[root]]
    seen = {root}
    while True:
        next_stage = []
        for sid in stages[-1]:
            fam_here = by_sid.get(sid, {}).get("family", {}) or {}
            for evo in fam_here.get("evolutions", []) or []:
                if evo in by_sid and evo not in seen:
                    next_stage.append(evo)
                    seen.add(evo)
        if not next_stage:
            break
        stages.append(next_stage)
    return stages


def build_ko_base_map(gm, dex_to_ko):
    """CLI용: 한글 베이스명(공백제거/소문자) → speciesId."""
    ko_to_sid = {}
    for p in gm["pokemon"]:
        dex = p.get("dex")
        sname = p.get("speciesName", "")
        sid = p.get("speciesId", "")
        if dex in dex_to_ko and "(" not in sname:
            ko_norm = dex_to_ko[dex].replace(" ", "").lower()
            ko_to_sid.setdefault(ko_norm, sid)
    return ko_to_sid


def _strip_variant_suffixes(sid):
    """sid에서 shadow/mega/region 제거한 'clean' sid 반환 (form_suffix는 남김)."""
    clean = sid
    if clean.endswith("_shadow"):
        clean = clean[: -len("_shadow")]
    for key, _pair in MEGA_VARIANTS:
        if clean.endswith("_" + key):
            clean = clean[: -(len(key) + 1)]
            break
    for key, _kor in REGIONAL_VARIANTS:
        if clean.endswith("_" + key):
            clean = clean[: -(len(key) + 1)]
            break
    return clean


def _decompose_sid(sid, by_sid, dex_common_base=None):
    """sid → (base_sid, is_shadow, mega_pair, region_kor, form_suffix).
    dex 번호가 같은 항목만 '폼'으로 취급 (porygon_z 같이 이름만 비슷한 별종은 베이스 유지).
    by_sid에 prefix가 없을 때 dex_common_base[dex] 도 시도."""
    this_dex = by_sid.get(sid, {}).get("dex")
    is_shadow = False
    rest = sid
    if rest.endswith("_shadow"):
        is_shadow = True
        rest = rest[: -len("_shadow")]

    mega_pair = ("", "")
    for key, pair in MEGA_VARIANTS:
        if rest.endswith("_" + key):
            rest = rest[: -(len(key) + 1)]
            mega_pair = pair
            break

    region_kor = ""
    for key, kor in REGIONAL_VARIANTS:
        if rest.endswith("_" + key):
            rest = rest[: -(len(key) + 1)]
            region_kor = kor
            break

    base_sid = rest
    form_suffix = ""
    parts = rest.split("_")
    for i in range(len(parts) - 1, 0, -1):
        pref = "_".join(parts[:i])
        pref_p = by_sid.get(pref)
        if pref_p and pref_p.get("dex") == this_dex:
            base_sid = pref
            form_suffix = "_".join(parts[i:])
            break

    if base_sid == rest and not form_suffix and dex_common_base:
        cb = dex_common_base.get(this_dex, "")
        if cb and cb != rest and rest.startswith(cb + "_"):
            base_sid = cb
            form_suffix = rest[len(cb) + 1:]

    # form_suffix 안에 region이 prefix로 들어있으면 분리 (예: darmanitan_galarian_standard)
    if form_suffix and not region_kor:
        for key, kor in REGIONAL_VARIANTS:
            if form_suffix == key:
                region_kor = kor
                form_suffix = ""
                break
            if form_suffix.startswith(key + "_"):
                region_kor = kor
                form_suffix = form_suffix[len(key) + 1:]
                break
    return base_sid, is_shadow, mega_pair, region_kor, form_suffix


def _compose_display(base_name, is_shadow, mega_pair, region_kor, form_ko):
    mega_p, mega_s = mega_pair
    main = base_name
    if mega_s:
        main = f"{main}{mega_s}"
    prefix_parts = []
    if is_shadow:
        prefix_parts.append("그림자")
    if mega_p:
        prefix_parts.append(mega_p)
    if region_kor:
        prefix_parts.append(region_kor)
    prefix_parts.append(main)
    disp = " ".join(prefix_parts)
    if form_ko:
        disp = f"{disp} ({form_ko})"
    return disp


def build_sid_display_full(gm, dex_to_ko):
    """모든 sid → 한글 디스플레이 (dedupe 없음, released=False 포함).
    build_display_entries 가 dedupe 로 빠뜨린 폼들을 위한 보조 맵."""
    by_sid = {p.get("speciesId"): p for p in gm["pokemon"]}
    dex_clean_sids = {}
    for p in gm["pokemon"]:
        sid = p.get("speciesId", "")
        dex_clean_sids.setdefault(p.get("dex"), set()).add(_strip_variant_suffixes(sid))
    dex_common_base = {}
    for dex, sset in dex_clean_sids.items():
        if len(sset) <= 1:
            continue
        slist = sorted(sset)
        common = slist[0]
        for s in slist[1:]:
            while common and not s.startswith(common):
                common = common[:-1]
        common = common.rstrip("_")
        if common:
            dex_common_base[dex] = common
    out = {}
    for p in gm["pokemon"]:
        sid = p.get("speciesId", "")
        base_sid, is_shadow, mega_pair, region_kor, form_suffix = _decompose_sid(
            sid, by_sid, dex_common_base
        )
        base_name = (
            dex_to_ko.get(p.get("dex"))
            or by_sid.get(base_sid, {}).get("speciesName")
            or p.get("speciesName", sid)
        )
        form_ko = FORM_KO.get(form_suffix, form_suffix.replace("_", " ")) if form_suffix else ""
        out[sid] = _compose_display(base_name, is_shadow, mega_pair, region_kor, form_ko)
    return out


def build_display_entries(gm, dex_to_ko):
    """GUI용: [(display_name, speciesId), ...] 전체 released 포켓몬 + 변형.
    같은 (dex, shadow, mega, region) 그룹 안에서 baseStats가 동일한 폼은
    PvP 결과가 같으므로 1개만 통과시키고, 그룹 안에 stats 다른 폼이 있을 때만
    폼 한글명을 표시한다."""
    by_sid = {p.get("speciesId"): p for p in gm["pokemon"]}

    dex_clean_sids = {}
    for p in gm["pokemon"]:
        if p.get("released", True) is False:
            continue
        sid = p.get("speciesId", "")
        dex_clean_sids.setdefault(p.get("dex"), set()).add(_strip_variant_suffixes(sid))

    dex_common_base = {}
    for dex, sset in dex_clean_sids.items():
        if len(sset) <= 1:
            continue
        slist = sorted(sset)
        common = slist[0]
        for s in slist[1:]:
            while common and not s.startswith(common):
                common = common[:-1]
        common = common.rstrip("_")
        if common:
            dex_common_base[dex] = common

    group_bs = {}
    for p in gm["pokemon"]:
        if p.get("released", True) is False:
            continue
        sid = p.get("speciesId", "")
        _, is_shadow, mega_pair, region_kor, _ = _decompose_sid(sid, by_sid, dex_common_base)
        bs = p.get("baseStats", {})
        types_key = tuple(p.get("types", []))
        bs_key = (bs.get("atk", 0), bs.get("def", 0), bs.get("hp", 0), types_key)
        group_bs.setdefault(
            (p.get("dex"), is_shadow, mega_pair, region_kor), set()
        ).add(bs_key)

    entries = []
    seen = set()
    for p in gm["pokemon"]:
        if p.get("released", True) is False:
            continue
        sid = p.get("speciesId", "")
        sname = p.get("speciesName", sid)
        dex = p.get("dex")

        base_sid, is_shadow, mega_pair, region_kor, form_suffix = _decompose_sid(
            sid, by_sid, dex_common_base
        )
        bs = p.get("baseStats", {})
        types_key = tuple(p.get("types", []))
        bs_key = (bs.get("atk", 0), bs.get("def", 0), bs.get("hp", 0), types_key)
        dedupe_key = (dex, is_shadow, mega_pair, region_kor, bs_key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        base_name = (
            dex_to_ko.get(dex)
            or by_sid.get(base_sid, {}).get("speciesName")
            or sname
        )

        unique_bs = len(group_bs.get((dex, is_shadow, mega_pair, region_kor), set()))
        form_ko = ""
        if form_suffix and unique_bs > 1:
            form_ko = FORM_KO.get(form_suffix, form_suffix.replace("_", " "))

        display = _compose_display(base_name, is_shadow, mega_pair, region_kor, form_ko)
        entries.append((display, sid))

    count = {}
    for d, _ in entries:
        count[d] = count.get(d, 0) + 1
    result = []
    for d, s in entries:
        if count[d] > 1:
            result.append((f"{d} [{s}]", s))
        else:
            result.append((d, s))
    return result


# ----- math -----

def compute_cp(base, ivs, cpm):
    atk = base["atk"] + ivs[0]
    defn = base["def"] + ivs[1]
    hp = base["hp"] + ivs[2]
    cp = (atk * (defn ** 0.5) * (hp ** 0.5) * (cpm ** 2)) / 10
    return max(10, int(cp))


def stat_product(base, ivs, cpm):
    atk = (base["atk"] + ivs[0]) * cpm
    defn = (base["def"] + ivs[1]) * cpm
    hp = int((base["hp"] + ivs[2]) * cpm)
    return atk * defn * hp


def best_level_under_cap(base, ivs, cp_cap, max_idx):
    if cp_cap is None:
        cpm = CPM[max_idx]
        return (max_idx, cpm, compute_cp(base, ivs, cpm))
    # CP는 레벨에 단조 증가 → 이진 탐색으로 cap 이하 최고 idx 찾기
    lo, hi = 0, max_idx
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if compute_cp(base, ivs, CPM[mid]) <= cp_cap:
            lo = mid
        else:
            hi = mid - 1
    cpm = CPM[lo]
    cp = compute_cp(base, ivs, cpm)
    if cp > cp_cap:
        return None  # Lv1조차 cap 초과 (드물지만 little cup에서 가능)
    return (lo, cpm, cp)


def rank_all(base, cp_cap, max_idx):
    # 핫루프: 지역 바인딩 + 인라인으로 함수 호출 오버헤드 제거
    atk_b, def_b, hp_b = base["atk"], base["def"], base["hp"]
    cpm_table = CPM
    results = []
    append = results.append

    if cp_cap is None:
        # 마스터리그: 전 IV가 max_idx에서 best — 스캔 불필요
        cpm = cpm_table[max_idx]
        cpm2 = cpm * cpm
        for a in range(16):
            atk = atk_b + a
            for d in range(16):
                defn = def_b + d
                for h in range(16):
                    hp = hp_b + h
                    cp = max(10, int((atk * (defn ** 0.5) * (hp ** 0.5) * cpm2) / 10))
                    sp = (atk * cpm) * (defn * cpm) * int(hp * cpm)
                    append(((a, d, h), sp, max_idx, cp))
    else:
        for a in range(16):
            atk = atk_b + a
            for d in range(16):
                defn = def_b + d
                d_root = defn ** 0.5
                for h in range(16):
                    hp = hp_b + h
                    h_root = hp ** 0.5
                    # 인라인 이진 탐색 — 실제 게임 CP는 int 캐스팅이므로 int 비교
                    lo, hi = 0, max_idx
                    while lo < hi:
                        mid = (lo + hi + 1) // 2
                        cpm_m = cpm_table[mid]
                        cp_m = max(10, int((atk * d_root * h_root * cpm_m * cpm_m) / 10))
                        if cp_m <= cp_cap:
                            lo = mid
                        else:
                            hi = mid - 1
                    cpm = cpm_table[lo]
                    cp = max(10, int((atk * d_root * h_root * cpm * cpm) / 10))
                    if cp > cp_cap:
                        append(((a, d, h), 0.0, -1, 0))
                    else:
                        sp = (atk * cpm) * (defn * cpm) * int(hp * cpm)
                        append(((a, d, h), sp, lo, cp))
    results.sort(key=lambda r: (-r[1], -(r[0][0] + r[0][1] + r[0][2])))
    return results


def level_from_idx(idx):
    return 1.0 + idx * 0.5


def idx_from_level(lvl):
    return int(round((lvl - 1.0) * 2))


def power_up_cost(start_idx, end_idx):
    """idx 단위로 강화 비용 합산. (별의모래, 사탕, XL사탕) 반환."""
    if end_idx <= start_idx:
        return (0, 0, 0)
    dust = candy = xl = 0
    for i in range(start_idx, min(end_idx, len(POWER_UP_COST))):
        d, c, x = POWER_UP_COST[i]
        dust += d
        candy += c
        xl += x
    return (dust, candy, xl)


def type_effectiveness(types):
    """방어 타입 리스트 → {공격타입: 배수} 딕셔너리."""
    result = {}
    for atk in TYPE_CHART:
        mult = 1.0
        for d in types:
            mult *= TYPE_CHART[atk].get(d, 1.0)
        result[atk] = mult
    return result


def find_iv_candidates(base, displayed_cp, displayed_hp, level_range=None,
                       max_idx=None):
    """CP+HP 매칭되는 (idx, (a,d,h)) 후보. level_range = (min_idx, max_idx)."""
    if max_idx is None:
        max_idx = len(CPM) - 1
    if level_range is None:
        lo, hi = 0, max_idx
    else:
        lo, hi = level_range
        hi = min(hi, max_idx)
    out = []
    for idx in range(lo, hi + 1):
        cpm = CPM[idx]
        for h in range(16):
            hp_calc = int((base["hp"] + h) * cpm)
            if hp_calc != displayed_hp:
                continue
            for a in range(16):
                for d in range(16):
                    if compute_cp(base, (a, d, h), cpm) == displayed_cp:
                        out.append((idx, (a, d, h)))
    return out


def analyze_pokemon(pokemon, ivs, max_level):
    """Returns list of (league_name, level, cp, sp, rank, pct, best_iv) + summary best."""
    max_idx = min(int(round((max_level - 1.0) * 2)), len(CPM) - 1)
    base = pokemon["baseStats"]
    rows = []
    best_rec = None
    for lg in LEAGUES:
        ranked = rank_all(base, lg.cap, max_idx)
        top_sp = ranked[0][1]
        top_iv = ranked[0][0]
        user_entry = None
        user_rank = None
        for rank_idx, entry in enumerate(ranked, 1):
            if entry[0] == tuple(ivs):
                user_entry = entry
                user_rank = rank_idx
                break
        if user_entry is None or user_entry[2] == -1 or top_sp == 0:
            rows.append((lg.name, None, None, None, None, None, None))
            continue
        _, sp, lvl_idx, cp = user_entry
        pct = sp / top_sp * 100
        lvl = level_from_idx(lvl_idx)
        rows.append((lg.name, lvl, cp, sp, user_rank, pct, top_iv))
        if best_rec is None or pct > best_rec[5]:
            best_rec = (lg.name, lvl, cp, sp, user_rank, pct, top_iv)
    return rows, best_rec


# ----- CLI -----

def strip_variant_cli(name):
    cleaned = name.strip()
    for kw, suffix in KOREAN_VARIANT_PREFIXES:
        for form in (kw + " ", kw):
            if cleaned.startswith(form):
                rest = cleaned[len(form):].strip()
                if rest:
                    return rest, suffix
    return cleaned, ""


def find_pokemon_cli(gm, ko_base_map, name):
    cleaned = name.strip()
    base, suffix = strip_variant_cli(cleaned)
    base_norm = base.replace(" ", "").lower()

    if base_norm in ko_base_map:
        target = (ko_base_map[base_norm] + suffix).lower()
        for p in gm["pokemon"]:
            if p.get("speciesId", "").lower() == target:
                return p, []
        cands = [p for p in gm["pokemon"]
                 if p.get("speciesId", "").lower().startswith(target)]
        if cands:
            cands.sort(key=lambda p: len(p["speciesId"]))
            return cands[0], [c["speciesId"] for c in cands[1:5]]

    needle = cleaned.lower().replace(" ", "_").replace("-", "_")
    for p in gm["pokemon"]:
        if p.get("speciesId", "").lower() == needle:
            return p, []
    for p in gm["pokemon"]:
        if p.get("speciesName", "").lower() == cleaned.lower():
            return p, []
    words = cleaned.lower().replace("-", " ").split()
    matches = [p for p in gm["pokemon"]
               if all(w in p.get("speciesId", "").lower() for w in words)]
    if matches:
        matches.sort(key=lambda p: len(p["speciesId"]))
        return matches[0], [m["speciesId"] for m in matches[1:5]]
    return None, []


def _dwidth(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def _pad(s, w):
    return str(s) + " " * max(w - _dwidth(s), 0)


def analyze_cli(gm, ko_base_map, sid_to_display, name, ivs, max_level):
    p, alts = find_pokemon_cli(gm, ko_base_map, name)
    if not p:
        print(f"'{name}' — 찾을 수 없음. 예: 마릴리, 메가 갸라도스, 그림자 뮤츠")
        return
    if alts:
        print(f"[다른 후보: {', '.join(alts)}]")

    rows, best = analyze_pokemon(p, ivs, max_level)
    base = p["baseStats"]
    sid = p["speciesId"]
    disp = sid_to_display.get(sid, p.get("speciesName", sid))
    print(f"\n=== {disp} ({sid}) ===")
    print(f"종족값: Atk {base['atk']} / Def {base['def']} / HP {base['hp']}")
    print(f"입력 개체값: {ivs[0]}/{ivs[1]}/{ivs[2]}\n")

    headers = ["리그", "레벨", "CP", "스탯곱(SP)", "랭크", "베스트대비", "리그 베스트 IV"]
    table = [headers]
    for r in rows:
        if r[1] is None:
            table.append([r[0], "—", "—", "—", "—", "—", "—"])
        else:
            league, lvl, cp, sp, rank, pct, best_iv = r
            table.append([
                league, f"Lv{lvl:g}", str(cp), f"{sp:,.0f}",
                f"#{rank}/4096", f"{pct:.2f}%",
                f"{best_iv[0]}/{best_iv[1]}/{best_iv[2]}",
            ])
    widths = [max(_dwidth(row[i]) for row in table) for i in range(len(headers))]
    for i, row in enumerate(table):
        print("  ".join(_pad(c, w) for c, w in zip(row, widths)))
        if i == 0:
            print("  ".join("-" * w for w in widths))

    if best:
        league, lvl, cp, _, rank, pct, _ = best
        print(f"\n★ 추천: {league} — 베스트 대비 {pct:.2f}%, "
              f"랭크 #{rank}/4096 @ Lv{lvl:g}, CP {cp}")


def parse_ivs(s):
    parts = s.replace(",", " ").replace("/", " ").split()
    if len(parts) != 3:
        raise ValueError("개체값 3개 필요 (공/방/체)")
    vals = [int(x) for x in parts]
    if any(v < 0 or v > 15 for v in vals):
        raise ValueError("개체값은 0~15 범위")
    return vals


def run_cli(args, gm):
    dex_to_ko = load_korean_dex_map()
    ko_base_map = build_ko_base_map(gm, dex_to_ko)
    sid_to_display = {sid: disp for disp, sid in build_display_entries(gm, dex_to_ko)}

    if args.pokemon and len(args.ivs) == 3:
        ivs = parse_ivs(" ".join(args.ivs))
        analyze_cli(gm, ko_base_map, sid_to_display, args.pokemon, ivs, args.max_level)
        return

    print("Pokemon GO PvP 개체값 리그 랭커 (CLI)")
    print(f"최대 레벨: {args.max_level}  (XL사탕 없으면 --max-level 40)")
    print("종료: 빈 줄에서 엔터 또는 Ctrl+C\n")
    while True:
        try:
            name = input("포켓몬: ").strip()
            if not name:
                print("종료.")
                break
            iv_str = input("개체값 (예: 1 15 14): ").strip()
            ivs = parse_ivs(iv_str)
            analyze_cli(gm, ko_base_map, sid_to_display, name, ivs, args.max_level)
            print()
        except (KeyboardInterrupt, EOFError):
            print("\n종료.")
            break
        except ValueError as e:
            print(f"입력 오류: {e}\n")


# ----- GUI -----

def run_gui(gm):
    import tkinter as tk
    from tkinter import ttk, messagebox

    # ----- mutable bindings (refresh-에서 재할당 가능하도록 list로 wrapping) -----
    state = {"gm": gm}

    dex_to_ko = load_korean_dex_map()
    entries = build_display_entries(gm, dex_to_ko)
    display_to_sid = dict(entries)
    sid_to_display = {s: d for d, s in entries}
    sid_to_display_full = build_sid_display_full(gm, dex_to_ko)
    # build_display_entries 가 dedupe 한 폼들 보충 (큐레무 화이트, 게노세크트 드라이브 등)
    for sid, disp in sid_to_display_full.items():
        sid_to_display.setdefault(sid, disp)
    all_displays_full = sorted(display_to_sid.keys(), key=lambda s: s.lower())

    # Preload league meta rankings (PvPoke overall)
    rankings = {}
    rankings_index = {}  # league_name → {sid: 1-based rank}
    for lg in LEAGUES:
        rk = load_league_rankings(lg.cup_id, lg.cap)
        rankings[lg.name] = rk
        rankings_index[lg.name] = {
            e.get("speciesId", ""): i + 1 for i, e in enumerate(rk)
        }
    # PvPoke 가 랭킹을 공개하지 않은 컵 (e.g. championshipseries 404) 은 드롭다운에서 제거
    LEAGUES[:] = [lg for lg in LEAGUES if rankings.get(lg.name)]

    # Korean move name map
    move_ko_map = load_move_ko_map()

    # Move data lookup (gamemaster)
    moves_by_id = {m["moveId"]: m for m in gm.get("moves", [])}

    # 즐겨찾기 + 설정
    favorites = load_favorites()
    settings = load_settings()

    def norm(s):
        return s.lower().replace(" ", "")

    def _category(sid):
        if sid.endswith(("_mega", "_mega_x", "_mega_y")):
            return "mega"
        if sid.endswith("_shadow"):
            return "shadow"
        return "normal"

    def filter_displays(query, only_favs=False,
                        show_normal=True, show_shadow=True, show_mega=True):
        q = norm(query)
        allowed = set()
        if show_normal: allowed.add("normal")
        if show_shadow: allowed.add("shadow")
        if show_mega:   allowed.add("mega")
        pool = [d for d in all_displays_full
                if _category(display_to_sid[d]) in allowed
                and (not only_favs or display_to_sid[d] in favorites)]
        if not q:
            return pool
        scored = []
        for d in pool:
            nd = norm(d)
            ns = display_to_sid[d].lower()
            if q in nd or q in ns:
                starts = 0 if (nd.startswith(q) or ns.startswith(q)) else 1
                scored.append((starts, len(d), d))
        scored.sort()
        return [d for *_, d in scored]

    def display_with_star(d):
        return ("★ " + d) if display_to_sid.get(d) in favorites else "   " + d

    def strip_star(d):
        if d.startswith("★ ") or d.startswith("☆ "):
            return d[2:]
        if d.startswith("   "):
            return d[3:]
        return d

    root = tk.Tk()
    root.title("Pokemon GO 개체값 리그 랭커")
    geom = settings.get("geometry", "1360x840")
    try:
        root.geometry(geom)
    except Exception:
        root.geometry("1360x840")
    root.minsize(1280, 740)

    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass

    # ===== Left: search + pokemon list =====
    left = ttk.Frame(root, padding=(12, 12, 6, 12))
    left.pack(side="left", fill="y")

    ttk.Label(left, text="포켓몬 검색", font=("", 10, "bold")).pack(anchor="w")
    search_var = tk.StringVar()

    search_row = ttk.Frame(left)
    search_row.pack(fill="x", pady=(2, 4))
    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True)
    search_button = ttk.Button(search_row, text="검색", width=5)
    search_button.pack(side="left", padx=(4, 0))
    clear_button = ttk.Button(search_row, text="초기화", width=6)
    clear_button.pack(side="left", padx=(4, 0))

    ttk.Label(left, text='Enter: 검색 · Esc: 초기화 · Ctrl+F: 포커스',
              font=("", 8), foreground="#777").pack(anchor="w", pady=(0, 4))

    fav_only_var = tk.BooleanVar(value=settings.get("fav_only", False))
    fav_count_var = tk.StringVar(value=f"★ 즐겨찾기만 보기  ({len(favorites)}개)")
    ttk.Checkbutton(left, textvariable=fav_count_var,
                    variable=fav_only_var,
                    command=lambda: trigger_search()).pack(anchor="w", pady=(0, 4))

    # 분류 필터: 일반 / 그림자 / 메가
    show_normal_var = tk.BooleanVar(value=settings.get("show_normal", True))
    show_shadow_var = tk.BooleanVar(value=settings.get("show_shadow", True))
    show_mega_var   = tk.BooleanVar(value=settings.get("show_mega",   True))
    cat_row = ttk.Frame(left)
    cat_row.pack(anchor="w", pady=(0, 4))
    ttk.Label(cat_row, text="분류:", font=("", 9), foreground="#555").pack(side="left", padx=(0, 4))
    for txt, var in (("일반", show_normal_var),
                     ("그림자", show_shadow_var),
                     ("메가", show_mega_var)):
        ttk.Checkbutton(cat_row, text=txt, variable=var,
                        command=lambda: trigger_search()).pack(side="left", padx=(0, 6))

    list_frame = ttk.Frame(left)
    list_frame.pack(fill="both", expand=True)
    list_scroll = ttk.Scrollbar(list_frame, orient="vertical")
    list_scroll.pack(side="right", fill="y")
    listbox = tk.Listbox(list_frame, width=30, height=30,
                         yscrollcommand=list_scroll.set,
                         exportselection=False, activestyle="dotbox",
                         font=("", 10))
    listbox.pack(side="left", fill="both", expand=True)
    list_scroll.config(command=listbox.yview)

    count_var = tk.StringVar(value=f"{len(all_displays_full)}종")
    ttk.Label(left, textvariable=count_var, font=("", 8), foreground="#777").pack(anchor="e", pady=(4, 0))

    # 데이터 갱신 영역 (좌측 하단)
    ttk.Separator(left, orient="horizontal").pack(fill="x", pady=(8, 6))
    data_status_var = tk.StringVar()

    def update_data_status_label():
        age = _file_age_days(CACHE_GM)
        if age == float("inf"):
            data_status_var.set("데이터 없음")
            return
        txt = f"데이터: {_format_age(CACHE_GM)}"
        if age > DATA_MAX_AGE_DAYS:
            txt += f"  ⚠ {age:.0f}일 전"
        data_status_var.set(txt)

    update_data_status_label()
    ttk.Label(left, textvariable=data_status_var, font=("", 8),
              foreground="#666").pack(anchor="w")
    ttk.Button(left, text="데이터 업데이트",
               command=lambda: do_data_refresh()).pack(fill="x", pady=(4, 0))

    # ===== Right: league + results =====
    right = ttk.Frame(root, padding=(6, 12, 12, 12))
    right.pack(side="left", fill="both", expand=True)

    # League selection row — 4개 빌트인 라디오 + 시즌 컵 콤보 (하이브리드)
    league_row = ttk.Frame(right)
    league_row.pack(fill="x", pady=(0, 8))
    ttk.Label(league_row, text="리그", font=("", 10, "bold")).pack(side="left", padx=(0, 10))
    league_var = tk.StringVar(value="슈퍼리그")

    def _league_label(lg):
        cap_txt = f"({lg.cap})" if lg.cap else "(무제한)"
        return f"{lg.name} {cap_txt}"

    CUP_PLACEHOLDER = "— 시즌 컵 —"
    cup_combo_var = tk.StringVar(value=CUP_PLACEHOLDER)
    cup_label_to_name = {}

    def _select_builtin(name):
        league_var.set(name)
        cup_combo_var.set(CUP_PLACEHOLDER)
        try:
            refresh()
        except NameError:
            pass  # refresh 아직 미정의 (초기 setup 단계)

    league_radios = []
    for lg in _BUILTIN_LEAGUES:
        cap_txt = f"({lg.cap})" if lg.cap else "(무제한)"
        rb = ttk.Radiobutton(league_row, text=f"{lg.name} {cap_txt}",
                             variable=league_var, value=lg.name,
                             command=lambda n=lg.name: _select_builtin(n))
        rb.pack(side="left", padx=4)
        league_radios.append(rb)

    ttk.Separator(league_row, orient="vertical").pack(side="left", fill="y", padx=10)
    ttk.Label(league_row, text="시즌 컵", font=("", 9)).pack(side="left", padx=(0, 4))
    cup_combo = ttk.Combobox(league_row, textvariable=cup_combo_var,
                             values=[CUP_PLACEHOLDER], state="readonly", width=24)
    cup_combo.pack(side="left", padx=2)

    def _refresh_cup_choices():
        """LEAGUES 가 변경되면 (data refresh 후 등) 컵 목록 재구성."""
        builtin_names = {lg.name for lg in _BUILTIN_LEAGUES}
        cup_leagues = [lg for lg in LEAGUES if lg.name not in builtin_names]
        cup_label_to_name.clear()
        cup_label_to_name.update({_league_label(lg): lg.name for lg in cup_leagues})
        cup_combo["values"] = [CUP_PLACEHOLDER] + [_league_label(lg) for lg in cup_leagues]

    _refresh_cup_choices()

    def _on_cup_select(_e=None):
        sel = cup_combo_var.get()
        if sel and sel != CUP_PLACEHOLDER and sel in cup_label_to_name:
            league_var.set(cup_label_to_name[sel])
            try:
                refresh()
            except NameError:
                pass
    cup_combo.bind("<<ComboboxSelected>>", _on_cup_select)

    # Tabs
    notebook = ttk.Notebook(right)
    notebook.pack(fill="both", expand=True)

    # --- Tab 1: 선택 포켓몬 베스트 개체값 ---
    iv_tab = ttk.Frame(notebook, padding=(6, 8))
    notebook.add(iv_tab, text="  PvP 분석  ")

    # 헤더: 스프라이트(좌) + 정보·진화 스택(우)
    header_frame = ttk.Frame(iv_tab)
    header_frame.pack(fill="x", pady=(0, 8))

    sprite_label = tk.Label(header_frame, width=96, height=96,
                            background="#f4f4f4", relief="flat", bd=0)
    sprite_label.pack(side="left", padx=(0, 12))
    sprite_label.image = None

    info_stack = ttk.Frame(header_frame)
    info_stack.pack(side="left", fill="both", expand=True)

    # 1행: 정보 + ★ 토글
    info_row = ttk.Frame(info_stack)
    info_row.pack(fill="x", pady=(0, 4))
    info_var = tk.StringVar(value="왼쪽에서 포켓몬을 선택하세요.")
    ttk.Label(info_row, textvariable=info_var, font=("", 10)).pack(side="left", anchor="w")
    fav_btn_var = tk.StringVar(value="☆ 즐겨찾기")
    fav_btn = ttk.Button(info_row, textvariable=fav_btn_var, width=12,
                         command=lambda: toggle_favorite())
    fav_btn.pack(side="right", padx=(8, 0))

    evo_frame = ttk.Frame(info_stack)
    evo_frame.pack(fill="x", pady=(0, 2))
    evo_title = ttk.Label(evo_frame, text="진화:", font=("", 9, "bold"), foreground="#555")
    evo_title.pack(side="left", padx=(0, 6))

    # 타입 상성 (약점/내성)
    type_frame = ttk.Frame(info_stack)
    type_frame.pack(fill="x", pady=(2, 0))
    type_title = ttk.Label(type_frame, text="타입:", font=("", 9, "bold"), foreground="#555")
    type_title.pack(side="left", padx=(0, 6))
    type_inner = ttk.Frame(type_frame)
    type_inner.pack(side="left", fill="x", expand=True)

    # My IV input → real-time rank display (비어있으면 내 순위 계산 안 함)
    my_iv_frame = ttk.Frame(iv_tab)
    my_iv_frame.pack(fill="x", pady=(0, 4))
    ttk.Label(my_iv_frame, text="내 개체값", font=("", 10, "bold")).pack(side="left", padx=(0, 8))

    ttk.Label(my_iv_frame, text="공").pack(side="left", padx=(0, 2))
    atk_var = tk.StringVar(value="")
    ttk.Spinbox(my_iv_frame, from_=0, to=15, textvariable=atk_var, width=4).pack(side="left")
    ttk.Label(my_iv_frame, text="방").pack(side="left", padx=(10, 2))
    def_var = tk.StringVar(value="")
    ttk.Spinbox(my_iv_frame, from_=0, to=15, textvariable=def_var, width=4).pack(side="left")
    ttk.Label(my_iv_frame, text="체").pack(side="left", padx=(10, 2))
    hp_var = tk.StringVar(value="")
    ttk.Spinbox(my_iv_frame, from_=0, to=15, textvariable=hp_var, width=4).pack(side="left")

    ttk.Separator(my_iv_frame, orient="vertical").pack(side="left", fill="y", padx=12)
    ttk.Label(my_iv_frame, text="현재 Lv").pack(side="left", padx=(0, 2))
    cur_lv_var = tk.StringVar(value="")
    ttk.Spinbox(my_iv_frame, from_=1.0, to=51.0, increment=0.5,
                textvariable=cur_lv_var, width=5).pack(side="left")
    ttk.Label(my_iv_frame, text="(강화 비용 계산용)",
              font=("", 8), foreground="#888").pack(side="left", padx=(4, 0))

    my_iv_result = tk.StringVar(value="")
    ttk.Label(my_iv_frame, textvariable=my_iv_result,
              font=("", 9), foreground="#666").pack(side="left", padx=(18, 0))

    # 4 리그 한눈에 보는 요약 테이블 (행 클릭 → 아래 Top 100 갱신)
    ttk.Label(iv_tab, text="▼ 리그별 요약  (행 클릭 → Top 100 전환)",
              font=("", 9, "bold"), foreground="#333").pack(anchor="w", pady=(6, 3))

    sum_frame = ttk.Frame(iv_tab)
    sum_frame.pack(fill="x", pady=(0, 10))

    sum_cols = ("league", "meta", "rank", "pct", "lvl", "cp", "best", "cost")
    sum_labels_t = ["리그", "메타 순위", "내 순위", "베스트대비", "레벨", "CP", "리그 베스트 IV", "강화비용"]
    sum_widths = [110, 85, 90, 80, 55, 65, 100, 200]
    summary_tree = ttk.Treeview(sum_frame, columns=sum_cols, show="headings",
                                height=4, selectmode="browse")
    for c, l, w in zip(sum_cols, sum_labels_t, sum_widths):
        summary_tree.heading(c, text=l)
        summary_tree.column(c, width=w, anchor="center")
    summary_tree.column("cost", anchor="w")
    summary_tree.pack(fill="x")

    # 아래 영역: Top 100 (좌) + 기술&점수 (우) 한 화면
    content_split = ttk.Frame(iv_tab)
    content_split.pack(fill="both", expand=True)

    # Left: Top 100 IV 랭킹
    iv_col = ttk.Frame(content_split)
    iv_col.pack(side="left", fill="both", expand=True, padx=(0, 8))

    table_label = tk.StringVar(value="")
    ttk.Label(iv_col, textvariable=table_label, font=("", 9),
              foreground="#555").pack(anchor="w", pady=(0, 4))

    tree_frame = ttk.Frame(iv_col)
    tree_frame.pack(fill="both", expand=True)
    tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
    tree_scroll.pack(side="right", fill="y")

    cols = ("rank", "iv", "lvl", "cp", "sp", "pct")
    labels = ["순위", "공 / 방 / 체", "레벨", "CP", "스탯곱(SP)", "베스트대비"]
    widths = [55, 115, 65, 65, 125, 85]
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                        yscrollcommand=tree_scroll.set, height=20)
    for c, l, w in zip(cols, labels, widths):
        tree.heading(c, text=l)
        tree.column(c, width=w, anchor="center")
    tree.pack(side="left", fill="both", expand=True)
    tree_scroll.config(command=tree.yview)

    # Right: 기술 & 점수
    moves_col = ttk.Frame(content_split)
    moves_col.pack(side="left", fill="both", expand=True)

    ttk.Label(moves_col, text="▼ 보유 기술  (★=리그 추천 · 획득=커뮤데이/레이드/엘리트 TM · 사용률=PvPoke)",
              font=("", 9, "bold"), foreground="#333").pack(anchor="w", pady=(0, 4))

    moves_rec_var = tk.StringVar(value="")
    ttk.Label(moves_col, textvariable=moves_rec_var,
              font=("", 9), foreground="#c33").pack(anchor="w", pady=(0, 6))

    ttk.Label(moves_col, text="노말 어택  (Fast Move)",
              font=("", 9, "bold")).pack(anchor="w", pady=(2, 2))
    fast_frame = ttk.Frame(moves_col)
    fast_frame.pack(fill="x", pady=(0, 8))
    fast_cols = ("rec", "acq", "name", "type", "power", "energy", "turns", "pct")
    fast_labels = ["★", "획득", "기술", "타입", "위력", "에너지+", "턴", "사용률"]
    fast_widths = [22, 70, 95, 55, 45, 55, 35, 60]
    fast_anchors = ["center", "center", "w", "center", "center", "center", "center", "center"]
    fast_tree = ttk.Treeview(fast_frame, columns=fast_cols, show="headings", height=4)
    for c, l, w, a in zip(fast_cols, fast_labels, fast_widths, fast_anchors):
        fast_tree.heading(c, text=l)
        fast_tree.column(c, width=w, anchor=a)
    fast_tree.pack(fill="x")

    ttk.Label(moves_col, text="스페셜 어택  (Charged Move)",
              font=("", 9, "bold")).pack(anchor="w", pady=(2, 2))
    charged_frame = ttk.Frame(moves_col)
    charged_frame.pack(fill="both", expand=True)
    charged_scroll = ttk.Scrollbar(charged_frame, orient="vertical")
    charged_scroll.pack(side="right", fill="y")
    charged_cols = ("rec", "acq", "name", "type", "power", "energy", "pct")
    charged_labels = ["★", "획득", "기술", "타입", "위력", "에너지", "사용률"]
    charged_widths = [22, 70, 125, 55, 45, 50, 70]
    charged_anchors = ["center", "center", "w", "center", "center", "center", "center"]
    charged_tree = ttk.Treeview(charged_frame, columns=charged_cols, show="headings",
                                yscrollcommand=charged_scroll.set, height=14)
    for c, l, w, a in zip(charged_cols, charged_labels, charged_widths, charged_anchors):
        charged_tree.heading(c, text=l)
        charged_tree.column(c, width=w, anchor=a)
    charged_tree.pack(side="left", fill="both", expand=True)
    charged_scroll.config(command=charged_tree.yview)

    # --- Tab 2: 리그 메타 랭킹 ---
    meta_tab = ttk.Frame(notebook, padding=(6, 8))
    notebook.add(meta_tab, text="  PvP 메타  ")

    meta_label = tk.StringVar(value="")
    ttk.Label(meta_tab, textvariable=meta_label, font=("", 10)).pack(anchor="w", pady=(0, 4))

    meta_search_row = ttk.Frame(meta_tab)
    meta_search_row.pack(fill="x", pady=(0, 4))
    ttk.Label(meta_search_row, text="검색", font=("", 9)).pack(side="left", padx=(0, 4))
    meta_search_var = tk.StringVar(value="")
    meta_search_entry = ttk.Entry(meta_search_row, textvariable=meta_search_var, width=22)
    meta_search_entry.pack(side="left")
    ttk.Button(meta_search_row, text="✕", width=3,
               command=lambda: (meta_search_var.set(""), refresh_meta(force=True))
               ).pack(side="left", padx=(2, 8))
    ttk.Label(meta_search_row,
              text="한글/영문 sid 부분 일치 · 행 더블클릭 → 좌측 리스트 선택",
              font=("", 8), foreground="#777").pack(side="left")

    meta_frame = ttk.Frame(meta_tab)
    meta_frame.pack(fill="both", expand=True)
    meta_scroll = ttk.Scrollbar(meta_frame, orient="vertical")
    meta_scroll.pack(side="right", fill="y")

    meta_cols = ("rank", "name", "score", "moves")
    meta_labels_txt = ["순위", "포켓몬", "점수", "추천 기술 조합"]
    meta_widths = [55, 210, 60, 310]
    meta_anchors = ["center", "w", "center", "w"]
    meta_tree = ttk.Treeview(meta_frame, columns=meta_cols, show="headings",
                             yscrollcommand=meta_scroll.set, height=30)
    for c, l, w, a in zip(meta_cols, meta_labels_txt, meta_widths, meta_anchors):
        meta_tree.heading(c, text=l)
        meta_tree.column(c, width=w, anchor=a)
    meta_tree.pack(side="left", fill="both", expand=True)
    meta_scroll.config(command=meta_tree.yview)

    # --- Tab 3: 내 IV로 포켓몬 찾기 (역검색) ---
    rev_tab = ttk.Frame(notebook, padding=(6, 8))
    notebook.add(rev_tab, text="  PvP IV검색  ")

    rev_top = ttk.Frame(rev_tab)
    rev_top.pack(fill="x", pady=(0, 8))
    ttk.Label(rev_top, text="개체값 입력 → 4리그별 그 IV가 잘 어울리는 포켓몬",
              font=("", 10, "bold")).pack(side="left")

    rev_input = ttk.Frame(rev_tab)
    rev_input.pack(fill="x", pady=(0, 8))
    ttk.Label(rev_input, text="공").pack(side="left", padx=(0, 2))
    ttk.Spinbox(rev_input, from_=0, to=15, textvariable=atk_var, width=4).pack(side="left")
    ttk.Label(rev_input, text="방").pack(side="left", padx=(10, 2))
    ttk.Spinbox(rev_input, from_=0, to=15, textvariable=def_var, width=4).pack(side="left")
    ttk.Label(rev_input, text="체").pack(side="left", padx=(10, 2))
    ttk.Spinbox(rev_input, from_=0, to=15, textvariable=hp_var, width=4).pack(side="left")
    ttk.Label(rev_input, text="(Tab 1 과 공유)",
              foreground="#888", font=("", 8)).pack(side="left", padx=(8, 0))
    ttk.Label(rev_input, text="  ·  메타 상위").pack(side="left", padx=(20, 2))
    rev_topn_var = tk.IntVar(value=200)
    ttk.Spinbox(rev_input, from_=50, to=500, increment=50,
                textvariable=rev_topn_var, width=5).pack(side="left")
    ttk.Label(rev_input, text="종 중에서").pack(side="left", padx=(2, 0))
    ttk.Button(rev_input, text="찾기",
               command=lambda: refresh_reverse()).pack(side="left", padx=(20, 0))

    ttk.Label(rev_tab,
              text="점수 = PvPoke 메타점수 × (내 IV의 이 포켓몬 베스트 대비%) ÷ 100   "
                   "행 더블클릭 → 좌측 리스트에 선택",
              font=("", 8), foreground="#777").pack(anchor="w", pady=(0, 6))

    rev_split = ttk.Frame(rev_tab)
    rev_split.pack(fill="both", expand=True)

    # 역검색 탭은 빌트인 4개 오픈 리그만 표시 (시즌 컵까지 나란히 두면 너무 좁음)
    rev_trees = {}
    for lg in _BUILTIN_LEAGUES:
        lname = lg.name
        col = ttk.Frame(rev_split)
        col.pack(side="left", fill="both", expand=True, padx=2)
        ttk.Label(col, text=lname, font=("", 9, "bold")).pack(anchor="w")
        rev_cols = ("rank", "name", "pct", "score")
        rev_labels = ["#", "포켓몬", "베스트%", "점수"]
        rev_widths = [25, 130, 55, 50]
        rev_anchors = ["e", "w", "e", "e"]
        sb = ttk.Scrollbar(col, orient="vertical")
        sb.pack(side="right", fill="y")
        rt = ttk.Treeview(col, columns=rev_cols, show="headings",
                          yscrollcommand=sb.set, height=25, selectmode="browse")
        for c, l, w, a in zip(rev_cols, rev_labels, rev_widths, rev_anchors):
            rt.heading(c, text=l)
            rt.column(c, width=w, anchor=a)
        rt.pack(side="left", fill="both", expand=True)
        sb.config(command=rt.yview)
        rev_trees[lname] = rt

    # --- Tab 4: CP → IV 추정 ---
    cp_tab = ttk.Frame(notebook, padding=(6, 8))
    notebook.add(cp_tab, text="  PvP CP→IV  ")

    ttk.Label(cp_tab,
              text="좌측에서 포켓몬 선택 후, 게임에서 보이는 CP/HP/(레벨)을 입력 → 가능한 IV 후보",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))

    cp_input = ttk.Frame(cp_tab)
    cp_input.pack(fill="x", pady=(0, 6))
    ttk.Label(cp_input, text="CP").pack(side="left", padx=(0, 2))
    cp_var = tk.StringVar(value="")
    ttk.Entry(cp_input, textvariable=cp_var, width=8).pack(side="left")
    ttk.Label(cp_input, text="HP").pack(side="left", padx=(12, 2))
    chp_var = tk.StringVar(value="")
    ttk.Entry(cp_input, textvariable=chp_var, width=6).pack(side="left")
    ttk.Label(cp_input, text="Lv (모르면 비워두기)").pack(side="left", padx=(12, 2))
    clv_var = tk.StringVar(value="")
    ttk.Spinbox(cp_input, from_=1.0, to=51.0, increment=0.5,
                textvariable=clv_var, width=6).pack(side="left")
    ttk.Button(cp_input, text="추정",
               command=lambda: refresh_cp_iv()).pack(side="left", padx=(20, 0))

    cp_status_var = tk.StringVar(value="")
    ttk.Label(cp_tab, textvariable=cp_status_var, font=("", 9),
              foreground="#666").pack(anchor="w", pady=(0, 4))

    cp_frame = ttk.Frame(cp_tab)
    cp_frame.pack(fill="both", expand=True)
    cp_scroll = ttk.Scrollbar(cp_frame, orient="vertical")
    cp_scroll.pack(side="right", fill="y")
    cp_cols = ("lvl", "iv", "total", "hp_calc", "cp_calc")
    cp_col_labels = ["레벨", "공/방/체", "합계 (%)", "HP", "CP"]
    cp_widths = [80, 110, 100, 60, 60]
    cp_tree = ttk.Treeview(cp_frame, columns=cp_cols, show="headings",
                           yscrollcommand=cp_scroll.set, height=24)
    for c, l, w in zip(cp_cols, cp_col_labels, cp_widths):
        cp_tree.heading(c, text=l)
        cp_tree.column(c, width=w, anchor="center")
    cp_tree.pack(side="left", fill="both", expand=True)
    cp_scroll.config(command=cp_tree.yview)

    # --- Tab 5: 타입 상성표 ---
    type_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(type_tab, text="  타입 상성  ")

    ttk.Label(type_tab,
              text="↓ 공격 타입  ·  → 방어 타입  (PoGO PvP 데미지 배율)",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))

    type_legend = ttk.Frame(type_tab)
    type_legend.pack(anchor="w", pady=(0, 8))
    for clr, txt in [("#7dcc7d", "1.6×  효과적"),
                     ("#f0f0f0", "1×  보통"),
                     ("#ffb37a", "0.625×  효과 없음"),
                     ("#e57373", "0.39×  매우 효과 없음")]:
        tk.Label(type_legend, text=txt, bg=clr, padx=8, pady=3,
                 relief="solid", borderwidth=1, font=("", 9)
                 ).pack(side="left", padx=(0, 6))

    type_grid = ttk.Frame(type_tab)
    type_grid.pack(anchor="nw")

    # 좌상단 코너
    tk.Label(type_grid, text="공\\방", font=("", 8, "bold"), width=5,
             bg="#cdd5e0", relief="solid", borderwidth=1
             ).grid(row=0, column=0, sticky="nsew")

    # 헤더 (방어 타입, 가로)
    for j, t in enumerate(TYPES_ORDER):
        tk.Label(type_grid, text=TYPE_KO.get(t, t),
                 font=("", 8, "bold"), width=5,
                 bg="#cdd5e0", relief="solid", borderwidth=1
                 ).grid(row=0, column=j + 1, sticky="nsew")

    # 데이터 행 (공격 타입 = 행)
    def _cell_for(mult):
        if mult >= 1.5:
            return "1.6", "#7dcc7d"
        if mult <= 0.4:
            return "0.39", "#e57373"
        if mult <= 0.7:
            return "0.625", "#ffb37a"
        return "1", "#f0f0f0"

    for i, atk in enumerate(TYPES_ORDER):
        tk.Label(type_grid, text=TYPE_KO.get(atk, atk),
                 font=("", 8, "bold"), width=5,
                 bg="#cdd5e0", relief="solid", borderwidth=1
                 ).grid(row=i + 1, column=0, sticky="nsew")
        atk_row = TYPE_CHART.get(atk, {})
        for j, dfd in enumerate(TYPES_ORDER):
            mult = atk_row.get(dfd, 1.0)
            txt, clr = _cell_for(mult)
            tk.Label(type_grid, text=txt, font=("", 8), width=5,
                     bg=clr, relief="solid", borderwidth=1
                     ).grid(row=i + 1, column=j + 1, sticky="nsew")

    ttk.Label(type_tab,
              text="• 메인 시리즈와 달리 PoGO 는 면역(0×)이 없고 0.39× 더블 저항으로 처리됩니다.\n"
                   "• 듀얼 타입 방어 시 곱셈으로 누적 → 최대 1.6²=2.56×, 최저 0.39²≈0.15×",
              font=("", 8), foreground="#666", justify="left"
              ).pack(anchor="w", pady=(8, 0))

    # --- Tab 6: 레이드 카운터 (PvE) ---
    raid_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(raid_tab, text="  PvE 카운터  ")

    raid_state = {"bosses": [], "current_boss": None, "current_weather": None}
    try:
        raid_state["bosses"] = load_raid_bosses()
    except Exception as e:
        print(f"레이드 보스 로드 실패: {e}")

    def _boss_label(b):
        tier = b.get("tier", "")
        if "5-Star" in tier or "5성" in tier:
            badge = "[5★]"
        elif "3-Star" in tier:
            badge = "[3★]"
        elif "1-Star" in tier:
            badge = "[1★]"
        elif "Mega" in tier:
            badge = "[메가]"
        elif "Shadow" in tier:
            badge = "[그림자]"
        elif "Elite" in tier:
            badge = "[엘리트]"
        else:
            badge = f"[{tier}]"
        # PvPoke 매칭 가능하면 한글 디스플레이명 사용, 아니면 영문 fallback
        en_name = b.get("name", "?")
        p = find_boss_pokemon(en_name, state["gm"])
        ko_name = sid_to_display.get(p["speciesId"], en_name) if p else en_name
        return f"{badge} {ko_name}"

    def _boss_pool_sorted():
        order = {"5-Star": 0, "Mega": 1, "Elite": 1, "Shadow": 2, "3-Star": 3, "1-Star": 4}
        def key(b):
            t = b.get("tier", "")
            for k, v in order.items():
                if k in t:
                    return (v, b.get("name", ""))
            return (9, b.get("name", ""))
        return sorted(raid_state["bosses"], key=key)

    raid_top = ttk.Frame(raid_tab)
    raid_top.pack(fill="x", pady=(0, 6))

    ttk.Label(raid_top, text="보스", font=("", 10, "bold")).pack(side="left")
    boss_var = tk.StringVar()
    boss_combo = ttk.Combobox(raid_top, textvariable=boss_var, width=36,
                              state="readonly", height=20)
    boss_combo.pack(side="left", padx=(6, 16))

    ttk.Label(raid_top, text="날씨", font=("", 10, "bold")).pack(side="left")
    weather_var = tk.StringVar(value="(없음)")
    weather_choices = ["(없음)"] + [WEATHER_KO[w] for w in
                                     ["sunny","rainy","partly_cloudy","cloudy","windy","snow","fog"]]
    weather_combo = ttk.Combobox(raid_top, textvariable=weather_var, values=weather_choices,
                                 width=14, state="readonly")
    weather_combo.pack(side="left", padx=(6, 16))

    ttk.Label(raid_top, text="모드", font=("", 10, "bold")).pack(side="left")
    boss_mode_var = tk.StringVar(value="raid")
    ttk.Radiobutton(raid_top, text="일반 레이드", variable=boss_mode_var,
                    value="raid", command=lambda: refresh_counters()
                    ).pack(side="left", padx=(6, 2))
    ttk.Radiobutton(raid_top, text="맥스 배틀", variable=boss_mode_var,
                    value="max", command=lambda: refresh_counters()
                    ).pack(side="left", padx=(0, 16))

    ttk.Label(raid_top, text="공격자 Lv", font=("", 10, "bold")).pack(side="left", padx=(0, 4))
    raid_lv_var = tk.StringVar(value="50")
    ttk.Combobox(raid_top, textvariable=raid_lv_var,
                 values=["40", "45", "50", "51"], width=5, state="readonly"
                 ).pack(side="left", padx=(0, 16))

    use_selected_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(raid_top, text="좌측 선택 포켓몬을 보스로",
                    variable=use_selected_var,
                    command=lambda: refresh_counters()).pack(side="left", padx=(0, 10))

    ttk.Button(raid_top, text="레이드 목록 갱신", width=14,
               command=lambda: _reload_raids()).pack(side="right")

    # 보스 정보
    boss_info_var = tk.StringVar(value="보스를 선택하세요")
    ttk.Label(raid_tab, textvariable=boss_info_var,
              font=("", 10), foreground="#444").pack(anchor="w", pady=(2, 4))

    # 필터
    raid_filter_row = ttk.Frame(raid_tab)
    raid_filter_row.pack(fill="x", pady=(0, 6))
    ttk.Label(raid_filter_row, text="공격자 풀:", font=("", 9), foreground="#555"
              ).pack(side="left", padx=(0, 6))
    inc_mega_var   = tk.BooleanVar(value=settings.get("pve_inc_mega",   True))
    inc_shadow_var = tk.BooleanVar(value=settings.get("pve_inc_shadow", True))
    inc_legend_var = tk.BooleanVar(value=settings.get("pve_inc_legend", True))
    fav_attacker_var = tk.BooleanVar(value=False)
    for txt, var in (("메가", inc_mega_var), ("그림자", inc_shadow_var),
                     ("전설/환상", inc_legend_var),
                     ("즐겨찾기만", fav_attacker_var)):
        ttk.Checkbutton(raid_filter_row, text=txt, variable=var,
                        command=lambda: refresh_counters()).pack(side="left", padx=(0, 8))

    # 카운터 테이블
    raid_table_frame = ttk.Frame(raid_tab)
    raid_table_frame.pack(fill="both", expand=True)
    raid_scroll = ttk.Scrollbar(raid_table_frame, orient="vertical")
    raid_scroll.pack(side="right", fill="y")
    raid_cols = ("rank", "name", "types", "fast", "charged", "edps", "dps", "tdo")
    raid_labels = ["#", "포켓몬", "타입", "속공", "차지", "eDPS", "DPS", "TDO"]
    raid_widths = [40, 180, 110, 130, 140, 70, 70, 80]
    raid_tree = ttk.Treeview(raid_table_frame, columns=raid_cols, show="headings",
                             yscrollcommand=raid_scroll.set, height=22)
    for c, l, w in zip(raid_cols, raid_labels, raid_widths):
        raid_tree.heading(c, text=l)
        anchor = "w" if c in ("name", "fast", "charged") else "center"
        raid_tree.column(c, width=w, anchor=anchor)
    raid_tree.pack(side="left", fill="both", expand=True)
    raid_scroll.config(command=raid_tree.yview)

    # 6마리 라인업 클리어 시간 추정
    raid_lineup_var = tk.StringVar(value="")
    ttk.Label(raid_tab, textvariable=raid_lineup_var,
              font=("", 9, "bold"), foreground="#205080").pack(anchor="w", pady=(6, 0))

    raid_status_var = tk.StringVar(
        value="• Lv50 / 15·15·15 가정 · 그림자는 1.2× 공/0.83× 방 적용 · "
              "데이터 출처: ScrapedDuck (LeekDuck 미러)"
    )
    ttk.Label(raid_tab, textvariable=raid_status_var,
              font=("", 8), foreground="#666").pack(anchor="w", pady=(4, 0))
    ttk.Label(raid_tab,
              text="⚠ DPS 절대값은 PvP 소스(pvpoke) 기반이라 PvE 실측보다 보수적 — "
                   "카운터 순위는 정확하지만 클리어 시간은 낙관 추정치임.",
              font=("", 8), foreground="#a06030"
              ).pack(anchor="w", pady=(2, 0))

    def _populate_boss_combo():
        bosses = _boss_pool_sorted()
        labels = [_boss_label(b) for b in bosses]
        boss_combo["values"] = labels
        if labels and not boss_var.get():
            boss_var.set(labels[0])

    def _selected_boss_entry():
        if use_selected_var.get():
            sel = listbox.curselection()
            if not sel:
                return None, None
            disp = strip_star(listbox.get(sel[0]))
            sid = display_to_sid.get(disp)
            if not sid:
                return None, None
            p = next((x for x in state["gm"]["pokemon"] if x["speciesId"] == sid), None)
            return p, {"name": disp, "tier": "직접 선택"}
        # combobox 에서 선택
        label = boss_var.get()
        if not label:
            return None, None
        bosses = _boss_pool_sorted()
        idx = boss_combo.current()
        if idx < 0 or idx >= len(bosses):
            return None, None
        b = bosses[idx]
        p = find_boss_pokemon(b["name"], state["gm"])
        return p, b

    def _weather_key():
        v = weather_var.get()
        for k, ko in WEATHER_KO.items():
            if ko == v:
                return k if k != "none" else None
        return None

    def refresh_counters():
        for r in raid_tree.get_children():
            raid_tree.delete(r)
        boss_p, boss_meta = _selected_boss_entry()
        if not boss_p:
            if boss_meta:
                boss_info_var.set(f"보스 매칭 실패: {boss_meta.get('name','?')} (PvPoke 데이터 없음)")
            else:
                boss_info_var.set("보스를 선택하세요")
            return
        types = [t for t in boss_p.get("types", []) if t and t != "none"]
        type_str = " · ".join(TYPE_KO.get(t, t) for t in types)
        # 약점 계산 (다중 약점 — 1.6× 이상)
        weakness_mult = {}
        for atk in TYPES_ORDER:
            mult = 1.0
            for d in types:
                mult *= TYPE_CHART.get(atk, {}).get(d, 1.0)
            if mult > 1.05:
                weakness_mult[atk] = mult
        weak_sorted = sorted(weakness_mult.items(), key=lambda x: -x[1])
        weak_str = " ".join(f"{TYPE_KO[t]}({m:.1f}×)" for t, m in weak_sorted[:5])
        tier_label = boss_meta.get("tier", "")
        boss_ko = sid_to_display.get(boss_p.get("speciesId", ""), boss_meta.get("name", "?"))
        boss_info_var.set(
            f"▶ {boss_ko} [{tier_label}] · 타입 {type_str}"
            + (f"  ·  주요 약점: {weak_str}" if weak_str else "")
        )
        weather = _weather_key()
        favs = favorites if fav_attacker_var.get() else None
        # 맥스 배틀 모드는 보스가 훨씬 단단함 (CPM ≈ 1.0). 임시로 boss_p 의 baseStats 를
        # 일시적으로 부풀리는 대신, top_counters 안의 cpm 분기 로직을 우회하기 위해
        # 보스 sid 에 _mega 가 없어도 강제 max cpm 을 쓰도록 처리.
        is_max_mode = (boss_mode_var.get() == "max")
        try:
            atk_lv = float(raid_lv_var.get())
        except ValueError:
            atk_lv = 50.0
        cnt = top_counters(
            boss_p, state["gm"], moves_by_id, n=20,
            weather=weather,
            include_shadow=inc_shadow_var.get(),
            include_mega=inc_mega_var.get(),
            include_legendary=inc_legend_var.get(),
            favorites_only=favs,
            force_boss_cpm=(1.0 if is_max_mode else None),
            attacker_level=atk_lv,
        )
        for i, c in enumerate(cnt, 1):
            disp = sid_to_display.get(c["sid"], c["sid"])
            tps = " · ".join(TYPE_KO.get(t, t) for t in c["pokemon"].get("types", [])
                             if t and t != "none")
            def _move_ko(mid):
                k = mid.lower().replace("_", "-")
                return move_ko_map.get(k) or moves_by_id.get(mid, {}).get("name", mid)
            f_name = _move_ko(c["fast_id"])
            ch_name = _move_ko(c["charged_id"])
            f_type = TYPE_KO.get(c["fast_type"], c["fast_type"])
            ch_type = TYPE_KO.get(c["charged_type"], c["charged_type"])
            raid_tree.insert("", "end", values=(
                i, disp, tps,
                f"{f_name} ({f_type})",
                f"{ch_name} ({ch_type})",
                f"{c['edps']:.1f}",
                f"{c['dps']:.1f}",
                f"{c['tdo']:.0f}",
            ))
        if not cnt:
            raid_status_var.set("⚠ 카운터 없음 — 필터를 완화해보세요")
            raid_lineup_var.set("")
        else:
            raid_status_var.set(
                f"• {len(cnt)}마리 표시 · 모드={'맥스 배틀' if is_max_mode else '일반 레이드'} · "
                f"날씨={weather_var.get()} · Lv{raid_lv_var.get()}/15·15·15 가정"
            )
            # 6마리 라인업 클리어 시간 추정
            # 보스 HP: 일반 레이드 5성≈15000, 맥스≈100000 (대략)
            tier_label = boss_meta.get("tier", "")
            if is_max_mode:
                boss_hp_est = 100000
            elif "5-Star" in tier_label or "Mega" in tier_label or "Elite" in tier_label or "Shadow" in tier_label:
                boss_hp_est = 15000
            elif "3-Star" in tier_label:
                boss_hp_est = 3600
            elif "1-Star" in tier_label:
                boss_hp_est = 600
            else:
                boss_hp_est = 15000
            top6 = cnt[:6]
            avg_dps = sum(c["dps"] for c in top6) / max(1, len(top6))
            # PoGO 레이드는 1마리씩 릴레이로 싸우므로 단일 DPS 기준.
            # 도지/페인트 부담은 무시한 낙관 추정.
            est_sec = boss_hp_est / max(1, avg_dps)
            mm, ss = divmod(int(est_sec), 60)
            time_str = f"{mm}분 {ss}초" if mm else f"{ss}초"
            top6_names = ", ".join(sid_to_display.get(c["sid"], c["sid"]) for c in top6)
            raid_lineup_var.set(
                f"▶ 6마리 라인업 낙관 추정 클리어: 약 {time_str}  "
                f"(상위 6 평균 DPS {avg_dps:.1f}, 보스 HP ≈ {boss_hp_est:,})\n"
                f"   추천: {top6_names}"
            )

    def _reload_raids():
        try:
            raid_state["bosses"] = load_raid_bosses(force=True)
        except Exception as e:
            messagebox.showerror("실패", f"갱신 실패: {e}")
            return
        _populate_boss_combo()
        refresh_counters()

    boss_combo.bind("<<ComboboxSelected>>", lambda e: refresh_counters())
    weather_combo.bind("<<ComboboxSelected>>", lambda e: refresh_counters())
    # 공격자 Lv 콤보 (raid_top 안에 있는 모든 콤보 중 boss/weather 외)
    for w in raid_top.winfo_children():
        if isinstance(w, ttk.Combobox) and w not in (boss_combo, weather_combo):
            w.bind("<<ComboboxSelected>>", lambda e: refresh_counters())
    _populate_boss_combo()

    # --- Tab 7: PvE DPS — 선택 포켓몬의 모든 무브셋 DPS 정렬 ---
    dps_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(dps_tab, text="  PvE DPS  ")

    dps_top = ttk.Frame(dps_tab)
    dps_top.pack(fill="x", pady=(0, 6))
    dps_pokemon_var = tk.StringVar(value="좌측에서 포켓몬 선택")
    ttk.Label(dps_top, textvariable=dps_pokemon_var,
              font=("", 11, "bold")).pack(side="left")

    ttk.Label(dps_top, text="  타겟 방어 타입:", font=("", 9)).pack(side="left", padx=(20, 4))
    dps_target_var = tk.StringVar(value="(중립)")
    target_choices = ["(중립)"] + [TYPE_KO[t] for t in TYPES_ORDER]
    ttk.Combobox(dps_top, textvariable=dps_target_var, values=target_choices,
                 width=10, state="readonly"
                 ).pack(side="left")

    ttk.Label(dps_top, text="  날씨:", font=("", 9)).pack(side="left", padx=(12, 4))
    dps_weather_var = tk.StringVar(value="(없음)")
    ttk.Combobox(dps_top, textvariable=dps_weather_var, values=weather_choices,
                 width=12, state="readonly").pack(side="left")

    ttk.Label(dps_top, text="  Lv:", font=("", 9)).pack(side="left", padx=(12, 4))
    dps_lv_var = tk.StringVar(value="50")
    ttk.Combobox(dps_top, textvariable=dps_lv_var,
                 values=["40", "45", "50", "51"], width=5, state="readonly"
                 ).pack(side="left")

    dps_status_var = tk.StringVar(
        value="• 좌측 포켓몬 선택 시 자동 갱신 · Lv50/15·15·15 가정")
    ttk.Label(dps_tab, textvariable=dps_status_var,
              font=("", 8), foreground="#666").pack(anchor="w", pady=(0, 4))
    ttk.Label(dps_tab,
              text="⚠ DPS 절대값은 PvP 소스(pvpoke) 기반이라 PvE 실측보다 보수적 — "
                   "무브셋 간 상대 순위는 정확함.",
              font=("", 8), foreground="#a06030"
              ).pack(anchor="w", pady=(0, 2))

    dps_table_frame = ttk.Frame(dps_tab)
    dps_table_frame.pack(fill="both", expand=True)
    dps_scroll = ttk.Scrollbar(dps_table_frame, orient="vertical")
    dps_scroll.pack(side="right", fill="y")
    dps_cols = ("rank", "fast", "charged", "fast_dmg", "ch_dmg", "edps", "dps", "tdo")
    dps_labels = ["#", "속공", "차지", "속공 데미지", "차지 데미지", "eDPS", "DPS", "TDO"]
    dps_widths = [40, 200, 220, 90, 90, 70, 70, 80]
    dps_tree = ttk.Treeview(dps_table_frame, columns=dps_cols, show="headings",
                            yscrollcommand=dps_scroll.set, height=22)
    for c, l, w in zip(dps_cols, dps_labels, dps_widths):
        dps_tree.heading(c, text=l)
        dps_tree.column(c, width=w, anchor="w" if c in ("fast", "charged") else "center")
    dps_tree.pack(side="left", fill="both", expand=True)
    dps_scroll.config(command=dps_tree.yview)

    def _selected_attacker():
        sel = listbox.curselection()
        if not sel:
            return None
        disp = strip_star(listbox.get(sel[0]))
        sid = display_to_sid.get(disp)
        if not sid:
            return None
        return next((p for p in state["gm"]["pokemon"]
                     if p.get("speciesId") == sid), None)

    def _dps_target_types():
        """타겟 방어 타입을 list 로. (중립) → []"""
        v = dps_target_var.get()
        for code, ko in TYPE_KO.items():
            if ko == v:
                return [code]
        return []

    def _dps_weather_key():
        v = dps_weather_var.get()
        for k, ko in WEATHER_KO.items():
            if ko == v:
                return k if k != "none" else None
        return None

    def refresh_pve_dps():
        for r in dps_tree.get_children():
            dps_tree.delete(r)
        atk = _selected_attacker()
        if not atk:
            dps_pokemon_var.set("좌측에서 포켓몬 선택")
            dps_status_var.set("• 좌측 포켓몬 선택 시 자동 갱신")
            return
        sid = atk.get("speciesId", "")
        ko = sid_to_display.get(sid, sid)
        types = " · ".join(TYPE_KO.get(t, t) for t in atk.get("types", [])
                           if t and t != "none")
        dps_pokemon_var.set(f"{ko}  ({types})")

        target_types = _dps_target_types()
        target_str = TYPE_KO.get(target_types[0], target_types[0]) if target_types else "중립"
        weather = _dps_weather_key()

        # 모든 (속공 × 차지) 조합 → DPS 리스트
        fasts = (atk.get("fastMoves") or []) + (atk.get("eliteMoves") or [])
        chargeds = (atk.get("chargedMoves") or []) + (atk.get("eliteMoves") or [])
        rows = []
        elite_set = set(atk.get("eliteMoves") or [])
        for fid in fasts:
            f = moves_by_id.get(fid)
            if not f or f.get("energyGain", 0) <= 0:
                continue
            for cid in chargeds:
                c = moves_by_id.get(cid)
                if not c or c.get("energy", 0) <= 0:
                    continue
                try:
                    lv = float(dps_lv_var.get())
                except ValueError:
                    lv = 50.0
                # 보스 가정: 5성급 보스 (cpm 0.5793, base def 180)
                r = attacker_dps_vs(atk, f, c, target_types,
                                    boss_cpm=0.5793, boss_base_def=180,
                                    weather=weather, attacker_level=lv)
                rows.append({**r, "fid": fid, "cid": cid})
        rows.sort(key=lambda x: x["edps"], reverse=True)

        def _move_ko(mid):
            k = mid.lower().replace("_", "-")
            return move_ko_map.get(k) or moves_by_id.get(mid, {}).get("name", mid)

        for i, r in enumerate(rows, 1):
            f = moves_by_id[r["fid"]]
            c = moves_by_id[r["cid"]]
            f_lbl = f"{_move_ko(r['fid'])} ({TYPE_KO.get(f['type'], f['type'])})"
            c_lbl = f"{_move_ko(r['cid'])} ({TYPE_KO.get(c['type'], c['type'])})"
            elite_mark = ""
            if r['fid'] in elite_set: f_lbl = "★ " + f_lbl
            if r['cid'] in elite_set: c_lbl = "★ " + c_lbl
            dps_tree.insert("", "end", values=(
                i, f_lbl, c_lbl,
                f"{r['fast_dmg']:.0f}",
                f"{r['charged_dmg']:.0f}",
                f"{r['edps']:.1f}",
                f"{r['dps']:.1f}",
                f"{r['tdo']:.0f}",
            ))
        dps_status_var.set(
            f"• {len(rows)}개 무브셋 · 타겟={target_str} · 날씨={dps_weather_var.get()} · "
            f"Lv{dps_lv_var.get()}/15·15·15 가정 · ★ = 엘리트/레거시 무브"
        )

    ttk.Combobox  # (placeholder for next bind block)
    for w in dps_top.winfo_children():
        if isinstance(w, ttk.Combobox):
            w.bind("<<ComboboxSelected>>", lambda e: refresh_pve_dps())

    # --- Tab 8: PvE 다이맥스 도감 ---
    dmax_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(dmax_tab, text="  PvE 다이맥스  ")

    ttk.Label(dmax_tab,
              text="포켓몬 GO 의 다이맥스/거다이맥스 가능 종 목록 (2026-04 기준, 손큐레이팅).\n"
                   "맥스 무브: 18개 타입별 표준 무브 (각 타입의 속공 무브 → 동일 타입 맥스 무브로 강화).\n"
                   "거다이맥스(GMax) 가능 종은 G열에 ★ 표시.",
              font=("", 9), foreground="#555", justify="left"
              ).pack(anchor="w", pady=(0, 6))

    dmax_table_frame = ttk.Frame(dmax_tab)
    dmax_table_frame.pack(fill="both", expand=True)
    dmax_scroll = ttk.Scrollbar(dmax_table_frame, orient="vertical")
    dmax_scroll.pack(side="right", fill="y")
    dmax_cols = ("name", "types", "gmax", "atk", "def", "hp", "best_max")
    dmax_labels = ["포켓몬", "타입", "G", "공", "방", "체", "최적 맥스 무브"]
    dmax_widths = [180, 130, 30, 50, 50, 50, 200]
    dmax_tree = ttk.Treeview(dmax_table_frame, columns=dmax_cols, show="headings",
                             yscrollcommand=dmax_scroll.set, height=22)
    for c, l, w in zip(dmax_cols, dmax_labels, dmax_widths):
        dmax_tree.heading(c, text=l)
        dmax_tree.column(c, width=w, anchor="w" if c in ("name", "best_max") else "center")
    dmax_tree.pack(side="left", fill="both", expand=True)
    dmax_scroll.config(command=dmax_tree.yview)

    dmax_status_var = tk.StringVar(value="")
    ttk.Label(dmax_tab, textvariable=dmax_status_var,
              font=("", 8), foreground="#666").pack(anchor="w", pady=(4, 0))

    dmax_sid_by_iid = {}  # tree iid → sid (행 더블클릭 시 카운터 탭으로 점프)

    def refresh_dynamax():
        for r in dmax_tree.get_children():
            dmax_tree.delete(r)
        dmax_sid_by_iid.clear()
        cnt = 0
        for sid, gmax in DYNAMAX_POOL:
            p = next((x for x in state["gm"]["pokemon"] if x.get("speciesId") == sid), None)
            if not p:
                continue
            disp = sid_to_display.get(sid, sid)
            types = [t for t in p.get("types", []) if t and t != "none"]
            type_str = " · ".join(TYPE_KO.get(t, t) for t in types)
            bs = p.get("baseStats", {})
            best_max = "맥스가드 / 맥스스피릿" if not types else \
                       f"맥스{MAX_MOVE_KO.get(types[0], '?')}"
            iid = dmax_tree.insert("", "end", values=(
                disp, type_str, "★" if gmax else "",
                bs.get("atk", "—"), bs.get("def", "—"), bs.get("hp", "—"),
                best_max,
            ))
            dmax_sid_by_iid[iid] = sid
            cnt += 1
        dmax_status_var.set(
            f"• 총 {cnt}/{len(DYNAMAX_POOL)} 종 표시 · ★ = 거다이맥스(GMax) 폼 존재 · "
            "데이터: PokeMiners GAME_MASTER 기반 큐레이션 · "
            "행 더블클릭 → PvE 카운터 탭으로 이 종을 보스로 분석"
        )

    def _on_dmax_double(_e=None):
        sel = dmax_tree.selection()
        if not sel:
            return
        sid = dmax_sid_by_iid.get(sel[0])
        if not sid:
            return
        # 좌측 listbox 에서 해당 sid 찾아 선택 + use_selected 모드 ON + PvE 카운터 탭으로
        target_disp = sid_to_display.get(sid)
        if target_disp:
            for idx in range(listbox.size()):
                if strip_star(listbox.get(idx)) == target_disp:
                    listbox.selection_clear(0, tk.END)
                    listbox.selection_set(idx)
                    listbox.activate(idx)
                    listbox.see(idx)
                    break
        use_selected_var.set(True)
        notebook.select(raid_tab)
        refresh_counters()

    dmax_tree.bind("<Double-Button-1>", _on_dmax_double)
    dmax_tree.bind("<Return>", _on_dmax_double)

    # --- Tab 9: PvE 로켓 — 로켓단 그런트 카운터 ---
    rkt_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(rkt_tab, text="  PvE 로켓  ")

    ttk.Label(rkt_tab,
              text="로켓단 그런트 카운터 — 그런트는 항상 한 가지 타입 테마로 팀을 구성하므로,\n"
                   "타입을 고르면 그 타입에 강한 카운터 TOP 20을 보여줍니다.\n"
                   "리더(클리프/아르로/시에라)와 지오반니는 로테이션 주기가 짧으므로 별도 표 대신,\n"
                   "PvE 카운터 탭의 \"좌측 선택 포켓몬을 보스로\" 모드를 활용하세요.",
              font=("", 9), foreground="#555", justify="left"
              ).pack(anchor="w", pady=(0, 8))

    rkt_top = ttk.Frame(rkt_tab)
    rkt_top.pack(fill="x", pady=(0, 6))
    ttk.Label(rkt_top, text="그런트 타입", font=("", 10, "bold")).pack(side="left", padx=(0, 6))
    rkt_type_var = tk.StringVar(value=TYPE_KO["fire"])
    rkt_type_combo = ttk.Combobox(rkt_top, textvariable=rkt_type_var,
                                  values=[TYPE_KO[t] for t in TYPES_ORDER],
                                  width=8, state="readonly")
    rkt_type_combo.pack(side="left", padx=(0, 20))

    ttk.Label(rkt_top, text="공격자 Lv", font=("", 10, "bold")).pack(side="left", padx=(0, 4))
    rkt_lv_var = tk.StringVar(value="50")
    rkt_lv_combo = ttk.Combobox(rkt_top, textvariable=rkt_lv_var,
                                values=["40", "45", "50", "51"],
                                width=5, state="readonly")
    rkt_lv_combo.pack(side="left", padx=(0, 16))

    rkt_inc_mega_var = tk.BooleanVar(value=True)
    rkt_inc_shadow_var = tk.BooleanVar(value=True)
    rkt_inc_legend_var = tk.BooleanVar(value=True)
    for txt, var in (("메가", rkt_inc_mega_var), ("그림자", rkt_inc_shadow_var),
                     ("전설/환상", rkt_inc_legend_var)):
        ttk.Checkbutton(rkt_top, text=txt, variable=var,
                        command=lambda: refresh_rocket()
                        ).pack(side="left", padx=(0, 6))

    # 로켓단 카운터 표
    rkt_table_frame = ttk.Frame(rkt_tab)
    rkt_table_frame.pack(fill="both", expand=True)
    rkt_scroll = ttk.Scrollbar(rkt_table_frame, orient="vertical")
    rkt_scroll.pack(side="right", fill="y")
    rkt_cols = ("rank", "name", "types", "fast", "charged", "edps", "dps")
    rkt_labels = ["#", "포켓몬", "타입", "속공", "차지", "eDPS", "DPS"]
    rkt_widths = [40, 180, 110, 140, 160, 70, 70]
    rkt_tree = ttk.Treeview(rkt_table_frame, columns=rkt_cols, show="headings",
                            yscrollcommand=rkt_scroll.set, height=20)
    for c, l, w in zip(rkt_cols, rkt_labels, rkt_widths):
        rkt_tree.heading(c, text=l)
        rkt_tree.column(c, width=w, anchor="w" if c in ("name", "fast", "charged") else "center")
    rkt_tree.pack(side="left", fill="both", expand=True)
    rkt_scroll.config(command=rkt_tree.yview)

    rkt_status_var = tk.StringVar(
        value="• 그런트 보스 능력치는 평균값 가정 (atk=200/def=180) · "
              "그림자 적은 1.2× 공격 적용 (실제와 동일)")
    ttk.Label(rkt_tab, textvariable=rkt_status_var,
              font=("", 8), foreground="#666").pack(anchor="w", pady=(4, 0))

    def _rkt_type_code():
        v = rkt_type_var.get()
        for code, ko in TYPE_KO.items():
            if ko == v:
                return code
        return "fire"

    def refresh_rocket():
        for r in rkt_tree.get_children():
            rkt_tree.delete(r)
        target = _rkt_type_code()
        # 가상 보스: 그런트 평균 능치 + 선택 타입 단일
        # 그림자 1.2x 공격은 어차피 이 보스의 def 만 영향 — counter 우선순위는 동일
        synthetic_boss = {
            "speciesId": f"_grunt_{target}",
            "types": [target, "none"],
            "baseStats": {"atk": 200, "def": 180, "hp": 200},
        }
        try:
            atk_lv = float(rkt_lv_var.get())
        except ValueError:
            atk_lv = 50.0
        cnt = top_counters(
            synthetic_boss, state["gm"], moves_by_id, n=20,
            weather=None,
            include_shadow=rkt_inc_shadow_var.get(),
            include_mega=rkt_inc_mega_var.get(),
            include_legendary=rkt_inc_legend_var.get(),
            attacker_level=atk_lv,
        )
        def _move_ko(mid):
            k = mid.lower().replace("_", "-")
            return move_ko_map.get(k) or moves_by_id.get(mid, {}).get("name", mid)
        for i, c in enumerate(cnt, 1):
            disp = sid_to_display.get(c["sid"], c["sid"])
            tps = " · ".join(TYPE_KO.get(t, t) for t in c["pokemon"].get("types", [])
                             if t and t != "none")
            f_lbl = f"{_move_ko(c['fast_id'])} ({TYPE_KO.get(c['fast_type'], c['fast_type'])})"
            c_lbl = f"{_move_ko(c['charged_id'])} ({TYPE_KO.get(c['charged_type'], c['charged_type'])})"
            rkt_tree.insert("", "end", values=(
                i, disp, tps, f_lbl, c_lbl,
                f"{c['edps']:.1f}", f"{c['dps']:.1f}",
            ))
        rkt_status_var.set(
            f"• {len(cnt)}마리 표시 · 그런트 타입={rkt_type_var.get()} · "
            f"Lv{rkt_lv_var.get()}/15·15·15 가정 · 그림자/메가 적은 그대로 사용 가능"
        )

    rkt_type_combo.bind("<<ComboboxSelected>>", lambda e: refresh_rocket())
    rkt_lv_combo.bind("<<ComboboxSelected>>", lambda e: refresh_rocket())

    # ===== Actions =====
    last_query = [""]
    last_fav_only = [None]
    last_cat = [(None, None, None)]

    def update_listbox(force=False, auto_select=True):
        q = search_entry.get()
        fo = fav_only_var.get()
        cat = (show_normal_var.get(), show_shadow_var.get(), show_mega_var.get())
        if not force and q == last_query[0] and fo == last_fav_only[0] and cat == last_cat[0]:
            return
        last_query[0] = q
        last_fav_only[0] = fo
        last_cat[0] = cat
        filtered = filter_displays(q, only_favs=fo,
                                   show_normal=cat[0],
                                   show_shadow=cat[1],
                                   show_mega=cat[2])
        listbox.delete(0, tk.END)
        for d in filtered:
            listbox.insert(tk.END, display_with_star(d))
        suffix = " (즐겨찾기)" if fo else ""
        if not filtered:
            if not any(cat):
                count_var.set("⚠ 분류 필터에서 일반/그림자/메가 중 하나는 켜야 함")
            elif fo and not favorites:
                count_var.set("⚠ 즐겨찾기 없음 — 포켓몬 선택 후 ☆ 버튼")
            elif q:
                count_var.set(f"⚠ '{q}' 검색 결과 없음 — 다른 단어로 시도")
            else:
                count_var.set("⚠ 표시할 포켓몬 없음")
        else:
            count_var.set(f"{len(filtered)}종 표시 / 전체 {len(all_displays_full)}종{suffix}")
        if filtered and auto_select:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(0)
            listbox.activate(0)
            refresh()

    def do_data_refresh():
        if not messagebox.askyesno("데이터 업데이트",
                                   "PvPoke 시즌 데이터를 다시 다운로드합니다.\n"
                                   "(인터넷 연결 필요, 약 5~15초)\n\n계속할까요?"):
            return
        try:
            refresh_all_data()
        except Exception as e:
            messagebox.showerror("실패", f"갱신 실패: {e}")
            return
        # 새 데이터 반영
        new_gm = load_gamemaster()
        state["gm"] = new_gm
        moves_by_id.clear()
        moves_by_id.update({m["moveId"]: m for m in new_gm.get("moves", [])})
        new_dex_to_ko = load_korean_dex_map()
        new_entries = build_display_entries(new_gm, new_dex_to_ko)
        display_to_sid.clear()
        display_to_sid.update(dict(new_entries))
        sid_to_display.clear()
        sid_to_display.update({s: d for d, s in new_entries})
        for sid, disp in build_sid_display_full(new_gm, new_dex_to_ko).items():
            sid_to_display.setdefault(sid, disp)
        all_displays_full[:] = sorted(display_to_sid.keys(), key=lambda s: s.lower())
        for lg in LEAGUES:
            rk = load_league_rankings(lg.cup_id, lg.cap)
            rankings[lg.name] = rk
            rankings_index[lg.name] = {
                e.get("speciesId", ""): i + 1 for i, e in enumerate(rk)
            }
        # 새 시즌에서 사라진 컵 / 랭킹 미공개 컵 드롭, 시즌 컵 콤보 갱신
        LEAGUES[:] = [lg for lg in LEAGUES if rankings.get(lg.name)]
        _refresh_cup_choices()
        # 현재 선택된 리그가 사라졌으면 슈퍼리그로 폴백
        if not any(lg.name == league_var.get() for lg in LEAGUES):
            _select_builtin("슈퍼리그")
        move_ko_map.clear()
        move_ko_map.update(load_move_ko_map())
        ranking_cache.clear()
        try:
            raid_state["bosses"] = load_raid_bosses(force=True)
            _populate_boss_combo()
        except Exception:
            pass
        update_data_status_label()
        update_listbox(force=True, auto_select=False)
        refresh_meta(force=True)
        messagebox.showinfo("완료", "데이터 업데이트 완료")

    last_meta_state = [(None, None)]  # (league, search_query)

    def refresh_meta(force=False):
        league_name = league_var.get()
        q = norm(meta_search_var.get())
        state_key = (league_name, q)
        if not force and last_meta_state[0] == state_key:
            return
        last_meta_state[0] = state_key
        ranking = rankings.get(league_name, [])

        for r in meta_tree.get_children():
            meta_tree.delete(r)

        shown = 0
        for i, entry in enumerate(ranking, 1):
            sid = entry.get("speciesId", "")
            disp = sid_to_display.get(sid, entry.get("speciesName", sid))
            if q and q not in norm(disp) and q not in sid.lower():
                continue
            score = entry.get("score", 0)
            moveset = entry.get("moveset") or []
            moves_str = " / ".join(prettify_move(m, move_ko_map) for m in moveset[:3])
            tag = "top" if i <= 5 else ""
            meta_tree.insert("", "end", values=(
                f"#{i}",
                disp,
                f"{score:.1f}" if isinstance(score, (int, float)) else str(score),
                moves_str,
            ), tags=(tag,))
            shown += 1
        meta_tree.tag_configure("top", background="#fff9dd")

        if q:
            meta_label.set(f"▼ {league_name} · 검색 '{meta_search_var.get()}' → {shown}종 / 전체 {len(ranking)}종")
        else:
            meta_label.set(f"▼ {league_name} 메타 전체 {len(ranking)}종")

    ranking_cache = {}  # sid → {league_name: valid_ranked_list}

    def find_ranking_entry(league_name, sid):
        for e in rankings.get(league_name, []):
            if e.get("speciesId") == sid:
                return e
        return None

    def clear_moves_tab():
        moves_rec_var.set("")
        for r in fast_tree.get_children():
            fast_tree.delete(r)
        for r in charged_tree.get_children():
            charged_tree.delete(r)

    def refresh_moves(pokemon, league_name):
        entry = find_ranking_entry(league_name, pokemon.get("speciesId"))
        rec_set = set(entry.get("moveset") or []) if entry else set()
        elite_set = set(pokemon.get("eliteMoves") or [])

        if rec_set:
            moveset_str = " / ".join(prettify_move(m, move_ko_map) for m in entry["moveset"][:3])
            moves_rec_var.set(f"추천 기술 조합 ({league_name}): {moveset_str}")
        else:
            moves_rec_var.set(f"({league_name} PvPoke 랭킹 미등재 — 사용률 데이터 없음)")

        uses_fast, uses_charged = {}, {}
        if entry and entry.get("moves"):
            for m in entry["moves"].get("fastMoves", []) or []:
                uses_fast[m["moveId"]] = m.get("uses", 0)
            for m in entry["moves"].get("chargedMoves", []) or []:
                uses_charged[m["moveId"]] = m.get("uses", 0)
        total_fast = sum(uses_fast.values()) or 0
        total_charged = sum(uses_charged.values()) or 0

        def build_rows(move_ids, uses_map, total):
            rows = []
            for mid in move_ids:
                info = moves_by_id.get(mid, {})
                uses = uses_map.get(mid, 0)
                pct = (uses / total * 100) if total else None
                rows.append({
                    "id": mid,
                    "name": prettify_move(mid, move_ko_map),
                    "type": TYPE_KO.get(info.get("type", ""), info.get("type", "")),
                    "power": info.get("power", "—"),
                    "energy_gain": info.get("energyGain", "—"),
                    "energy_cost": info.get("energy", "—"),
                    "turns": info.get("turns", "—"),
                    "uses": uses,
                    "pct": pct,
                    "rec": mid in rec_set,
                    "acq": move_acquisition(pokemon, mid, elite_set),
                })
            rows.sort(key=lambda r: (-(r["uses"] or 0), not r["rec"], r["name"]))
            return rows

        # Fast
        for r in fast_tree.get_children():
            fast_tree.delete(r)
        for row in build_rows(pokemon.get("fastMoves") or [], uses_fast, total_fast):
            pct_str = f"{row['pct']:.1f}%" if row["pct"] is not None else "—"
            tag = "rec" if row["rec"] else ""
            fast_tree.insert("", "end", values=(
                "★" if row["rec"] else "",
                ACQ_LABEL.get(row["acq"], ""),
                row["name"], row["type"], row["power"],
                row["energy_gain"], row["turns"], pct_str,
            ), tags=(tag,))
        fast_tree.tag_configure("rec", background="#fff2cc")

        # Charged
        for r in charged_tree.get_children():
            charged_tree.delete(r)
        for row in build_rows(pokemon.get("chargedMoves") or [], uses_charged, total_charged):
            pct_str = f"{row['pct']:.1f}%" if row["pct"] is not None else "—"
            tag = "rec" if row["rec"] else ""
            charged_tree.insert("", "end", values=(
                "★" if row["rec"] else "",
                ACQ_LABEL.get(row["acq"], ""),
                row["name"], row["type"], row["power"],
                row["energy_cost"], pct_str,
            ), tags=(tag,))
        charged_tree.tag_configure("rec", background="#fff2cc")

    def clear_evo_row():
        for w in list(evo_frame.winfo_children()):
            if w is not evo_title:
                w.destroy()

    def clear_sprite():
        sprite_label.config(image="", text="이미지\n없음", fg="#bbb",
                            font=("", 9), anchor="center", justify="center")
        sprite_label.image = None

    def load_sprite(pokemon):
        path = get_sprite_path(pokemon)
        if not path:
            clear_sprite()
            return
        try:
            img = tk.PhotoImage(file=path)
            sprite_label.config(image=img, text="")
            sprite_label.image = img  # keep ref (tk GC)
        except Exception:
            clear_sprite()

    def select_pokemon_by_display(disp):
        search_var.set("")
        if fav_only_var.get() and display_to_sid.get(disp) not in favorites:
            fav_only_var.set(False)
        update_listbox(force=True, auto_select=False)
        for idx in range(listbox.size()):
            if strip_star(listbox.get(idx)) == disp:
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(idx)
                listbox.activate(idx)
                listbox.see(idx)
                refresh()
                return

    def render_evo_chain(current_sid):
        clear_evo_row()
        stages = get_family_chain(state["gm"], current_sid)
        if not stages:
            ttk.Label(evo_frame, text="(단일종 · 진화 없음)",
                      font=("", 9), foreground="#999").pack(side="left")
            return
        for i, stage in enumerate(stages):
            if i > 0:
                ttk.Label(evo_frame, text="→", font=("", 11),
                          foreground="#888").pack(side="left", padx=4)
            for j, s in enumerate(stage):
                if j > 0:
                    ttk.Label(evo_frame, text="/", font=("", 10),
                              foreground="#aaa").pack(side="left", padx=2)
                disp = sid_to_display.get(s, s)
                is_current = (s == current_sid)
                if is_current:
                    ttk.Label(evo_frame, text=disp,
                              font=("", 10, "bold"), foreground="#c33").pack(side="left")
                else:
                    lbl = tk.Label(evo_frame, text=disp,
                                   font=("TkDefaultFont", 10, "underline"),
                                   fg="#0066cc", cursor="hand2")
                    lbl.pack(side="left")
                    lbl.bind("<Button-1>", lambda e, d=disp: select_pokemon_by_display(d))

    def clear_type_row():
        for w in list(type_inner.winfo_children()):
            w.destroy()

    def render_type_effectiveness(types):
        clear_type_row()
        types = [t for t in types if t and t != "none"]
        if not types:
            return
        types_str = " / ".join(TYPE_KO.get(t, t) for t in types)
        ttk.Label(type_inner, text=f"[{types_str}]",
                  font=("", 9, "bold"), foreground="#333").pack(side="left", padx=(0, 8))
        eff = type_effectiveness(types)
        # PoGO 실제 배수: 1.6 / 0.625 / 0.39 단일, 듀얼은 곱셈 (2.56 / 0.244 / 0.152 등)
        big_w   = sorted([t for t, m in eff.items() if m > 1.6])      # 2.56× (듀얼 약점 중첩)
        w       = sorted([t for t, m in eff.items() if 1.0 < m <= 1.6])  # 1.6× 단일
        r       = sorted([t for t, m in eff.items() if 0.5 < m < 1.0])    # 0.625×
        big_r   = sorted([t for t, m in eff.items() if m <= 0.5])         # 0.39× 이하
        for label, lst, color in [
            ("2.56× 약점",     big_w, "#c00"),
            ("1.6× 약점",       w,     "#e70"),
            ("0.625× 내성",     r,     "#070"),
            ("0.39×↓ 이중내성", big_r, "#055"),
        ]:
            if lst:
                names = " ".join(TYPE_KO.get(t, t) for t in lst)
                ttk.Label(type_inner, text=f"{label}:",
                          font=("", 8, "bold"), foreground=color).pack(side="left", padx=(8, 2))
                ttk.Label(type_inner, text=names,
                          font=("", 8), foreground=color).pack(side="left")

    def toggle_favorite():
        sel = listbox.curselection()
        if not sel:
            return
        disp = strip_star(listbox.get(sel[0]))
        sid = display_to_sid.get(disp)
        if not sid:
            return
        if sid in favorites:
            favorites.discard(sid)
        else:
            favorites.add(sid)
        save_favorites(favorites)
        # 리스트 갱신 (선택 유지)
        idx_before = sel[0]
        listbox.delete(idx_before)
        listbox.insert(idx_before, display_with_star(disp))
        listbox.selection_set(idx_before)
        update_fav_btn(sid)
        fav_count_var.set(f"★ 즐겨찾기만 보기  ({len(favorites)}개)")

    def update_fav_btn(sid):
        if sid in favorites:
            fav_btn_var.set("★ 즐겨찾기")
        else:
            fav_btn_var.set("☆ 즐겨찾기")

    def refresh():
        refresh_meta()
        sel = listbox.curselection()
        if not sel:
            info_var.set("왼쪽에서 포켓몬을 선택하세요.")
            clear_evo_row()
            clear_sprite()
            clear_moves_tab()
            clear_type_row()
            fav_btn_var.set("☆ 즐겨찾기")
            table_label.set("")
            my_iv_result.set("")
            for r in tree.get_children():
                tree.delete(r)
            for r in summary_tree.get_children():
                summary_tree.delete(r)
            return

        disp = strip_star(listbox.get(sel[0]))
        sid = display_to_sid.get(disp)
        pokemon = next((p for p in state["gm"]["pokemon"] if p.get("speciesId") == sid), None)
        if not pokemon:
            return
        base = pokemon["baseStats"]
        update_fav_btn(sid)
        render_type_effectiveness(pokemon.get("types") or [])

        # 현재 레벨 (강화 비용 계산용)
        cur_lv_s = cur_lv_var.get().strip()
        try:
            cur_lv = float(cur_lv_s) if cur_lv_s else None
            cur_idx = idx_from_level(cur_lv) if cur_lv else None
        except ValueError:
            cur_idx = None

        # Compute all 4 leagues once per Pokemon, cache
        if ranking_cache.get("_sid") != sid:
            ranking_cache.clear()
            ranking_cache["_sid"] = sid
            max_idx = len(CPM) - 1
            for lg in LEAGUES:
                r = rank_all(base, lg.cap, max_idx)
                ranking_cache[lg.name] = [e for e in r if e[2] != -1]

        # Parse user IV — StringVar 비어있으면 None
        def _iv(sv):
            s = sv.get().strip()
            if s == "":
                return None
            try:
                v = int(s)
                return v if 0 <= v <= 15 else None
            except ValueError:
                return None
        a_, d_, h_ = _iv(atk_var), _iv(def_var), _iv(hp_var)
        user_iv = (a_, d_, h_) if a_ is not None and d_ is not None and h_ is not None else None

        info_var.set(
            f"{disp}   ·   종족값 공 {base['atk']} / 방 {base['def']} / 체 {base['hp']}"
        )
        render_evo_chain(sid)
        load_sprite(pokemon)
        refresh_moves(pokemon, league_var.get())

        # Per-league metrics
        metrics = {}
        for lg in LEAGUES:
            lname = lg.name
            valid = ranking_cache.get(lname, [])
            if not valid:
                metrics[lname] = None
                continue
            top_sp = valid[0][1]
            top_iv = valid[0][0]
            user_rank, user_entry = None, None
            if user_iv:
                for i, entry in enumerate(valid, 1):
                    if entry[0] == user_iv:
                        user_rank, user_entry = i, entry
                        break
            metrics[lname] = dict(valid=valid, top_sp=top_sp, top_iv=top_iv,
                                  user_rank=user_rank, user_entry=user_entry)

        # Best league (highest user pct)
        best_lname, best_pct = None, -1
        for lname, m in metrics.items():
            if m and m["user_entry"]:
                pct = m["user_entry"][1] / m["top_sp"] * 100
                if pct > best_pct:
                    best_pct, best_lname = pct, lname

        # Summary table
        for r in summary_tree.get_children():
            summary_tree.delete(r)
        current_league = league_var.get()
        current_item = None

        def _cost_str(target_idx):
            if cur_idx is None:
                return "현재Lv 입력→"
            if target_idx <= cur_idx:
                return "강화 불필요 ✓"
            d, c, x = power_up_cost(cur_idx, target_idx)
            xl_str = f" · XL의사탕 {x}" if x else ""
            return f"별의모래 {d:,} · 사탕 {c}{xl_str}"

        for lg in LEAGUES:
            lname = lg.name
            m = metrics.get(lname)
            star = "★ " if best_lname == lname else "   "
            meta_rk = rankings_index.get(lname, {}).get(sid)
            meta_total = len(rankings.get(lname, []))
            if meta_rk and meta_total:
                meta_str = f"#{meta_rk}/{meta_total}"
            else:
                meta_str = "미등재"
            if m is None:
                iid = summary_tree.insert("", "end", values=(
                    f"{star}{lname}", meta_str, "못 들어감", "—", "—", "—", "—", "—"
                ), tags=(lname,))
            elif m["user_entry"]:
                _, sp, lvl_idx, cp = m["user_entry"]
                pct = sp / m["top_sp"] * 100
                lvl = level_from_idx(lvl_idx)
                top_iv = m["top_iv"]
                cost = _cost_str(lvl_idx)
                iid = summary_tree.insert("", "end", values=(
                    f"{star}{lname}",
                    meta_str,
                    f"#{m['user_rank']}/4096",
                    f"{pct:.2f}%",
                    f"Lv{lvl:g}",
                    cp,
                    f"{top_iv[0]}/{top_iv[1]}/{top_iv[2]}",
                    cost,
                ), tags=(lname, "best") if best_lname == lname else (lname,))
            else:
                top_iv = m["top_iv"]
                top_idx = m["valid"][0][2]
                cost = _cost_str(top_idx) if cur_idx is not None else "—"
                iid = summary_tree.insert("", "end", values=(
                    f"{star}{lname}", meta_str, "-", "-",
                    f"Lv{level_from_idx(top_idx):g}",
                    m["valid"][0][3],
                    f"{top_iv[0]}/{top_iv[1]}/{top_iv[2]}",
                    cost,
                ), tags=(lname,))
            if lname == current_league:
                current_item = iid

        summary_tree.tag_configure("best", background="#fff2cc")
        if current_item:
            summary_tree.selection_set(current_item)

        # My IV short summary line
        cm = metrics.get(current_league)
        if user_iv is None:
            my_iv_result.set("· 입력하면 리그별 내 순위가 계산됩니다")
        elif cm and cm["user_entry"]:
            _, sp, lvl_idx, cp = cm["user_entry"]
            pct = sp / cm["top_sp"] * 100
            lvl = level_from_idx(lvl_idx)
            my_iv_result.set(
                f"· 선택리그({current_league}) → #{cm['user_rank']}/4096  Lv{lvl:g}  CP{cp}  {pct:.2f}%"
            )
        else:
            my_iv_result.set(f"· 선택리그({current_league})에는 못 들어감")

        # Top 100 detail table for current league
        for r in tree.get_children():
            tree.delete(r)
        if not cm:
            table_label.set(f"▼ {current_league} — 이 포켓몬은 못 들어감")
            return

        table_label.set(
            f"▼ {current_league} 기준 베스트 개체값 Top 100"
            f"{'   |   내 개체값 = 빨간 행' if cm['user_rank'] and cm['user_rank'] <= 100 else ''}"
        )

        user_item_id = None
        for rank_idx, entry in enumerate(cm["valid"][:100], 1):
            iv, sp, lvl_idx, cp = entry
            lvl = level_from_idx(lvl_idx)
            pct = sp / cm["top_sp"] * 100 if cm["top_sp"] > 0 else 0
            if user_iv and iv == user_iv:
                tag = "user"
            elif rank_idx <= 3:
                tag = "top"
            else:
                tag = ""
            iid = tree.insert("", "end", values=(
                f"#{rank_idx}",
                f"{iv[0]} / {iv[1]} / {iv[2]}",
                f"Lv{lvl:g}",
                cp,
                f"{sp:,.0f}",
                f"{pct:.2f}%",
            ), tags=(tag,))
            if tag == "user":
                user_item_id = iid
        tree.tag_configure("top", background="#fff9dd")
        tree.tag_configure("user", background="#ffd6d6", foreground="#000")

        if user_item_id:
            tree.see(user_item_id)
            tree.selection_set(user_item_id)

    # ----- IV 역검색 -----
    def refresh_reverse():
        def _iv(sv):
            s = sv.get().strip()
            try:
                v = int(s)
                return v if 0 <= v <= 15 else None
            except (ValueError, AttributeError):
                return None
        a, d, h = _iv(atk_var), _iv(def_var), _iv(hp_var)
        if a is None or d is None or h is None:
            for tr in rev_trees.values():
                for r in tr.get_children():
                    tr.delete(r)
            return
        user_iv = (a, d, h)
        topn = max(50, min(500, rev_topn_var.get() or 200))
        max_idx = len(CPM) - 1
        gm_pokemon = state["gm"]["pokemon"]
        by_sid = {p["speciesId"]: p for p in gm_pokemon}

        for lg in _BUILTIN_LEAGUES:
            lname = lg.name
            cap = lg.cap
            tr = rev_trees[lname]
            for r in tr.get_children():
                tr.delete(r)
            league_rk = rankings.get(lname, [])[:topn]
            results = []
            for entry in league_rk:
                sid = entry.get("speciesId")
                p = by_sid.get(sid)
                if not p:
                    continue
                base = p["baseStats"]
                # 사용자 IV의 SP
                blu = best_level_under_cap(base, user_iv, cap, max_idx)
                if blu is None:
                    continue
                _, cpm_u, _ = blu
                user_sp = stat_product(base, user_iv, cpm_u)
                # 이 포켓몬 최고 SP (15/15/15가 마스터에서 최적, 다른 리그도 사실상 최적 근사)
                # 정확한 top SP 는 PvPoke의 stats.product * 1000 사용
                top_sp_pvpoke = entry.get("stats", {}).get("product", 0) * 1000
                if top_sp_pvpoke <= 0:
                    continue
                pct = min(100.0, user_sp / top_sp_pvpoke * 100)
                meta_score = entry.get("score", 0)
                combined = meta_score * pct / 100
                results.append((combined, pct, meta_score, sid, entry.get("speciesName", sid)))
            results.sort(key=lambda r: -r[0])
            for i, (combined, pct, meta, sid, name) in enumerate(results[:50], 1):
                disp = sid_to_display.get(sid, name)
                tag = "top3" if i <= 3 else ""
                tr.insert("", "end", values=(
                    i, disp, f"{pct:.1f}", f"{combined:.1f}",
                ), tags=(sid, tag))
            tr.tag_configure("top3", background="#fff9dd")

    def on_rev_double(event, lname):
        tr = rev_trees[lname]
        sel = tr.selection()
        if not sel:
            return
        tags = tr.item(sel[0], "tags")
        if not tags:
            return
        sid = tags[0]
        disp = sid_to_display.get(sid)
        if disp:
            select_pokemon_by_display(disp)
            notebook.select(iv_tab)

    for _lname in rev_trees:
        rev_trees[_lname].bind(
            "<Double-Button-1>",
            lambda e, n=_lname: on_rev_double(e, n)
        )

    # ----- CP → IV 추정 -----
    def refresh_cp_iv():
        for r in cp_tree.get_children():
            cp_tree.delete(r)
        sel = listbox.curselection()
        if not sel:
            cp_status_var.set("좌측에서 포켓몬을 먼저 선택하세요.")
            return
        disp = strip_star(listbox.get(sel[0]))
        sid = display_to_sid.get(disp)
        pokemon = next((p for p in state["gm"]["pokemon"] if p.get("speciesId") == sid), None)
        if not pokemon:
            cp_status_var.set("포켓몬 정보를 찾을 수 없음.")
            return
        try:
            cp_in = int(cp_var.get().strip())
            hp_in = int(chp_var.get().strip())
        except (ValueError, AttributeError):
            cp_status_var.set("CP, HP 둘 다 정수로 입력하세요.")
            return
        lv_s = clv_var.get().strip()
        level_range = None
        if lv_s:
            try:
                lv = float(lv_s)
                idx = idx_from_level(lv)
                level_range = (idx, idx)
            except ValueError:
                cp_status_var.set("Lv 형식 오류 — 비워두면 전체 레벨 검색.")
                return
        base = pokemon["baseStats"]
        cands = find_iv_candidates(base, cp_in, hp_in, level_range=level_range)
        if not cands:
            cp_status_var.set(
                f"매칭되는 IV 없음. CP/HP 값을 다시 확인하세요 "
                f"(현재 입력: CP {cp_in}, HP {hp_in})"
            )
            return
        cp_status_var.set(
            f"{disp}  →  매칭 후보 {len(cands)}건  "
            f"(합계% = (공+방+체)/45 * 100, 100% = 15/15/15)"
        )
        # group by level
        for idx, iv in cands:
            lvl = level_from_idx(idx)
            cpm = CPM[idx]
            hp_calc = int((base["hp"] + iv[2]) * cpm)
            cp_calc = compute_cp(base, iv, cpm)
            total = (iv[0] + iv[1] + iv[2]) / 45 * 100
            tag = "perfect" if iv == (15, 15, 15) else ""
            cp_tree.insert("", "end", values=(
                f"Lv{lvl:g}",
                f"{iv[0]} / {iv[1]} / {iv[2]}",
                f"{iv[0]+iv[1]+iv[2]} ({total:.0f}%)",
                hp_calc, cp_calc,
            ), tags=(tag,))
        cp_tree.tag_configure("perfect", background="#fff2cc")

    # Bindings
    # IME(한글) 조합 중에는 entry.get()이 비어있어서 실시간 필터링이 어려움.
    # → Enter 또는 검색 버튼으로 강제 확정. 폴링은 commit 후 반영 백업용.
    def trigger_search():
        update_listbox(force=True)

    def poll():
        update_listbox()
        root.after(150, poll)

    def clear_all():
        search_var.set("")
        last_query[0] = "___reset___"
        atk_var.set("")
        def_var.set("")
        hp_var.set("")
        update_listbox(force=True, auto_select=False)
        listbox.selection_clear(0, tk.END)
        cur_lv_var.set("")
        info_var.set("왼쪽에서 포켓몬을 선택하세요.")
        clear_evo_row()
        clear_sprite()
        clear_moves_tab()
        clear_type_row()
        fav_btn_var.set("☆ 즐겨찾기")
        table_label.set("")
        my_iv_result.set("")
        for r in tree.get_children():
            tree.delete(r)
        for r in summary_tree.get_children():
            summary_tree.delete(r)
        refresh_meta()
        search_entry.focus_set()

    def on_meta_double(event):
        sel = meta_tree.selection()
        if not sel:
            return
        vals = meta_tree.item(sel[0], "values")
        if len(vals) < 2:
            return
        target = vals[1]
        search_var.set("")
        update_listbox(force=True)
        for idx in range(listbox.size()):
            if strip_star(listbox.get(idx)) == target:
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(idx)
                listbox.activate(idx)
                listbox.see(idx)
                notebook.select(iv_tab)
                refresh()
                return

    search_entry.bind("<Return>", lambda e: trigger_search())
    search_entry.bind("<Escape>", lambda e: clear_all())
    search_entry.bind("<KeyRelease>", lambda e: root.after(10, update_listbox))
    search_button.configure(command=trigger_search)
    clear_button.configure(command=clear_all)

    iv_pending = [None]
    def on_iv_change(*_):
        if iv_pending[0]:
            root.after_cancel(iv_pending[0])
        iv_pending[0] = root.after(120, _iv_apply)

    def _iv_apply():
        refresh()
        # 현재 IV로 포켓몬 찾기 탭 활성 시 그쪽도 자동 갱신
        try:
            if notebook.tab(notebook.select(), "text").strip() == "PvP IV검색":
                refresh_reverse()
        except Exception:
            pass

    atk_var.trace_add("write", on_iv_change)
    def_var.trace_add("write", on_iv_change)
    hp_var.trace_add("write", on_iv_change)
    cur_lv_var.trace_add("write", on_iv_change)

    def on_summary_select(event=None):
        sel = summary_tree.selection()
        if not sel:
            return
        tags = summary_tree.item(sel[0], "tags")
        target_lname = tags[0] if tags else None
        if target_lname and target_lname != league_var.get() and target_lname != "best":
            league_var.set(target_lname)
            refresh()

    summary_tree.bind("<<TreeviewSelect>>", on_summary_select)
    def _on_listbox_select(_e=None):
        refresh()
        # 활성 탭에 따라 추가 갱신 (PvE DPS / PvE 카운터 임의 보스 모드)
        try:
            tab = notebook.tab(notebook.select(), "text").strip()
            if tab == "PvE DPS":
                refresh_pve_dps()
            elif tab == "PvE 카운터" and use_selected_var.get():
                refresh_counters()
        except Exception:
            pass
    listbox.bind("<<ListboxSelect>>", _on_listbox_select)
    listbox.bind("<Return>", _on_listbox_select)
    meta_tree.bind("<Double-Button-1>", on_meta_double)
    meta_tree.bind("<Return>", on_meta_double)

    meta_search_pending = [None]
    def on_meta_search(*_):
        if meta_search_pending[0]:
            root.after_cancel(meta_search_pending[0])
        meta_search_pending[0] = root.after(150, refresh_meta)
    meta_search_entry.bind("<KeyRelease>", on_meta_search)
    meta_search_entry.bind("<Return>", lambda e: refresh_meta(force=True))
    meta_search_entry.bind("<Escape>",
        lambda e: (meta_search_var.set(""), refresh_meta(force=True)))
    for rb in league_row.winfo_children():
        if isinstance(rb, ttk.Radiobutton):
            rb.configure(command=refresh)

    # 단축키
    def _focus_search(_e=None):
        search_entry.focus_set()
        search_entry.select_range(0, tk.END)
        return "break"

    def _switch_league(idx, _e=None):
        if 0 <= idx < len(LEAGUES):
            lg = LEAGUES[idx]
            league_var.set(lg.name)
            # 빌트인이면 컵 콤보 클리어, 컵이면 컵 콤보에 표시
            if lg in _BUILTIN_LEAGUES:
                cup_combo_var.set(CUP_PLACEHOLDER)
            else:
                cup_combo_var.set(_league_label(lg))
            refresh()

    root.bind("<Control-f>", _focus_search)
    root.bind("<Control-F>", _focus_search)
    # 리그 단축키 1~9 — Alt+숫자로 변경 (Bare 숫자는 검색창/IV 입력에서 가로채면 안 됨)
    for i, lg in enumerate(LEAGUES[:9], 1):
        root.bind(f"<Alt-Key-{i}>", lambda e, idx=i-1: _switch_league(idx, e))
    root.bind("<Control-r>", lambda e: do_data_refresh())

    # IV 역검색 / 레이드 카운터 탭으로 전환 시 자동으로 결과 갱신
    def _on_tab_changed(_e=None):
        try:
            tab = notebook.tab(notebook.select(), "text").strip()
            if tab == "PvP IV검색":
                refresh_reverse()
            elif tab == "PvE 카운터":
                refresh_counters()
            elif tab == "PvE DPS":
                refresh_pve_dps()
            elif tab == "PvE 다이맥스":
                refresh_dynamax()
            elif tab == "PvE 로켓":
                refresh_rocket()
        except Exception:
            pass
    notebook.bind("<<NotebookTabChanged>>", _on_tab_changed)

    # 검색창에서 ↓/↑/Enter → 리스트박스 네비게이션
    def _search_arrow(direction):
        size = listbox.size()
        if size == 0:
            return "break"
        cur = listbox.curselection()
        new_idx = (cur[0] + direction) if cur else (0 if direction > 0 else size - 1)
        new_idx = max(0, min(size - 1, new_idx))
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(new_idx)
        listbox.activate(new_idx)
        listbox.see(new_idx)
        refresh()
        return "break"
    search_entry.bind("<Down>", lambda e: _search_arrow(1))
    search_entry.bind("<Up>", lambda e: _search_arrow(-1))

    # 종료 시 설정 저장
    def on_close():
        try:
            settings["geometry"] = root.geometry()
            settings["fav_only"] = bool(fav_only_var.get())
            settings["show_normal"] = bool(show_normal_var.get())
            settings["show_shadow"] = bool(show_shadow_var.get())
            settings["show_mega"]   = bool(show_mega_var.get())
            settings["pve_inc_mega"]   = bool(inc_mega_var.get())
            settings["pve_inc_shadow"] = bool(inc_shadow_var.get())
            settings["pve_inc_legend"] = bool(inc_legend_var.get())
            settings["league"] = league_var.get()
            save_settings(settings)
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # 저장된 리그 복원
    saved_lg = settings.get("league")
    if saved_lg:
        for lg in LEAGUES:
            if lg.name == saved_lg:
                league_var.set(lg.name)
                if lg not in _BUILTIN_LEAGUES:
                    cup_combo_var.set(_league_label(lg))
                break

    update_listbox(force=True)
    root.after(150, poll)
    search_entry.focus_set()
    root.mainloop()


# ----- main -----

def main():
    ap = argparse.ArgumentParser(description="Pokemon GO PvP 개체값 리그 랭커",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("--cli", action="store_true", help="콘솔 CLI 모드 강제")
    ap.add_argument("pokemon", nargs="?", help="포켓몬 이름 (한글/영문)")
    ap.add_argument("ivs", nargs="*", help="개체값 3개 (공 방 체)")
    ap.add_argument("--max-level", type=float, default=51.0, help="최대 레벨 (기본 51)")
    ap.add_argument("--refresh", action="store_true",
                    help="시즌 데이터 강제 재다운로드 (gamemaster + rankings)")
    args = ap.parse_args()

    if args.refresh:
        print("=== 데이터 강제 갱신 ===")
        refresh_all_data()
        print("=== 갱신 완료 ===\n")

    gm = load_gamemaster()
    init_leagues(gm)

    if args.cli or args.pokemon:
        run_cli(args, gm)
    else:
        run_gui(gm)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        try:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("pogo_iv 오류", f"{type(e).__name__}: {e}\n\n{tb}")
            r.destroy()
        except Exception:
            print(tb, file=sys.stderr)
        sys.exit(1)
