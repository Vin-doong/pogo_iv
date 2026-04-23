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
RANKINGS_URL_TEMPLATE = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/all/overall/rankings-{cap}.json"
SPRITE_URL_BASE = "https://play.pokemonshowdown.com/sprites/gen5"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_GM = os.path.join(SCRIPT_DIR, "gamemaster.json")
CACHE_KO = os.path.join(SCRIPT_DIR, "korean_names.csv")
CACHE_MOVES = os.path.join(SCRIPT_DIR, "moves.csv")
CACHE_MOVE_NAMES = os.path.join(SCRIPT_DIR, "move_names.csv")
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

LEAGUES = [
    ("리틀컵",    500),
    ("슈퍼리그",  1500),
    ("하이퍼리그", 2500),
    ("마스터리그", None),
]

KOREAN_VARIANT_PREFIXES = [
    ("섀도우", "_shadow"),
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
TYPE_MULT_SE = 1.6     # super effective
TYPE_MULT_NVE = 0.625  # not very effective
TYPE_MULT_NE = 0.390625  # immune (메인은 0배, PoGO는 0.39)

# attacker → list of (defender, multiplier)
TYPE_CHART = {
    "normal":  {"rock": "nve", "steel": "nve", "ghost": "ne"},
    "fire":    {"grass": "se", "ice": "se", "bug": "se", "steel": "se",
                "fire": "nve", "water": "nve", "rock": "nve", "dragon": "nve"},
    "water":   {"fire": "se", "ground": "se", "rock": "se",
                "water": "nve", "grass": "nve", "dragon": "nve"},
    "electric":{"water": "se", "flying": "se",
                "electric": "nve", "grass": "nve", "dragon": "nve", "ground": "ne"},
    "grass":   {"water": "se", "ground": "se", "rock": "se",
                "fire": "nve", "grass": "nve", "poison": "nve", "flying": "nve",
                "bug": "nve", "dragon": "nve", "steel": "nve"},
    "ice":     {"grass": "se", "ground": "se", "flying": "se", "dragon": "se",
                "fire": "nve", "water": "nve", "ice": "nve", "steel": "nve"},
    "fighting":{"normal": "se", "ice": "se", "rock": "se", "dark": "se", "steel": "se",
                "poison": "nve", "flying": "nve", "psychic": "nve", "bug": "nve",
                "fairy": "nve", "ghost": "ne"},
    "poison":  {"grass": "se", "fairy": "se",
                "poison": "nve", "ground": "nve", "rock": "nve", "ghost": "nve",
                "steel": "ne"},
    "ground":  {"fire": "se", "electric": "se", "poison": "se", "rock": "se", "steel": "se",
                "grass": "nve", "bug": "nve", "flying": "ne"},
    "flying":  {"grass": "se", "fighting": "se", "bug": "se",
                "electric": "nve", "rock": "nve", "steel": "nve"},
    "psychic": {"fighting": "se", "poison": "se",
                "psychic": "nve", "steel": "nve", "dark": "ne"},
    "bug":     {"grass": "se", "psychic": "se", "dark": "se",
                "fire": "nve", "fighting": "nve", "poison": "nve", "flying": "nve",
                "ghost": "nve", "steel": "nve", "fairy": "nve"},
    "rock":    {"fire": "se", "ice": "se", "flying": "se", "bug": "se",
                "fighting": "nve", "ground": "nve", "steel": "nve"},
    "ghost":   {"psychic": "se", "ghost": "se", "dark": "nve", "normal": "ne"},
    "dragon":  {"dragon": "se", "steel": "nve", "fairy": "ne"},
    "dark":    {"psychic": "se", "ghost": "se",
                "fighting": "nve", "dark": "nve", "fairy": "nve"},
    "steel":   {"ice": "se", "rock": "se", "fairy": "se",
                "fire": "nve", "water": "nve", "electric": "nve", "steel": "nve"},
    "fairy":   {"fighting": "se", "dragon": "se", "dark": "se",
                "fire": "nve", "poison": "nve", "steel": "nve"},
}

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


def load_league_rankings(cap, force=False):
    """PvPoke overall rankings for the league (score-desc sorted)."""
    c = cap if cap is not None else 10000
    path = os.path.join(SCRIPT_DIR, f"rankings-{c}.json")
    _ensure_file(path, lambda p: _download(RANKINGS_URL_TEMPLATE.format(cap=c), p),
                 f"리그 랭킹 cap={c}", DATA_MAX_AGE_DAYS, force)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"랭킹 파일 파싱 실패 (cap={c}): {e}")
        return []


