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
import re
import sys
import threading
import time
import urllib.request
from collections import namedtuple
from datetime import datetime, timedelta

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
TEAM_META_URL_TEMPLATE = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/training/teams/{cup_id}/{cap}.json"
SPRITE_URL_BASE = "https://play.pokemonshowdown.com/sprites/gen5"
SCRAPEDUCK_RAIDS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.json"
SCRAPEDUCK_EVENTS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
SCRAPEDUCK_EGGS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/eggs.json"
SCRAPEDUCK_RESEARCH_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/research.json"
SCRAPEDUCK_ROCKETS_URL  = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/rocketLineups.json"
POGOMATE_RAIDS_URL = "https://pogomate.com/raids"
# pokemon-go-api: 안정적 JSON 레이드 보스 소스 (한글명·티어·CP 내장).
# pogomate HTML 스크래핑이 깨질 때의 폴백으로 사용.
POKEMONGOAPI_RAIDS_URL = "https://pokemon-go-api.github.io/pokemon-go-api/api/raidboss.json"
# pokemon-go-api pokedex: PoGo 네이티브 한글명 (PokeAPI CSV 노후로 빠진 신규 종 보강용).
POKEMONGOAPI_DEX_URL = "https://pokemon-go-api.github.io/pokemon-go-api/api/pokedex.json"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_GM = os.path.join(SCRIPT_DIR, "gamemaster.json")
CACHE_KO = os.path.join(SCRIPT_DIR, "korean_names.csv")
CACHE_MOVES = os.path.join(SCRIPT_DIR, "moves.csv")
CACHE_MOVE_NAMES = os.path.join(SCRIPT_DIR, "move_names.csv")
CACHE_RAIDS = os.path.join(SCRIPT_DIR, "raids.json")
CACHE_EVENTS = os.path.join(SCRIPT_DIR, "events.json")
CACHE_EGGS = os.path.join(SCRIPT_DIR, "eggs.json")
CACHE_RESEARCH = os.path.join(SCRIPT_DIR, "research.json")
CACHE_ROCKETS  = os.path.join(SCRIPT_DIR, "rocket_lineups.json")
CACHE_KR_RAIDS = os.path.join(SCRIPT_DIR, "kr_raids.json")
CACHE_PGOAPI_DEX = os.path.join(SCRIPT_DIR, "pgoapi_pokedex.json")
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


def compute_leagues(gm):
    """gm 에서 리그 목록을 계산해 새 리스트로 반환 (전역 LEAGUES 미변경 — 스레드 안전)."""
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
    return list(_BUILTIN_LEAGUES) + extras


def init_leagues(gm):
    """gamemaster.formats 에서 리그 목록을 동적으로 빌드. 빌트인 4개 + 시즌 컵."""
    leagues = compute_leagues(gm)
    LEAGUES.clear()
    LEAGUES.extend(leagues)
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
# 공식 강화 비용 (별의모래, 사탕, XL의 사탕) — 각 칸 = +0.5 레벨 1 step.
# idx i = CPM 레벨 idx i → i+1 로 올릴 때 비용. idx 0 = Lv1.0→1.5, idx 97 = Lv49.5→50.0.
# 출처: Bulbapedia / Pokémon GO Wiki (Lv40→50 합계 별의모래 250,000·XL 296 으로 검증).
# Lv40 부터는 일반 사탕 0 + XL의 사탕 사용. Lv50→51 은 베스트 친구 보너스(무료)라 표에 없음.
POWER_UP_COST = [
    *([(200, 1, 0)] * 4),    # Lv1.0~2.5
    *([(400, 1, 0)] * 4),    # Lv3.0~4.5
    *([(600, 1, 0)] * 4),    # Lv5.0~6.5
    *([(800, 1, 0)] * 4),    # Lv7.0~8.5
    *([(1000, 1, 0)] * 4),   # Lv9.0~10.5
    *([(1300, 2, 0)] * 4),   # Lv11.0~12.5
    *([(1600, 2, 0)] * 4),   # Lv13.0~14.5
    *([(1900, 2, 0)] * 4),   # Lv15.0~16.5
    *([(2200, 2, 0)] * 4),   # Lv17.0~18.5
    *([(2500, 2, 0)] * 4),   # Lv19.0~20.5
    *([(3000, 3, 0)] * 4),   # Lv21.0~22.5
    *([(3500, 3, 0)] * 4),   # Lv23.0~24.5
    *([(4000, 3, 0)] * 2),   # Lv25.0~25.5
    *([(4000, 4, 0)] * 2),   # Lv26.0~26.5
    *([(4500, 4, 0)] * 4),   # Lv27.0~28.5
    *([(5000, 4, 0)] * 4),   # Lv29.0~30.5
    *([(6000, 6, 0)] * 4),   # Lv31.0~32.5
    *([(7000, 8, 0)] * 4),   # Lv33.0~34.5
    *([(8000, 10, 0)] * 4),  # Lv35.0~36.5
    *([(9000, 12, 0)] * 4),  # Lv37.0~38.5
    *([(10000, 15, 0)] * 2),  # Lv39.0~39.5
    *([(10000, 0, 10)] * 2),  # Lv40.0~40.5
    *([(11000, 0, 10)] * 2),  # Lv41.0~41.5
    *([(11000, 0, 12)] * 2),  # Lv42.0~42.5
    *([(12000, 0, 12)] * 2),  # Lv43.0~43.5
    *([(12000, 0, 15)] * 2),  # Lv44.0~44.5
    *([(13000, 0, 15)] * 2),  # Lv45.0~45.5
    *([(13000, 0, 17)] * 2),  # Lv46.0~46.5
    *([(14000, 0, 17)] * 2),  # Lv47.0~47.5
    *([(14000, 0, 20)] * 2),  # Lv48.0~48.5
    *([(15000, 0, 20)] * 2),  # Lv49.0~49.5
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

# 베스트 친구 보너스 (+1 레벨) 없이 일반적으로 도달 가능한 최대 레벨.
# PvPoke, pvpivs, pokemongo-get 등 주요 사이트가 모두 Lv50 을 기본 캡으로 사용.
# Best Buddy 활성 포켓몬은 CLI 의 --max-level 51 로 따로 지정.
DEFAULT_MAX_LEVEL = 50.0
DEFAULT_MAX_IDX = int(round((DEFAULT_MAX_LEVEL - 1.0) * 2))  # = 98


# ----- data loading -----

def _download(url, dest):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (pogo_iv.py)",
        "Accept": "application/json, text/csv, text/plain",
    })
    # 임시 파일에 받은 뒤 원자적 교체 — 다운로드가 중간에 끊겨도 기존
    # 캐시(또는 빈 파일)가 손상되지 않게 한다. 실패 시 tmp 정리.
    tmp = dest + ".tmp"
    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(tmp, "wb") as f:
            f.write(resp.read())
        os.replace(tmp, dest)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


def _file_age_days(path):
    if not os.path.exists(path):
        return float("inf")
    return (time.time() - os.path.getmtime(path)) / 86400.0


def _is_stale(path, max_age_days):
    return _file_age_days(path) > max_age_days


def _format_age(path):
    if not os.path.exists(path):
        return "(없음)"
    mt = os.path.getmtime(path)
    return datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")