def refresh_all_data():
    """모든 시즌별 데이터 강제 재다운로드. 새 gm 객체 + last-update timestamp 반환."""
    load_gamemaster(force=True)
    load_korean_dex_map(force=True)
    load_move_ko_map(force=True)
    for _, cap in LEAGUES:
        load_league_rankings(cap, force=True)


def data_status():
    """[(label, path, age_days), ...] — 각 데이터 파일 현황."""
    items = [("게임마스터", CACHE_GM), ("한글 이름", CACHE_KO),
             ("기술 한글", CACHE_MOVE_NAMES)]
    for lname, cap in LEAGUES:
        c = cap if cap is not None else 10000
        items.append((f"랭킹·{lname}", os.path.join(SCRIPT_DIR, f"rankings-{c}.json")))
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
    "weather-ball":      "웨더볼",
}

TYPE_KO = {
    "normal": "노말", "fire": "불꽃", "water": "물", "electric": "전기",
    "grass": "풀", "ice": "얼음", "fighting": "격투", "poison": "독",
    "ground": "땅", "flying": "비행", "psychic": "에스퍼", "bug": "벌레",
    "rock": "바위", "ghost": "고스트", "dragon": "드래곤", "dark": "악",
    "steel": "강철", "fairy": "페어리",
}


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

    # 2) 변형 접미사 제거 + underscore flatten (섀도우/변형 → 베이스)
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
    변형(섀도우/메가)일 경우 해당 변형의 family 우선, 없으면 베이스로.
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
        prefix_parts.append("섀도우")
    if mega_p:
        prefix_parts.append(mega_p)
    if region_kor:
        prefix_parts.append(region_kor)
    prefix_parts.append(main)
    disp = " ".join(prefix_parts)
    if form_ko:
        disp = f"{disp} ({form_ko})"
    return disp


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
            tag = TYPE_CHART[atk].get(d)
            if tag == "se":
                mult *= TYPE_MULT_SE
            elif tag == "nve":
                mult *= TYPE_MULT_NVE
            elif tag == "ne":
                mult *= TYPE_MULT_NE
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
    for league_name, cap in LEAGUES:
        ranked = rank_all(base, cap, max_idx)
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
            rows.append((league_name, None, None, None, None, None, None))
            continue
        _, sp, lvl_idx, cp = user_entry
        pct = sp / top_sp * 100
        lvl = level_from_idx(lvl_idx)
        rows.append((league_name, lvl, cp, sp, user_rank, pct, top_iv))
        if best_rec is None or pct > best_rec[5]:
            best_rec = (league_name, lvl, cp, sp, user_rank, pct, top_iv)
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


def analyze_cli(gm, ko_base_map, name, ivs, max_level):
    p, alts = find_pokemon_cli(gm, ko_base_map, name)
    if not p:
        print(f"'{name}' — 찾을 수 없음. 예: 마릴리, 메가 갸라도스, 섀도우 뮤츠")
        return
    if alts:
        print(f"[다른 후보: {', '.join(alts)}]")

    rows, best = analyze_pokemon(p, ivs, max_level)
    base = p["baseStats"]
    print(f"\n=== {p['speciesName']} ({p['speciesId']}) ===")
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

    if args.pokemon and len(args.ivs) == 3:
        ivs = parse_ivs(" ".join(args.ivs))
        analyze_cli(gm, ko_base_map, args.pokemon, ivs, args.max_level)
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
            analyze_cli(gm, ko_base_map, name, ivs, args.max_level)
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
    all_displays_full = sorted(display_to_sid.keys(), key=lambda s: s.lower())

    # Preload league meta rankings (PvPoke overall)
    rankings = {}
    rankings_index = {}  # league_name → {sid: 1-based rank}
    for lname, cap in LEAGUES:
        rk = load_league_rankings(cap)
        rankings[lname] = rk
        rankings_index[lname] = {
            e.get("speciesId", ""): i + 1 for i, e in enumerate(rk)
        }

    # Korean move name map
    move_ko_map = load_move_ko_map()

    # Move data lookup (gamemaster)
    moves_by_id = {m["moveId"]: m for m in gm.get("moves", [])}

    # 즐겨찾기 + 설정
    favorites = load_favorites()
    settings = load_settings()

    def norm(s):
        return s.lower().replace(" ", "")

    def filter_displays(query, only_favs=False):
        q = norm(query)
        pool = (d for d in all_displays_full if display_to_sid[d] in favorites) \
            if only_favs else all_displays_full
        if not q:
            return list(pool)
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
    root.minsize(1100, 700)

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
    ttk.Checkbutton(left, text=f"★ 즐겨찾기만 보기  ({len(favorites)}개)",
                    variable=fav_only_var,
                    command=lambda: trigger_search()).pack(anchor="w", pady=(0, 4))

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

    # League selection row
    league_row = ttk.Frame(right)
    league_row.pack(fill="x", pady=(0, 8))
    ttk.Label(league_row, text="리그", font=("", 10, "bold")).pack(side="left", padx=(0, 10))
    league_var = tk.StringVar(value="슈퍼리그")
    for lname, cap in LEAGUES:
        cap_txt = f"({cap})" if cap else "(무제한)"
        ttk.Radiobutton(league_row, text=f"{lname} {cap_txt}", variable=league_var,
                        value=lname).pack(side="left", padx=4)

    # Tabs
    notebook = ttk.Notebook(right)
    notebook.pack(fill="both", expand=True)

    # --- Tab 1: 선택 포켓몬 베스트 개체값 ---
    iv_tab = ttk.Frame(notebook, padding=(6, 8))
    notebook.add(iv_tab, text="  선택 포켓몬 · 베스트 개체값  ")

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

    ttk.Label(moves_col, text="▼ 보유 기술  (★=리그 추천 · ⚡=엘리트 기술 머신 · 사용률=PvPoke)",
              font=("", 9, "bold"), foreground="#333").pack(anchor="w", pady=(0, 4))

    moves_rec_var = tk.StringVar(value="")
    ttk.Label(moves_col, textvariable=moves_rec_var,
              font=("", 9), foreground="#c33").pack(anchor="w", pady=(0, 6))

    ttk.Label(moves_col, text="노말 어택  (Fast Move)",
              font=("", 9, "bold")).pack(anchor="w", pady=(2, 2))
    fast_frame = ttk.Frame(moves_col)
    fast_frame.pack(fill="x", pady=(0, 8))
    fast_cols = ("rec", "elite", "name", "type", "power", "energy", "turns", "pct")
    fast_labels = ["★", "⚡", "기술", "타입", "위력", "에너지+", "턴", "사용률"]
    fast_widths = [25, 25, 115, 55, 45, 55, 35, 60]
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
    charged_cols = ("rec", "elite", "name", "type", "power", "energy", "pct")
    charged_labels = ["★", "⚡", "기술", "타입", "위력", "에너지", "사용률"]
    charged_widths = [25, 25, 145, 55, 45, 50, 70]
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
    notebook.add(meta_tab, text="  리그 메타 랭킹  ")

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
    notebook.add(rev_tab, text="  IV로 포켓몬 찾기  ")

    rev_top = ttk.Frame(rev_tab)
    rev_top.pack(fill="x", pady=(0, 8))
    ttk.Label(rev_top, text="개체값 입력 → 4리그별 그 IV가 잘 어울리는 포켓몬",
              font=("", 10, "bold")).pack(side="left")

    rev_input = ttk.Frame(rev_tab)
    rev_input.pack(fill="x", pady=(0, 8))
    ttk.Label(rev_input, text="공").pack(side="left", padx=(0, 2))
    rev_a_var = tk.StringVar(value="")
    ttk.Spinbox(rev_input, from_=0, to=15, textvariable=rev_a_var, width=4).pack(side="left")
    ttk.Label(rev_input, text="방").pack(side="left", padx=(10, 2))
    rev_d_var = tk.StringVar(value="")
    ttk.Spinbox(rev_input, from_=0, to=15, textvariable=rev_d_var, width=4).pack(side="left")
    ttk.Label(rev_input, text="체").pack(side="left", padx=(10, 2))
    rev_h_var = tk.StringVar(value="")
    ttk.Spinbox(rev_input, from_=0, to=15, textvariable=rev_h_var, width=4).pack(side="left")
    ttk.Label(rev_input, text="  메타 상위").pack(side="left", padx=(20, 2))
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

    rev_trees = {}
    for lname, _ in LEAGUES:
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
    notebook.add(cp_tab, text="  CP → IV 추정  ")

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

    # ===== Actions =====
    last_query = [""]
    last_fav_only = [None]

    def update_listbox(force=False, auto_select=True):
        q = search_entry.get()
        fo = fav_only_var.get()
        if not force and q == last_query[0] and fo == last_fav_only[0]:
            return
        last_query[0] = q
        last_fav_only[0] = fo
        filtered = filter_displays(q, only_favs=fo)
        listbox.delete(0, tk.END)
        for d in filtered:
            listbox.insert(tk.END, display_with_star(d))
        suffix = " (즐겨찾기)" if fo else ""
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
        all_displays_full[:] = sorted(display_to_sid.keys(), key=lambda s: s.lower())
        for lname, cap in LEAGUES:
            rk = load_league_rankings(cap)
            rankings[lname] = rk
            rankings_index[lname] = {
                e.get("speciesId", ""): i + 1 for i, e in enumerate(rk)
            }
        move_ko_map.clear()
        move_ko_map.update(load_move_ko_map())
        ranking_cache.clear()
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
                    "elite": mid in elite_set,
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
                "⚡" if row["elite"] else "",
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
                "⚡" if row["elite"] else "",
                row["name"], row["type"], row["power"],
                row["energy_cost"], pct_str,
            ), tags=(tag,))
        charged_tree.tag_configure("rec", background="#fff2cc")

    def clear_evo_row():
        for w in list(evo_frame.winfo_children()):
            if w is not evo_title:
                w.destroy()

    def clear_sprite():
        sprite_label.config(image="")
        sprite_label.image = None

    def load_sprite(pokemon):
        path = get_sprite_path(pokemon)
        if not path:
            clear_sprite()
            return
        try:
            img = tk.PhotoImage(file=path)
            sprite_label.config(image=img)
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
        if not types:
            return
        types_str = " / ".join(TYPE_KO.get(t, t) for t in types)
        ttk.Label(type_inner, text=f"[{types_str}]",
                  font=("", 9, "bold"), foreground="#333").pack(side="left", padx=(0, 8))
        eff = type_effectiveness(types)
        # 4x, 2x = weakness; 0.5x, 0.25x, 0.39x = resistance
        x4 = sorted([t for t, m in eff.items() if m > 1.6])
        x2 = sorted([t for t, m in eff.items() if 1.0 < m <= 1.6])
        x05 = sorted([t for t, m in eff.items() if 0.4 < m < 1.0])
        x025 = sorted([t for t, m in eff.items() if m <= 0.4])
        for label, lst, color in [
            ("4×약점", x4, "#c00"),
            ("2×약점", x2, "#e70"),
            ("0.5×내성", x05, "#070"),
            ("0.39×이중내성", x025, "#055"),
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
        # Checkbox 라벨 업데이트는 trace 없이 단순화 — 다음 토글 시 보임

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
            for lname, cap in LEAGUES:
                r = rank_all(base, cap, max_idx)
                ranking_cache[lname] = [e for e in r if e[2] != -1]

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
        for lname, _ in LEAGUES:
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

        for lname, _ in LEAGUES:
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
        a, d, h = _iv(rev_a_var), _iv(rev_d_var), _iv(rev_h_var)
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

        for lname, cap in LEAGUES:
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
        iv_pending[0] = root.after(120, refresh)

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
    listbox.bind("<<ListboxSelect>>", lambda e: refresh())
    listbox.bind("<Return>", lambda e: refresh())
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
            league_var.set(LEAGUES[idx][0])
            refresh()

    root.bind("<Control-f>", _focus_search)
    root.bind("<Control-F>", _focus_search)
    for i, (lname, _) in enumerate(LEAGUES, 1):
        root.bind(f"<Key-{i}>", lambda e, idx=i-1: _switch_league(idx, e))
    root.bind("<Control-r>", lambda e: do_data_refresh())

    # 종료 시 설정 저장
    def on_close():
        try:
            settings["geometry"] = root.geometry()
            settings["fav_only"] = bool(fav_only_var.get())
            settings["league"] = league_var.get()
            save_settings(settings)
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # 저장된 리그 복원
    saved_lg = settings.get("league")
    if saved_lg and any(saved_lg == n for n, _ in LEAGUES):
        league_var.set(saved_lg)

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