def _freshness_label(path, prefix=""):
    """파일 마지막 수정 → ('5시간 전' 문구, 색상코드).
    < 1일 회색 · 1~7일 주황 · 7일+ 빨강 · 없음 빨강."""
    if not os.path.exists(path):
        return (f"{prefix}없음", "#a00")
    age = time.time() - os.path.getmtime(path)
    if   age < 60:    t = "방금 전"
    elif age < 3600:  t = f"{int(age/60)}분 전"
    elif age < 86400: t = f"{int(age/3600)}시간 전"
    else:             t = f"{int(age/86400)}일 전"
    if   age < 86400:  c = "#666"
    elif age < 604800: c = "#c80"
    else:              c = "#a00"
    return (f"{prefix}{t}", c)


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
    """dex 번호 → 한글 베이스 이름.
    1차: PokeAPI CSV. 신규 종(CSV 노후로 누락)은 pokemon-go-api pokedex 로 보강."""
    _ensure_file(CACHE_KO, lambda p: _download(KOREAN_CSV_URL, p),
                 "한글 이름", STATIC_MAX_AGE_DAYS, force)
    dex_to_ko = {}
    if os.path.exists(CACHE_KO):
        with open(CACHE_KO, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 3 and row[1] == "3":  # language_id 3 = Korean
                    try:
                        dex_to_ko[int(row[0])] = row[2].strip()
                    except ValueError:
                        pass
    # 보강: CSV 에 없는 dex 번호만 pokemon-go-api 한글명으로 채움 (best-effort)
    try:
        _ensure_file(CACHE_PGOAPI_DEX,
                     lambda p: _download(POKEMONGOAPI_DEX_URL, p),
                     "한글 이름 보강", STATIC_MAX_AGE_DAYS, force)
        if os.path.exists(CACHE_PGOAPI_DEX):
            with open(CACHE_PGOAPI_DEX, encoding="utf-8") as f:
                for entry in json.load(f):
                    dex = entry.get("dexNr")
                    ko = (entry.get("names") or {}).get("Korean")
                    if dex and ko and dex not in dex_to_ko:
                        dex_to_ko[dex] = ko.strip()
    except Exception as e:
        print(f"한글 이름 보강 실패 (무시): {e}")
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
    각 항목: {name, tier, types, image, ...}. 1일마다 자동 갱신.
    (원본 ScrapedDuck 는 10분마다 LeekDuck 스크래핑 — 글로벌 기준)
    """
    _ensure_file(CACHE_RAIDS, lambda p: _download(SCRAPEDUCK_RAIDS_URL, p),
                 "현재 레이드 보스", 1, force)
    if not os.path.exists(CACHE_RAIDS):
        return []
    try:
        with open(CACHE_RAIDS, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"raids.json 파싱 실패: {e}")
        return []


def load_events(force=False):
    """ScrapedDuck (LeekDuck mirror) 의 이벤트 일정. 1일마다 자동 갱신."""
    _ensure_file(CACHE_EVENTS, lambda p: _download(SCRAPEDUCK_EVENTS_URL, p),
                 "이벤트 일정", 1, force)
    if not os.path.exists(CACHE_EVENTS):
        return []
    try:
        with open(CACHE_EVENTS, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"events.json 파싱 실패: {e}")
        return []


def load_eggs(force=False):
    """ScrapedDuck 알 부화 풀. 7일마다 자동 갱신."""
    _ensure_file(CACHE_EGGS, lambda p: _download(SCRAPEDUCK_EGGS_URL, p),
                 "알 부화 풀", 7, force)
    if not os.path.exists(CACHE_EGGS):
        return []
    try:
        with open(CACHE_EGGS, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"eggs.json 파싱 실패: {e}")
        return []


# --- 필드 리서치 영문 → 한글 번역기 (정규식 패턴 매칭) ---
import re as _re_research

_RESEARCH_TYPE_KO = {
    "normal": "노말", "fire": "불꽃", "water": "물", "electric": "전기",
    "grass": "풀", "ice": "얼음", "fighting": "격투", "poison": "독",
    "ground": "땅", "flying": "비행", "psychic": "에스퍼", "bug": "벌레",
    "rock": "바위", "ghost": "고스트", "dragon": "드래곤", "dark": "악",
    "steel": "강철", "fairy": "페어리",
}

def _t_type(en):
    return _RESEARCH_TYPE_KO.get(en.lower(), en)

# 매칭 우선순위 순서 (구체적 패턴 먼저)
_RESEARCH_RULES = [
    # 스로우 — in a row 패턴 먼저
    (r"^Make (\d+) Great Curveball Throws? in a row$",
     lambda m: f"Great 커브볼 스로우 {m.group(1)}회 연속"),
    (r"^Make (\d+) Excellent Throws? in a row$",
     lambda m: f"Excellent 스로우 {m.group(1)}회 연속"),
    (r"^Make (\d+) Great Throws? in a row$",
     lambda m: f"Great 스로우 {m.group(1)}회 연속"),
    (r"^Make (\d+) Nice Throws? in a row$",
     lambda m: f"Nice 스로우 {m.group(1)}회 연속"),
    (r"^Make (\d+) Curveball Throws? in a row$",
     lambda m: f"커브볼 스로우 {m.group(1)}회 연속"),
    (r"^Make (\d+) Throws? in a row$",
     lambda m: f"스로우 {m.group(1)}회 연속"),
    # 스로우 — 단순
    (r"^Make (\d+) Great Curveball Throws?$",
     lambda m: f"Great 커브볼 스로우 {m.group(1)}회"),
    (r"^Make (\d+) Excellent Throws?$",
     lambda m: f"Excellent 스로우 {m.group(1)}회"),
    (r"^Make (\d+) Great Throws?$",
     lambda m: f"Great 스로우 {m.group(1)}회"),
    (r"^Make (\d+) Nice Throws?$",
     lambda m: f"Nice 스로우 {m.group(1)}회"),
    (r"^Make (\d+) Curveball Throws?$",
     lambda m: f"커브볼 스로우 {m.group(1)}회"),
    # 포획
    (r"^Catch (\d+) Pokémon with Weather Boost$",
     lambda m: f"날씨 부스트 포켓몬 {m.group(1)}마리 잡기"),
    (r"^Catch (\d+) different species of Pokémon$",
     lambda m: f"포켓몬 {m.group(1)}종류 잡기"),
    (r"^Catch (\d+) ([A-Z][a-z]+)-type Pokémon$",
     lambda m: f"{_t_type(m.group(2))} 타입 포켓몬 {m.group(1)}마리 잡기"),
    (r"^Catch a ([A-Z][a-z]+)-type Pokémon$",
     lambda m: f"{_t_type(m.group(1))} 타입 포켓몬 1마리 잡기"),
    (r"^Catch (\d+) Pokémon$",
     lambda m: f"포켓몬 {m.group(1)}마리 잡기"),
    (r"^Catch a Pokémon$",
     lambda m: "포켓몬 1마리 잡기"),
    # 포켓스톱/체육관
    (r"^Spin (\d+) PokéStops? or Gyms?$",
     lambda m: f"포켓스톱/체육관 {m.group(1)}개 돌리기"),
    (r"^Spin a PokéStop or Gym$",
     lambda m: "포켓스톱/체육관 1개 돌리기"),
    # 강화
    (r"^Power up Pokémon (\d+) times?$",
     lambda m: f"포켓몬 {m.group(1)}회 강화"),
    # 진화/교환/스냅
    (r"^Evolve (\d+) Pokémon$",
     lambda m: f"포켓몬 {m.group(1)}마리 진화"),
    (r"^Evolve a Pokémon$",
     lambda m: "포켓몬 1마리 진화"),
    (r"^Trade (\d+) Pokémon$",
     lambda m: f"포켓몬 {m.group(1)}마리 교환"),
    (r"^Trade a Pokémon$",
     lambda m: "포켓몬 1마리 교환"),
    (r"^Take a snapshot of a wild Pokémon$",
     lambda m: "야생 포켓몬 스냅 촬영"),
    (r"^Take (\d+) snapshots? of wild Pokémon$",
     lambda m: f"야생 포켓몬 스냅 {m.group(1)}장 촬영"),
    # 알/사탕/걷기
    (r"^Hatch (\d+) Eggs?$",
     lambda m: f"알 {m.group(1)}개 부화"),
    (r"^Hatch an Egg$",
     lambda m: "알 1개 부화"),
    (r"^Explore (\d+(?:\.\d+)?) km$",
     lambda m: f"{m.group(1)}km 탐험"),
    (r"^Walk (\d+(?:\.\d+)?) km$",
     lambda m: f"{m.group(1)}km 걷기"),
    (r"^Earn (\d+) Cand(?:y|ies) walking with your buddy$",
     lambda m: f"버디와 함께 걸어 사탕 {m.group(1)}개 획득"),
    # 선물/베리
    (r"^Send (\d+) Gifts? and add a sticker to each$",
     lambda m: f"스티커 붙인 선물 {m.group(1)}개 보내기"),
    (r"^Send (\d+) Gifts?$",
     lambda m: f"선물 {m.group(1)}개 보내기"),
    (r"^Use (\d+) Berr(?:y|ies) to help catch Pokémon$",
     lambda m: f"포획에 베리 {m.group(1)}개 사용"),
    # 레이드
    (r"^Win (\d+) raids?$",
     lambda m: f"레이드 {m.group(1)}회 승리"),
    (r"^Win a raid$",
     lambda m: "레이드 1회 승리"),
    (r"^Win a three-star raid or higher$",
     lambda m: "3성 이상 레이드 1회 승리"),
    (r"^Win a (\d+)-star raid or higher$",
     lambda m: f"{m.group(1)}성 이상 레이드 1회 승리"),
    # GO 로켓단
    (r"^Defeat a Team GO Rocket Grunt$",
     lambda m: "GO 로켓단 따까리 1명 처치"),
    (r"^Defeat (\d+) Team GO Rocket Grunts?$",
     lambda m: f"GO 로켓단 따까리 {m.group(1)}명 처치"),
    (r"^Defeat a Team GO Rocket Leader$",
     lambda m: "GO 로켓단 간부 1명 처치"),
    # 배틀
    (r"^Win (\d+) Trainer Battles?$",
     lambda m: f"트레이너 배틀 {m.group(1)}회 승리"),
    (r"^Win a Trainer Battle$",
     lambda m: "트레이너 배틀 1회 승리"),
    (r"^Win (\d+) Gym Battles?$",
     lambda m: f"체육관 배틀 {m.group(1)}회 승리"),
]


def translate_research_task(en_text):
    """영문 리서치 태스크 → 한글. 매칭 실패 시 원문 반환."""
    if not en_text:
        return en_text
    s = en_text.strip()
    for pat, fn in _RESEARCH_RULES:
        m = _re_research.match(pat, s)
        if m:
            return fn(m)
    return en_text  # fallback: 원문


def load_rocket_lineups(force=False):
    """ScrapedDuck rocketLineups.json — 보스/간부/조무래기 라인업. 1일 캐싱."""
    _ensure_file(CACHE_ROCKETS, lambda p: _download(SCRAPEDUCK_ROCKETS_URL, p),
                 "로켓 라인업", 1, force)
    if not os.path.exists(CACHE_ROCKETS):
        return []
    try:
        with open(CACHE_ROCKETS, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"rocketLineups.json 파싱 실패: {e}")
        return []


def load_research(force=False):
    """ScrapedDuck 필드 리서치 태스크. 1일마다 자동 갱신."""
    _ensure_file(CACHE_RESEARCH, lambda p: _download(SCRAPEDUCK_RESEARCH_URL, p),
                 "필드 리서치", 1, force)
    if not os.path.exists(CACHE_RESEARCH):
        return []
    try:
        with open(CACHE_RESEARCH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"research.json 파싱 실패: {e}")
        return []


# --- pogomate.com 한국 레이드 스크래퍼 (HTML 정규식 파싱) ---
_TYPE_KO_TO_EN = {
    "노말": "normal", "불꽃": "fire", "물": "water", "전기": "electric",
    "풀": "grass", "얼음": "ice", "격투": "fighting", "독": "poison",
    "땅": "ground", "비행": "flying", "에스퍼": "psychic", "벌레": "bug",
    "바위": "rock", "고스트": "ghost", "드래곤": "dragon", "악": "dark",
    "강철": "steel", "페어리": "fairy",
}


def _slug_to_en_name(slug):
    """pogomate slug → 영문 종 이름 (ScrapedDuck name 호환).
    예: 'glalie-mega' → 'Mega Glalie', 'tapu-bulu' → 'Tapu Bulu',
        'charizard-megax' → 'Mega Charizard X'
    """
    s = slug
    mega_x = mega_y = mega = shadow = False
    if s.endswith("-megax"): s = s[:-6]; mega_x = True
    elif s.endswith("-megay"): s = s[:-6]; mega_y = True
    elif s.endswith("-mega"): s = s[:-5]; mega = True
    elif s.endswith("-shadow"): s = s[:-7]; shadow = True
    base = " ".join(p.capitalize() for p in s.split("-"))
    if mega_x: return f"Mega {base} X"
    if mega_y: return f"Mega {base} Y"
    if mega:   return f"Mega {base}"
    if shadow: return f"Shadow {base}"
    return base


def _parse_pogomate_raids_html(html):
    """pogomate.com/raids HTML → 한국 활성 레이드 보스 리스트.
    출력 형식은 ScrapedDuck raids.json 와 호환 + 추가 필드(_source, _korea_only, _period, _name_ko).
    """
    import re as _re
    m = _re.search(r"현재 레이드 보스(.*?)예정된 레이드", html, _re.S)
    if not m:
        return []
    section = m.group(1)
    # <h3>전설 (5성)</h3> / <h3>메가</h3> / <h3>그림자</h3> 로 분할
    parts = _re.split(r"<h3[^>]*>([^<]+)</h3>", section)
    cat_tier_map = {
        "전설": "5-Star Raids", "5성": "5-Star Raids",
        "메가": "Mega Raids", "그림자": "Shadow Raids",
        "엘리트": "Elite Raids", "1성": "1-Star Raids", "3성": "3-Star Raids",
    }
    results = []
    for i in range(1, len(parts), 2):
        cat = parts[i].strip()
        cont = parts[i+1] if i+1 < len(parts) else ""
        tier = None
        for k, v in cat_tier_map.items():
            if k in cat:
                tier = v
                break
        if not tier:
            continue
        for am in _re.finditer(r'<a href="/raids/([^"]+)"[^>]*>(.*?)</a>',
                               cont, _re.S):
            slug = am.group(1)
            body = am.group(2)
            text = _re.sub(r"<[^>]+>", " ", body)
            text = _re.sub(r"\s+", " ", text).strip()
            en_name = _slug_to_en_name(slug)
            # 한국명: text 의 첫 한글 토큰들 (영문 시작 전까지)
            ko_m = _re.match(r"^([가-힣 ]+?)\s+[A-Za-z]", text)
            name_ko = ko_m.group(1).strip() if ko_m else ""
            # CP: "CP: 2,155 - 2,249"
            cp_m = _re.search(r"CP:\s*([\d,]+)\s*-\s*([\d,]+)", text)
            cp_min = int(cp_m.group(1).replace(",", "")) if cp_m else None
            cp_max = int(cp_m.group(2).replace(",", "")) if cp_m else None
            # 타입: 한글 타입 단어
            types = []
            for ko, en in _TYPE_KO_TO_EN.items():
                if _re.search(rf"(?<![가-힣]){ko}(?![가-힣])", text):
                    types.append({"name": en})
            # 색이 다른 가능 여부
            shiny = "색이 다른" in text
            # 기간: "5/13(수) 10:00 ~ 5/20(수) 10:00"
            period_m = _re.search(r"(\d+/\d+\([가-힣]\)[^~]+~[^<]+?\d+:\d+)", text)
            period = period_m.group(1).strip() if period_m else ""
            results.append({
                "name": en_name,
                "tier": tier,
                "types": types,
                "canBeShiny": shiny,
                "combatPower": {
                    "normal": {"min": cp_min, "max": cp_max} if cp_min else {}
                },
                "_source": "pogomate",
                "_name_ko": name_ko,
                "_period": period,
                "_slug": slug,
            })
    return results


_PGOAPI_LEVEL_TO_TIER = {
    "mega": "Mega Raids",
    "lvl5": "5-Star Raids", "lvl3": "3-Star Raids", "lvl1": "1-Star Raids",
    "shadow_lvl5": "5-Star Shadow Raids",
    "shadow_lvl3": "3-Star Shadow Raids",
    "shadow_lvl1": "1-Star Shadow Raids",
}


def _parse_pokemongoapi_raids(data):
    """pokemon-go-api raidboss.json → pogomate/ScrapedDuck 호환 레이드 리스트.
    글로벌 기준이지만 안정적 JSON + 한글명 내장이라 pogomate 폴백으로 사용."""
    cur = data.get("currentList", {}) if isinstance(data, dict) else {}
    results = []
    for level_key, bosses in cur.items():
        tier = _PGOAPI_LEVEL_TO_TIER.get(level_key, level_key)
        for b in bosses or []:
            names = b.get("names", {}) or {}
            cp = b.get("cpRange") or [None, None]
            cp_min = cp[0] if len(cp) > 0 else None
            cp_max = cp[1] if len(cp) > 1 else None
            results.append({
                "name": names.get("English", b.get("id", "")),
                "tier": tier,
                # ScrapedDuck/pogomate 와 동일하게 소문자 타입 name
                "types": [{"name": str(t).lower()} for t in (b.get("types") or [])],
                "canBeShiny": bool(b.get("shiny")),
                "combatPower": {
                    "normal": {"min": cp_min, "max": cp_max} if cp_min else {}
                },
                "_source": "pokemon-go-api",
                "_name_ko": names.get("Korean", ""),
                "_period": "",
                "_slug": (b.get("form") or b.get("id") or "").lower(),
            })
    return results


def _kr_raids_downloader(dest):
    """한국 레이드 보스 다운로드 → kr_raids.json 저장.
    1차: pogomate.com/raids 스크래핑. 실패하거나 빈 결과면
    2차: pokemon-go-api raidboss.json (안정적 JSON 폴백)."""
    parsed = []
    try:
        req = urllib.request.Request(
            POGOMATE_RAIDS_URL,
            headers={"User-Agent": "Mozilla/5.0 (pogo_iv.py)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        parsed = _parse_pogomate_raids_html(html)
    except Exception as e:
        print(f"pogomate 레이드 스크래핑 실패 — pokemon-go-api 폴백: {e}")

    if not parsed:
        # 폴백: 안정적 JSON 소스. 여기서도 실패하면 예외 → 기존 캐시 유지.
        req = urllib.request.Request(
            POKEMONGOAPI_RAIDS_URL,
            headers={"User-Agent": "Mozilla/5.0 (pogo_iv.py)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        parsed = _parse_pokemongoapi_raids(data)

    _atomic_write_json(dest, parsed)


def load_kr_raids(force=False):
    """한국 활성 레이드 보스 (pogomate.com 스크래핑, 1일 캐싱).
    실패 시 빈 리스트 반환 (best-effort)."""
    _ensure_file(CACHE_KR_RAIDS, _kr_raids_downloader,
                 "한국 레이드 보스", 1, force)
    if not os.path.exists(CACHE_KR_RAIDS):
        return []
    try:
        with open(CACHE_KR_RAIDS, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"kr_raids.json 파싱 실패: {e}")
        return []


def _team_meta_cache_path(cup_id, cap):
    return os.path.join(SCRIPT_DIR, f"team_meta-{cup_id}-{cap}.json")


def load_team_meta(cup_id, cap, force=False):
    """PvPoke training/teams/{cup}/{cap}.json — 메타 팀 슬롯 8개.
    각 슬롯: {slot, synergies, weight, pokemon: [{speciesId, fastMove, chargedMoves, weight}]}.
    """
    path = _team_meta_cache_path(cup_id, cap)
    url = TEAM_META_URL_TEMPLATE.format(cup_id=cup_id, cap=cap)
    _ensure_file(path, lambda p: _download(url, p),
                 f"메타 팀·{cup_id}·{cap}", DATA_MAX_AGE_DAYS, force)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"team_meta 파싱 실패: {e}")
        return []


def load_combined_raids(force=False):
    """LeekDuck(글로벌) + pogomate(한국) 합본.
    중복(영문명+티어 같음)은 한 행에서 출처만 'global+kr'로 표기.
    한국 전용은 _korea_only=True, 글로벌 전용은 _global_only=True 마크.
    """
    g = load_raid_bosses(force=force) or []
    k = load_kr_raids(force=force) or []
    # 키: 영문 종 이름만 (티어는 글로벌/한국이 다를 수 있음)
    def _key(b):
        return b.get("name", "")
    g_keys = {_key(b) for b in g}
    k_keys = {_key(b) for b in k}
    merged = []
    for b in g:
        b2 = dict(b)
        if _key(b) in k_keys:
            b2["_source"] = "global+kr"
        else:
            b2["_source"] = "global"
            b2["_global_only"] = True
        merged.append(b2)
    for b in k:
        if _key(b) not in g_keys:
            b2 = dict(b)
            b2["_source"] = "kr"
            b2["_korea_only"] = True
            merged.append(b2)
    return merged


def download_all_data():
    """모든 데이터 파일을 디스크로 강제 재다운로드. 전역 메모리 상태는 건드리지 않음.
    (백그라운드 워커 스레드 안전용 — init_leagues/전역 dict 재구성은 메인 스레드 책임.)
    """
    gm = load_gamemaster(force=True)
    load_korean_dex_map(force=True)
    load_move_ko_map(force=True)
    load_raid_bosses(force=True)
    load_kr_raids(force=True)
    load_events(force=True)
    load_eggs(force=True)
    load_research(force=True)
    load_rocket_lineups(force=True)
    # 리그 랭킹 — gm 에서 리그 목록을 로컬 계산 (전역 LEAGUES 미변경)
    for lg in compute_leagues(gm):
        try:
            load_league_rankings(lg.cup_id, lg.cap, force=True)
        except Exception as e:
            print(f"랭킹 다운로드 실패 {lg.name}: {e}")


def refresh_all_data():
    """모든 시즌별 데이터 강제 재다운로드. gm 갱신 후 LEAGUES 재구성. (메인 스레드 전용)"""
    gm = load_gamemaster(force=True)
    init_leagues(gm)
    load_korean_dex_map(force=True)
    load_move_ko_map(force=True)
    load_raid_bosses(force=True)
    load_kr_raids(force=True)
    load_events(force=True)
    load_eggs(force=True)
    load_research(force=True)
    load_rocket_lineups(force=True)
    for lg in LEAGUES:
        load_league_rankings(lg.cup_id, lg.cap, force=True)


def data_status():
    """[(label, path, age_days), ...] — 각 데이터 파일 현황."""
    items = [("게임마스터", CACHE_GM), ("한글 이름", CACHE_KO),
             ("한글 이름(보강)", CACHE_PGOAPI_DEX),
             ("기술 슬러그", CACHE_MOVES), ("기술 한글", CACHE_MOVE_NAMES),
             ("레이드(글로벌)", CACHE_RAIDS), ("레이드(한국)", CACHE_KR_RAIDS),
             ("이벤트", CACHE_EVENTS),
             ("알 부화", CACHE_EGGS), ("리서치", CACHE_RESEARCH),
             ("로켓 라인업", CACHE_ROCKETS)]
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


def _atomic_write_json(path, obj):
    """tmp 파일에 쓰고 os.replace 로 교체 — 쓰는 도중 종료/크래시 시
    기존 파일이 잘려 통째로 손실되는 것을 막는다."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_favorites(species_set):
    try:
        _atomic_write_json(FAVORITES_PATH, {"species": sorted(species_set)})
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
        _atomic_write_json(SETTINGS_PATH, settings)
    except Exception as e:
        print(f"설정 저장 실패: {e}")


# 매일/주간 챙겨야 할 루틴 (포고 일일 루틴 — dcinside 정보글 기반)
# (key, 라벨, 한 줄 설명)
DAILY_ROUTINE = [
    ("raid_pass",  "무료 레이드 패스 1장 사용",   "체육관 회전판으로 매일 1장 — 전설 레이드에 쓰면 가성비 최고"),
    ("research",   "필드 리서치 과제 받기·완료",  "포켓스탑 돌려 과제 수령, 도장 7개 모으면 리서치 돌파(주간)"),
    ("gifts",      "친구 선물 보내기·열기",        "베프 유지 + 1일 1회 반짝교환(확반) 확정 가능 — 가성비 최고 컨텐츠"),
    ("buddy",      "버디 하트 채우기",            "산책·먹이·사진 등으로 하트, 메가/베스트버디 진행"),
    ("gym",        "체육관 점령(8시간 20분+)",     "하루 포켓코인 상한 50개 — 아침에 미리 점령해두기"),
    ("particles",  "맥스 파티클 수집(파워스팟)",   "일일 상한 800, 맥스배틀용 — 한도 차기 전에 소비"),
    ("incense",    "데일리 어드벤처 인센스",       "매일 무료 향로, 희귀·지역 포켓몬 조우(가끔 갈라르 새 등)"),
    ("route",      "루트 걷기",                   "기술머신 노말·지가르데 셀 획득"),
]

WEEKLY_ROUTINE = [
    ("adv_sync",     "주간 모험싱크 보상",        "5/25/50km 누적 — 사탕·별의모래·기술머신"),
    ("breakthrough", "리서치 돌파(도장 7개)",      "주 1회 전설/유용한 보상 — 도장 매일 1개씩 쌓기"),
    ("spotlight",    "스포트라이트 아워(화 18시)", "특정 종 대량 등장 + 사탕/경험치 보너스 — 사탕벌이 찬스"),
]


# ── 다이맥스/거다이맥스 배틀 티어 (참고용) ──
# 맥스배틀은 일반 레이드와 역학이 달라(맥스무브 레벨·역할 분담) 별도 큐레이션.
# 출처: GO Hub / doctorpokegogo 2026 가이드. 메타 변동 시 이 표만 갱신하면 됨.
MAXBATTLE_UPDATED = "2026-07"
# (타입, 추천 어택커, 맥스무브)
MAXBATTLE_ATTACKERS_BY_TYPE = [
    ("노말",   "거다이맥스 잠만보",   "G-Max 리플레니쉬"),
    ("불꽃",   "거다이맥스 에이스번", "G-Max 파이어볼"),
    ("물",     "거다이맥스 인텔리온", "G-Max 하이드로스나이프"),
    ("전기",   "거다이맥스 스트린더", "G-Max 스턴쇼크"),
    ("풀",     "거다이맥스 고릴타",   "G-Max 드럼솔로"),
    ("얼음",   "글레이시아",          "맥스 헤일스톰"),
    ("격투",   "거다이맥스 괴력몬",   "G-Max 치스트라이크"),
    ("독",     "거다이맥스 더스트나", "G-Max 말로더"),
    ("땅",     "두더류",              "맥스 퀘이크"),
    ("비행",   "파이어",              "맥스 에어스트림"),
    ("에스퍼", "후딘",                "맥스 마인드스톰"),
    ("벌레",   "거다이맥스 버터플",   "G-Max 비퍼들"),
    ("바위",   "기가이아스",          "맥스 록폴"),
    ("고스트", "거다이맥스 팬텀",     "G-Max 테러"),
    ("드래곤", "무한다이노",          "맥스 웜윈드"),
    ("악",     "거다이맥스 오롱털",   "G-Max 스누즈"),
    ("강철",   "자시안(검의 왕)",     "맥스 스틸스파이크"),
    ("페어리", "가디안 / 마휘핑",     "맥스 스타폴"),
]
# 최우선 S급 어택커 (보스가 약점이면 거다이맥스가 항상 최우선)
MAXBATTLE_S_ATTACKERS = [
    "거다이맥스 인텔리온", "거다이맥스 팬텀", "거다이맥스 킹크랩",
    "거다이맥스 고릴타", "거다이맥스 에이스번", "거다이맥스 괴력몬",
    "자시안(검의 왕)", "무한다이노",
]
# 탱커 (0.5초 평타로 게이지 빠르게 — 변신 빠르고 덜 맞음)
MAXBATTLE_TANKS = [
    ("해피너스",            "들이받기(0.5초)", "게임 내 최대 HP + 가장 빠른 게이지 — 만능 탱커"),
    ("자마젠타(방패의 왕)", "메탈클로(0.5초)", "내구+강철, 시작 시 실드 부여"),
    ("거다이맥스 잠만보",   "핥기(0.5초)",     "막대한 내구 + 팀 회복 유틸(G-Max 리플레니쉬)"),
    ("라티아스",            "용의숨결(0.5초)", "드래곤 보스 상대 무난한 내구"),
    ("메타그로스",          "탄환펀치(0.5초)", "강철 내구 + 범용"),
    ("거다이맥스 라프라스", "어는바람(0.5초)", "물/얼음 내구 탱커"),
    ("아머까오",            "에어슬래시",      "비행/강철 내구 + 자체 실드"),
    ("샤미드",              "물기(0.5초)",     "물 보스 외 무난한 HP 탱커"),
]
# 힐러 (높은 HP로 맥스 스피릿 회복량 극대화)
MAXBATTLE_HEALERS = [
    ("해피너스", "압도적 1순위 — 최대 HP로 회복량/생존 모두 최고"),
    ("럭키",     "해피너스 대용(HP 높음)"),
    ("라프라스", "내구형 힐러 겸 물 어택"),
    ("잠만보",   "높은 HP, 힐+탱 겸용"),
    ("푸크린",   "값싼 HP 힐러 대용"),
]

# ── 출시된 다이맥스/거다이맥스 로스터 (참고 · 2026-07 기준) ──
# 거다이맥스 = 6성 맥스배틀 전용, 고유 G-Max 무브. 다이맥스 = 일반 맥스배틀.
# 데이터에는 없는 큐레이션 목록 — 신규 출시 시 이 두 리스트만 갱신.
# 거다이맥스 17종 (출처: Dexerto/locachange 2026)
MAXBATTLE_GIGANTAMAX = [
    "이상해꽃", "리자몽", "거북왕", "버터플", "피카츄", "나옹", "괴력몬",
    "팬텀", "킹크랩", "라프라스", "잠만보", "더스트나", "고릴타",
    "에이스번", "인텔리레온", "스트린더", "오롱털",
]
# 다이맥스 (일반) — 대규모 순환 풀이라 '확인된 주요 종'만. 게임 내 '다이맥스' 검색으로 보유분 확인 권장.
MAXBATTLE_DYNAMAX = [
    "이상해씨", "파이리", "꼬부기", "부우부", "랄토스", "세꿀버리", "콩둘기",
    "오케이징", "달콤아", "흥나숭", "럭키", "모노두", "깨봉이", "빈티나",
]

# ── 포켓몬샵 박스 효율 — 아이템 코인 기준가 (단품 환산, 참고용) ──
# 세일/지역/시즌에 따라 변동. GUI 에서 편집 가능, 박스 가격 대비 할인율 계산용.
SHOP_ITEM_PRICES = [
    ("프리미엄 배틀패스", 100),
    ("원격 레이드 패스",  100),
    ("행운의 알",         80),
    ("별의 조각",         80),
    ("향로",              80),
    ("일반 부화장치",     150),
    ("슈퍼 부화장치",     200),
    ("로켓 레이더",       200),
]


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

# 로켓단 조무래기 배틀 전 대사 → 타입 매핑 (한국 PoGO 공식 대사)
# 출처: namu.wiki / poketory.com 교차 검증
# 키워드 substring 매치로 타입 추정 (구두점/띄어쓰기 무관). 매칭 우선순위는 정의 순서.
# 각 타입마다 (1) 핵심 어구 + (2) 짧은 단일 단어 키워드를 추가해 약식 입력도 매칭되게 함.
GRUNT_PHRASES = [
    # (키워드, 타입 code, 대표 대사)
    # 핵심 어구 (긴 매칭 — 우선)
    ("노말이 약하다",   "normal",   "노말이 약하다고 생각해?"),
    ("단단한 몸",       "fighting", "이 단단한 몸은 장식이 아니야!"),
    ("새포켓몬",        "flying",   "내 새포켓몬이 배틀을 원한다! (남)"),
    ("화려하게 날아",   "flying",   "내 포켓몬이 화려하게 날아오른다! (여)"),
    ("독으로 공격",     "poison",   "독으로 공격할 준비 완료!"),
    ("땅에 때려",       "ground",   "땅에 때려눕혀 주지!"),
    ("락앤롤",          "rock",     "렛츠 락앤롤!"),
    ("벌레 포켓몬",     "bug",      "가랏! 내 벌레 포켓몬!"),
    ("흐... 흐",        "ghost",    "흐... 흐... 흐... 흐... 흐흣!"),
    ("흐흐",            "ghost",    "흐... 흐... 흐... 흐... 흐흣!"),
    ("철벽",            "steel",    "철벽 공격이다!"),
    ("불의 온도",       "fire",     "포켓몬이 뱉어내는 불의 온도가 몇 도인지 알아?"),
    ("바다는 위험",     "water",    "이 바다는 위험해!"),
    ("바다",            "water",    "이 바다는 위험해!"),
    ("우릴 상관",       "grass",    "우릴 상관 마!"),
    ("짜릿",            "electric", "짜릿하게 만들어주지!"),
    ("에스퍼",          "psychic",  "보이지 않는 힘을 쓰는 에스퍼를 무섭다고 생각해?"),
    ("얼려",            "ice",      "널 얼려버리겠다!"),
    ("크아",            "dragon",   "크아아아아! 무섭지!"),
    ("그늘",            "dark",     "빛이 있으면 그늘이 있는 법."),
    ("귀여운 포켓몬",   "fairy",    "내 귀여운 포켓몬 어때!"),
    ("귀여운",          "fairy",    "내 귀여운 포켓몬 어때!"),
]

# 특수(decoy) 조무래기 — 단일 타입으로 매핑 안 됨, 멀티 타입 팀 (잠만보 등)
GRUNT_PHRASES_SPECIAL = [
    "어디 이겨볼까", "각오해", "승자만이 승리", "이미 이겼어",
]


def find_grunt_type(phrase):
    """조무래기 대사 → ('type_code', '대표 대사') 또는 ('special', None) 또는 (None, None)."""
    if not phrase:
        return (None, None)
    norm = phrase.strip().lower().replace(" ", "")
    for kw, code, rep in GRUNT_PHRASES:
        if kw.lower().replace(" ", "") in norm:
            return (code, rep)
    for kw in GRUNT_PHRASES_SPECIAL:
        if kw.lower().replace(" ", "") in norm:
            return ("special", None)
    return (None, None)


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
                    attacker_level=50, boss_base_atk=None,
                    boss_fast=None, boss_charged=None):
    """공격자 1마리 × (속공, 차지) 조합 → DPS / TDO / eDPS.
    attacker: PvPoke pokemon 엔트리. fast/charged: gamemaster moves 엔트리.
    boss_types: 보스 타입 list (소문자, 'none' 허용).
    weather: 날씨 string (부스트 계산), None 이면 부스트 없음.
    boss_fast/boss_charged: 보스의 대표 무브셋(moves 엔트리). 주어지면 보스가
        공격자에게 입히는 피해를 실제 기술 + 타입 상성으로 계산해 TDO 정확도를
        높인다 (boss_best_moveset 으로 미리 구함). 없으면 base_atk 휴리스틱 폴백.
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
    # 보스가 1초당 공격자에게 입히는 피해(incoming DPS) → 생존시간 → TDO.
    if boss_fast and boss_charged and boss_base_atk:
        # 정확 모드: 보스 실제 무브셋으로 데미지 계산. 보스는 레이드 표준대로
        # IV 가산 없이 base_atk × tier CPM. 공격자 타입(atk_types)에 대한 상성·
        # 보스 STAB·날씨 부스트까지 반영 → 보스 기술에 약점/내성인 카운터를 구분.
        boss_atk_eff = boss_base_atk * boss_cpm
        bf_dmg = _move_damage(boss_fast.get("power", 0), boss_atk_eff, def_eff,
                              boss_fast.get("type", ""), boss_types, atk_types,
                              boss_fast.get("type", "") in boosted_types)
        bc_dmg = _move_damage(boss_charged.get("power", 0), boss_atk_eff, def_eff,
                              boss_charged.get("type", ""), boss_types, atk_types,
                              boss_charged.get("type", "") in boosted_types)
        incoming_dps = max(1.0, _combo_dps(
            bf_dmg, boss_fast.get("cooldown", 1000) / 1000.0,
            boss_fast.get("energyGain", 0),
            bc_dmg, boss_charged.get("cooldown", 500) / 1000.0,
            boss_charged.get("energy", 0)))
    else:
        # 폴백: 보스 무브셋 정보 없을 때 base_atk × 상수 휴리스틱.
        boss_atk = boss_base_atk if boss_base_atk else boss_base_def * 1.5
        incoming_dps = max(1.0, boss_atk * boss_cpm / def_eff * 35.0)
    survival_s = hp / incoming_dps
    tdo = dps * survival_s
    edps = (dps * tdo) ** 0.5 if tdo > 0 else 0.0
    return {"dps": dps, "tdo": tdo, "edps": edps,
            "fast_dmg": fast_dmg, "charged_dmg": charged_dmg, "hp": hp}


def boss_best_moveset(boss, moves_by_id, boss_cpm, boss_base_atk):
    """보스의 대표 무브셋(중립 방어자 기준 DPS 최고) → (fast_move, charged_move).
    공격자별로 달라지지 않는 '보스가 실제로 쓰는 한 세트'를 고정하기 위해 미리 구한다
    (공격자마다 보스가 약점 커버 기술로 바꿔 쓴다고 가정하면 incoming 이 과대평가됨)."""
    fasts = (boss.get("fastMoves") or []) + (boss.get("eliteMoves") or [])
    chargeds = (boss.get("chargedMoves") or []) + (boss.get("eliteMoves") or [])
    boss_types = [t for t in boss.get("types", []) if t and t != "none"]
    atk_eff = (boss_base_atk or 180) * boss_cpm  # 보스는 IV 가산 없음
    best, best_dps = None, -1.0
    for fid in fasts:
        f = moves_by_id.get(fid)
        if not f or f.get("energyGain", 0) <= 0:
            continue
        f_dmg = _move_damage(f.get("power", 0), atk_eff, 100.0,
                             f.get("type", ""), boss_types, [], False)
        for cid in chargeds:
            c = moves_by_id.get(cid)
            if not c or c.get("energy", 0) <= 0:
                continue
            c_dmg = _move_damage(c.get("power", 0), atk_eff, 100.0,
                                 c.get("type", ""), boss_types, [], False)
            dps = _combo_dps(f_dmg, f.get("cooldown", 1000) / 1000.0,
                             f.get("energyGain", 0),
                             c_dmg, c.get("cooldown", 500) / 1000.0,
                             c.get("energy", 0))
            if dps > best_dps:
                best_dps, best = dps, (f, c)
    return best  # None 이면 호출부에서 휴리스틱 폴백


def best_moveset_vs(attacker, boss_types, moves_by_id, boss_cpm=0.79,
                    boss_base_def=180, weather=None, attacker_level=50,
                    boss_base_atk=None, boss_fast=None, boss_charged=None):
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
                                boss_cpm, boss_base_def, weather, attacker_level,
                                boss_base_atk, boss_fast, boss_charged)
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
    boss_base_atk = boss.get("baseStats", {}).get("atk")  # 실제 공격력 (TDO 정확도)
    boss_sid = boss.get("speciesId", "")
    if force_boss_cpm is not None:
        boss_cpm = force_boss_cpm
    elif "_mega" in boss_sid:
        boss_cpm = RAID_TIER_CPM["mega"]
    else:
        boss_cpm = RAID_TIER_CPM["5"]

    # 보스 대표 무브셋을 한 번만 구해 모든 공격자에 재사용 → TDO 정확 모드.
    bm_pair = boss_best_moveset(boss, moves_by_id, boss_cpm, boss_base_atk)
    boss_fast, boss_charged = bm_pair if bm_pair else (None, None)

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
                             boss_base_def, weather, attacker_level,
                             boss_base_atk, boss_fast, boss_charged)
        if bm is None:
            continue
        results.append({"sid": sid, "pokemon": p, **bm})
    results.sort(key=lambda r: r["edps"], reverse=True)
    return results[:n]


# 범용 PvE 딜러 평가용 가상 5성 보스 근사.
GENERIC_DEF_BASE = 180   # 평균 5성 보스 방어 종족값 근사
GENERIC_DEF_ATK = 200    # incoming DPS 추정용 보스 공격 (TDO 분모)

# 타입별 딜러 랭킹은 "그 타입에 약점인 방어자" 기준으로 평가한다. 그래야 STAB·약점
# 보너스를 받는 진짜 해당 타입 딜러가 상위에 오고, 비STAB 차지만 가진 포켓몬
# (예: 그란돈 + 불대문자)이 과대평가되지 않는다. (normal 은 약점 타입이 없어 중립)
TYPE_WEAK_DEFENDER = {
    "normal": None, "fire": "grass", "water": "rock", "electric": "water",
    "grass": "water", "ice": "dragon", "fighting": "normal", "poison": "grass",
    "ground": "rock", "flying": "grass", "psychic": "fighting", "bug": "psychic",
    "rock": "flying", "ghost": "psychic", "dragon": "dragon", "dark": "psychic",
    "steel": "fairy", "fairy": "dragon",
}


def all_type_attacker_rankings(gm, moves_by_id, attacker_level=40,
                               include_shadow=True, include_mega=True,
                               include_legendary=True):
    """전 포켓몬을 1회 순회하며, 각 공격 타입별 최적 무브셋 eDPS 랭킹을 만든다.
    중립 방어자 기준이라 '이 타입 딜러로 키울 가치' 판단용. (타입별 list, eDPS 내림차순)
    반환: {atype: [{sid, pokemon, edps, dps, tdo, fast_id, charged_id}, ...]}"""
    boss_cpm = RAID_TIER_CPM["5"]
    by_type = {t: [] for t in TYPES_ORDER}
    for p in gm.get("pokemon", []):
        sid = p.get("speciesId", "")
        if p.get("released") is False:
            continue
        if not include_shadow and sid.endswith("_shadow"):
            continue
        if not include_mega and sid.endswith(("_mega", "_mega_x", "_mega_y")):
            continue
        if not include_legendary:
            tags = p.get("tags") or []
            if "legendary" in tags or "mythical" in tags:
                continue
        fasts = (p.get("fastMoves") or []) + (p.get("eliteMoves") or [])
        chargeds = (p.get("chargedMoves") or []) + (p.get("eliteMoves") or [])
        # 차지 무브 타입별 최적 무브셋 (주력 데미지 = 차지 타입으로 분류)
        best_by_ctype = {}
        for fid in fasts:
            f = moves_by_id.get(fid)
            if not f or f.get("energyGain", 0) <= 0:
                continue
            for cid in chargeds:
                c = moves_by_id.get(cid)
                if not c or c.get("energy", 0) <= 0:
                    continue
                ct = c.get("type")
                if ct not in by_type:
                    continue
                weak = TYPE_WEAK_DEFENDER.get(ct)
                def_types = [weak] if weak else []
                r = attacker_dps_vs(p, f, c, def_types, boss_cpm, GENERIC_DEF_BASE,
                                    None, attacker_level, GENERIC_DEF_ATK)
                prev = best_by_ctype.get(ct)
                if prev is None or r["edps"] > prev["edps"]:
                    best_by_ctype[ct] = {**r, "fast_id": fid, "charged_id": cid}
        for ct, rec in best_by_ctype.items():
            by_type[ct].append({"sid": sid, "pokemon": p, **rec})
    # 범용 딜러 가치는 DPS 우선 (eDPS 는 내구가 과대 반영돼 그란돈류 비전문 탱키가
    # 상위로 올라옴). '뭘 키울까'는 화력 기준이 직관적이라 DPS 로 정렬.
    for t in by_type:
        by_type[t].sort(key=lambda r: r["dps"], reverse=True)
    return by_type


def best_attackers_for_type(gm, moves_by_id, atype, n=20, attacker_level=40,
                            include_shadow=True, include_mega=True,
                            include_legendary=True):
    """특정 공격 타입의 범용 PvE 딜러 TOP N (= '뭘 키워야 하나' 가이드)."""
    rankings = all_type_attacker_rankings(gm, moves_by_id, attacker_level,
                                          include_shadow, include_mega,
                                          include_legendary)
    return rankings.get(atype, [])[:n]


def investment_priority(gm, moves_by_id, favorites, attacker_level=40,
                        include_shadow=True, include_mega=True, rankings=None):
    """즐겨찾기(보유 가정) 포켓몬을 PvE 투자 가치 순으로 정렬.
    각 포켓몬의 '최고 가치 역할'(DPS 최고 타입) + 그 타입 범용 랭킹 내 순위/백분위를
    매겨, 상위권일수록 투자 우선. 반환 list 는 우선순위 내림차순.
    rankings: all_type_attacker_rankings 결과를 미리 넘기면 재계산 생략."""
    if rankings is None:
        rankings = all_type_attacker_rankings(gm, moves_by_id, attacker_level,
                                              include_shadow, include_mega, True)
    locate = {}  # sid -> [{type, rank, total, edps, fast_id, charged_id}, ...]
    for atype, lst in rankings.items():
        total = len(lst)
        for i, r in enumerate(lst):
            locate.setdefault(r["sid"], []).append({
                "type": atype, "rank": i + 1, "total": total,
                "dps": r["dps"], "edps": r["edps"], "fast_id": r["fast_id"],
                "charged_id": r["charged_id"]})
    out = []
    for sid in favorites:
        recs = locate.get(sid)
        if not recs:
            continue
        best = max(recs, key=lambda x: x["dps"])  # 최고 가치 역할 (화력 기준)
        out.append({"sid": sid, **best,
                    "percentile": best["rank"] / max(1, best["total"]) * 100})
    out.sort(key=lambda x: x["rank"] / max(1, x["total"]))
    return out


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

    PvPoke gamemaster 에 일부 종(gastrodon, silvally 등) 은 family.parent 가
    누락되어 있어, 모든 종의 family.evolutions 를 역인덱스해 만든
    evo_to_parent 맵을 fallback 으로 사용한다.
    """
    by_sid = {p.get("speciesId"): p for p in gm["pokemon"]}

    # 역방향 인덱스: evolved_sid → parent_sid (family.parent 누락 보정용)
    evo_to_parent: dict = {}
    for q in gm["pokemon"]:
        qfam = q.get("family") or {}
        for evo in qfam.get("evolutions", []) or []:
            evo_to_parent.setdefault(evo, q.get("speciesId"))

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
        # family 가 통째로 None 이지만 다른 종의 evolutions 에 등록된 경우
        # (예: gastrodon, silvally) — 진화 체인 일원으로 간주
        if not fam and species_id in evo_to_parent:
            fam = {"parent": evo_to_parent[species_id]}
        if not fam:
            return []

    # Walk back to root.
    # PvPoke gamemaster 일부 항목은 family.parent 가 실제 부모와 다른 종을 가리킴
    # (예: carkol.parent=boltund, raticate.parent=rattata_alolan, mothim.parent=burmy_trash
    # 인데 사용자가 burmy_plant 에서 들어와도 trash 로 우회). 양방향 검증으로 보정한다 —
    # parent 의 evolutions 에 내가 포함되어 있을 때만 신뢰, 아니면 evo_to_parent fallback.
    root = species_id
    visited = {root}
    while True:
        pr = by_sid.get(root, {}).get("family") or {}
        claimed = pr.get("parent")
        # 검증: claimed.evolutions 가 root 를 포함하는가?
        if claimed:
            par_fam = by_sid.get(claimed, {}).get("family") or {}
            if root not in (par_fam.get("evolutions") or []):
                claimed = None  # 비대칭 → 신뢰 안 함
        parent = claimed or evo_to_parent.get(root)
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


def find_acquisition_for_sid(target_sid, gm, eggs, raids_combined,
                              rocket_lineups, research, sid_to_display):
    """target_sid 의 진화 사슬을 따라 현재 일정상 입수 가능한 경로를 찾는다.

    eggs / raids_combined / rocket_lineups / research 는 ScrapedDuck 캐시 포맷.
    raids_combined 는 load_combined_raids() 의 글로벌+한국 합본.

    사전 진화 단계까지 포함해 검색 — 가령 라프라스를 진화시켜 만드는 ㄴ오라를
    골랐을 때 "사전 진화 라프라스가 10km 알에 있음" 이 함께 표시된다.

    반환: 사람이 읽는 텍스트(여러 줄 가능). 어디서도 안 잡히면 안내 문구.
    """
    # 영문 이름 → speciesId. find_boss_pokemon 가 메가/그림자/지역폼 처리.
    def _to_sid(en_name):
        p = find_boss_pokemon(en_name, gm) if en_name else None
        return p.get("speciesId") if p else None

    stages = get_family_chain(gm, target_sid)
    target_stage_idx = -1
    for i, stage in enumerate(stages):
        if target_sid in stage:
            target_stage_idx = i
            break

    if target_stage_idx < 0:
        relevant = {target_sid: 0}
        target_stage_idx = 0
    else:
        relevant = {}
        for i in range(target_stage_idx + 1):
            for s in stages[i]:
                relevant[s] = i

    by_sid: dict = {}  # sid -> [(icon, detail), ...]
    def _add(sid, icon, detail):
        by_sid.setdefault(sid, []).append((icon, detail))

    # 알
    for e in eggs or []:
        sid = _to_sid(e.get("name", ""))
        if sid not in relevant:
            continue
        flags = []
        if e.get("isAdventureSync"): flags.append("어드벤처싱크")
        if e.get("canBeShiny"): flags.append("✨")
        if e.get("isRegional"): flags.append("지역한정")
        suffix = f" ({' · '.join(flags)})" if flags else ""
        _add(sid, "🥚", f"{e.get('eggType', '?')}{suffix}")

    # 레이드 (글로벌+한국 합본)
    raid_seen = set()
    tier_short_map = [
        ("5-Star", "5★"), ("Mega", "메가"), ("Shadow", "그림자"),
        ("Elite", "엘리트"), ("3-Star", "3★"), ("1-Star", "1★"),
    ]
    for r in raids_combined or []:
        sid = _to_sid(r.get("name", ""))
        if sid not in relevant:
            continue
        tier_raw = r.get("tier", "") or ""
        tier_short = tier_raw
        for k, v in tier_short_map:
            if k in tier_raw:
                tier_short = v
                break
        if (sid, tier_short) in raid_seen:
            continue
        raid_seen.add((sid, tier_short))
        cp = r.get("combatPower", {}) or {}
        normal = cp.get("normal", {}) if "normal" in cp else cp
        cp_str = ""
        if isinstance(normal, dict) and normal.get("min") and normal.get("max"):
            cp_str = f" CP{normal['min']}~{normal['max']}"
        src = r.get("_source", "")
        src_tag = " 🇰🇷" if src == "kr" else ""
        _add(sid, "⚔", f"{tier_short} 레이드{cp_str}{src_tag}")

    # 필드 리서치
    research_tasks: dict = {}
    for task in research or []:
        text = task.get("text", "")
        for reward in task.get("rewards", []) or []:
            sid = _to_sid(reward.get("name", ""))
            if sid not in relevant:
                continue
            research_tasks.setdefault(sid, []).append(translate_research_task(text))
    for sid, tasks in research_tasks.items():
        uniq = list(dict.fromkeys(tasks))
        sample = " / ".join(uniq[:2])
        extra = f" 외 {len(uniq) - 2}건" if len(uniq) > 2 else ""
        _add(sid, "📋", f"리서치: {sample}{extra}")

    # 로켓 라인업 (isEncounter=True 슬롯만 = 실제 포획 가능)
    leader_ko = {"Cliff": "클리프", "Sierra": "시에라", "Arlo": "알로"}
    rocket_labels: dict = {}
    for entry in rocket_lineups or []:
        role_en = entry.get("title", "")
        npc_name = entry.get("name", "")
        for slot_key in ("firstPokemon", "secondPokemon", "thirdPokemon"):
            for p in entry.get(slot_key, []) or []:
                if not p.get("isEncounter"):
                    continue
                sid = _to_sid(p.get("name", ""))
                if sid not in relevant:
                    continue
                if role_en == "Team GO Rocket Boss":
                    label = "지오반시"
                elif role_en == "Team GO Rocket Leader":
                    label = f"{leader_ko.get(npc_name, npc_name)}(간부)"
                else:
                    t = (entry.get("type") or "").lower()
                    if t and t in _RESEARCH_TYPE_KO:
                        label = f"{_RESEARCH_TYPE_KO[t]} 따까리"
                    else:
                        label = "따까리"
                rocket_labels.setdefault(sid, set()).add(label)
    for sid, labels in rocket_labels.items():
        _add(sid, "🤖", f"로켓: {', '.join(sorted(labels))}")

    if not by_sid:
        return "(현재 일정상 입수 경로 없음 — 야생 출현 / 둥지 / 진화로만 획득 가능)"

    # target 자신 먼저, 사전 진화체는 별도 줄
    lines = []
    if target_sid in by_sid:
        items = by_sid.pop(target_sid)
        lines.append(" · ".join(f"{i} {d}" for i, d in items))
    for sid, items in by_sid.items():
        diff = target_stage_idx - relevant.get(sid, 0)
        disp = sid_to_display.get(sid, sid)
        if diff <= 1:
            prefix = f"(사전 진화 {disp}) "
        else:
            prefix = f"(사전 진화 {disp}, {diff}단계 전) "
        body = " · ".join(f"{i} {d}" for i, d in items)
        lines.append(prefix + body)
    return "\n".join(lines)


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


def appraisal_label(ivs):
    """포켓몬 GO 어필 화면 등급. (별 4단계 + 어필러/100% 마크)"""
    a, d, h = ivs
    total = a + d + h
    if total >= 37:   stars = 4
    elif total >= 30: stars = 3
    elif total >= 23: stars = 2
    else:             stars = 1
    star_str = "★" * stars + "☆" * (4 - stars)
    label = f"{star_str} 합 {total}/45"
    if total == 45:
        label += " · 100% Hundo"
    elif all(v >= 13 for v in ivs):
        label += " · 어필러"
    elif all(v >= 12 for v in ivs):
        label += " · 준어필러"
    return label


# 거래(Trading) 시 친구 등급별 IV 최소값 (모든 IV 가 [floor, 15] 범위에서 균등 랜덤)
# PvPoke training/teams 의 slot / synergies 영문 → 한글 매핑
TM_LABEL_KO = {
    # 타입 (PvPoke 표기는 첫글자 대문자)
    "Normal": "노말", "Fire": "불꽃", "Water": "물", "Electric": "전기",
    "Grass": "풀", "Ice": "얼음", "Fighting": "격투", "Poison": "독",
    "Ground": "땅", "Flying": "비행", "Psychic": "에스퍼", "Bug": "벌레",
    "Rock": "바위", "Ghost": "고스트", "Dragon": "드래곤", "Dark": "악",
    "Steel": "강철", "Fairy": "페어리",
    # 역할 키워드
    "Tank": "탱커", "Flex": "자유 슬롯",
    "Charm": "차밍 페어리", "Mudboi": "땅 어태커",
    # 자주 등장하는 포켓몬 이름 (슬롯 단위 메타)
    "Azumarill": "마릴리", "Giratina": "기라티나",
    "Dialga": "디아루가", "Registeel": "레지스틸",
    "Medicham": "요가램", "Skarmory": "강철톤",
    "Trevenant": "달뜨기", "Lickitung": "내룸벨트",
    "Sableye": "안주",
}


def tm_label_ko(s):
    """팀 메타 slot/synergy 한 토큰 → 한글. Anti-X 패턴도 처리."""
    if not s:
        return s
    if s.startswith("Anti-"):
        rest = s[5:]
        return f"대 {TM_LABEL_KO.get(rest, rest)}"
    return TM_LABEL_KO.get(s, s)


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
        # 사용자 입력 레벨이 범위를 벗어나도 안전하게 클램프 (음수 idx → 잘못된 결과 방지)
        lo = max(0, min(lo, max_idx))
        hi = max(lo, min(hi, max_idx))
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
    print("\n" + iv_impact_note())


def _find_league(name):
    """리그명(부분 일치 허용) → League 객체 (없으면 None)."""
    nl = name.strip().replace(" ", "").lower()
    if not nl:
        return None
    for lg in LEAGUES:
        if lg.name.replace(" ", "").lower() == nl:
            return lg
    for lg in LEAGUES:
        if nl in lg.name.replace(" ", "").lower():
            return lg
    return None


def report_best_ivs_per_league(gm, ko_base_map, sid_to_display, name, max_level):
    """개체값 입력 없이 — 각 리그에서 '제일 좋은 개체값(랭크 #1)'을 보여준다."""
    p, alts = find_pokemon_cli(gm, ko_base_map, name)
    if not p:
        print(f"'{name}' — 찾을 수 없음. 예: 마릴리, 메가 갸라도스, 그림자 뮤츠")
        return
    if alts:
        print(f"[다른 후보: {', '.join(alts)}]")
    base = p["baseStats"]
    sid = p["speciesId"]
    disp = sid_to_display.get(sid, p.get("speciesName", sid))
    max_idx = min(int(round((max_level - 1.0) * 2)), len(CPM) - 1)
    print(f"\n=== {disp} ({sid}) — 리그별 최고 개체값 ===")
    print(f"종족값: Atk {base['atk']} / Def {base['def']} / HP {base['hp']}\n")
    headers = ["리그", "베스트 IV(공/방/체)", "레벨", "CP", "스탯곱(SP)"]
    table = [headers]
    for lg in LEAGUES:
        ranked = rank_all(base, lg.cap, max_idx)
        if not ranked or ranked[0][1] == 0:
            table.append([lg.name, "—", "—", "—", "—"])
            continue
        iv, sp, lvl_idx, cp = ranked[0]
        table.append([lg.name, f"{iv[0]}/{iv[1]}/{iv[2]}",
                      f"Lv{level_from_idx(lvl_idx):g}", str(cp), f"{sp:,.0f}"])
    widths = [max(_dwidth(row[i]) for row in table) for i in range(len(headers))]
    for i, row in enumerate(table):
        print("  ".join(_pad(c, w) for c, w in zip(row, widths)))
        if i == 0:
            print("  ".join("-" * w for w in widths))
    print("\n특정 리그의 상위 개체값 목록을 보려면 개체값 대신 리그명을 입력하세요 "
          "(예: 슈퍼리그). 단발 실행은 --league 슈퍼리그 [--top 20]")
    print("\n" + iv_impact_note())


def report_top_ivs_for_league(gm, ko_base_map, sid_to_display, name, lg,
                              max_level, topn=10):
    """특정 리그에서 상위 N개 개체값(순위표)을 보여준다."""
    p, alts = find_pokemon_cli(gm, ko_base_map, name)
    if not p:
        print(f"'{name}' — 찾을 수 없음.")
        return
    if alts:
        print(f"[다른 후보: {', '.join(alts)}]")
    base = p["baseStats"]
    sid = p["speciesId"]
    disp = sid_to_display.get(sid, p.get("speciesName", sid))
    max_idx = min(int(round((max_level - 1.0) * 2)), len(CPM) - 1)
    ranked = rank_all(base, lg.cap, max_idx)
    if not ranked or ranked[0][1] == 0:
        print(f"{disp} — {lg.name}에서 유효한 개체값 없음 (CP 상한 미달).")
        return
    top_sp = ranked[0][1]
    print(f"\n=== {disp} ({sid}) — {lg.name} 상위 {topn} 개체값 ===")
    print(f"종족값: Atk {base['atk']} / Def {base['def']} / HP {base['hp']}\n")
    headers = ["순위", "공/방/체", "레벨", "CP", "스탯곱(SP)", "베스트대비"]
    table = [headers]
    for rk, (iv, sp, lvl_idx, cp) in enumerate(ranked[:topn], 1):
        if sp == 0:
            continue
        table.append([f"#{rk}", f"{iv[0]}/{iv[1]}/{iv[2]}",
                      f"Lv{level_from_idx(lvl_idx):g}", str(cp), f"{sp:,.0f}",
                      f"{sp / top_sp * 100:.2f}%"])
    widths = [max(_dwidth(row[i]) for row in table) for i in range(len(headers))]
    for i, row in enumerate(table):
        print("  ".join(_pad(c, w) for c, w in zip(row, widths)))
        if i == 0:
            print("  ".join("-" * w for w in widths))
    iv0 = ranked[0][0]
    ex, near = ingame_search_strings(iv0, name=disp)
    print(f"\n🔍 인게임 검색 — 정확: {ex}\n            근사: {near}")


# ── 인게임 검색 문자열 ──
def ingame_search_strings(iv, name=None):
    """베스트 IV (공,방,체) → 인게임 검색 문자열 (정확/근사) 튜플.
    포켓몬 GO 검색 구문: '<범위>공격&<범위>방어&<범위>hp' (범위 예: 0, 14-15)."""
    a, d, h = iv

    def _rng(v, lo_off, hi_off):
        lo = max(0, v - lo_off)
        hi = min(15, v + hi_off)
        return f"{lo}-{hi}" if lo != hi else f"{lo}"

    prefix = (f"{name}&" if name else "")
    exact = f"{prefix}{a}공격&{d}방어&{h}hp"
    # 근사: 공격은 같거나 +1(저공격 선호), 방어/체력은 -1까지 허용 → 베스트 근방
    near = f"{prefix}{_rng(a, 0, 1)}공격&{_rng(d, 1, 0)}방어&{_rng(h, 1, 0)}hp"
    return exact, near


# ── 인게임 검색어 사전 (카테고리 → [(설명, 검색어)]) ──
# 포켓몬 GO 검색창에 그대로 붙여넣어 쓰는 필터. & = 그리고, 쉼표 = 또는, ! = 제외.
# 범위: '3-4' = 3~4, '3-' = 3 이상, '-1' = 1 이하.
SEARCH_LIBRARY = [
    ("개체값 / 어필 등급", [
        ("100% 개체값 (⭐⭐⭐)", "4*"),
        ("82% 이상 (⭐⭐ 이상)", "3-4*"),
        ("3성만 (82~98%)", "3*"),
        ("2성 (66~80%)", "2*"),
        ("1성 (51~64%)", "1*"),
        ("최악 0성 (0~49%)", "0*"),
        ("나쁜 것 (0~1성) — 전송용", "0-1*"),
        ("어중간 이하 (0~2성)", "0-2*"),
    ]),
    ("세부 개체값 (공/방/체)", [
        ("공격 0 (PvP 저공격)", "0공격"),
        ("공격 0~1", "-1공격"),
        ("공격 15 (만렙)", "15공격"),
        ("방어 15", "15방어"),
        ("방어 14~15", "14-방어"),
        ("체력 15", "15hp"),
        ("체력 14~15", "14-hp"),
        ("PvP 최적 근사 (저공격·고방체)", "-1공격&14-방어&14-hp"),
        ("고방체(방·체 13 이상)", "13-방어&13-hp"),
    ]),
    ("상태 / 속성", [
        ("색이 다른 (이로치)", "색이다른"),
        ("교환 가능", "교환가능"),
        ("행운 (럭키)", "행운"),
        ("즐겨찾기 ★", "즐겨찾기"),
        ("그림자", "그림자"),
        ("정화된", "정화"),
        ("진화 가능", "진화"),
        ("코스튬 착용", "코스튬"),
        ("전설", "전설"),
        ("환상", "환상"),
        ("수비 중 (체육관)", "수비중"),
    ]),
    ("배틀 / 레이드 / 맥스", [
        ("다이맥스 가능", "다이맥스"),
        ("거다이맥스 가능", "거다이맥스"),
        ("배틀 사용 가능", "배틀"),
        ("레이드 획득", "레이드"),
        ("리서치 획득", "필드리서치"),
        ("이벤트 획득", "이벤트"),
    ]),
    ("레벨 / 종류", [
        ("레벨 40 이상", "40-"),
        ("레벨 1~30", "1-30"),
        ("메가진화 가능", "메가진화"),
        ("4세대(신오)", "세대4"),
        ("아이템 소지", "아이템"),
    ]),
    ("정리(박사 전송용) 조합", [
        ("약한 것만 (0~2성·즐겨찾기·교환 제외)", "0-2*&!즐겨찾기&!교환가능"),
        ("100%도 즐겨찾기도 아닌 것", "!4*&!즐겨찾기"),
        ("그림자 아닌 저성능", "0-1*&!그림자&!즐겨찾기"),
        ("교환용 골라내기 (색다른·행운 제외)", "교환가능&!색이다른&!행운"),
    ]),
    ("연산자 사용법", [
        ("그리고 (AND)", "뮤&4*"),
        ("또는 (OR)", "물,불꽃"),
        ("제외 (NOT)", "!전설"),
    ]),
]

# 하위호환: 평평한 리스트가 필요한 곳(예: --search 하단 참고 출력)
COMMON_SEARCH_TERMS = [
    ("100% 개체값", "4*"),
    ("최악(0%)", "0*"),
    ("PvP용 저공격", "0공격"),
    ("색이 다른(이로치)", "색이다른"),
    ("교환 가능", "교환가능"),
    ("즐겨찾기", "즐겨찾기"),
    ("전송용 잡몹", "0-2*&!즐겨찾기&!교환가능"),
]


def iv_impact_note():
    """개체값이 실제 성능에 미치는 영향 요약 (레이드 vs 마스터리그)."""
    return (
        "ℹ️ 개체값 영향도 — 레이드(PvE): IV 1당 약 0.3~0.4%, 300초 기준 ~6초 차로 "
        "사실상 무의미(100% 개체는 효율보다 감성). 마스터리그: 2% 차가 미러전 승패를 "
        "가르므로 100% 개체가 중요. 슈퍼/하이퍼리그: 'CP 상한 내 스탯곱'이 핵심이라 "
        "저공격(예: 0/15/15)이 자주 1위."
    )


# ── 합체/변신 에너지 ──
FUSION_ENERGY_BASE = 80          # 1회 보상 기본 에너지
FUSION_ENERGY_PER_DROP = 10      # 에너지 당첨 꾸러미 1개당
FUSION_ENERGY_DROP_RATE = 0.25   # 꾸러미가 에너지일 확률
FUSION_GOAL_DEFAULT = 1000       # 합체/변신 1회 제작에 필요한 에너지
# (비스트볼/파워스폿 처치 보상 꾸러미 → 기대 에너지) — dcinside 정보글 #72554
FUSION_BEASTBALL_TABLE = [
    ("8~10",  "7~8", "약 97~100"),
    ("11~13", "9",   "약 102"),
    ("14~15", "10",  "약 105"),
    ("16~17", "11",  "약 107"),
]


def fusion_expected_energy(bundles):
    """보상 꾸러미 수 → 기대 합체 에너지. 공식: 80 + 10×(꾸러미×0.25)."""
    return FUSION_ENERGY_BASE + FUSION_ENERGY_PER_DROP * (bundles * FUSION_ENERGY_DROP_RATE)


def boss_weaknesses(types):
    """방어 타입 리스트 → 약점(배수>1) 공격타입 리스트 (배수 큰 순)."""
    eff = type_effectiveness([t for t in types if t])
    weak = [(atk, m) for atk, m in eff.items() if m > 1.0]
    weak.sort(key=lambda x: -x[1])
    return weak


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

    # 단발 실행
    if args.pokemon and len(args.ivs) == 3:
        ivs = parse_ivs(" ".join(args.ivs))
        analyze_cli(gm, ko_base_map, sid_to_display, args.pokemon, ivs, args.max_level)
        return
    if args.pokemon and not args.ivs:
        # 개체값 없이 이름만 → 제일 좋은 개체값 조회
        if args.league:
            lg = _find_league(args.league)
            if not lg:
                print(f"리그를 찾을 수 없음: {args.league}  "
                      f"(가능: {', '.join(l.name for l in LEAGUES)})")
                return
            report_top_ivs_for_league(gm, ko_base_map, sid_to_display,
                                      args.pokemon, lg, args.max_level, args.top)
        else:
            report_best_ivs_per_league(gm, ko_base_map, sid_to_display,
                                       args.pokemon, args.max_level)
        return

    print("Pokemon GO PvP 개체값 리그 랭커 (CLI)")
    print(f"최대 레벨: {args.max_level}  "
          f"(XL사탕 없으면 --max-level 40, Best Buddy 활성은 --max-level 51)")
    print("종료: 빈 줄에서 엔터 또는 Ctrl+C\n")
    while True:
        try:
            name = input("포켓몬: ").strip()
            if not name:
                print("종료.")
                break
            iv_str = input("개체값 (예: 1 15 14 · 빈칸=리그별 최고 개체값 · "
                           "리그명=그 리그 상위 목록): ").strip()
            if not iv_str:
                report_best_ivs_per_league(gm, ko_base_map, sid_to_display,
                                           name, args.max_level)
                print()
                continue
            lg = _find_league(iv_str)
            if lg and not any(ch.isdigit() for ch in iv_str):
                report_top_ivs_for_league(gm, ko_base_map, sid_to_display,
                                          name, lg, args.max_level, args.top)
                print()
                continue
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
    from tkinter import ttk, messagebox, filedialog

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

    def make_searchable_combo(parent, textvariable, values, on_select=None, **kwargs):
        """검색 가능한 콤보박스 — 타이핑하면 dropdown 이 substring 매치로 필터링.
        on_select: 선택 시 호출되는 콜백 (None 가능). 빈 텍스트면 전체 목록 복원.
        값을 콤보 자체에 _all_values 로 캐싱.
        """
        kwargs.setdefault("state", "normal")
        combo = ttk.Combobox(parent, textvariable=textvariable, **kwargs)
        combo._all_values = list(values)
        combo["values"] = combo._all_values

        def _filter(_e=None):
            typed = textvariable.get().strip().lower()
            if not typed:
                combo["values"] = combo._all_values
                return
            filtered = [v for v in combo._all_values if typed in v.lower()]
            combo["values"] = filtered if filtered else combo._all_values

        def _on_select(_e=None):
            combo["values"] = combo._all_values  # 선택 후 dropdown 복원
            if on_select:
                on_select()

        combo.bind("<KeyRelease>", _filter)
        combo.bind("<<ComboboxSelected>>", _on_select)
        return combo

    def update_combo_values(combo, new_values):
        """make_searchable_combo 가 만든 콤보의 캐시된 values 갱신."""
        combo._all_values = list(new_values)
        combo["values"] = combo._all_values

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

    # speciesId → pokemon 엔트리 (선택/IV 입력 hot path 에서 O(n) 선형 스캔 제거)
    sid_to_pokemon = {p.get("speciesId"): p for p in gm.get("pokemon", [])}

    # 기술 ID → 한글명 (여러 refresh 함수에서 공통 사용)
    def move_ko(mid):
        k = mid.lower().replace("_", "-")
        return move_ko_map.get(k) or moves_by_id.get(mid, {}).get("name", mid)

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

    # 검색 핫루프용 사전 캐시 — 키 입력마다 norm()/category lookup 재계산 방지.
    # 데이터 갱신(do_data_refresh) 시 _rebuild_search_cache() 로 다시 채움.
    search_cache = {
        "norm_d": {},   # display → norm(display)
        "norm_s": {},   # display → sid.lower()
        "cat":    {},   # display → category
        "len":    {},   # display → len(display)
    }

    def _rebuild_search_cache():
        nd, ns, cat, ln = {}, {}, {}, {}
        for d in all_displays_full:
            sid = display_to_sid[d]
            nd[d]  = norm(d)
            ns[d]  = sid.lower()
            cat[d] = _category(sid)
            ln[d]  = len(d)
        search_cache["norm_d"] = nd
        search_cache["norm_s"] = ns
        search_cache["cat"]    = cat
        search_cache["len"]    = ln
    _rebuild_search_cache()

    def filter_displays(query, only_favs=False,
                        show_normal=True, show_shadow=True, show_mega=True):
        q = norm(query)
        c_normal, c_shadow, c_mega = show_normal, show_shadow, show_mega
        nd_map = search_cache["norm_d"]
        ns_map = search_cache["norm_s"]
        cat_map = search_cache["cat"]
        len_map = search_cache["len"]

        if not q:
            # 무검색 경로: 정렬된 all_displays_full 순서 그대로
            if c_normal and c_shadow and c_mega and not only_favs:
                return list(all_displays_full)
            out = []
            append = out.append
            for d in all_displays_full:
                cat = cat_map[d]
                if cat == "normal" and not c_normal: continue
                if cat == "shadow" and not c_shadow: continue
                if cat == "mega"   and not c_mega:   continue
                if only_favs and display_to_sid[d] not in favorites: continue
                append(d)
            return out

        # 검색 경로: 카테고리/즐겨찾기 + substring 매치를 한 패스에 처리
        scored = []
        append = scored.append
        for d in all_displays_full:
            cat = cat_map[d]
            if cat == "normal" and not c_normal: continue
            if cat == "shadow" and not c_shadow: continue
            if cat == "mega"   and not c_mega:   continue
            if only_favs and display_to_sid[d] not in favorites: continue
            nd = nd_map[d]
            ns = ns_map[d]
            if q in nd or q in ns:
                starts = 0 if (nd.startswith(q) or ns.startswith(q)) else 1
                append((starts, len_map[d], d))
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
    # 창/작업표시줄 아이콘 (몬스터볼) — 스크립트 폴더의 icon.ico 사용, 없으면 무시
    try:
        _icon_dir = os.path.dirname(os.path.abspath(__file__))
        _ico = os.path.join(_icon_dir, "icon.ico")
        if os.path.exists(_ico):
            root.iconbitmap(default=_ico)
        else:
            _png = os.path.join(_icon_dir, "icon.png")
            if os.path.exists(_png):
                root.iconphoto(True, tk.PhotoImage(file=_png))
    except Exception:
        pass
    geom = settings.get("geometry", "1500x920")
    try:
        root.geometry(geom)
    except Exception:
        root.geometry("1500x920")
    # 저장된 위치가 화면 밖이면 (모니터 변경/해상도 변경 등) 다시 보이는 곳으로.
    # 안 그러면 창이 보이지 않는 좌표에 떠서 "앱이 안 켜진다"로 오인됨.
    try:
        m = re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geom)
        if m:
            w, h, x, y = (int(m.group(1)), int(m.group(2)),
                          int(m.group(3)), int(m.group(4)))
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            # 창의 상당 부분이 화면 안에 보이는지 확인 (제목표시줄 ~40px 여유)
            if x + w < 60 or x > sw - 60 or y < 0 or y > sh - 60:
                root.geometry(f"{min(w, sw)}x{min(h, sh)}+50+50")
    except Exception:
        pass
    root.minsize(1360, 800)

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

    # 베스트 친구(Lv51) 토글 — 켜면 IV 랭킹/내 IV 계산 캡을 Lv50 → Lv51 로.
    # PvPoke 등 기본은 Lv50, 베스트버디 보너스(+1)는 Lv51. 요약표의 'Lv' 열로 구분됨.
    best_buddy_var = tk.BooleanVar(value=settings.get("best_buddy", False))

    def current_max_idx():
        return 100 if best_buddy_var.get() else DEFAULT_MAX_IDX

    def _on_best_buddy_toggle():
        try:
            settings["best_buddy"] = bool(best_buddy_var.get())
            save_settings(settings)
        except Exception:
            pass
        # 캡이 바뀌면 캐시된 랭킹은 무효 → 비우고 현재 뷰 재계산
        _ranking_lru.clear()
        _ranking_lru_order.clear()
        ranking_cache.clear()
        for _fn in (refresh,):
            try:
                _fn()
            except Exception as e:
                print(f"베스트버디 토글 갱신 실패: {e}")

    bb_row = ttk.Frame(left)
    bb_row.pack(anchor="w", pady=(0, 4))
    ttk.Checkbutton(bb_row, text="베스트 친구(Lv51)", variable=best_buddy_var,
                    command=_on_best_buddy_toggle).pack(side="left")
    ttk.Label(bb_row, text="끄면 Lv50 캡", font=("", 8),
              foreground="#999").pack(side="left", padx=(4, 0))

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
    data_refresh_btn = ttk.Button(left, text="데이터 업데이트",
                                  command=lambda: do_data_refresh())
    data_refresh_btn.pack(fill="x", pady=(4, 0))

    # ----- 즐겨찾기 백업 (내보내기 / 가져오기) -----
    def _export_favorites():
        if not favorites:
            messagebox.showinfo("내보내기", "즐겨찾기가 비어 있습니다.")
            return
        path = filedialog.asksaveasfilename(
            title="즐겨찾기 내보내기", defaultextension=".json",
            initialfile="pogo_favorites.json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            _atomic_write_json(path, {"species": sorted(favorites)})
            messagebox.showinfo("내보내기", f"{len(favorites)}개 즐겨찾기를 저장했습니다.\n{path}")
        except Exception as e:
            messagebox.showerror("내보내기 실패", str(e))

    def _import_favorites():
        path = filedialog.askopenfilename(
            title="즐겨찾기 가져오기",
            filetypes=[("JSON", "*.json"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                incoming = set(json.load(f).get("species", []))
        except Exception as e:
            messagebox.showerror("가져오기 실패", f"파일을 읽을 수 없습니다: {e}")
            return
        if not incoming:
            messagebox.showinfo("가져오기", "파일에 즐겨찾기가 없습니다.")
            return
        merge = messagebox.askyesnocancel(
            "가져오기",
            f"{len(incoming)}개를 불러왔습니다.\n\n"
            f"[예] 기존 {len(favorites)}개에 합치기\n"
            f"[아니오] 기존을 덮어쓰기\n"
            f"[취소] 취소")
        if merge is None:
            return
        if not merge:
            favorites.clear()
        favorites.update(incoming)
        save_favorites(favorites)
        fav_count_var.set(f"★ 즐겨찾기만 보기  ({len(favorites)}개)")
        update_listbox(force=True, auto_select=False)
        messagebox.showinfo("가져오기", f"완료 — 현재 즐겨찾기 {len(favorites)}개")

    bk_row = ttk.Frame(left)
    bk_row.pack(fill="x", pady=(2, 0))
    ttk.Button(bk_row, text="즐겨찾기 내보내기", command=_export_favorites
               ).pack(side="left", fill="x", expand=True, padx=(0, 2))
    ttk.Button(bk_row, text="가져오기", command=_import_favorites
               ).pack(side="left", fill="x", expand=True, padx=(2, 0))

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

    def _on_cup_select():
        sel = cup_combo_var.get()
        if sel and sel != CUP_PLACEHOLDER and sel in cup_label_to_name:
            league_var.set(cup_label_to_name[sel])
            try:
                refresh()
            except NameError:
                pass
    cup_combo = make_searchable_combo(league_row, cup_combo_var,
                                      [CUP_PLACEHOLDER],
                                      on_select=_on_cup_select, width=24)
    cup_combo.pack(side="left", padx=2)

    def _refresh_cup_choices():
        """LEAGUES 가 변경되면 (data refresh 후 등) 컵 목록 재구성."""
        builtin_names = {lg.name for lg in _BUILTIN_LEAGUES}
        cup_leagues = [lg for lg in LEAGUES if lg.name not in builtin_names]
        cup_label_to_name.clear()
        cup_label_to_name.update({_league_label(lg): lg.name for lg in cup_leagues})
        update_combo_values(cup_combo,
                            [CUP_PLACEHOLDER] + [_league_label(lg) for lg in cup_leagues])

    _refresh_cup_choices()

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

    # 입수처: 현재 일정상 어디서 잡힐 수 있는지 (알 / 레이드 / 리서치 / 로켓)
    # 사전 진화 단계까지 거슬러 검색 — 진화로만 얻을 수 있는 포켓몬도 표시됨.
    acq_frame = ttk.Frame(info_stack)
    acq_frame.pack(fill="x", pady=(2, 0))
    ttk.Label(acq_frame, text="입수:", font=("", 9, "bold"),
              foreground="#555").pack(side="left", padx=(0, 6), anchor="nw")
    acq_var = tk.StringVar(value="")
    acq_lbl = ttk.Label(acq_frame, textvariable=acq_var, font=("", 9),
                        foreground="#333", wraplength=600, justify="left")
    acq_lbl.pack(side="left", fill="x", expand=True, anchor="w")
    # info_stack 너비에 맞춰 wraplength 동적 조정
    def _on_info_stack_resize(event):
        acq_lbl.configure(wraplength=max(200, event.width - 60))
    info_stack.bind("<Configure>", _on_info_stack_resize)

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

    ttk.Label(iv_tab, text=iv_impact_note(), font=("", 8), foreground="#888",
              wraplength=980, justify="left").pack(anchor="w", pady=(3, 0))

    # 아래 영역: Top 100 (좌) + 기술&점수 (우) 한 화면
    content_split = ttk.Frame(iv_tab)
    content_split.pack(fill="both", expand=True)

    # Left: Top 100 IV 랭킹
    iv_col = ttk.Frame(content_split)
    iv_col.pack(side="left", fill="both", expand=True, padx=(0, 8))

    table_label = tk.StringVar(value="")
    ttk.Label(iv_col, textvariable=table_label, font=("", 9),
              foreground="#555").pack(anchor="w", pady=(0, 4))

    # 인게임 검색 문자열 (현재 리그 베스트 IV 기준) — 복사해서 게임에 붙여넣기
    search_str_var = tk.StringVar(value="")
    search_row = ttk.Frame(iv_col)
    search_row.pack(fill="x", pady=(0, 4))
    ttk.Label(search_row, text="🔍 검색", font=("", 9, "bold"),
              foreground="#2a5a8a").pack(side="left")
    ttk.Entry(search_row, textvariable=search_str_var, state="readonly"
              ).pack(side="left", fill="x", expand=True, padx=(6, 4))

    def _copy_search():
        s = search_str_var.get()
        if s:
            root.clipboard_clear()
            root.clipboard_append(s)
    ttk.Button(search_row, text="복사", width=6, command=_copy_search).pack(side="left")

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

    # --- Tab 2: PvP 비교 (두 포켓몬 나란히) ---
    compare_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(compare_tab, text="  PvP 비교  ")

    ttk.Label(compare_tab,
              text="두 포켓몬을 IV/레벨/리그별로 나란히 비교. 입력 시 자동 갱신.",
              font=("", 9), foreground="#555").pack(anchor="w", pady=(0, 6))

    # forward-ref 안전한 디바운서 (refresh_compare 는 아래에서 정의)
    _cmp_after_id = [None]
    def _schedule_cmp_refresh(*_a):
        if _cmp_after_id[0]:
            try:
                root.after_cancel(_cmp_after_id[0])
            except Exception:
                pass
        _cmp_after_id[0] = root.after(180, lambda: refresh_compare())

    cmp_inputs_row = ttk.Frame(compare_tab)
    cmp_inputs_row.pack(fill="x", pady=(0, 6))

    def _build_cmp_panel(parent, label):
        f = ttk.LabelFrame(parent, text=f"  {label}  ", padding=(8, 6))
        name_v = tk.StringVar(value="")
        ttk.Label(f, text="포켓몬").grid(row=0, column=0, sticky="w", padx=(0, 4))
        name_combo = make_searchable_combo(f, name_v, all_displays_full,
                                           on_select=_schedule_cmp_refresh, width=24)
        name_combo.grid(row=0, column=1, columnspan=5, sticky="w", pady=(0, 4))

        a_v = tk.StringVar(value="15")
        d_v = tk.StringVar(value="15")
        h_v = tk.StringVar(value="15")
        ttk.Label(f, text="공").grid(row=1, column=0, sticky="e", pady=(2, 0))
        ttk.Spinbox(f, from_=0, to=15, textvariable=a_v, width=4).grid(row=1, column=1, sticky="w", pady=(2, 0))
        ttk.Label(f, text="방").grid(row=1, column=2, sticky="e", padx=(8, 0), pady=(2, 0))
        ttk.Spinbox(f, from_=0, to=15, textvariable=d_v, width=4).grid(row=1, column=3, sticky="w", pady=(2, 0))
        ttk.Label(f, text="체").grid(row=1, column=4, sticky="e", padx=(8, 0), pady=(2, 0))
        ttk.Spinbox(f, from_=0, to=15, textvariable=h_v, width=4).grid(row=1, column=5, sticky="w", pady=(2, 0))

        lv_v = tk.StringVar(value="51")
        ttk.Label(f, text="최대 Lv").grid(row=2, column=0, sticky="e", pady=(4, 0))
        ttk.Combobox(f, textvariable=lv_v, values=["40", "45", "50", "51"],
                     width=5, state="readonly").grid(row=2, column=1, sticky="w", pady=(4, 0))

        for v in (a_v, d_v, h_v, lv_v):
            v.trace_add("write", _schedule_cmp_refresh)

        return f, {"name": name_v, "a": a_v, "d": d_v, "h": h_v, "lv": lv_v}

    panel_a, cmp_a = _build_cmp_panel(cmp_inputs_row, "포켓몬 A (좌)")
    panel_a.pack(side="left", fill="y", padx=(0, 8))
    panel_b, cmp_b = _build_cmp_panel(cmp_inputs_row, "포켓몬 B (우)")
    panel_b.pack(side="left", fill="y")

    cmp_ctrl = ttk.Frame(compare_tab)
    cmp_ctrl.pack(fill="x", pady=(0, 4))
    ttk.Label(cmp_ctrl, text="비교 기준 리그",
              font=("", 9, "bold")).pack(side="left", padx=(0, 6))
    cmp_league_var = tk.StringVar(value="슈퍼리그")
    cmp_league_combo = ttk.Combobox(cmp_ctrl, textvariable=cmp_league_var,
                                    values=[lg.name for lg in LEAGUES],
                                    state="readonly", width=22)
    cmp_league_combo.pack(side="left")
    cmp_league_combo.bind("<<ComboboxSelected>>", _schedule_cmp_refresh)
    ttk.Label(cmp_ctrl,
              text="(메타 점수·순위는 빌트인 4리그 모두 표시 / 매치업·추천 무브셋은 선택 리그)",
              font=("", 8), foreground="#888").pack(side="left", padx=(10, 0))

    cmp_frame = ttk.Frame(compare_tab)
    cmp_frame.pack(fill="both", expand=True, pady=(4, 6))
    cmp_scroll = ttk.Scrollbar(cmp_frame, orient="vertical")
    cmp_scroll.pack(side="right", fill="y")
    cmp_tree = ttk.Treeview(cmp_frame, columns=("metric", "a", "b"),
                            show="headings", yscrollcommand=cmp_scroll.set, height=20)
    cmp_tree.heading("metric", text="항목")
    cmp_tree.heading("a", text="A")
    cmp_tree.heading("b", text="B")
    cmp_tree.column("metric", width=160, anchor="w")
    cmp_tree.column("a", width=380, anchor="w")
    cmp_tree.column("b", width=380, anchor="w")
    cmp_tree.pack(side="left", fill="both", expand=True)
    cmp_scroll.config(command=cmp_tree.yview)
    cmp_tree.tag_configure("hdr", background="#eef")
    cmp_tree.tag_configure("emph", background="#fff9dd")

    cmp_action_row = ttk.Frame(compare_tab)
    cmp_action_row.pack(fill="x")
    cmp_status_var = tk.StringVar(value="")

    def _open_pvpoke_compare():
        da = cmp_a["name"].get().strip()
        db = cmp_b["name"].get().strip()
        sa = display_to_sid.get(da)
        sb = display_to_sid.get(db)
        if not (sa and sb):
            cmp_status_var.set("두 포켓몬 모두 선택해주세요.")
            return
        lg = next((l for l in LEAGUES if l.name == cmp_league_var.get()), None)
        cap = lg.cap if (lg and lg.cap) else 10000
        url = f"https://pvpoke.com/battle/{cap}/{sa}/{sb}/11/"
        try:
            import webbrowser
            webbrowser.open(url)
            cmp_status_var.set(f"→ {url}")
        except Exception as e:
            cmp_status_var.set(f"브라우저 열기 실패: {e}")

    ttk.Button(cmp_action_row, text="PvPoke 매치업으로 열기 (브라우저)",
               command=_open_pvpoke_compare).pack(side="left")
    ttk.Label(cmp_action_row, textvariable=cmp_status_var,
              foreground="#666", font=("", 8)).pack(side="left", padx=(10, 0), fill="x", expand=True)

    # ───── 비교 계산 / 렌더링 ─────
    def _cmp_parse_iv(s, default=15):
        s = (s or "").strip()
        try:
            v = int(s)
            return v if 0 <= v <= 15 else default
        except ValueError:
            return default

    def _cmp_parse_lv(s):
        try:
            return float(s)
        except (ValueError, TypeError):
            return 51.0

    def _cmp_lookup_pokemon(display_name):
        sid = display_to_sid.get(display_name)
        if not sid:
            return None, None
        p = next((x for x in state["gm"]["pokemon"] if x.get("speciesId") == sid), None)
        return p, sid

    def _cmp_weak_resist_strs(types):
        clean = [t for t in (types or []) if t and t != "none"]
        if not clean:
            return "—", "—"
        weak, resist = [], []
        for atk in TYPES_ORDER:
            mult = 1.0
            for d in clean:
                mult *= TYPE_CHART.get(atk, {}).get(d, 1.0)
            if mult > 1.01:
                weak.append((atk, mult))
            elif mult < 0.99:
                resist.append((atk, mult))
        weak.sort(key=lambda x: -x[1])
        resist.sort(key=lambda x: x[1])
        fmt = lambda t, m: f"{TYPE_KO.get(t, t)}×{m:.2f}"
        return (", ".join(fmt(*x) for x in weak) or "—",
                ", ".join(fmt(*x) for x in resist) or "—")

    def _cmp_type_mult(attack_type, defender_types):
        clean = [t for t in (defender_types or []) if t and t != "none"]
        mult = 1.0
        for d in clean:
            mult *= TYPE_CHART.get(attack_type, {}).get(d, 1.0)
        return mult

    def _cmp_matchup_line(my_pokemon, opp_types):
        clean = [t for t in (opp_types or []) if t and t != "none"]
        if not clean:
            return "—"
        bm = best_moveset_vs(my_pokemon, clean, moves_by_id,
                             boss_cpm=0.79, boss_base_def=180, attacker_level=50)
        if not bm:
            return "—"
        ftype = bm["fast_type"]
        ctype = bm["charged_type"]
        fm = _cmp_type_mult(ftype, clean)
        cm = _cmp_type_mult(ctype, clean)
        def emoji(m):
            if m >= 1.6:
                return " 💥"
            if m <= 0.625:
                return " 🛡"
            return ""
        f_name = prettify_move(bm["fast_id"], move_ko_map)
        c_name = prettify_move(bm["charged_id"], move_ko_map)
        return (f"{f_name}({TYPE_KO.get(ftype, ftype)}) ×{fm:.2f}{emoji(fm)}  ·  "
                f"{c_name}({TYPE_KO.get(ctype, ctype)}) ×{cm:.2f}{emoji(cm)}")

    def refresh_compare():
        for r in cmp_tree.get_children():
            cmp_tree.delete(r)

        pa, sa = _cmp_lookup_pokemon(cmp_a["name"].get())
        pb, sb = _cmp_lookup_pokemon(cmp_b["name"].get())

        ia = (_cmp_parse_iv(cmp_a["a"].get()),
              _cmp_parse_iv(cmp_a["d"].get()),
              _cmp_parse_iv(cmp_a["h"].get()))
        ib = (_cmp_parse_iv(cmp_b["a"].get()),
              _cmp_parse_iv(cmp_b["d"].get()),
              _cmp_parse_iv(cmp_b["h"].get()))
        lva = _cmp_parse_lv(cmp_a["lv"].get())
        lvb = _cmp_parse_lv(cmp_b["lv"].get())

        def row(metric, va, vb, tag=""):
            cmp_tree.insert("", "end", values=(metric, va, vb),
                            tags=(tag,) if tag else ())

        ta = sid_to_display.get(sa, "—") if pa else "—"
        tb = sid_to_display.get(sb, "—") if pb else "—"
        row("포켓몬", ta, tb, "hdr")

        if not (pa and pb):
            row("(안내)",
                "좌측 콤보에서 포켓몬을 선택하세요." if not pa else f"입력: {ta}",
                "우측 콤보에서 포켓몬을 선택하세요." if not pb else f"입력: {tb}")
            return

        bsa, bsb = pa["baseStats"], pb["baseStats"]
        row("종족값 (공/방/체)",
            f"{bsa['atk']} / {bsa['def']} / {bsa['hp']}",
            f"{bsb['atk']} / {bsb['def']} / {bsb['hp']}")

        types_a = [t for t in pa.get("types", []) if t and t != "none"]
        types_b = [t for t in pb.get("types", []) if t and t != "none"]
        row("타입",
            " / ".join(TYPE_KO.get(t, t) for t in types_a) or "—",
            " / ".join(TYPE_KO.get(t, t) for t in types_b) or "—")

        wa, ra = _cmp_weak_resist_strs(types_a)
        wb, rb = _cmp_weak_resist_strs(types_b)
        row("약점 (>×1)", wa, wb)
        row("내성 (<×1)", ra, rb)

        rows_a, _ = analyze_pokemon(pa, ia, lva)
        rows_b, _ = analyze_pokemon(pb, ib, lvb)
        lname_to_a = {r[0]: r for r in rows_a}
        lname_to_b = {r[0]: r for r in rows_b}

        def lstr(rr, sid, lname):
            if not rr or rr[1] is None:
                return "(못 들어감)"
            _, lvl, cp, sp, rank, pct, _top = rr
            meta_rk = rankings_index.get(lname, {}).get(sid)
            mtotal = len(rankings.get(lname, []))
            meta = f"메타 #{meta_rk}/{mtotal}" if meta_rk else "메타 미등재"
            return f"Lv{lvl:g} CP{cp} SP{sp:,.0f}\n{meta} · IV순위 #{rank}/4096 · {pct:.1f}%"

        for lg in _BUILTIN_LEAGUES:
            lname = lg.name
            row(f"▶ {lname}",
                lstr(lname_to_a.get(lname), sa, lname),
                lstr(lname_to_b.get(lname), sb, lname))

        sel_lname = cmp_league_var.get()
        sel_lg = next((l for l in LEAGUES if l.name == sel_lname), None)
        if sel_lg:
            def meta_entry(sid):
                rk = rankings.get(sel_lname, [])
                for e in rk:
                    if e.get("speciesId") == sid:
                        return e
                return None

            ea = meta_entry(sa)
            eb = meta_entry(sb)

            def meta_moves_str(entry):
                if not entry:
                    return "—"
                ms = entry.get("moveset") or []
                return " / ".join(prettify_move(m, move_ko_map) for m in ms[:3]) or "—"
            row(f"추천 무브셋 ({sel_lname})",
                meta_moves_str(ea), meta_moves_str(eb), "emph")
            row("A 무브 → B 매치업",
                _cmp_matchup_line(pa, types_b), "—", "emph")
            row("B 무브 → A 매치업",
                "—", _cmp_matchup_line(pb, types_a), "emph")

            # ───── ✦ 종합 판단 ─────
            # 1) 메타 점수 (PvPoke score, 선택 리그)
            score_a = ea.get("score") if ea else None
            score_b = eb.get("score") if eb else None
            rank_a = rankings_index.get(sel_lname, {}).get(sa)
            rank_b = rankings_index.get(sel_lname, {}).get(sb)

            def _meta_cell(score, rank, is_winner, is_tie):
                if score is None:
                    return "미등재"
                base = f"{score:.1f}"
                if rank:
                    base += f" (#{rank})"
                if is_tie:
                    return base + "  (비슷)"
                return base + ("  ← 우세" if is_winner else "")

            if score_a is not None and score_b is not None:
                diff = score_a - score_b
                tie = abs(diff) < 1.0  # 1.0 점 이내 → 비슷
                a_meta_win = (not tie) and diff > 0
                b_meta_win = (not tie) and diff < 0
            else:
                tie = False
                a_meta_win = b_meta_win = False
            row(f"✦ 메타 점수 ({sel_lname})",
                _meta_cell(score_a, rank_a, a_meta_win, tie),
                _meta_cell(score_b, rank_b, b_meta_win, tie), "emph")

            # 2) 매치업 eDPS — 상대 타입을 방어자로 둔 최고 무브셋 eDPS 직접 비교
            #    boss_cpm/boss_def 는 PvP 기준 아니지만 양쪽 동일 baseline → 상대 비교 유효
            def _edps_vs(attacker, defender_types):
                clean = [t for t in (defender_types or []) if t and t != "none"]
                if not clean:
                    return None
                bm = best_moveset_vs(attacker, clean, moves_by_id,
                                     boss_cpm=0.79, boss_base_def=180,
                                     attacker_level=50)
                return bm["edps"] if bm else None

            edps_a = _edps_vs(pa, types_b)
            edps_b = _edps_vs(pb, types_a)

            def _edps_cell(v, is_winner, is_tie):
                if v is None:
                    return "—"
                base = f"{v:.2f}"
                if is_tie:
                    return base + "  (비슷)"
                return base + ("  ← 유리" if is_winner else "")

            if edps_a and edps_b:
                ratio = edps_a / edps_b
                e_tie = 0.9 <= ratio <= 1.1  # ±10% 이내 → 비슷
                a_edps_win = (not e_tie) and ratio > 1.0
                b_edps_win = (not e_tie) and ratio < 1.0
            else:
                e_tie = False
                a_edps_win = b_edps_win = False
            row("✦ 매치업 공격 효율 (eDPS, 상대 비교)",
                _edps_cell(edps_a, a_edps_win, e_tie),
                _edps_cell(edps_b, b_edps_win, e_tie), "emph")

            row("※ 참고",
                "실 PvP 결과는 무브 회전·실드·스왑 어드밴티지로 달라질 수 있음 — 정밀 비교는 PvPoke 시뮬레이터(아래 버튼) 권장",
                "—")

    refresh_compare()  # 초기 placeholder 렌더

    # --- Tab 3: 리그 메타 랭킹 (개별 메타 + 팀 메타 토글) ---
    meta_tab = ttk.Frame(notebook, padding=(6, 8))
    notebook.add(meta_tab, text="  PvP 메타  ")

    meta_label = tk.StringVar(value="")
    ttk.Label(meta_tab, textvariable=meta_label, font=("", 10)).pack(anchor="w", pady=(0, 4))

    # 개별 메타 / 팀 메타 전환 토글 — 한 탭에서 라디오로 뷰 교체
    meta_mode_var = tk.StringVar(value="individual")

    def _refresh_meta_active():
        """현재 활성 모드만 갱신 (탭 진입 시 호출)."""
        if meta_mode_var.get() == "team":
            _refresh_team_meta()
        else:
            refresh_meta()

    def _on_meta_mode():
        if meta_mode_var.get() == "team":
            meta_indiv_container.pack_forget()
            meta_team_container.pack(fill="both", expand=True)
            _refresh_team_meta()
        else:
            meta_team_container.pack_forget()
            meta_indiv_container.pack(fill="both", expand=True)
            refresh_meta(force=True)

    meta_mode_row = ttk.Frame(meta_tab)
    meta_mode_row.pack(fill="x", pady=(0, 6))
    ttk.Radiobutton(meta_mode_row, text="개별 메타", value="individual",
                    variable=meta_mode_var, command=_on_meta_mode).pack(side="left")
    ttk.Radiobutton(meta_mode_row, text="팀 메타", value="team",
                    variable=meta_mode_var, command=_on_meta_mode).pack(side="left", padx=(12, 0))
    ttk.Label(meta_mode_row, text="  · 개별=강한 포켓몬 순위, 팀=추천 조합",
              font=("", 8), foreground="#888").pack(side="left", padx=(8, 0))

    # 두 뷰 컨테이너 (pack/pack_forget 로 전환)
    meta_indiv_container = ttk.Frame(meta_tab)
    meta_team_container = ttk.Frame(meta_tab)
    meta_indiv_container.pack(fill="both", expand=True)

    meta_search_row = ttk.Frame(meta_indiv_container)
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

    meta_frame = ttk.Frame(meta_indiv_container)
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
        raid_state["bosses"] = load_combined_raids()
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
    boss_combo = make_searchable_combo(raid_top, boss_var, [],
                                       on_select=lambda: refresh_counters(),
                                       width=36, height=20)
    boss_combo.pack(side="left", padx=(6, 16))

    ttk.Label(raid_top, text="날씨", font=("", 10, "bold")).pack(side="left")
    weather_var = tk.StringVar(value="(없음)")
    weather_choices = ["(없음)"] + [WEATHER_KO[w] for w in
                                     ["sunny","rainy","partly_cloudy","cloudy","windy","snow","fog"]]
    weather_combo = make_searchable_combo(raid_top, weather_var, weather_choices,
                                          on_select=lambda: refresh_counters(), width=14)
    weather_combo.pack(side="left", padx=(6, 16))

    # boss_mode_var: 보스가 일반 레이드(raid) 인지 맥스 배틀(max) 인지.
    # 현재는 보스 데이터(raid_state)가 일반 레이드 보스만 제공하므로 항상 'raid' 고정.
    # 향후 다이맥스 보스 데이터가 추가되면 라디오 UI 복원 가능.
    boss_mode_var = tk.StringVar(value="raid")

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

    ttk.Label(raid_filter_row, text="  표시:", font=("", 9), foreground="#555"
              ).pack(side="left", padx=(8, 4))
    raid_topn_var = tk.StringVar(value="20")
    raid_topn_combo = ttk.Combobox(raid_filter_row, textvariable=raid_topn_var,
                                   values=["20", "50", "100", "200", "전체"],
                                   width=6, state="readonly")
    raid_topn_combo.pack(side="left")
    raid_topn_combo.bind("<<ComboboxSelected>>", lambda e: refresh_counters())

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
        update_combo_values(boss_combo, labels)
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
        try:
            topn = 10000 if raid_topn_var.get() == "전체" else int(raid_topn_var.get())
        except ValueError:
            topn = 20
        # 보스 티어별 CPM — 1·3성 보스를 5성 CPM(0.5793)으로 계산하면 카운터 수치가
        # 과대평가되므로 실제 티어를 반영한다. 5성/메가/엘리트/그림자는 top_counters
        # 의 sid 기반 분기(메가 여부)에 맡기려 None 으로 둔다.
        if is_max_mode:
            force_cpm = 1.0
        elif "1-Star" in tier_label:
            force_cpm = RAID_TIER_CPM["1"]
        elif "3-Star" in tier_label:
            force_cpm = RAID_TIER_CPM["3"]
        else:
            force_cpm = None
        cnt = top_counters(
            boss_p, state["gm"], moves_by_id, n=topn,
            weather=weather,
            include_shadow=inc_shadow_var.get(),
            include_mega=inc_mega_var.get(),
            include_legendary=inc_legend_var.get(),
            favorites_only=favs,
            force_boss_cpm=force_cpm,
            attacker_level=atk_lv,
        )
        for i, c in enumerate(cnt, 1):
            disp = sid_to_display.get(c["sid"], c["sid"])
            tps = " · ".join(TYPE_KO.get(t, t) for t in c["pokemon"].get("types", [])
                             if t and t != "none")
            f_name = move_ko(c["fast_id"])
            ch_name = move_ko(c["charged_id"])
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
                f"• {len(cnt)}마리 표시 · 날씨={weather_var.get()} · "
                f"Lv{raid_lv_var.get()}/15·15·15 가정"
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
            raid_state["bosses"] = load_combined_raids(force=True)
        except Exception as e:
            messagebox.showerror("실패", f"갱신 실패: {e}")
            return
        _populate_boss_combo()
        refresh_counters()

    # 공격자 Lv 콤보 (boss/weather 는 make_searchable_combo 가 이미 on_select 바인딩)
    for w in raid_top.winfo_children():
        if isinstance(w, ttk.Combobox) and w not in (boss_combo, weather_combo):
            w.bind("<<ComboboxSelected>>", lambda e: refresh_counters())
    _populate_boss_combo()

    # --- Tab: PvE 로켓 — 로켓단 조무래기 카운터 ---
    rkt_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(rkt_tab, text="  PvE 로켓  ")

    ttk.Label(rkt_tab,
              text="GO 로켓단 통합 탭 — 위쪽 표에서 NPC 선택 시 자동으로 타입별 카운터 표시. "
                   "직접 대사/타입 입력도 가능. 조무래기는 단일 타입 팀, 간부/보스는 슬롯별 다양.",
              font=("", 9), foreground="#555", justify="left"
              ).pack(anchor="w", pady=(0, 8))

    # 대사 입력 (선택 시 타입 자동 추정) — 검색 가능 콤보로
    rkt_phrase_row = ttk.Frame(rkt_tab)
    rkt_phrase_row.pack(fill="x", pady=(0, 6))
    ttk.Label(rkt_phrase_row, text="조무래기 대사", font=("", 10, "bold")).pack(side="left", padx=(0, 6))
    rkt_phrase_var = tk.StringVar(value="")
    # 캐논 대사 목록 — 동일 대표 대사 dedupe
    _phrase_options = []
    _seen_reps = set()
    for kw, code, rep in GRUNT_PHRASES:
        if rep not in _seen_reps:
            _phrase_options.append(rep)
            _seen_reps.add(rep)
    rkt_phrase_entry = make_searchable_combo(
        rkt_phrase_row, rkt_phrase_var, _phrase_options,
        on_select=lambda: _apply_phrase(),  # 대사 선택 시 타입 추정
        width=44)
    rkt_phrase_entry.pack(side="left", padx=(0, 8))
    rkt_phrase_result = tk.StringVar(value="(드롭다운에서 선택 또는 키워드 입력: '바다', '짜릿' 등)")
    ttk.Label(rkt_phrase_row, textvariable=rkt_phrase_result,
              font=("", 9), foreground="#666").pack(side="left")

    rkt_top = ttk.Frame(rkt_tab)
    rkt_top.pack(fill="x", pady=(0, 6))
    ttk.Label(rkt_top, text="조무래기 타입", font=("", 10, "bold")).pack(side="left", padx=(0, 6))
    rkt_type_var = tk.StringVar(value=TYPE_KO["fire"])
    rkt_type_combo = make_searchable_combo(
        rkt_top, rkt_type_var, [TYPE_KO[t] for t in TYPES_ORDER],
        on_select=lambda: refresh_rocket(), width=8)
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
        value="• 조무래기 보스 능력치는 평균값 가정 (atk=200/def=180) · "
              "그림자 적은 1.2× 공격 적용 (실제와 동일)")
    ttk.Label(rkt_tab, textvariable=rkt_status_var,
              font=("", 8), foreground="#666").pack(anchor="w", pady=(4, 0))

    ttk.Label(rkt_tab,
              text="※ 간부(클리프/아르로/시에라)/보스 지오반니 라인업은 로테이션이 짧아 별도 표 없음. "
                   "특정 포켓몬에 대한 카운터가 필요하면 PvE 카운터 탭에서 좌측 포켓몬 선택 후 "
                   "「좌측 선택 포켓몬을 보스로」 체크하세요.",
              font=("", 8), foreground="#888", wraplength=900, justify="left"
              ).pack(anchor="w", pady=(8, 0))

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
        # 가상 보스: 조무래기 평균 능치 + 선택 타입 단일
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
        for i, c in enumerate(cnt, 1):
            disp = sid_to_display.get(c["sid"], c["sid"])
            tps = " · ".join(TYPE_KO.get(t, t) for t in c["pokemon"].get("types", [])
                             if t and t != "none")
            f_lbl = f"{move_ko(c['fast_id'])} ({TYPE_KO.get(c['fast_type'], c['fast_type'])})"
            c_lbl = f"{move_ko(c['charged_id'])} ({TYPE_KO.get(c['charged_type'], c['charged_type'])})"
            rkt_tree.insert("", "end", values=(
                i, disp, tps, f_lbl, c_lbl,
                f"{c['edps']:.1f}", f"{c['dps']:.1f}",
            ))
        rkt_status_var.set(
            f"• {len(cnt)}마리 표시 · 조무래기 타입={rkt_type_var.get()} · "
            f"Lv{rkt_lv_var.get()}/15·15·15 가정 · 그림자/메가 적은 그대로 사용 가능"
        )

    # rkt_type_combo 는 make_searchable_combo 가 이미 바인딩
    rkt_lv_combo.bind("<<ComboboxSelected>>", lambda e: refresh_rocket())

    rkt_phrase_pending = [None]
    def _apply_phrase():
        phrase = rkt_phrase_var.get()
        if not phrase.strip():
            rkt_phrase_result.set("(예: \"이 바다는 위험해!\" → 물 타입)")
            return
        code, rep = find_grunt_type(phrase)
        if code == "special":
            rkt_phrase_result.set("⚠ 특수 조무래기 (멀티 타입, 잠만보 등) — 타입 추정 불가")
            return
        if not code:
            rkt_phrase_result.set("⚠ 매칭 안 됨 — 대사 일부 키워드만 입력해도 됨 (예: '바다', '얼려', '짜릿')")
            return
        rkt_type_var.set(TYPE_KO[code])
        rkt_phrase_result.set(f"→ {TYPE_KO[code]} 타입 (대표: {rep})")
        refresh_rocket()
    def _on_phrase_change(*_):
        if rkt_phrase_pending[0]:
            root.after_cancel(rkt_phrase_pending[0])
        rkt_phrase_pending[0] = root.after(150, _apply_phrase)
    rkt_phrase_var.trace_add("write", _on_phrase_change)
    rkt_phrase_entry.bind("<Return>", lambda e: _apply_phrase())

    # ===== Actions =====
    last_query = [""]
    last_fav_only = [None]
    last_cat = [(None, None, None)]

    refresh_pending = [None]

    def _schedule_refresh():
        # 무거운 refresh 를 idle 콜백으로 미룸 → listbox/카운트가 먼저 그려져 즉각 반응처럼 느낌.
        if refresh_pending[0] is not None:
            try:
                root.after_cancel(refresh_pending[0])
            except Exception:
                pass
        refresh_pending[0] = root.after_idle(lambda: (refresh_pending.__setitem__(0, None), refresh()))

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
            target_sid = display_to_sid.get(filtered[0])
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(0)
            listbox.activate(0)
            # 첫 항목이 이미 화면에 그려진 포켓몬과 동일하면 refresh 스킵 (체감 즉각)
            if ranking_cache.get("_sid") == target_sid:
                return
            _schedule_refresh()

    refresh_in_flight = [False]  # 데이터 갱신 중복 실행 가드 (버튼+Ctrl-R 공유)

    def do_data_refresh():
        # 중복 실행 가드 — 버튼 비활성화는 키바인드(Ctrl-R)를 막지 못하므로 플래그로 이중 잠금.
        if refresh_in_flight[0]:
            return
        if not messagebox.askyesno("데이터 업데이트",
                                   "PvPoke 시즌 데이터 + 일정/메타/팀 데이터를 모두 다시 다운로드합니다.\n"
                                   "(인터넷 연결 필요, 약 10~30초)\n\n계속할까요?"):
            return
        refresh_in_flight[0] = True
        data_status_var.set("⟳ 갱신 중… (다운로드)")
        data_refresh_btn.configure(state="disabled")

        # 다운로드는 백그라운드 스레드에서 — UI 가 멈추지 않게.
        # 워커는 *디스크 다운로드만* 수행 (download_all_data: 전역 메모리 미변경).
        # 전역 LEAGUES/rankings 재구성은 메인 스레드(_apply_refresh_body)에서만 —
        # 700ms 폴링이 같은 전역을 읽으므로 워커가 건드리면 경쟁 상태 발생.
        def _worker():
            err = None
            try:
                download_all_data()
                # 팀 메타 — 빌트인 4리그 강제 갱신 (download_all_data 에는 없음, 전역 미변경)
                for lg in _BUILTIN_LEAGUES:
                    cap = lg.cap if lg.cap else 10000
                    try:
                        load_team_meta("all", cap, force=True)
                    except Exception as e:
                        print(f"팀메타 갱신 실패 {lg.name}: {e}")
            except Exception as e:
                err = e
            root.after(0, lambda: _apply_refresh(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_refresh(err):
        try:
            if err is not None:
                messagebox.showerror("실패", f"갱신 실패: {err}")
                update_data_status_label()
                return
            data_status_var.set("⟳ 적용 중…")
            root.update_idletasks()
            _apply_refresh_body()
        finally:
            data_refresh_btn.configure(state="normal")
            refresh_in_flight[0] = False

    def _apply_refresh_body():
        # 새 데이터 반영
        new_gm = load_gamemaster()
        state["gm"] = new_gm
        moves_by_id.clear()
        moves_by_id.update({m["moveId"]: m for m in new_gm.get("moves", [])})
        sid_to_pokemon.clear()
        sid_to_pokemon.update({p.get("speciesId"): p for p in new_gm.get("pokemon", [])})
        new_dex_to_ko = load_korean_dex_map()
        new_entries = build_display_entries(new_gm, new_dex_to_ko)
        display_to_sid.clear()
        display_to_sid.update(dict(new_entries))
        sid_to_display.clear()
        sid_to_display.update({s: d for d, s in new_entries})
        for sid, disp in build_sid_display_full(new_gm, new_dex_to_ko).items():
            sid_to_display.setdefault(sid, disp)
        all_displays_full[:] = sorted(display_to_sid.keys(), key=lambda s: s.lower())
        _rebuild_search_cache()
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
        _ranking_lru.clear()
        _ranking_lru_order.clear()

        # ───── 모든 탭 뷰 갱신 ─────
        # 일정 4탭: state reload + populate + 신선도 라벨 갱신
        try:
            raid_state["bosses"] = load_combined_raids()
            _populate_boss_combo()
            _populate_raid_sched(raid_state["bosses"])
            _update_sched_fresh()
        except Exception as e:
            print(f"레이드 일정 뷰 갱신 실패: {e}")
        try:
            events_state["data"] = load_events()
            _populate_events()
            _update_ev_fresh()
        except Exception as e:
            print(f"이벤트 뷰 갱신 실패: {e}")
        try:
            eggs_state["data"] = load_eggs()
            _populate_eggs()
            _update_eg_fresh()
        except Exception as e:
            print(f"알 뷰 갱신 실패: {e}")
        try:
            research_state["data"] = load_research()
            _populate_research()
            _update_rs_fresh()
        except Exception as e:
            print(f"리서치 뷰 갱신 실패: {e}")
        try:
            rkt_state["data"] = load_rocket_lineups()
            _populate_rocket()  # 자체 신선도 라벨 갱신 포함
        except Exception as e:
            print(f"로켓 뷰 갱신 실패: {e}")

        # PvP/PvE 뷰 갱신 — 한 탭이 깨져도 나머지는 갱신되도록 개별 보호.
        # 실패는 콘솔에 로깅(조용히 삼키면 어느 탭이 깨졌는지 진단 불가).
        for _name, _fn in (("PvP 메타", lambda: refresh_meta(force=True)),
                           ("PvP 비교", refresh_compare),
                           ("레이드 카운터", refresh_counters),
                           ("로켓", refresh_rocket),
                           ("팀 메타", lambda: _refresh_team_meta(force=False))):
            try:
                _fn()
            except Exception as e:
                print(f"{_name} 뷰 갱신 실패: {e}")

        update_data_status_label()
        update_listbox(force=True, auto_select=False)
        messagebox.showinfo("완료",
            "데이터 업데이트 완료\n"
            "• 시즌 데이터·랭킹·팀 메타·일정 4종·로켓 라인업 모두 갱신")

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

    ranking_cache = {}  # 현재 포켓몬 뷰 (sid + 리그별 결과). refresh 가 사용.

    # LRU: 최근 본 포켓몬 N개 분의 rank_all 결과 보관 — 왔다갔다 시 재계산 방지.
    # 항목 1개 = 4리그 × ~4096 IV = 16k 튜플 ≈ 0.5MB. 8개면 ~4MB.
    _ranking_lru = {}        # sid → {league_name: valid_ranked_list}
    _ranking_lru_order = []  # MRU first
    RANKING_LRU_MAX = 8

    def _get_ranking_for(sid, base):
        cached = _ranking_lru.get(sid)
        if cached is not None:
            try:
                _ranking_lru_order.remove(sid)
            except ValueError:
                pass
            _ranking_lru_order.insert(0, sid)
            return cached
        max_idx = current_max_idx()
        data = {}
        for lg in LEAGUES:
            r = rank_all(base, lg.cap, max_idx)
            data[lg.name] = [e for e in r if e[2] != -1]
        _ranking_lru[sid] = data
        _ranking_lru_order.insert(0, sid)
        while len(_ranking_lru_order) > RANKING_LRU_MAX:
            old = _ranking_lru_order.pop()
            _ranking_lru.pop(old, None)
        return data

    # ===== PvP 팀 메타 (PvPoke training/teams 데이터) — 'PvP 메타' 탭의 '팀 메타' 모드 =====
    # 별도 탭이 아니라 meta_team_container 안에 배치 (라디오 토글로 전환)
    team_meta_tab = ttk.Frame(meta_team_container, padding=(0, 0))
    team_meta_tab.pack(fill="both", expand=True)

    ttk.Label(team_meta_tab,
              text="PvPoke 메타 팀 — 8개 역할 슬롯과 각 역할의 추천 포켓몬·무브셋. "
                   "더블클릭 시 좌측 리스트 선택 + PvP 분석으로 이동. "
                   "무브 prefix: ★ 엘리트 TM · 🎉 커뮤니티 데이 · ⚔ 레이드 데이",
              font=("", 9), foreground="#555",
              justify="left", wraplength=1000).pack(anchor="w", pady=(0, 6))

    tm_top = ttk.Frame(team_meta_tab)
    tm_top.pack(fill="x", pady=(0, 6))

    ttk.Label(tm_top, text="리그:", font=("", 10, "bold")).pack(side="left")
    tm_league_var = tk.StringVar(value="슈퍼리그")
    _TM_LEAGUE_CAPS = {"슈퍼리그": 1500, "하이퍼리그": 2500, "마스터리그": 10000}
    tm_league_combo = ttk.Combobox(tm_top, textvariable=tm_league_var,
                                   values=list(_TM_LEAGUE_CAPS.keys()),
                                   width=10, state="readonly")
    tm_league_combo.pack(side="left", padx=(6, 12))
    tm_league_combo.bind("<<ComboboxSelected>>", lambda e: _refresh_team_meta())

    ttk.Button(tm_top, text="갱신", width=8,
               command=lambda: _refresh_team_meta(force=True)).pack(side="right")
    tm_fresh_lbl = ttk.Label(tm_top, text="", font=("", 8))
    tm_fresh_lbl.pack(side="right", padx=(0, 10))

    tm_frame = ttk.Frame(team_meta_tab)
    tm_frame.pack(fill="both", expand=True)
    tm_scroll = ttk.Scrollbar(tm_frame, orient="vertical")
    tm_scroll.pack(side="right", fill="y")
    tm_tree = ttk.Treeview(tm_frame,
                           columns=("slot", "role", "synergy", "pokemon",
                                    "fast", "charged", "weight"),
                           show="headings", height=22, selectmode="browse",
                           yscrollcommand=tm_scroll.set)
    for c, h, w in [("slot", "#", 30), ("role", "역할", 130),
                    ("synergy", "시너지", 120), ("pokemon", "포켓몬", 200),
                    ("fast", "빠른공격", 130), ("charged", "차지공격", 240),
                    ("weight", "선택률", 70)]:
        tm_tree.heading(c, text=h,
                        command=lambda col=c: _sort_tree(tm_tree, col))
        tm_tree.column(c, width=w,
                       anchor="w" if c in ("role", "synergy", "pokemon",
                                            "fast", "charged") else "center")
    tm_tree.pack(side="left", fill="both", expand=True)
    tm_scroll.config(command=tm_tree.yview)
    tm_tree.tag_configure("slot_head", background="#eef0f5",
                          foreground="#333", font=("", 9, "bold"))
    tm_tree.tag_configure("top_pick",  background="#fff9dd")

    def _refresh_team_meta(force=False):
        for r in tm_tree.get_children():
            tm_tree.delete(r)
        cap = _TM_LEAGUE_CAPS.get(tm_league_var.get(), 1500)
        try:
            slots = load_team_meta("all", cap, force=force)
        except Exception as e:
            print(f"메타 팀 로드 실패: {e}")
            slots = []
        # 신선도
        path = _team_meta_cache_path("all", cap)
        txt, c = _freshness_label(path, "갱신: ")
        tm_fresh_lbl.configure(text=txt, foreground=c)
        if not slots:
            tm_tree.insert("", "end",
                           values=("", "(데이터 없음)", "", "", "", "", ""),
                           tags=("slot_head",))
            return
        # 무브 획득 표시용 sid → gamemaster pokemon 인덱스
        gm_by_sid = {p.get("speciesId"): p for p in state["gm"].get("pokemon", [])}

        def _move_with_acq(gm_p, move_id, elite_set):
            """무브 한글명 + 획득 카테고리 prefix (★/🎉/⚔)."""
            if not move_id:
                return ""
            name = prettify_move(move_id, move_ko_map)
            if not gm_p:
                return name
            acq = move_acquisition(gm_p, move_id, elite_set)
            if acq == "elite":  return f"★ {name}"
            if acq == "cd":     return f"🎉 {name}"
            if acq == "raid":   return f"⚔ {name}"
            return name

        # PvPoke gamemaster 의 speciesId → 한글 display
        for idx, slot in enumerate(slots, start=1):
            role_en = slot.get("slot", "?")
            role = tm_label_ko(role_en)
            # 영문이 매칭 안 됐으면 원문 병기, 매칭됐으면 한글만
            if role != role_en:
                role_disp = f"{role} ({role_en})"
            else:
                role_disp = role
            synergies = slot.get("synergies", []) or []
            syn_str = ", ".join(tm_label_ko(s) for s in synergies[:3])
            poks = slot.get("pokemon", []) or []
            # 슬롯 헤더 행
            tm_tree.insert("", "end",
                           values=(f"#{idx}", role_disp, syn_str,
                                   f"({len(poks)}종 후보)", "", "", ""),
                           tags=("slot_head",),
                           text="")
            # 가중치 합 → 백분율
            total_w = sum(p.get("weight", 0) for p in poks) or 1
            # 가중치 큰 순 정렬
            for p in sorted(poks, key=lambda x: -x.get("weight", 0)):
                sid = p.get("speciesId", "")
                disp = sid_to_display.get(sid, sid)
                gm_p = gm_by_sid.get(sid)
                elite_set = set(gm_p.get("eliteMoves") or []) if gm_p else set()
                fast = _move_with_acq(gm_p, p.get("fastMove", ""), elite_set)
                charged = " / ".join(_move_with_acq(gm_p, m, elite_set)
                                     for m in (p.get("chargedMoves") or [])[:2])
                w = p.get("weight", 0)
                pct = f"{w/total_w*100:.0f}%"
                tag = "top_pick" if w / total_w >= 0.25 else ""
                tm_tree.insert("", "end",
                               values=("", "", "", disp, fast, charged, pct),
                               tags=(tag,) if tag else (),
                               text=sid)

    def _on_team_meta_double(_e=None):
        sel = tm_tree.selection()
        if not sel: return
        sid = tm_tree.item(sel[0], "text")
        if not sid: return  # 슬롯 헤더
        disp = sid_to_display.get(sid)
        if not disp: return
        try:
            select_pokemon_by_display(disp)
            notebook.select(iv_tab)
        except Exception:
            pass
    tm_tree.bind("<Double-Button-1>", _on_team_meta_double)
    _refresh_team_meta()

    # ===== 신규 일정 탭들의 공용 헬퍼 =====
    def _en_to_display(en_name):
        """영어 포켓몬 이름 → 한글 display명 (실패 시 영문 그대로)."""
        if not en_name:
            return ""
        p = find_boss_pokemon(en_name, state["gm"])
        if p:
            return sid_to_display.get(p["speciesId"], en_name)
        return en_name

    def _format_iso_short(iso_str):
        """ISO 8601 문자열 → 'MM/DD HH:mm' (실패 시 원문 앞 16자)."""
        if not iso_str:
            return ""
        try:
            from datetime import datetime
            s = iso_str.replace("Z", "").split(".")[0]
            dt = datetime.fromisoformat(s)
            return dt.strftime("%m/%d %H:%M")
        except Exception:
            return iso_str[:16]

    def _translate_event_name(name):
        """이벤트 영문 이름 → 한글. 반복 패턴(커뮤니티 데이/스포트라이트/레이드류 등)만
        규칙 번역하고, 포켓몬 이름은 _en_to_display 로 변환. 매칭 실패 시 영문 그대로."""
        if not name:
            return name
        s = name.strip()

        def _ko1(p):
            return _en_to_display(p.strip()) or p.strip()

        def _ko_multi(seg):
            parts = [p for p in re.split(r",\s*|\s+and\s+", seg) if p.strip()]
            return " · ".join(_ko1(p) for p in parts)

        rules = [
            (r"^(.+?) Community Day(?: Classic)?$", lambda m: f"{_ko_multi(m.group(1))} 커뮤니티 데이"),
            (r"^(.+?) Spotlight Hour$", lambda m: f"{_ko_multi(m.group(1))} 스포트라이트 아워"),
            (r"^Mega (.+?) (?:in )?Mega Raids?$", lambda m: f"메가 레이드: 메가 {_ko1(m.group(1))}"),
            (r"^(.+?) in Mega Raids?$", lambda m: f"메가 레이드: {_ko_multi(m.group(1))}"),
            (r"^Shadow (.+?) (?:in )?Shadow Raids?$", lambda m: f"그림자 레이드: 그림자 {_ko1(m.group(1))}"),
            (r"^(.+?) in Shadow Raids?$", lambda m: f"그림자 레이드: {_ko_multi(m.group(1))}"),
            (r"^(.+?) in (\d+)-star Raid Battles?$", lambda m: f"{m.group(2)}성 레이드: {_ko_multi(m.group(1))}"),
            (r"^(.+?) in Raid Battles?$", lambda m: f"레이드: {_ko_multi(m.group(1))}"),
            (r"^(.+?) Super Mega Raid Day$", lambda m: f"{_ko_multi(m.group(1))} 슈퍼 메가 레이드 데이"),
            (r"^(.+?) Raid Day$", lambda m: f"{_ko_multi(m.group(1))} 레이드 데이"),
            (r"^(.+?) Raid Hour$", lambda m: f"{_ko_multi(m.group(1))} 레이드 아워"),
            (r"^(.+?) Raid Weekend$", lambda m: f"{_ko_multi(m.group(1))} 레이드 주말"),
            (r"^Gigantamax (.+?) during Max Monday$", lambda m: f"맥스 먼데이: 거다이맥스 {_ko1(m.group(1))}"),
            (r"^Dynamax (.+?) during Max Monday$", lambda m: f"맥스 먼데이: 다이맥스 {_ko1(m.group(1))}"),
            (r"^Gigantamax (.+)$", lambda m: f"거다이맥스 {_ko_multi(m.group(1))}"),
            (r"^Dynamax (.+)$", lambda m: f"다이맥스 {_ko_multi(m.group(1))}"),
            (r"^Choose Your Path: (.+)$", lambda m: f"갈림길: {m.group(1)}"),
        ]
        for pat, fn in rules:
            mm = re.match(pat, s)
            if mm:
                try:
                    return fn(mm)
                except Exception:
                    break

        # GBL 리그 로테이션 등 — 패턴 미매칭 시 리그/시즌 키워드만 부분 치환.
        # (컵 고유명은 영문 유지) 길이 긴 항목부터 치환해야 중복 매칭을 피한다.
        if "League" in s or "Forever Forward" in s:
            out = s
            for en, ko in (
                ("Master League: Mega Edition", "마스터 리그: 메가 버전"),
                ("Great League Edition", "그레이트 리그 버전"),
                ("Ultra League Edition", "울트라 리그 버전"),
                ("Master League", "마스터 리그"),
                ("Great League", "그레이트 리그"),
                ("Ultra League", "울트라 리그"),
                ("Master Premier", "마스터 프리미어"),
                ("Mega Edition", "메가 버전"),
                ("Forever Forward", "영원한 전진"),
            ):
                out = out.replace(en, ko)
            out = out.replace(", and ", " · ").replace(" and ", " · ").replace(", ", " · ")
            return out
        return name

    # ===== Tab: PvE 투자 추천 (타입별 범용 딜러 랭킹 + 즐겨찾기 투자 우선순위) =====
    invest_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(invest_tab, text="  PvE 투자  ")

    inv_cache = {}  # (level, shadow, mega, legend) → all_type_attacker_rankings 결과

    def _inv_rankings(level, shadow, mega, legend):
        key = (level, shadow, mega, legend)
        if key not in inv_cache:
            inv_cache[key] = all_type_attacker_rankings(
                state["gm"], moves_by_id, level, shadow, mega, legend)
        return inv_cache[key]

    inv_top = ttk.Frame(invest_tab)
    inv_top.pack(fill="x", pady=(0, 6))

    inv_mode_var = tk.StringVar(value="type")
    ttk.Radiobutton(inv_top, text="타입별 딜러", value="type",
                    variable=inv_mode_var,
                    command=lambda: _inv_refresh()).pack(side="left")
    ttk.Radiobutton(inv_top, text="내 즐겨찾기 투자", value="fav",
                    variable=inv_mode_var,
                    command=lambda: _inv_refresh()).pack(side="left", padx=(6, 16))

    inv_type_lbl = ttk.Label(inv_top, text="타입", font=("", 10, "bold"))
    inv_type_lbl.pack(side="left")
    inv_type_var = tk.StringVar(value=TYPE_KO["fire"])
    inv_type_combo = make_searchable_combo(
        inv_top, inv_type_var, [TYPE_KO[t] for t in TYPES_ORDER if t != "normal"],
        on_select=lambda: _inv_refresh(), width=8, height=20)
    inv_type_combo.pack(side="left", padx=(6, 16))

    ttk.Label(inv_top, text="공격자 Lv", font=("", 10, "bold")).pack(side="left", padx=(0, 4))
    inv_lv_var = tk.StringVar(value="40")
    inv_lv_combo = ttk.Combobox(inv_top, textvariable=inv_lv_var,
                                values=["40", "45", "50", "51"], width=5,
                                state="readonly")
    inv_lv_combo.pack(side="left", padx=(0, 16))
    inv_lv_combo.bind("<<ComboboxSelected>>", lambda e: _inv_refresh())

    inv_filter_row = ttk.Frame(invest_tab)
    inv_filter_row.pack(fill="x", pady=(0, 6))
    ttk.Label(inv_filter_row, text="포함:", font=("", 9), foreground="#555"
              ).pack(side="left", padx=(0, 6))
    inv_inc_mega   = tk.BooleanVar(value=True)
    inv_inc_shadow = tk.BooleanVar(value=True)
    inv_inc_legend = tk.BooleanVar(value=True)
    for txt, var in (("메가", inv_inc_mega), ("그림자", inv_inc_shadow),
                     ("전설/환상", inv_inc_legend)):
        ttk.Checkbutton(inv_filter_row, text=txt, variable=var,
                        command=lambda: _inv_refresh()).pack(side="left", padx=(0, 8))
    ttk.Label(inv_filter_row, text="행 더블클릭 → PvP 분석으로 이동",
              font=("", 8), foreground="#888").pack(side="right")

    inv_info_var = tk.StringVar(value="")
    ttk.Label(invest_tab, textvariable=inv_info_var, font=("", 9),
              foreground="#444", justify="left", wraplength=1000
              ).pack(anchor="w", pady=(0, 4))

    inv_table_frame = ttk.Frame(invest_tab)
    inv_table_frame.pack(fill="both", expand=True)
    inv_scroll = ttk.Scrollbar(inv_table_frame, orient="vertical")
    inv_scroll.pack(side="right", fill="y")
    inv_tree = ttk.Treeview(inv_table_frame, show="headings",
                            yscrollcommand=inv_scroll.set, height=22)
    inv_tree.pack(side="left", fill="both", expand=True)
    inv_scroll.config(command=inv_tree.yview)

    def _inv_on_double(_e=None):
        """행 더블클릭 → 좌측 리스트에서 그 포켓몬 선택 + PvP 분석 탭으로 이동."""
        sel = inv_tree.selection()
        if not sel:
            return
        disp = inv_tree.set(sel[0], "name")
        if disp:
            select_pokemon_by_display(disp)
            notebook.select(iv_tab)
    inv_tree.bind("<Double-1>", _inv_on_double)

    inv_cols_type = ("rank", "name", "types", "fast", "charged", "dps", "edps", "tdo")
    inv_labels_type = ["#", "포켓몬", "타입", "속공", "차지", "DPS", "eDPS", "TDO"]
    inv_widths_type = [40, 170, 110, 130, 140, 70, 70, 80]
    inv_cols_fav = ("name", "role", "rank", "dps", "edps", "grade")
    inv_labels_fav = ["포켓몬", "역할(타입)", "타입내 순위", "DPS", "eDPS", "등급"]
    inv_widths_fav = [180, 100, 110, 70, 70, 110]

    def _inv_set_columns(cols, labels, widths):
        inv_tree.config(columns=cols)
        for c, l, w in zip(cols, labels, widths):
            inv_tree.heading(c, text=l,
                             command=lambda col=c: _sort_tree(inv_tree, col))
            anchor = "w" if c in ("name", "fast", "charged") else "center"
            inv_tree.column(c, width=w, anchor=anchor)

    def _inv_grade(pct):
        if pct <= 5:
            return "★★★ 최우선"
        if pct <= 15:
            return "★★ 우선"
        if pct <= 35:
            return "★ 쓸만함"
        return "— 비주력"

    def _inv_refresh():
        for r in inv_tree.get_children():
            inv_tree.delete(r)
        try:
            level = float(inv_lv_var.get())
        except ValueError:
            level = 40.0
        shadow, mega, legend = (inv_inc_shadow.get(), inv_inc_mega.get(),
                                inv_inc_legend.get())
        mode = inv_mode_var.get()
        # 타입 선택 위젯은 타입 모드에서만 의미 있음
        show_type = (mode == "type")
        for w in (inv_type_lbl, inv_type_combo):
            try:
                w.configure(state=("normal" if show_type else "disabled"))
            except tk.TclError:
                pass
        if mode == "type":
            _inv_set_columns(inv_cols_type, inv_labels_type, inv_widths_type)
            atype = _TYPE_KO_TO_EN.get(inv_type_var.get(), "fire")
            ranks = _inv_rankings(level, shadow, mega, legend)
            rows = ranks.get(atype, [])[:50]
            inv_info_var.set(
                f"▶ {TYPE_KO.get(atype, atype)} 타입 범용 PvE 딜러 — "
                f"'그 타입에 약점인 보스' 기준 DPS 순. 키울 가치 큰 딜러 가이드 "
                f"(Lv{level:g}). 전설/메가 제외하면 현실적 후보만.")
            for i, r in enumerate(rows, 1):
                disp = sid_to_display.get(r["sid"], r["sid"])
                tps = " · ".join(TYPE_KO.get(t, t) for t in r["pokemon"].get("types", [])
                                 if t and t != "none")
                ftype = TYPE_KO.get(r.get("fast_type", ""), "")
                ctype = TYPE_KO.get(r.get("charged_type", ""), "")
                inv_tree.insert("", "end", values=(
                    i, disp, tps,
                    f"{move_ko(r['fast_id'])} ({ftype})",
                    f"{move_ko(r['charged_id'])} ({ctype})",
                    f"{r['dps']:.1f}", f"{r['edps']:.1f}", f"{r['tdo']:.0f}"))
            if not rows:
                inv_info_var.set("해당 타입 딜러 없음 — 필터를 완화해보세요.")
        else:
            _inv_set_columns(inv_cols_fav, inv_labels_fav, inv_widths_fav)
            if not favorites:
                inv_info_var.set("즐겨찾기가 비어 있습니다. 좌측에서 ★ 로 보유/관심 "
                                 "포켓몬을 등록하면 PvE 투자 우선순위를 매겨드립니다.")
                return
            ranks = _inv_rankings(level, shadow, mega, True)  # 투자는 전설 포함 비교
            res = investment_priority(state["gm"], moves_by_id, favorites,
                                      attacker_level=level, rankings=ranks)
            inv_info_var.set(
                f"▶ 즐겨찾기 {len(favorites)}마리의 PvE 투자 우선순위 — 각자의 최고 "
                f"화력 역할(타입)과 그 타입 전체 딜러 중 순위. 상위권(★)일수록 키울 "
                f"가치 큼 (Lv{level:g}).")
            for r in res:
                disp = sid_to_display.get(r["sid"], r["sid"])
                inv_tree.insert("", "end", values=(
                    disp, TYPE_KO.get(r["type"], r["type"]),
                    f"#{r['rank']}/{r['total']}",
                    f"{r['dps']:.1f}", f"{r['edps']:.1f}",
                    _inv_grade(r["percentile"])))

    _inv_refresh()

    _sort_state = {}  # tree id → (col, descending)

    def _sort_tree(tree, col):
        """heading 클릭 시 컬럼 정렬 (숫자/날짜/문자열 자동 판단)."""
        key = id(tree)
        prev_col, prev_desc = _sort_state.get(key, (None, False))
        desc = (col == prev_col) and (not prev_desc)
        _sort_state[key] = (col, desc)
        items = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        def _key(pair):
            v = pair[0]
            # 'min~max' CP 범위 → max 기준
            if "~" in v:
                tail = v.split("~")[-1]
                try: return (0, float(tail))
                except ValueError: pass
            try: return (0, float(v))
            except ValueError: pass
            return (1, v.lower())
        items.sort(key=_key, reverse=desc)
        for idx, (_, iid) in enumerate(items):
            tree.move(iid, "", idx)

    def _jump_to_pokemon_by_en(en_name):
        """영어 이름의 포켓몬을 좌측 리스트박스에서 선택 + PvP 분석 탭으로 이동."""
        p = find_boss_pokemon(en_name, state["gm"])
        if not p:
            return False
        sid = p["speciesId"]
        disp = sid_to_display.get(sid)
        if not disp:
            return False
        try:
            select_pokemon_by_display(disp)
            notebook.select(iv_tab)
            return True
        except Exception:
            return False

    # ===== Tab: 레이드 일정 =====
    raid_sched_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(raid_sched_tab, text="  레이드 일정  ")

    sched_top = ttk.Frame(raid_sched_tab)
    sched_top.pack(fill="x", pady=(0, 6))
    ttk.Label(sched_top, text="현재 활성 레이드 보스 — 더블클릭 시 PvE 카운터로 이동",
              font=("", 9), foreground="#555").pack(side="left")
    ttk.Button(sched_top, text="갱신", width=8,
               command=lambda: _reload_raid_sched()).pack(side="right")
    sched_fresh_lbl = ttk.Label(sched_top, text="", font=("", 8))
    sched_fresh_lbl.pack(side="right", padx=(0, 10))

    def _update_sched_fresh():
        g_txt, _ = _freshness_label(CACHE_RAIDS, "🌐 ")
        k_txt, _ = _freshness_label(CACHE_KR_RAIDS, "🇰🇷 ")
        # 둘 중 더 오래된 것 기준 색상
        import os.path as _op, time as _t
        ages = [_t.time() - _op.getmtime(p) for p in (CACHE_RAIDS, CACHE_KR_RAIDS) if _op.exists(p)]
        max_age = max(ages) if ages else float("inf")
        if max_age < 86400:  c = "#666"
        elif max_age < 604800: c = "#c80"
        else: c = "#a00"
        sched_fresh_lbl.configure(text=f"{g_txt} · {k_txt}", foreground=c)

    ttk.Label(raid_sched_tab,
              text="ℹ 글로벌(LeekDuck) + 한국(pogomate.com) 통합 표시. "
                   "출처 컬럼: 🌐 글로벌만 · 🇰🇷 한국만 · ✓ 양쪽 동일. "
                   "양쪽 모두 1일마다 자동 갱신, 지금 받으려면 [갱신] 클릭.",
              font=("", 8), foreground="#444",
              justify="left", wraplength=1000).pack(anchor="w", pady=(0, 4))

    raid_sched_frame = ttk.Frame(raid_sched_tab)
    raid_sched_frame.pack(fill="both", expand=True)
    raid_sched_scroll = ttk.Scrollbar(raid_sched_frame, orient="vertical")
    raid_sched_scroll.pack(side="right", fill="y")
    raid_sched_tree = ttk.Treeview(raid_sched_frame,
                                   columns=("source", "tier", "name", "types", "cp", "shiny", "period"),
                                   show="headings", height=22, selectmode="browse",
                                   yscrollcommand=raid_sched_scroll.set)
    for c, h, w in [("source", "출처", 60), ("tier", "티어", 90),
                    ("name", "포켓몬", 220), ("types", "타입", 110),
                    ("cp", "CP 범위", 100), ("shiny", "색이다른", 70),
                    ("period", "기간(한국)", 220)]:
        raid_sched_tree.heading(c, text=h,
                                command=lambda col=c: _sort_tree(raid_sched_tree, col))
        raid_sched_tree.column(c, width=w,
                               anchor="w" if c in ("name", "period") else "center")
    raid_sched_tree.pack(side="left", fill="both", expand=True)
    raid_sched_scroll.config(command=raid_sched_tree.yview)
    raid_sched_tree.tag_configure("legendary",  background="#fff4e0")
    raid_sched_tree.tag_configure("mega",       background="#f0e0ff")
    raid_sched_tree.tag_configure("shadow",     background="#e0e0e0")
    raid_sched_tree.tag_configure("korea_only", background="#e0f0ff")  # 한국 한정

    def _reload_raid_sched():
        for r in raid_sched_tree.get_children():
            raid_sched_tree.delete(r)
        try:
            bosses = load_combined_raids(force=True)
            raid_state["bosses"] = bosses
            _populate_raid_sched(bosses)
        except Exception as e:
            print(f"레이드 일정 갱신 실패: {e}")
        _update_sched_fresh()

    def _populate_raid_sched(bosses):
        for r in raid_sched_tree.get_children():
            raid_sched_tree.delete(r)
        order = {"5-star": 0, "Mega": 1, "Elite": 1, "Shadow": 2,
                 "3-star": 3, "1-star": 4}
        # 출처 우선순위: 양쪽(✓) > 한국(🇰🇷) > 글로벌(🌐)
        src_order = {"global+kr": 0, "kr": 1, "global": 2}
        def key(b):
            t = (b.get("tier") or "").lower()
            t_rank = 9
            for k, v in order.items():
                if k.lower() in t:
                    t_rank = v; break
            return (src_order.get(b.get("_source", "global"), 9),
                    t_rank, b.get("name", ""))
        for b in sorted(bosses, key=key):
            tier_raw = b.get("tier", "") or ""
            tl = tier_raw.lower()
            if "5-star" in tl: tier_ko, tag = "5★ 전설", "legendary"
            elif "mega" in tl: tier_ko, tag = "메가", "mega"
            elif "shadow" in tl: tier_ko, tag = "그림자", "shadow"
            elif "elite" in tl: tier_ko, tag = "엘리트", "mega"
            elif "3-star" in tl: tier_ko, tag = "3★", ""
            elif "1-star" in tl: tier_ko, tag = "1★", ""
            else: tier_ko, tag = tier_raw, ""

            src = b.get("_source", "global")
            if src == "global+kr": src_label = "✓"
            elif src == "kr":      src_label = "🇰🇷"; tag = "korea_only"
            else:                  src_label = "🌐"

            en_name = b.get("name", "?")
            # 한국 데이터에 한국명이 있으면 우선 사용
            ko = b.get("_name_ko") or _en_to_display(en_name)
            types_raw = b.get("types", []) or []
            type_names = [(t.get("name") if isinstance(t, dict) else t) or "" for t in types_raw]
            type_str = " · ".join(TYPE_KO.get(n.lower(), n) for n in type_names if n)
            cp = b.get("combatPower", {}) or {}
            normal = cp.get("normal", {}) or {}
            cp_min = normal.get("min") or cp.get("min") or "-"
            cp_max = normal.get("max") or cp.get("max") or "-"
            cp_str = f"{cp_min}~{cp_max}" if cp_min != "-" else "-"
            shiny = "○" if b.get("canBeShiny") else ""
            period = b.get("_period", "")
            raid_sched_tree.insert("", "end",
                                   values=(src_label, tier_ko, ko, type_str,
                                           cp_str, shiny, period),
                                   tags=(tag,) if tag else (),
                                   text=en_name)

    def _on_raid_sched_double(_e=None):
        sel = raid_sched_tree.selection()
        if not sel:
            return
        en_name = raid_sched_tree.item(sel[0], "text")
        # 좌측 리스트 + iv 탭으로 점프
        if not _jump_to_pokemon_by_en(en_name):
            # 매칭 안 되면 PvE 카운터 탭으로만 이동
            notebook.select(raid_tab)
            return
        notebook.select(raid_tab)

    raid_sched_tree.bind("<Double-Button-1>", _on_raid_sched_double)
    _populate_raid_sched(raid_state.get("bosses", []))
    _update_sched_fresh()

    # ===== Tab: 이벤트 캘린더 =====
    events_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(events_tab, text="  이벤트  ")

    events_state = {"data": [], "filter": "all"}

    ev_top = ttk.Frame(events_tab)
    ev_top.pack(fill="x", pady=(0, 6))
    ttk.Label(ev_top, text="포켓몬 GO 이벤트 일정 (LeekDuck mirror)",
              font=("", 9), foreground="#555").pack(side="left")

    ev_filter_var = tk.StringVar(value="진행/예정")
    ev_filter_combo = ttk.Combobox(ev_top, textvariable=ev_filter_var,
                                   values=["진행/예정", "진행 중", "예정", "전체"],
                                   width=10, state="readonly")
    ev_filter_combo.pack(side="left", padx=(12, 4))
    ev_filter_combo.bind("<<ComboboxSelected>>", lambda e: _populate_events())

    ttk.Button(ev_top, text="갱신", width=8,
               command=lambda: _reload_events()).pack(side="right")
    ev_fresh_lbl = ttk.Label(ev_top, text="", font=("", 8))
    ev_fresh_lbl.pack(side="right", padx=(0, 10))

    def _update_ev_fresh():
        txt, c = _freshness_label(CACHE_EVENTS)
        ev_fresh_lbl.configure(text=f"갱신: {txt}", foreground=c)

    ev_frame = ttk.Frame(events_tab)
    ev_frame.pack(fill="both", expand=True)
    ev_scroll = ttk.Scrollbar(ev_frame, orient="vertical")
    ev_scroll.pack(side="right", fill="y")
    ev_tree = ttk.Treeview(ev_frame,
                           columns=("start", "end", "type", "name"),
                           show="headings", height=22, selectmode="browse",
                           yscrollcommand=ev_scroll.set)
    for c, h, w in [("start", "시작", 110), ("end", "종료", 110),
                    ("type", "종류", 130), ("name", "이벤트", 540)]:
        ev_tree.heading(c, text=h,
                        command=lambda col=c: _sort_tree(ev_tree, col))
        ev_tree.column(c, width=w, anchor="w" if c == "name" else "center")
    ev_tree.pack(side="left", fill="both", expand=True)
    ev_scroll.config(command=ev_tree.yview)
    ev_tree.tag_configure("active",  background="#e0ffe0")
    ev_tree.tag_configure("soon",    background="#fffadf")
    ev_tree.tag_configure("past",    foreground="#999")

    ev_detail_var = tk.StringVar(value="")
    ttk.Label(events_tab, textvariable=ev_detail_var,
              font=("", 9), foreground="#444",
              justify="left", wraplength=1000).pack(anchor="w", fill="x", pady=(6, 0))

    EVENT_TYPE_KO = {
        "community-day": "커뮤니티 데이",
        "choose-your-path": "갈림길",
        "max-mondays": "맥스 먼데이",
        "max-monday": "맥스 먼데이",
        "raid-battles": "레이드",
        "raid-hour": "레이드 아워",
        "raid-day": "레이드 데이",
        "raid-weekend": "레이드 주말",
        "pokemon-spotlight-hour": "스포트라이트 아워",
        "research": "리서치",
        "timed-research": "시간제한 리서치",
        "research-breakthrough": "리서치 돌파",
        "go-battle-league": "GO 배틀 리그",
        "pokemon-go-fest": "GO Fest",
        "ticketed-event": "유료 이벤트",
        "event": "일반 이벤트",
        "season": "시즌",
        "go-pass": "GO 패스",
        "live-event": "오프라인 이벤트",
        "global-challenge": "글로벌 챌린지",
        "update": "업데이트",
    }

    def _reload_events():
        try:
            events_state["data"] = load_events(force=True)
        except Exception as e:
            print(f"이벤트 갱신 실패: {e}")
        _populate_events()
        _update_ev_fresh()

    def _populate_events():
        for r in ev_tree.get_children():
            ev_tree.delete(r)
        from datetime import datetime
        now = datetime.now()
        filt = ev_filter_var.get()
        rows = []
        for ev in events_state["data"]:
            start_iso = ev.get("start") or ""
            end_iso = ev.get("end") or ""
            try:
                start_dt = datetime.fromisoformat(start_iso.replace("Z", "").split(".")[0]) if start_iso else None
            except Exception:
                start_dt = None
            try:
                end_dt = datetime.fromisoformat(end_iso.replace("Z", "").split(".")[0]) if end_iso else None
            except Exception:
                end_dt = None
            # 상태 판정
            if start_dt and end_dt:
                if end_dt < now: status = "past"
                elif start_dt <= now <= end_dt: status = "active"
                else: status = "soon"
            elif start_dt:
                status = "active" if start_dt <= now else "soon"
            else:
                status = "active"
            # 필터
            if filt == "진행 중" and status != "active": continue
            if filt == "예정" and status != "soon": continue
            if filt == "진행/예정" and status == "past": continue
            rows.append((start_dt or datetime.max, ev, status))
        rows.sort(key=lambda x: x[0])
        for _, ev, status in rows:
            et = ev.get("eventType", "") or ""
            type_ko = EVENT_TYPE_KO.get(et, et)
            ev_tree.insert("", "end",
                           values=(_format_iso_short(ev.get("start")),
                                   _format_iso_short(ev.get("end")),
                                   type_ko,
                                   _translate_event_name(ev.get("name", ""))),
                           tags=(status,),
                           text=ev.get("eventID", ""))

    def _on_event_select(_e=None):
        sel = ev_tree.selection()
        if not sel:
            ev_detail_var.set("")
            return
        eid = ev_tree.item(sel[0], "text")
        ev = next((e for e in events_state["data"] if e.get("eventID") == eid), None)
        if not ev:
            ev_detail_var.set("")
            return
        parts = []
        if ev.get("heading"):
            parts.append(f"📌 {ev['heading']}")
        extra = ev.get("extraData") or {}
        # community-day spawns
        cd = extra.get("communityday") or {}
        spawns = cd.get("spawns") or []
        if spawns:
            names = [_en_to_display(s.get("name", "")) for s in spawns[:5]]
            parts.append(f"🎉 출현: {', '.join(n for n in names if n)}")
        bonuses = cd.get("bonuses") or []
        if bonuses:
            parts.append(f"보너스: {' · '.join(str(b.get('text', b)) for b in bonuses[:4])}")
        # raid bosses
        rb = extra.get("raidbattles") or {}
        rbosses = rb.get("bosses") or []
        if rbosses:
            names = [_en_to_display(b.get("name", "")) for b in rbosses[:6]]
            parts.append(f"⚔ 보스: {', '.join(n for n in names if n)}")
        # generic spawns
        gen = extra.get("generic") or {}
        if gen.get("hasSpawns"):
            parts.append("• 야생 스폰 증가")
        if gen.get("hasFieldResearchTasks"):
            parts.append("• 시간제한 필드 리서치")
        if ev.get("link"):
            parts.append(f"🔗 {ev['link']}")
        ev_detail_var.set("    ".join(parts) if parts else "(추가 정보 없음)")

    def _on_event_double(_e=None):
        """이벤트의 첫 출현/보스 포켓몬을 좌측 리스트에서 선택."""
        sel = ev_tree.selection()
        if not sel: return
        eid = ev_tree.item(sel[0], "text")
        ev = next((e for e in events_state["data"] if e.get("eventID") == eid), None)
        if not ev: return
        extra = ev.get("extraData") or {}
        candidates = []
        cd = extra.get("communityday") or {}
        for s in (cd.get("spawns") or []):
            if s.get("name"):
                candidates.append(s["name"])
        rb = extra.get("raidbattles") or {}
        for b in (rb.get("bosses") or []):
            if b.get("name"):
                candidates.append(b["name"])
        for en in candidates:
            if _jump_to_pokemon_by_en(en):
                return

    ev_tree.bind("<<TreeviewSelect>>", _on_event_select)
    ev_tree.bind("<Double-Button-1>", _on_event_double)

    # ===== Tab: 알 부화 풀 =====
    eggs_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(eggs_tab, text="  알 부화  ")

    eggs_state = {"data": []}

    eg_top = ttk.Frame(eggs_tab)
    eg_top.pack(fill="x", pady=(0, 6))
    ttk.Label(eg_top,
              text="거리별 알 부화 풀 — 더블클릭 시 좌측 선택 + PvP 분석 이동",
              font=("", 9), foreground="#555").pack(side="left")

    eg_filter_var = tk.StringVar(value="전체")
    eg_filter_combo = ttk.Combobox(eg_top, textvariable=eg_filter_var,
                                   values=["전체", "1 km", "2 km", "5 km",
                                           "7 km", "10 km", "12 km"],
                                   width=8, state="readonly")
    eg_filter_combo.pack(side="left", padx=(12, 4))
    eg_filter_combo.bind("<<ComboboxSelected>>", lambda e: _populate_eggs())

    eg_shiny_only_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(eg_top, text="색이 다른 가능만",
                    variable=eg_shiny_only_var,
                    command=lambda: _populate_eggs()).pack(side="left", padx=(8, 4))

    ttk.Button(eg_top, text="갱신", width=8,
               command=lambda: _reload_eggs()).pack(side="right")
    eg_fresh_lbl = ttk.Label(eg_top, text="", font=("", 8))
    eg_fresh_lbl.pack(side="right", padx=(0, 10))

    def _update_eg_fresh():
        txt, c = _freshness_label(CACHE_EGGS)
        eg_fresh_lbl.configure(text=f"갱신: {txt}", foreground=c)

    eg_frame = ttk.Frame(eggs_tab)
    eg_frame.pack(fill="both", expand=True)
    eg_scroll = ttk.Scrollbar(eg_frame, orient="vertical")
    eg_scroll.pack(side="right", fill="y")
    eg_tree = ttk.Treeview(eg_frame,
                           columns=("dist", "name", "cp", "shiny", "flags"),
                           show="headings", height=22, selectmode="browse",
                           yscrollcommand=eg_scroll.set)
    for c, h, w in [("dist", "거리", 80), ("name", "포켓몬", 280),
                    ("cp", "CP 범위", 120), ("shiny", "색이다른", 80),
                    ("flags", "특이사항", 240)]:
        eg_tree.heading(c, text=h,
                        command=lambda col=c: _sort_tree(eg_tree, col))
        eg_tree.column(c, width=w, anchor="w" if c in ("name", "flags") else "center")
    eg_tree.pack(side="left", fill="both", expand=True)
    eg_scroll.config(command=eg_tree.yview)
    eg_tree.tag_configure("adv",     background="#e8e8ff")  # 모험 모드
    eg_tree.tag_configure("gift",    background="#fff0f0")  # 선물
    eg_tree.tag_configure("regional", background="#fff8d0")  # 지역한정

    def _reload_eggs():
        try:
            eggs_state["data"] = load_eggs(force=True)
        except Exception as e:
            print(f"알 갱신 실패: {e}")
        _populate_eggs()
        _update_eg_fresh()

    def _populate_eggs():
        for r in eg_tree.get_children():
            eg_tree.delete(r)
        filt_dist = eg_filter_var.get()
        shiny_only = eg_shiny_only_var.get()
        # 거리별 정렬
        dist_order = {"1 km": 1, "2 km": 2, "5 km": 5,
                      "7 km": 7, "10 km": 10, "12 km": 12}
        rows = []
        for egg in eggs_state["data"]:
            d = egg.get("eggType", "")
            if filt_dist != "전체" and d != filt_dist:
                continue
            if shiny_only and not egg.get("canBeShiny"):
                continue
            rows.append(egg)
        rows.sort(key=lambda e: (dist_order.get(e.get("eggType", ""), 99),
                                 -((e.get("combatPower") or {}).get("max") or 0)))
        for egg in rows:
            en = egg.get("name", "")
            ko = _en_to_display(en)
            cp = egg.get("combatPower") or {}
            cp_str = f"{cp.get('min', '-')}~{cp.get('max', '-')}"
            shiny = "○" if egg.get("canBeShiny") else ""
            flags = []
            if egg.get("isAdventureSync"):
                flags.append("모험 모드")
            if egg.get("isGiftExchange"):
                flags.append("선물 알")
            if egg.get("isRegional"):
                flags.append("지역 한정")
            # 색상 우선순위: 지역한정 > 선물 > 모험
            if egg.get("isRegional"):    tag = "regional"
            elif egg.get("isGiftExchange"): tag = "gift"
            elif egg.get("isAdventureSync"): tag = "adv"
            else:                          tag = ""
            dist_disp = (egg.get("eggType", "") or "").replace(" km", "km")
            eg_tree.insert("", "end",
                           values=(dist_disp, ko, cp_str, shiny,
                                   " · ".join(flags)),
                           tags=(tag,) if tag else (),
                           text=en)

    def _on_egg_double(_e=None):
        sel = eg_tree.selection()
        if not sel: return
        en = eg_tree.item(sel[0], "text")
        _jump_to_pokemon_by_en(en)

    eg_tree.bind("<Double-Button-1>", _on_egg_double)

    # ===== Tab: 필드 리서치 =====
    research_tab = ttk.Frame(notebook, padding=(8, 8))
    notebook.add(research_tab, text="  리서치  ")

    research_state = {"data": []}

    rs_top = ttk.Frame(research_tab)
    rs_top.pack(fill="x", pady=(0, 6))
    ttk.Label(rs_top,
              text="필드 리서치 태스크 → 보상 매핑 (더블클릭 시 보상 포켓몬 선택)",
              font=("", 9), foreground="#555").pack(side="left")

    rs_search_var = tk.StringVar()
    ttk.Entry(rs_top, textvariable=rs_search_var, width=24
              ).pack(side="left", padx=(12, 4))
    ttk.Label(rs_top, text="(검색)", font=("", 8), foreground="#888"
              ).pack(side="left")
    rs_search_var.trace_add("write", lambda *_: _populate_research())

    rs_shiny_only_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(rs_top, text="색이 다른 가능만",
                    variable=rs_shiny_only_var,
                    command=lambda: _populate_research()).pack(side="left", padx=(8, 4))

    ttk.Button(rs_top, text="갱신", width=8,
               command=lambda: _reload_research()).pack(side="right")
    rs_fresh_lbl = ttk.Label(rs_top, text="", font=("", 8))
    rs_fresh_lbl.pack(side="right", padx=(0, 10))

    def _update_rs_fresh():
        txt, c = _freshness_label(CACHE_RESEARCH)
        rs_fresh_lbl.configure(text=f"갱신: {txt}", foreground=c)

    rs_show_en_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(rs_top, text="영문 원문도 표시",
                    variable=rs_show_en_var,
                    command=lambda: _populate_research()).pack(side="left", padx=(8, 4))

    rs_frame = ttk.Frame(research_tab)
    rs_frame.pack(fill="both", expand=True)
    rs_scroll = ttk.Scrollbar(rs_frame, orient="vertical")
    rs_scroll.pack(side="right", fill="y")
    rs_tree = ttk.Treeview(rs_frame,
                           columns=("task", "task_en", "reward", "cp", "shiny"),
                           show="headings", height=22, selectmode="browse",
                           yscrollcommand=rs_scroll.set)
    for c, h, w in [("task", "태스크 (한글)", 320), ("task_en", "원문 (영문)", 260),
                    ("reward", "보상 포켓몬", 220), ("cp", "CP 범위", 110),
                    ("shiny", "색이다른", 70)]:
        rs_tree.heading(c, text=h,
                        command=lambda col=c: _sort_tree(rs_tree, col))
        rs_tree.column(c, width=w,
                       anchor="w" if c in ("task", "task_en", "reward") else "center")
    rs_tree.pack(side="left", fill="both", expand=True)
    rs_scroll.config(command=rs_tree.yview)
    rs_tree.tag_configure("untranslated", foreground="#888")

    def _toggle_en_col(*_):
        if rs_show_en_var.get():
            rs_tree.column("task_en", width=260, stretch=True)
            rs_tree.heading("task_en", text="원문 (영문)")
        else:
            rs_tree.column("task_en", width=0, stretch=False, minwidth=0)
            rs_tree.heading("task_en", text="")
    _toggle_en_col()

    def _reload_research():
        try:
            research_state["data"] = load_research(force=True)
        except Exception as e:
            print(f"리서치 갱신 실패: {e}")
        _populate_research()
        _update_rs_fresh()

    def _populate_research():
        for r in rs_tree.get_children():
            rs_tree.delete(r)
        _toggle_en_col()
        q = rs_search_var.get().strip().lower()
        shiny_only = rs_shiny_only_var.get()
        for task in research_state["data"]:
            text_en = task.get("text", "")
            text_ko = translate_research_task(text_en)
            translated = text_ko != text_en
            rewards = task.get("rewards") or []
            if not rewards:
                continue
            for rw in rewards:
                en = rw.get("name", "")
                if shiny_only and not rw.get("canBeShiny"):
                    continue
                ko = _en_to_display(en)
                if q and (q not in text_en.lower()
                          and q not in text_ko.lower()
                          and q not in ko.lower()
                          and q not in en.lower()):
                    continue
                cp = rw.get("combatPower") or {}
                cp_str = f"{cp.get('min', '-')}~{cp.get('max', '-')}"
                shiny = "○" if rw.get("canBeShiny") else ""
                tag = "untranslated" if not translated else ""
                rs_tree.insert("", "end",
                               values=(text_ko, text_en, ko, cp_str, shiny),
                               tags=(tag,) if tag else (),
                               text=en)

    def _on_research_double(_e=None):
        sel = rs_tree.selection()
        if not sel: return
        en = rs_tree.item(sel[0], "text")
        _jump_to_pokemon_by_en(en)

    rs_tree.bind("<Double-Button-1>", _on_research_double)

    # ===== 로켓 라인업 섹션 (PvE 로켓 탭 상단으로 통합) =====
    # rkt_tab 안에 직접 pack. 행 선택 시 아래 카운터 자동 갱신.
    rkt_lineup_tab = ttk.Frame(rkt_tab)

    rkt_state = {"data": []}

    ttk.Label(rkt_lineup_tab,
              text="▼ 로켓 라인업 — 행 클릭 시 아래 카운터 자동 갱신, "
                   "더블클릭 시 첫 슬롯 포켓몬으로 좌측 선택.",
              font=("", 9, "bold"), foreground="#444",
              justify="left", wraplength=1100).pack(anchor="w", pady=(0, 4))

    rkl_top = ttk.Frame(rkt_lineup_tab)
    rkl_top.pack(fill="x", pady=(0, 6))
    rkl_filter_var = tk.StringVar(value="전체")
    ttk.Label(rkl_top, text="필터:", font=("", 9)).pack(side="left")
    rkl_filter_combo = ttk.Combobox(rkl_top, textvariable=rkl_filter_var,
                                    values=["전체", "보스", "간부", "조무래기",
                                            "색이 다른 가능만"],
                                    width=18, state="readonly")
    rkl_filter_combo.pack(side="left", padx=(4, 8))
    rkl_filter_combo.bind("<<ComboboxSelected>>", lambda e: _populate_rocket())

    ttk.Button(rkl_top, text="갱신", width=8,
               command=lambda: _reload_rocket()).pack(side="right")
    rkl_fresh_lbl = ttk.Label(rkl_top, text="", font=("", 8))
    rkl_fresh_lbl.pack(side="right", padx=(0, 10))

    rkl_frame = ttk.Frame(rkt_lineup_tab)
    rkl_frame.pack(fill="both", expand=True)
    rkl_scroll = ttk.Scrollbar(rkl_frame, orient="vertical")
    rkl_scroll.pack(side="right", fill="y")
    rkl_tree = ttk.Treeview(rkl_frame,
                            columns=("rank", "name", "type", "s1", "s2", "s3", "shiny"),
                            show="headings", height=10, selectmode="browse",
                            yscrollcommand=rkl_scroll.set)
    for c, h, w in [("rank", "등급", 70), ("name", "NPC", 200),
                    ("type", "타입", 70),
                    ("s1", "슬롯 1", 200), ("s2", "슬롯 2", 220),
                    ("s3", "슬롯 3", 220), ("shiny", "색다른", 60)]:
        rkl_tree.heading(c, text=h,
                         command=lambda col=c: _sort_tree(rkl_tree, col))
        rkl_tree.column(c, width=w,
                        anchor="w" if c in ("name", "s1", "s2", "s3") else "center")
    rkl_tree.pack(side="left", fill="both", expand=True)
    rkl_scroll.config(command=rkl_tree.yview)
    rkl_tree.tag_configure("boss",   background="#ffd0d0", font=("", 9, "bold"))
    rkl_tree.tag_configure("leader", background="#fff0d0", font=("", 9, "bold"))
    rkl_tree.tag_configure("grunt",  background="")

    # 간부 이름 한글 매핑 (한국 PoGO 공식)
    _ROCKET_NPC_KO = {
        "Giovanni": "보스 지오반니",
        "Cliff":    "클리프",
        "Arlo":     "알로",
        "Sierra":   "시에라",
    }

    def _npc_name_ko(en_name, en_type=""):
        """영문 NPC 이름 → 한글. 조무래기는 '<타입> 타입 조무래기 (남/여)' 패턴."""
        if en_name in _ROCKET_NPC_KO:
            return _ROCKET_NPC_KO[en_name]
        # "Fire-type Female Grunt", "Decoy Female Grunt" 등
        gender = ""
        if "Male" in en_name:   gender = " (남)"
        elif "Female" in en_name: gender = " (여)"
        if "Decoy" in en_name:
            return f"미끼 조무래기{gender}"
        if "Beginner" in en_name:
            return f"초보 조무래기{gender}"
        type_ko = TYPE_KO.get(en_type.lower(), en_type) if en_type else ""
        if type_ko:
            return f"{type_ko}타입 조무래기{gender}"
        return en_name

    def _slot_str(slot_list):
        """슬롯 옵션 → 한글 포켓몬명 ', ' 조합 + 색다른 ★ 표시."""
        if not slot_list:
            return ""
        names = []
        for p in slot_list:
            en = p.get("name", "")
            ko = _en_to_display(en) if en else "?"
            mark = "★" if p.get("canBeShiny") else ""
            enc = "💎" if p.get("isEncounter") else ""
            names.append(f"{mark}{enc}{ko}")
        return ", ".join(names)

    def _slot_has_shiny(slot_list):
        return any(p.get("canBeShiny") for p in (slot_list or []))

    def _populate_rocket():
        for r in rkl_tree.get_children():
            rkl_tree.delete(r)
        filt = rkl_filter_var.get()
        rows = []
        for npc in rkt_state.get("data", []):
            title = npc.get("title", "") or ""
            if "Boss" in title:    rank, tag, sort_k = "보스", "boss", 0
            elif "Leader" in title: rank, tag, sort_k = "간부", "leader", 1
            else:                   rank, tag, sort_k = "조무래기", "grunt", 2
            if filt == "보스" and rank != "보스": continue
            if filt == "간부" and rank != "간부": continue
            if filt == "조무래기" and rank != "조무래기": continue
            # 색이 다른 가능만 필터
            any_shiny = any(_slot_has_shiny(npc.get(k)) for k in
                            ("firstPokemon","secondPokemon","thirdPokemon"))
            if filt == "색이 다른 가능만" and not any_shiny:
                continue
            rows.append((sort_k, npc, rank, tag, any_shiny))
        # 정렬: 보스/간부 우선, 그 다음 조무래기는 타입 순
        type_order = ["normal","fire","water","electric","grass","ice","fighting",
                      "poison","ground","flying","psychic","bug","rock","ghost",
                      "dragon","dark","steel","fairy",""]
        def _key(r):
            sort_k, npc, rank, tag, _ = r
            t = (npc.get("type") or "").lower()
            return (sort_k, type_order.index(t) if t in type_order else 99,
                    npc.get("name",""))
        rows.sort(key=_key)
        for _, npc, rank, tag, any_shiny in rows:
            en = npc.get("name","")
            type_en = npc.get("type","") or ""
            ko_name = _npc_name_ko(en, type_en)
            type_disp = TYPE_KO.get(type_en.lower(), type_en) if type_en else "-"
            shiny_disp = "★" if any_shiny else ""
            rkl_tree.insert("", "end",
                            values=(rank, ko_name, type_disp,
                                    _slot_str(npc.get("firstPokemon")),
                                    _slot_str(npc.get("secondPokemon")),
                                    _slot_str(npc.get("thirdPokemon")),
                                    shiny_disp),
                            tags=(tag,),
                            text=en)
        # 신선도 라벨
        txt, c = _freshness_label(CACHE_ROCKETS, "갱신: ")
        rkl_fresh_lbl.configure(text=txt, foreground=c)

    def _reload_rocket():
        try:
            rkt_state["data"] = load_rocket_lineups(force=True)
        except Exception as e:
            print(f"로켓 라인업 갱신 실패: {e}")
        _populate_rocket()

    def _on_rocket_select(_e=None):
        """행 선택 시 — 타입 자동 설정 + 아래 카운터 갱신."""
        sel = rkl_tree.selection()
        if not sel: return
        en = rkl_tree.item(sel[0], "text")
        npc = next((n for n in rkt_state.get("data", []) if n.get("name") == en), None)
        if not npc: return
        type_en = (npc.get("type") or "").lower()
        if type_en and type_en in TYPE_KO:
            try:
                rkt_type_var.set(TYPE_KO[type_en])
                refresh_rocket()
            except Exception:
                pass

    def _on_rocket_double(_e=None):
        """더블클릭 시 — 첫 슬롯 포켓몬으로 좌측 리스트 선택."""
        sel = rkl_tree.selection()
        if not sel: return
        en = rkl_tree.item(sel[0], "text")
        npc = next((n for n in rkt_state.get("data", []) if n.get("name") == en), None)
        if not npc: return
        first_opts = npc.get("firstPokemon") or []
        if first_opts:
            first_en = first_opts[0].get("name", "")
            _jump_to_pokemon_by_en(first_en)

    rkl_tree.bind("<<TreeviewSelect>>", _on_rocket_select)
    rkl_tree.bind("<Double-Button-1>", _on_rocket_double)

    # rkt_tab 안에서 라인업을 안내 라벨 바로 다음(대사 입력 위)에 배치
    rkt_lineup_tab.pack(fill="both", expand=False, pady=(0, 8),
                        before=rkt_phrase_row)
    ttk.Separator(rkt_tab, orient="horizontal").pack(fill="x", pady=(0, 6),
                                                     before=rkt_phrase_row)

    # 초기 로딩 (블록되지 않도록 try)
    try:
        events_state["data"] = load_events()
        _populate_events()
    except Exception as e:
        print(f"이벤트 초기 로드 실패: {e}")
    _update_ev_fresh()
    try:
        eggs_state["data"] = load_eggs()
        _populate_eggs()
    except Exception as e:
        print(f"알 초기 로드 실패: {e}")
    _update_eg_fresh()
    try:
        research_state["data"] = load_research()
        _populate_research()
    except Exception as e:
        print(f"리서치 초기 로드 실패: {e}")
    _update_rs_fresh()
    try:
        rkt_state["data"] = load_rocket_lineups()
        _populate_rocket()
    except Exception as e:
        print(f"로켓 라인업 초기 로드 실패: {e}")

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
        sid = display_to_sid.get(disp)
        # 진화 링크가 메가/그림자 폼이면 해당 카테고리 자동 활성화 — 안 그러면
        # 좌측 리스트에 그 폼이 없어서 선택이 실패하고 타입/IV 등이 갱신 안 됨.
        if sid:
            cat = _category(sid)
            if cat == "mega" and not show_mega_var.get():
                show_mega_var.set(True)
            elif cat == "shadow" and not show_shadow_var.get():
                show_shadow_var.set(True)
            elif cat == "normal" and not show_normal_var.get():
                show_normal_var.set(True)
        if fav_only_var.get() and sid not in favorites:
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

        # 진화 후 CP 미리보기: IV + 현재 Lv 모두 입력되어야 표시
        user_ivs_lv = None
        try:
            a_s, d_s, h_s = atk_var.get().strip(), def_var.get().strip(), hp_var.get().strip()
            lv_s = cur_lv_var.get().strip()
            if a_s and d_s and h_s and lv_s:
                ivs = (int(a_s), int(d_s), int(h_s))
                lv = float(lv_s)
                if all(0 <= v <= 15 for v in ivs) and 1.0 <= lv <= 51.0:
                    cur_idx = idx_from_level(lv)
                    if 0 <= cur_idx < len(CPM):
                        user_ivs_lv = (ivs, CPM[cur_idx])
        except (ValueError, TypeError):
            user_ivs_lv = None

        pokemon_by_sid = {p.get("speciesId"): p for p in state["gm"].get("pokemon", [])}

        for i, stage in enumerate(stages):
            if i > 0:
                ttk.Label(evo_frame, text="→", font=("", 11),
                          foreground="#888").pack(side="left", padx=4)
            for j, s in enumerate(stage):
                if j > 0:
                    ttk.Label(evo_frame, text="/", font=("", 10),
                              foreground="#aaa").pack(side="left", padx=2)
                disp = sid_to_display.get(s, s)
                cp_suffix = ""
                if user_ivs_lv:
                    p = pokemon_by_sid.get(s)
                    if p and p.get("baseStats"):
                        ivs, cpm = user_ivs_lv
                        cp = compute_cp(p["baseStats"], ivs, cpm)
                        cp_suffix = f" (CP{cp})"
                text = disp + cp_suffix
                is_current = (s == current_sid)
                if is_current:
                    ttk.Label(evo_frame, text=text,
                              font=("", 10, "bold"), foreground="#c33").pack(side="left")
                else:
                    lbl = tk.Label(evo_frame, text=text,
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

    def render_acquisition(sid):
        """현재 일정상 입수 경로를 입수 라벨에 채운다. 데이터가 아직 로드 안 됐으면 빈 칸."""
        if not sid:
            acq_var.set("")
            return
        try:
            eggs = eggs_state.get("data") or []
        except NameError:
            eggs = []
        try:
            raids_c = raid_state.get("bosses") or []
        except NameError:
            raids_c = []
        try:
            rocket = rkt_state.get("data") or []
        except NameError:
            rocket = []
        try:
            research = research_state.get("data") or []
        except NameError:
            research = []
        try:
            text = find_acquisition_for_sid(sid, state["gm"], eggs, raids_c,
                                             rocket, research, sid_to_display)
        except Exception as exc:
            text = f"(입수처 계산 실패: {exc})"
        acq_var.set(text)

    def refresh():
        refresh_meta()
        sel = listbox.curselection()
        if not sel:
            info_var.set("왼쪽에서 포켓몬을 선택하세요.")
            clear_evo_row()
            clear_sprite()
            clear_moves_tab()
            clear_type_row()
            acq_var.set("")
            fav_btn_var.set("☆ 즐겨찾기")
            table_label.set("")
            my_iv_result.set("")
            search_str_var.set("")
            for r in tree.get_children():
                tree.delete(r)
            for r in summary_tree.get_children():
                summary_tree.delete(r)
            return

        disp = strip_star(listbox.get(sel[0]))
        sid = display_to_sid.get(disp)
        pokemon = sid_to_pokemon.get(sid)
        if not pokemon:
            return
        base = pokemon["baseStats"]
        update_fav_btn(sid)
        render_type_effectiveness(pokemon.get("types") or [])
        render_acquisition(sid)

        # 현재 레벨 (강화 비용 계산용)
        cur_lv_s = cur_lv_var.get().strip()
        try:
            cur_lv = float(cur_lv_s) if cur_lv_s else None
            cur_idx = idx_from_level(cur_lv) if cur_lv else None
        except ValueError:
            cur_idx = None

        # 같은 포켓몬이면 ranking_cache 그대로. 다르면 LRU 에서 끌어오거나 새로 계산.
        if ranking_cache.get("_sid") != sid:
            data = _get_ranking_for(sid, base)
            ranking_cache.clear()
            ranking_cache["_sid"] = sid
            ranking_cache.update(data)

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
            parts = [f"별의모래 {d:,}"]
            if c:
                parts.append(f"사탕 {c}")
            if x:
                parts.append(f"XL의 사탕 {x}")
            return " · ".join(parts)

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
        if cm and cm.get("top_iv"):
            _ex, _ = ingame_search_strings(cm["top_iv"], name=disp)
            search_str_var.set(_ex)
        else:
            search_str_var.set("")
        if user_iv is None:
            my_iv_result.set("· 입력하면 리그별 내 순위가 계산됩니다")
        else:
            ap = appraisal_label(user_iv)
            if cm and cm["user_entry"]:
                _, sp, lvl_idx, cp = cm["user_entry"]
                pct = sp / cm["top_sp"] * 100
                lvl = level_from_idx(lvl_idx)
                my_iv_result.set(
                    f"· {ap}  ·  {current_league} #{cm['user_rank']}/4096  Lv{lvl:g}  CP{cp}  {pct:.2f}%"
                )
            else:
                my_iv_result.set(f"· {ap}  ·  {current_league}에는 못 들어감")

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

    # Bindings
    # IME(한글) 조합 중에는 entry.get()이 비어있어서 실시간 필터링이 어려움.
    # → Enter 또는 검색 버튼으로 강제 확정. 폴링은 commit 후 반영 백업용 (느슨한 주기).
    def trigger_search():
        # 즐겨찾기/분류 필터는 변경 즉시 저장 — 종료 방식에 상관없이 마지막 상태 유지
        try:
            settings["fav_only"]    = bool(fav_only_var.get())
            settings["show_normal"] = bool(show_normal_var.get())
            settings["show_shadow"] = bool(show_shadow_var.get())
            settings["show_mega"]   = bool(show_mega_var.get())
            save_settings(settings)
        except Exception:
            pass
        update_listbox(force=True)

    def poll():
        update_listbox()
        # IME commit 백업용 폴링 — 700ms 면 한글 조합 끝난 뒤 자연스럽게 반영
        root.after(700, poll)

    # KeyRelease 디바운스: 한 글자 칠 때 자/모음별로 여러 KeyRelease 가 발생하므로
    # 마지막 입력 후 180ms 정도 쉬어야 필터링을 한 번만 실행.
    search_pending = [None]
    def _on_search_keyrelease(_event=None):
        if search_pending[0]:
            root.after_cancel(search_pending[0])
        search_pending[0] = root.after(180, lambda: update_listbox())

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
        acq_var.set("")
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
    search_entry.bind("<KeyRelease>", _on_search_keyrelease)
    search_button.configure(command=trigger_search)
    clear_button.configure(command=clear_all)

    iv_pending = [None]
    def on_iv_change(*_):
        if iv_pending[0]:
            root.after_cancel(iv_pending[0])
        iv_pending[0] = root.after(120, _iv_apply)

    def _iv_apply():
        refresh()

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
        # 활성 탭에 따라 추가 갱신 (PvE 카운터 임의 보스 모드)
        # — 사용자가 PvE 탭에 머무는 흐름을 깨지 않도록 그 탭은 자동 전환 안 함.
        active_tab_text = ""
        try:
            active_tab_text = notebook.tab(notebook.select(), "text").strip()
            if active_tab_text == "PvE 카운터" and use_selected_var.get():
                refresh_counters()
        except Exception:
            pass
        # PvE 카운터(임의 보스) 외의 탭에서는 PvP 분석으로 자동 점프
        # — 좌측에서 종을 클릭한 의도는 보통 그 종의 PvP 분석 보기.
        if not (
            active_tab_text == "PvE 카운터" and use_selected_var.get()
        ):
            try:
                notebook.select(iv_tab)
            except Exception:
                pass
    listbox.bind("<<ListboxSelect>>", _on_listbox_select)
    listbox.bind("<Return>", _on_listbox_select)
    meta_tree.bind("<Double-Button-1>", on_meta_double)
    meta_tree.bind("<Return>", on_meta_double)
    # 단일 클릭으로도 같은 동작 — 행을 누르면 좌측 리스트 + PvP 분석 탭으로 점프
    meta_tree.bind("<ButtonRelease-1>", on_meta_double)

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

    # ===== PvE 다맥 티어 탭 =====
    maxbox_tab = ttk.Frame(notebook, padding=(10, 8))
    notebook.add(maxbox_tab, text="  PvE 다맥  ")

    tcanvas = tk.Canvas(maxbox_tab, highlightthickness=0)
    tvsb = ttk.Scrollbar(maxbox_tab, orient="vertical", command=tcanvas.yview)
    tcanvas.configure(yscrollcommand=tvsb.set)
    tvsb.pack(side="right", fill="y")
    tcanvas.pack(side="left", fill="both", expand=True)
    tbody = ttk.Frame(tcanvas)
    twin = tcanvas.create_window((0, 0), window=tbody, anchor="nw")
    tbody.bind("<Configure>", lambda e: tcanvas.configure(scrollregion=tcanvas.bbox("all")))
    tcanvas.bind("<Configure>", lambda e: tcanvas.itemconfigure(twin, width=e.width))

    def _tier_wheel(e):
        tcanvas.yview_scroll(int(-(e.delta or 0) / 120), "units")
    tcanvas.bind("<Enter>", lambda e: tcanvas.bind_all("<MouseWheel>", _tier_wheel))
    tcanvas.bind("<Leave>", lambda e: tcanvas.unbind_all("<MouseWheel>"))

    def _tsec(t):
        ttk.Label(tbody, text=t, font=("", 11, "bold"),
                  foreground="#222").pack(anchor="w", pady=(12, 2))

    def _tline(t, c="#333"):
        ttk.Label(tbody, text=t, font=("", 9),
                  foreground=c).pack(anchor="w", padx=(14, 0))

    _tline(f"맥스배틀 추천 (참고용 · {MAXBATTLE_UPDATED} 기준 · 출처 GO Hub/doctorpokegogo)", "#999")
    _tsec("⭐ 최우선 S급 어택커")
    _tline("  ·  ".join(MAXBATTLE_S_ATTACKERS), "#2a5a8a")
    _tline("보스가 약점이면 거다이맥스가 항상 1순위. 소수만 키운다면 "
           "자시안(강철)·무한다이노(드래곤)·거다이맥스 팬텀(고스트)부터.", "#666")
    _tsec("⚔️ 타입별 추천 어택커")
    for _ty, _nm, _mv in MAXBATTLE_ATTACKERS_BY_TYPE:
        _tline(f"[{_ty}] {_nm}  —  {_mv}")
    _tsec("🛡️ 탱커 (0.5초 평타 = 변신 빠름 = 덜 맞음)")
    for _nm, _mv, _why in MAXBATTLE_TANKS:
        _tline(f"{_nm}  ({_mv})  —  {_why}")
    _tsec("➕ 힐러 (높은 HP → 회복량 ↑)")
    for _nm, _why in MAXBATTLE_HEALERS:
        _tline(f"{_nm}  —  {_why}")

    _tsec(f"🐋 출시된 거다이맥스 ({len(MAXBATTLE_GIGANTAMAX)}종)")
    _tline("6성 맥스배틀 전용 · 고유 G-Max 무브. 보스가 약점이면 항상 최우선 딜러.", "#666")
    for _i in range(0, len(MAXBATTLE_GIGANTAMAX), 6):
        _tline("  ·  ".join(MAXBATTLE_GIGANTAMAX[_i:_i + 6]), "#2a5a8a")
    _tsec("🔷 출시된 다이맥스 (주요)")
    _tline("일반 맥스배틀. 순환 풀이라 전체는 게임 내 '다이맥스' 검색으로 보유분 확인.", "#666")
    for _i in range(0, len(MAXBATTLE_DYNAMAX), 6):
        _tline("  ·  ".join(MAXBATTLE_DYNAMAX[_i:_i + 6]))
    _tline("※ 다이맥스/거다이맥스는 별도 종이 아니라 '전투 상태' — 종 자체는 왼쪽 목록에 이미 있음. "
           "게임 검색창에 '다이맥스' / '거다이맥스' 입력 시 보유 개체가 걸러짐 (검색어 탭 참고).", "#888")

    # ===== 검색어 탭 (인게임 검색 문자열 모음 · 복사) =====
    search_tab = ttk.Frame(notebook, padding=(10, 8))
    notebook.add(search_tab, text="  검색어  ")

    sh_head = ttk.Frame(search_tab)
    sh_head.pack(fill="x", pady=(0, 4))
    ttk.Label(sh_head, text="포켓몬GO 인게임 검색어 — 오른쪽 [복사] 후 게임 검색창에 붙여넣기",
              font=("", 11, "bold")).pack(side="left")
    sh_toast = tk.StringVar(value="")
    ttk.Label(sh_head, textvariable=sh_toast, font=("", 9),
              foreground="#2a7a3a").pack(side="right")
    ttk.Label(search_tab,
              text="& = 그리고 · 쉼표(,) = 또는 · ! = 제외 · 범위: 3-4 / 3-(이상) / -1(이하)",
              font=("", 8), foreground="#888").pack(anchor="w", pady=(0, 6))

    sh_canvas = tk.Canvas(search_tab, highlightthickness=0)
    sh_vsb = ttk.Scrollbar(search_tab, orient="vertical", command=sh_canvas.yview)
    sh_canvas.configure(yscrollcommand=sh_vsb.set)
    sh_vsb.pack(side="right", fill="y")
    sh_canvas.pack(side="left", fill="both", expand=True)
    sh_body = ttk.Frame(sh_canvas)
    sh_win = sh_canvas.create_window((0, 0), window=sh_body, anchor="nw")
    sh_body.bind("<Configure>",
                 lambda e: sh_canvas.configure(scrollregion=sh_canvas.bbox("all")))
    sh_canvas.bind("<Configure>", lambda e: sh_canvas.itemconfigure(sh_win, width=e.width))

    def _sh_wheel(e):
        sh_canvas.yview_scroll(int(-(e.delta or 0) / 120), "units")
    sh_canvas.bind("<Enter>", lambda e: sh_canvas.bind_all("<MouseWheel>", _sh_wheel))
    sh_canvas.bind("<Leave>", lambda e: sh_canvas.unbind_all("<MouseWheel>"))

    _sh_toast_after = [None]

    def _sh_copy(term):
        root.clipboard_clear()
        root.clipboard_append(term)
        sh_toast.set(f"복사됨: {term}")
        if _sh_toast_after[0]:
            try:
                root.after_cancel(_sh_toast_after[0])
            except Exception:
                pass
        _sh_toast_after[0] = root.after(2500, lambda: sh_toast.set(""))

    for _cat, _items in SEARCH_LIBRARY:
        ttk.Label(sh_body, text=_cat, font=("", 11, "bold"),
                  foreground="#222").pack(anchor="w", pady=(12, 3))
        for _label, _term in _items:
            _row = ttk.Frame(sh_body)
            _row.pack(anchor="w", fill="x", padx=(10, 0), pady=1)
            ttk.Button(_row, text="복사", width=6,
                       command=lambda t=_term: _sh_copy(t)).pack(side="left")
            _ent = ttk.Entry(_row, width=34)
            _ent.insert(0, _term)
            _ent.configure(state="readonly")
            _ent.pack(side="left", padx=(6, 8))
            ttk.Label(_row, text=_label, font=("", 9),
                      foreground="#555").pack(side="left")

    # ===== 오늘 할 일 대시보드 (레이드·이벤트·알·리서치 한눈에) =====
    # 모든 일정 state 가 만들어진 뒤(여기) 구성 → notebook.insert 로 일정 그룹 앞으로 이동
    dash_tab = ttk.Frame(notebook, padding=(10, 8))
    notebook.add(dash_tab, text="  오늘 할 일  ")

    dash_head = ttk.Frame(dash_tab)
    dash_head.pack(fill="x", pady=(0, 4))
    ttk.Label(dash_head, text="오늘 할 일 — 루틴 체크리스트 · 레이드·이벤트·알·리서치 요약",
              font=("", 11, "bold")).pack(side="left")
    ttk.Button(dash_head, text="새로고침", width=10,
               command=lambda: _refresh_dashboard()).pack(side="right")

    # 스크롤 가능한 본문
    dash_canvas = tk.Canvas(dash_tab, highlightthickness=0)
    dash_vsb = ttk.Scrollbar(dash_tab, orient="vertical", command=dash_canvas.yview)
    dash_canvas.configure(yscrollcommand=dash_vsb.set)
    dash_vsb.pack(side="right", fill="y")
    dash_canvas.pack(side="left", fill="both", expand=True)
    dash_body = ttk.Frame(dash_canvas)
    dash_win = dash_canvas.create_window((0, 0), window=dash_body, anchor="nw")
    dash_body.bind("<Configure>",
                   lambda e: dash_canvas.configure(scrollregion=dash_canvas.bbox("all")))
    dash_canvas.bind("<Configure>",
                     lambda e: dash_canvas.itemconfigure(dash_win, width=e.width))

    def _dash_wheel(e):
        dash_canvas.yview_scroll(int(-(e.delta or 0) / 120), "units")
    dash_canvas.bind("<Enter>", lambda e: dash_canvas.bind_all("<MouseWheel>", _dash_wheel))
    dash_canvas.bind("<Leave>", lambda e: dash_canvas.unbind_all("<MouseWheel>"))

    # 새로고침 때 갈아끼우는 요약부(dash_summary) + 항상 유지되는 박스 계산기부(box_section)
    dash_summary = ttk.Frame(dash_body)
    dash_summary.pack(fill="x", anchor="w")
    box_section = ttk.Frame(dash_body)
    box_section.pack(fill="x", anchor="w", pady=(12, 0))

    # --- 🛒 박스 효율 계산기 (입력값 유지) ---
    ttk.Label(box_section, text="🛒 박스 효율 계산기", font=("", 11, "bold"),
              foreground="#222").pack(anchor="w", pady=(6, 2))
    ttk.Label(box_section,
              text="박스 가격과 구성품 개수를 넣으면 단품 대비 가치·할인율을 계산. "
                   "단품가는 참고 기본값(세일·시즌 변동) — 직접 수정 가능.",
              font=("", 8), foreground="#999").pack(anchor="w", padx=(14, 0), pady=(0, 4))
    bgrid = ttk.Frame(box_section)
    bgrid.pack(anchor="w", fill="x", padx=(14, 0))
    ttk.Label(bgrid, text="아이템", width=16, font=("", 9, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(bgrid, text="단품가(코인)", font=("", 9, "bold")).grid(row=0, column=1, padx=6)
    ttk.Label(bgrid, text="개수", font=("", 9, "bold")).grid(row=0, column=2, padx=6)
    box_rows = []
    for _i, (_name, _price) in enumerate(SHOP_ITEM_PRICES, 1):
        ttk.Label(bgrid, text=_name, width=16).grid(row=_i, column=0, sticky="w")
        _pv = tk.StringVar(value=str(_price))
        _qv = tk.StringVar(value="0")
        ttk.Entry(bgrid, textvariable=_pv, width=8).grid(row=_i, column=1, padx=6, pady=1)
        ttk.Entry(bgrid, textvariable=_qv, width=6).grid(row=_i, column=2, padx=6, pady=1)
        box_rows.append((_name, _pv, _qv))
    pf = ttk.Frame(box_section)
    pf.pack(anchor="w", pady=(8, 4), padx=(14, 0))
    ttk.Label(pf, text="박스 가격(코인): ").pack(side="left")
    box_price_var = tk.StringVar(value="")
    ttk.Entry(pf, textvariable=box_price_var, width=10).pack(side="left")
    ttk.Button(pf, text="계산", command=lambda: _calc_box()).pack(side="left", padx=8)
    box_result = ttk.Label(box_section, text="", font=("", 10), justify="left")
    box_result.pack(anchor="w", pady=(6, 0), padx=(14, 0))

    def _calc_box():
        total = 0.0
        for _name, _pv, _qv in box_rows:
            try:
                total += float(_pv.get() or 0) * float(_qv.get() or 0)
            except ValueError:
                pass
        try:
            price = float(box_price_var.get() or 0)
        except ValueError:
            price = 0
        if total <= 0:
            box_result.config(text="구성품 개수를 입력하세요.", foreground="#999")
            return
        if price <= 0:
            box_result.config(text=f"총 단품 가치: {total:,.0f} 코인 "
                                   f"(박스 가격을 넣으면 할인율 계산)", foreground="#333")
            return
        disc = (1 - price / total) * 100
        ratio = total / price
        if disc >= 50:
            verdict, col = "🔥 매우 좋음 (즉시 구매급)", "#2a7a3a"
        elif disc >= 30:
            verdict, col = "👍 좋음", "#2a7a3a"
        elif disc >= 10:
            verdict, col = "🆗 무난", "#a06020"
        else:
            verdict, col = "👎 비효율 (단품/세일이 나음)", "#b03030"
        box_result.config(
            text=(f"총 단품 가치 {total:,.0f}코인  vs  박스 {price:,.0f}코인\n"
                  f"할인율 {disc:.0f}%  (가치비 {ratio:.2f}배)  →  {verdict}"),
            foreground=col)

    # --- ⚛️ 합체/변신 에너지 계산기 ---
    ttk.Label(box_section, text="⚛️ 합체/변신 에너지 계산기", font=("", 11, "bold"),
              foreground="#222").pack(anchor="w", pady=(16, 2))
    ttk.Label(box_section,
              text=f"네크로즈마·큐레무·버드렉스 등. 공식: 80 + 10×(에너지 당첨 꾸러미). "
                   f"합체 1회 ≈ {FUSION_GOAL_DEFAULT} 에너지.",
              font=("", 8), foreground="#999").pack(anchor="w", padx=(14, 0), pady=(0, 4))
    ff = ttk.Frame(box_section)
    ff.pack(anchor="w", padx=(14, 0), pady=(2, 2))
    ttk.Label(ff, text="보상 꾸러미 수: ").pack(side="left")
    fusion_bundles_var = tk.StringVar(value="")
    ttk.Entry(ff, textvariable=fusion_bundles_var, width=8).pack(side="left")
    ttk.Label(ff, text="   목표 에너지: ").pack(side="left")
    fusion_goal_var = tk.StringVar(value=str(FUSION_GOAL_DEFAULT))
    ttk.Entry(ff, textvariable=fusion_goal_var, width=8).pack(side="left")
    ttk.Button(ff, text="계산", command=lambda: _calc_fusion()).pack(side="left", padx=8)
    fusion_result = ttk.Label(box_section, text="", font=("", 10), justify="left")
    fusion_result.pack(anchor="w", padx=(14, 0), pady=(2, 0))

    def _calc_fusion():
        try:
            b = float(fusion_bundles_var.get() or 0)
        except ValueError:
            b = 0
        try:
            goal = float(fusion_goal_var.get() or FUSION_GOAL_DEFAULT)
        except ValueError:
            goal = FUSION_GOAL_DEFAULT
        if b <= 0:
            fusion_result.config(text="보상 꾸러미 수를 입력하세요.", foreground="#999")
            return
        e = fusion_expected_energy(b)
        runs = max(1, int(round(goal / e))) if e > 0 else 0
        fusion_result.config(
            text=f"회당 기대 에너지 ~{e:.0f}  →  목표 {goal:.0f} 까지 약 {runs}회",
            foreground="#2a7a3a")

    def _refresh_dashboard():
        for w in dash_summary.winfo_children():
            w.destroy()
        now = datetime.now()

        def section(title):
            ttk.Label(dash_summary, text=title, font=("", 11, "bold"),
                      foreground="#222").pack(anchor="w", pady=(12, 2))

        def line(txt, color="#333"):
            ttk.Label(dash_summary, text=txt, font=("", 9),
                      foreground=color).pack(anchor="w", padx=(14, 0))

        def _pdt(iso):
            try:
                return datetime.fromisoformat((iso or "").replace("Z", "").split(".")[0]) if iso else None
            except Exception:
                return None

        # ── 일일/주간 루틴 체크리스트 ──
        today_str = now.strftime("%Y-%m-%d")
        _iso = now.isocalendar()
        week_str = f"{_iso[0]}-W{_iso[1]:02d}"
        r = settings.get("routine") or {}
        if r.get("date") != today_str:
            r["date"] = today_str
            r["daily_done"] = []
        if r.get("week") != week_str:
            r["week"] = week_str
            r["weekly_done"] = []
        settings["routine"] = r
        save_settings(settings)

        routine_vars = []  # (scope, key, var)
        routine_hdr = ttk.Label(dash_summary, text="✅ 오늘의 루틴 체크리스트",
                                font=("", 11, "bold"), foreground="#222")
        routine_hdr.pack(anchor="w", pady=(6, 2))

        def _routine_progress():
            n = sum(1 for _s, _k, v in routine_vars if v.get())
            routine_hdr.config(text=f"✅ 오늘의 루틴 체크리스트 ({n}/{len(routine_vars)})")

        def _toggle_routine(scope, key, var):
            rr = settings.get("routine") or {}
            bucket = "daily_done" if scope == "daily" else "weekly_done"
            d = set(rr.get(bucket, []))
            if var.get():
                d.add(key)
            else:
                d.discard(key)
            rr[bucket] = sorted(d)
            settings["routine"] = rr
            save_settings(settings)
            _routine_progress()

        def _routine_item(scope, key, label, note, done_set):
            var = tk.BooleanVar(value=(key in done_set))
            row = ttk.Frame(dash_summary)
            row.pack(anchor="w", fill="x", padx=(14, 0))
            ttk.Checkbutton(row, text=label, variable=var,
                            command=lambda: _toggle_routine(scope, key, var)).pack(side="left")
            ttk.Label(row, text=f"— {note}", font=("", 8),
                      foreground="#999").pack(side="left", padx=(6, 0))
            routine_vars.append((scope, key, var))

        _daily_done = set(r.get("daily_done", []))
        _weekly_done = set(r.get("weekly_done", []))
        for _k, _lbl, _note in DAILY_ROUTINE:
            _routine_item("daily", _k, _lbl, _note, _daily_done)
        ttk.Label(dash_summary, text="주간", font=("", 9, "bold"),
                  foreground="#666").pack(anchor="w", padx=(14, 0), pady=(4, 0))
        for _k, _lbl, _note in WEEKLY_ROUTINE:
            _routine_item("weekly", _k, _lbl, _note, _weekly_done)
        _routine_progress()

        # ── 이벤트: 진행 중 / 곧 시작 (이번 달) ──
        active, soon = [], []
        for ev in events_state.get("data", []):
            s, e = _pdt(ev.get("start")), _pdt(ev.get("end"))
            if s and e:
                if e < now:
                    continue
                if s <= now <= e:
                    active.append((s, e, ev))
                elif s <= now + timedelta(days=31):
                    soon.append((s, e, ev))
            elif s and s >= now and s <= now + timedelta(days=31):
                soon.append((s, None, ev))
        active.sort(key=lambda x: x[1] or datetime.max)
        soon.sort(key=lambda x: x[0])

        section(f"🟢 진행 중 이벤트 ({len(active)})")
        if not active:
            line("진행 중인 이벤트 없음", "#999")
        for _s, _e, ev in active[:15]:
            line(f"• {_translate_event_name(ev.get('name',''))}  —  ~{_format_iso_short(ev.get('end'))} 종료", "#2a7a3a")

        section(f"🔜 곧 시작 (이번 달, {len(soon)})")
        if not soon:
            line("예정 이벤트 없음", "#999")
        for _s, _e, ev in soon[:15]:
            line(f"• {_translate_event_name(ev.get('name',''))}  —  {_format_iso_short(ev.get('start'))} 시작", "#a06020")

        # ── 주목 레이드 (5★ / 메가 / 엘리트) ──
        bosses = raid_state.get("bosses", []) or []
        hi = [b for b in bosses
              if any(k in (b.get("tier") or "").lower() for k in ("5-star", "mega", "elite"))]
        section(f"⚔️ 주목 레이드 ({len(hi)})")
        if not hi:
            line("표시할 레이드 없음 — '데이터 업데이트' 후 확인", "#999")
        for b in hi[:16]:
            ko = b.get("_name_ko") or _en_to_display(b.get("name", "?"))
            tl = (b.get("tier") or "").lower()
            tier_ko = "5★" if "5-star" in tl else ("메가" if "mega" in tl else "엘리트")
            tnames = [(t.get("name") if isinstance(t, dict) else t) or ""
                      for t in (b.get("types", []) or [])]
            tstr = " · ".join(TYPE_KO.get(n.lower(), n) for n in tnames if n)
            line(f"• [{tier_ko}] {ko}    {tstr}")

        # ── 즐겨찾기로 잡는 주목 레이드 (상성 후보) ──
        section("🎯 내 즐겨찾기로 잡는 주목 레이드 (상성 후보)")
        if not favorites:
            line("즐겨찾기가 비어 있음 — 좌측에서 ★로 보유 포켓몬을 등록하면 표시", "#999")
        elif not hi:
            line("표시할 레이드 없음", "#999")
        else:
            def _types_of(obj):
                out = []
                for t in (obj.get("types", []) or []):
                    n = (t.get("name") if isinstance(t, dict) else t) or ""
                    n = n.lower()
                    if n and n != "none":
                        out.append(n)
                return out
            fav_info = []
            for fsid in favorites:
                fp = sid_to_pokemon.get(fsid)
                if fp:
                    fav_info.append((sid_to_display.get(fsid, fsid), set(_types_of(fp))))
            shown = 0
            for b in hi[:16]:
                weak = {atk for atk, _m in boss_weaknesses(_types_of(b))}
                if not weak:
                    continue
                matches = [disp for disp, fts in fav_info if fts & weak]
                if matches:
                    ko = b.get("_name_ko") or _en_to_display(b.get("name", "?"))
                    extra = f" 외 {len(matches) - 6}" if len(matches) > 6 else ""
                    line(f"• {ko} → {', '.join(matches[:6])}{extra}", "#2a7a3a")
                    shown += 1
            if shown == 0:
                line("현재 주목 레이드에 상성 맞는 즐겨찾기가 없음 "
                     "(타입 상성 기준 후보 — 무브셋은 별도 확인)", "#999")

        # ── 알 / 리서치 요약 ──
        eggs = eggs_state.get("data", []) or []
        shiny_eggs = sum(1 for e in eggs if e.get("canBeShiny"))
        res = research_state.get("data", []) or []
        section("🥚 알 부화 · 🔬 리서치")
        line(f"부화 풀 {len(eggs)}종 (색이 다른 포켓몬 {shiny_eggs}종) — 자세히는 '알 부화' 탭")
        line(f"필드 리서치 과제 {len(res)}건 — 자세히는 '리서치' 탭")

        ttk.Label(dash_summary, text=f"갱신: {now:%Y-%m-%d %H:%M}",
                  font=("", 8), foreground="#999").pack(anchor="w", pady=(14, 0))

    _refresh_dashboard()

    # 레이드 카운터 등 탭으로 전환 시 자동으로 결과 갱신
    def _on_tab_changed(_e=None):
        try:
            tab = notebook.tab(notebook.select(), "text").strip()
            if tab == "PvP 메타":
                _refresh_meta_active()
            elif tab == "PvE 카운터":
                refresh_counters()
            elif tab == "PvE 로켓":
                refresh_rocket()
            elif tab == "오늘 할 일":
                _refresh_dashboard()
        except Exception:
            pass
    notebook.bind("<<NotebookTabChanged>>", _on_tab_changed)

    # 탭 정렬: PvP → PvE → 공통 (시작 탭 PvP 분석이 맨 앞)
    tab_order = [
        # PvP (고배틀리그)
        iv_tab, compare_tab, meta_tab,
        # PvE (레이드·맥스배틀)
        raid_tab, rkt_tab, invest_tab, maxbox_tab,
        # 공통 (게임 전반 정보·유틸)
        dash_tab, search_tab, type_tab, events_tab, raid_sched_tab, eggs_tab, research_tab,
    ]
    for _idx, _t in enumerate(tab_order):
        try:
            notebook.insert(_idx, _t)
        except Exception:
            pass
    # 시작 시 PvP 분석(좌측 종 리스트가 구동하는 핵심 탭)에 포커스
    try:
        notebook.select(iv_tab)
    except Exception:
        pass

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
            settings["best_buddy"] = bool(best_buddy_var.get())
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

def _pretty_move(mid):
    """moveId(WATERFALL) → 보기 좋은 문자열(Waterfall)."""
    return (mid or "").replace("_", " ").title()


def print_attackers_cli(gm, type_input, n, level):
    """--attackers: 특정 타입 범용 PvE 딜러 랭킹 출력."""
    moves_by_id = {m["moveId"]: m for m in gm.get("moves", [])}
    dex_to_ko = load_korean_dex_map()
    sid_to_display = {sid: disp for disp, sid in build_display_entries(gm, dex_to_ko)}
    atype = _TYPE_KO_TO_EN.get(type_input.strip(), type_input.strip().lower())
    if atype not in TYPES_ORDER:
        print(f"알 수 없는 타입: {type_input}  (가능: {', '.join(TYPE_KO.values())})")
        return
    res = best_attackers_for_type(gm, moves_by_id, atype, n=n, attacker_level=level)
    print(f"=== {TYPE_KO.get(atype, atype)} 타입 범용 PvE 딜러 TOP {n} "
          f"(Lv{level:g}, DPS 순) ===\n")
    print(f"{'순위':<5}{'포켓몬':<20}{'eDPS':>7}{'DPS':>7}{'TDO':>7}  무브셋")
    print("-" * 72)
    for i, r in enumerate(res, 1):
        disp = sid_to_display.get(r["sid"], r["sid"])
        ms = f"{_pretty_move(r['fast_id'])} + {_pretty_move(r['charged_id'])}"
        print(f"{i:<5}{disp:<20}{r['edps']:>7.1f}{r['dps']:>7.1f}"
              f"{r['tdo']:>7.0f}  {ms}")


def print_invest_cli(gm, n, level):
    """--invest: 즐겨찾기 PvE 투자 우선순위 출력."""
    favorites = load_favorites()
    if not favorites:
        print("즐겨찾기가 비어 있습니다. GUI 에서 ★ 로 보유/관심 포켓몬을 등록한 뒤 다시 실행하세요.")
        return
    moves_by_id = {m["moveId"]: m for m in gm.get("moves", [])}
    dex_to_ko = load_korean_dex_map()
    sid_to_display = {sid: disp for disp, sid in build_display_entries(gm, dex_to_ko)}
    res = investment_priority(gm, moves_by_id, favorites, attacker_level=level)
    print(f"=== 즐겨찾기 PvE 투자 우선순위 (Lv{level:g}) ===")
    print("각 포켓몬의 최고 가치 역할(타입) + 그 타입 전체 딜러 중 순위. "
          "상위권일수록 키울 가치 큼.\n")
    print(f"{'포켓몬':<20}{'역할':<7}{'타입내순위':>12}{'eDPS':>8}  등급")
    print("-" * 64)
    for r in res:
        disp = sid_to_display.get(r["sid"], r["sid"])
        pct = r["percentile"]
        if pct <= 5:
            grade = "★★★ 최우선"
        elif pct <= 15:
            grade = "★★ 우선"
        elif pct <= 35:
            grade = "★ 쓸만함"
        else:
            grade = "— 비주력"
        rank_str = f"#{r['rank']}/{r['total']}"
        print(f"{disp:<20}{TYPE_KO.get(r['type'], r['type']):<7}"
              f"{rank_str:>12}{r['edps']:>8.1f}  {grade}")


def print_routine_cli():
    """--routine: 매일/주간 챙겨야 할 포고 루틴 체크리스트 출력."""
    print("=== 포켓몬GO 일일 루틴 체크리스트 ===")
    print("매일 챙기면 좋은 것들 (가성비 높은 순)\n")
    print("[매일]")
    for _k, label, note in DAILY_ROUTINE:
        print(f"  □ {label}")
        print(f"      └ {note}")
    print("\n[주간]")
    for _k, label, note in WEEKLY_ROUTINE:
        print(f"  □ {label}")
        print(f"      └ {note}")
    print("\n(GUI '오늘 할 일' 탭에서는 체크 상태가 저장되고 매일/매주 자동 초기화됩니다.)")


def print_maxtier_cli():
    """--maxtier: 다이맥스/거다이맥스 배틀 추천 티어 출력."""
    print(f"=== 다이맥스/거다이맥스 배틀 추천 (참고용 · {MAXBATTLE_UPDATED} 기준) ===")
    print("출처: GO Hub / doctorpokegogo. 맥스배틀은 레이드와 역학이 달라 별도 큐레이션.\n")
    print("[⭐ 최우선 S급 어택커]")
    print("  " + ", ".join(MAXBATTLE_S_ATTACKERS))
    print("\n[⚔️ 타입별 추천 어택커]")
    for ty, name, mv in MAXBATTLE_ATTACKERS_BY_TYPE:
        print(f"  {ty:<4} {name:<16} {mv}")
    print("\n[🛡️ 탱커] (0.5초 평타 = 변신 빠름 = 덜 맞음)")
    for name, mv, why in MAXBATTLE_TANKS:
        print(f"  {name:<18} {mv:<14} {why}")
    print("\n[➕ 힐러] (높은 HP → 회복량 ↑)")
    for name, why in MAXBATTLE_HEALERS:
        print(f"  {name:<10} {why}")
    print(f"\n[🐋 출시된 거다이맥스 {len(MAXBATTLE_GIGANTAMAX)}종]")
    print("  " + ", ".join(MAXBATTLE_GIGANTAMAX))
    print("\n[🔷 출시된 다이맥스 (주요)]")
    print("  " + ", ".join(MAXBATTLE_DYNAMAX))
    print("  ※ 다이맥스는 순환 풀이라 전체는 게임 내 '다이맥스' 검색으로 확인.")


def print_search_cli(gm, name, league=None, max_level=DEFAULT_MAX_LEVEL):
    """--search: 베스트 개체값 인게임 검색 문자열 출력."""
    dex_to_ko = load_korean_dex_map()
    ko_base_map = build_ko_base_map(gm, dex_to_ko)
    sid_to_display = {sid: disp for disp, sid in build_display_entries(gm, dex_to_ko)}
    p, alts = find_pokemon_cli(gm, ko_base_map, name)
    if not p:
        print(f"'{name}' — 찾을 수 없음.")
        return
    base = p["baseStats"]
    disp = sid_to_display.get(p["speciesId"], p.get("speciesName", name))
    max_idx = min(int(round((max_level - 1.0) * 2)), len(CPM) - 1)
    print(f"=== {disp} — 베스트 개체값 인게임 검색 문자열 ===\n")
    lgs = [_find_league(league)] if league else list(LEAGUES)
    for lg in lgs:
        if not lg:
            print(f"리그를 찾을 수 없음: {league}")
            return
        ranked = rank_all(base, lg.cap, max_idx)
        if not ranked or ranked[0][1] == 0:
            continue
        iv = ranked[0][0]
        ex, near = ingame_search_strings(iv, name=disp)
        print(f"[{lg.name}]  베스트 {iv[0]}/{iv[1]}/{iv[2]}")
        print(f"   정확: {ex}")
        print(f"   근사: {near}")
    print("\n자주 쓰는 검색어:")
    for label, term in COMMON_SEARCH_TERMS:
        print(f"   {label:<22} {term}")


def print_searchhelp_cli():
    """--searchhelp: 인게임 검색어 사전 전체 출력 (복사용)."""
    print("=== 포켓몬GO 인게임 검색어 모음 (복사해서 검색창에 붙여넣기) ===")
    print("& = 그리고 · 쉼표 = 또는 · ! = 제외 · 범위: 3-4 / 3-(이상) / -1(이하)\n")
    for cat, items in SEARCH_LIBRARY:
        print(f"[{cat}]")
        for label, term in items:
            print(f"   {term:<28} {label}")
        print()


def print_fusion_cli(bundles=None, goal=FUSION_GOAL_DEFAULT):
    """--fusion: 합체/변신 에너지 공식·표 + (선택) 기대 에너지 추정."""
    print("=== 합체/변신 에너지 계산 (네크로즈마·큐레무·버드렉스 등) ===")
    print(f"공식: 1회 보상 에너지 = {FUSION_ENERGY_BASE} + {FUSION_ENERGY_PER_DROP}×(에너지 당첨 꾸러미 수)")
    print(f"      에너지 당첨 확률 ≈ {FUSION_ENERGY_DROP_RATE:.0%}, 합체 1회 제작 ≈ {goal} 에너지\n")
    print(f"{'비스트볼':<8}{'보상 꾸러미':<12}{'기대 에너지':<12}")
    print("-" * 32)
    for balls, bundle, energy in FUSION_BEASTBALL_TABLE:
        print(f"{balls:<10}{bundle:<14}{energy}")
    if bundles is not None:
        e = fusion_expected_energy(bundles)
        runs = max(1, int(round(goal / e)))
        print(f"\n보상 꾸러미 {bundles}개 → 기대 에너지 약 {e:.0f}")
        print(f"목표 {goal} 달성까지 약 {runs}회 필요 (회당 ~{e:.0f})")


def main():
    ap = argparse.ArgumentParser(description="Pokemon GO PvP 개체값 리그 랭커",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("--cli", action="store_true", help="콘솔 CLI 모드 강제")
    ap.add_argument("pokemon", nargs="?", help="포켓몬 이름 (한글/영문)")
    ap.add_argument("ivs", nargs="*", help="개체값 3개 (공 방 체)")
    ap.add_argument("--max-level", type=float, default=DEFAULT_MAX_LEVEL,
                    help="최대 레벨 (기본 50 = Best Buddy 없이 도달 가능; "
                         "Best Buddy 활성 시 51 지정)")
    ap.add_argument("--league", metavar="리그",
                    help="개체값 없이 이름만 줄 때, 이 리그의 상위 개체값 목록 출력 "
                         "(예: --league 슈퍼리그). 생략하면 리그별 최고 개체값 표")
    ap.add_argument("--top", type=int, default=10,
                    help="--league 와 함께 — 상위 몇 개 개체값을 보일지 (기본 10)")
    ap.add_argument("--refresh", action="store_true",
                    help="시즌 데이터 강제 재다운로드 (gamemaster + rankings)")
    ap.add_argument("--attackers", metavar="타입",
                    help="해당 타입의 범용 PvE 딜러 랭킹 (예: --attackers 불꽃 / fire)")
    ap.add_argument("--invest", action="store_true",
                    help="즐겨찾기 포켓몬의 PvE 투자 우선순위 분석")
    ap.add_argument("--routine", action="store_true",
                    help="매일/주간 챙겨야 할 포고 루틴 체크리스트 출력")
    ap.add_argument("--maxtier", action="store_true",
                    help="다이맥스/거다이맥스 배틀 추천 티어 출력")
    ap.add_argument("--search", metavar="포켓몬",
                    help="베스트 개체값 인게임 검색 문자열 생성 (--league 로 리그 한정 가능)")
    ap.add_argument("--searchhelp", action="store_true",
                    help="인게임 검색어 사전 전체 출력 (복사용)")
    ap.add_argument("--fusion", nargs="?", const=-1, type=int, metavar="꾸러미수",
                    help="합체/변신 에너지 공식·표 출력 (보상 꾸러미 수를 주면 기대 에너지 추정)")
    ap.add_argument("--level", type=float, default=40,
                    help="--attackers/--invest 공격자 레벨 (기본 40)")
    ap.add_argument("-n", type=int, default=20,
                    help="--attackers/--invest 표시 개수 (기본 20)")
    args = ap.parse_args()

    if args.routine:
        print_routine_cli()
        return

    if args.maxtier:
        print_maxtier_cli()
        return

    if args.searchhelp:
        print_searchhelp_cli()
        return

    if args.fusion is not None:
        print_fusion_cli(None if args.fusion == -1 else args.fusion)
        return

    if args.refresh:
        print("=== 데이터 강제 갱신 ===")
        refresh_all_data()
        print("=== 갱신 완료 ===\n")

    gm = load_gamemaster()
    init_leagues(gm)

    if args.search:
        print_search_cli(gm, args.search, league=args.league, max_level=args.max_level)
    elif args.attackers:
        print_attackers_cli(gm, args.attackers, args.n, args.level)
    elif args.invest:
        print_invest_cli(gm, args.n, args.level)
    elif args.cli or args.pokemon:
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
