"""Pokemon GO 디스코드 봇 — Gemini 자연어 라우팅.

사용자가 "@봇 라프라스 어디서 잡아?" 처럼 자연어로 물어보면
Gemini가 적절한 도구를 호출해서 답변한다.

실행:
    pip install -r requirements-bot.txt
    # .env 작성 (.env.example 참고)
    python bot.py
"""
from __future__ import annotations

import asyncio
import functools
import os
import sys
import traceback
from typing import Any

# stdout/stderr line-buffered 강제 (백그라운드 실행 시 print 즉시 보이도록)
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types

import pogo_iv as P

# ───────────── 환경 설정 ─────────────
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
ALLOWED_CHANNEL_IDS = {
    int(x) for x in os.environ.get("ALLOWED_CHANNEL_IDS", "").split(",") if x.strip().isdigit()
}

if not GEMINI_API_KEY or not DISCORD_BOT_TOKEN:
    sys.exit("환경변수 GEMINI_API_KEY / DISCORD_BOT_TOKEN 이 비어있음. .env 확인.")

# 무료 티어 RPD 한도가 매우 작아서(2026-05 기준 Flash 20 RPD) Lite 를 메인으로.
# Lite 도 도구 라우팅엔 충분히 똑똑하고 한도 더 여유 있음. Flash 는 Lite 가 다 떨어졌을 때 폴백.
GEMINI_MODEL_FALLBACKS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

# ───────────── 봇 시작 시 한 번 로드 ─────────────
print("[bot] pogo_iv 데이터 로딩…", flush=True)
GM = P.load_gamemaster()
P.init_leagues(GM)
DEX_TO_KO = P.load_korean_dex_map()        # 1 → "이상해씨" 같은 매핑
KO_TO_SID = P.build_ko_base_map(GM, DEX_TO_KO)  # "누오" → "quagsire" 매핑 (검색용 — 이게 핵심)
MOVE_KO = P.load_move_ko_map()
MOVES_BY_ID = {m["moveId"]: m for m in GM.get("moves", [])}
SID_TO_DISPLAY = P.build_sid_display_full(GM, DEX_TO_KO)
print(f"[bot] 포켓몬 {len(GM.get('pokemon', []))}종 / 한글검색 {len(KO_TO_SID)}개 / 기술 {len(MOVES_BY_ID)}개 로드 완료", flush=True)


def _refresh_schedule_data() -> dict:
    """매번 호출 시 캐시 정책(1일)대로 자동 재다운로드되므로 부담 없음."""
    return {
        "eggs": P.load_eggs(),
        "raids": P.load_combined_raids(),
        "rockets": P.load_rocket_lineups(),
        "research": P.load_research(),
        "events": P.load_events(),
    }


# ───────────── 헬퍼: 포켓몬 한글 이름 → pokemon dict ─────────────
def _find(name: str):
    p, alts = P.find_pokemon_cli(GM, KO_TO_SID, name)
    return p, alts


def _display(p: dict) -> str:
    sid = p.get("speciesId", "")
    return SID_TO_DISPLAY.get(sid, p.get("speciesName", sid))


# ───────────── Gemini 도구 함수 (자연어로 호출됨) ─────────────
# 핵심 원칙: 함수 시그니처와 docstring만 보고 Gemini가 언제/어떻게 부를지 판단함.
# 따라서 docstring을 충실히 작성하고 인자 타입은 단순하게.

def _tool(fn):
    """도구 함수를 감싸서 호출 로그 + 예외 traceback 출력.
    자동 함수 호출 모드에선 SDK가 예외를 삼키므로 여기서 잡아 로깅한다."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        arg_repr = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
        print(f"[tool] {fn.__name__}({arg_repr})", flush=True)
        try:
            result = fn(*args, **kwargs)
            preview = result[:200].replace("\n", " ⏎ ") if isinstance(result, str) else repr(result)[:200]
            print(f"[tool] {fn.__name__} → {preview}", flush=True)
            return result
        except Exception as e:
            print(f"[tool] {fn.__name__} 예외: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            return f"[도구 오류] {type(e).__name__}: {e}"
    return wrapper

@_tool
def analyze_pokemon(name: str, atk: int = 15, defense: int = 15, hp: int = 15) -> str:
    """포켓몬의 IV(개체값) 분석 + 각 PvP 리그(리틀/슈퍼/하이퍼/마스터)에서의 순위/CP/최적 레벨.

    다음과 같은 질문에 모두 이 도구를 써:
    - "X 슈퍼리그에서 1등 IV가 뭐야?" / "X의 최적 IV 조합?" (사용자 IV 안 줘도 호출 — 결과에 각 리그별 최적 IV가 포함됨)
    - "X IV 0/15/14 어때?" / "이거 100% 좋아?" (사용자가 준 IV 분석)
    - "X 슈퍼리그 갈만해?" / "X 어느 리그가 좋아?"

    Args:
        name: 한글 포켓몬 이름. "누오", "마릴리", "메가 갸라도스", "그림자 뮤츠" 같은 폼 prefix 지원.
        atk: 사용자 공격 IV (0~15). 사용자가 IV 안 알려줬으면 15 그대로 둬.
        defense: 사용자 방어 IV (0~15). 사용자가 IV 안 알려줬으면 15 그대로 둬.
        hp: 사용자 체력 IV (0~15). 사용자가 IV 안 알려줬으면 15 그대로 둬.

    Returns:
        리그별로 사용자 IV 의 순위/CP + 그 리그의 최적(1등) IV 조합 텍스트.
    """
    p, alts = _find(name)
    if not p:
        return f"'{name}' 포켓몬을 찾을 수 없음. 한글 이름으로 다시 시도해줘."
    ivs = (max(0, min(15, atk)), max(0, min(15, defense)), max(0, min(15, hp)))
    rows, best = P.analyze_pokemon(p, ivs, max_level=51)
    label = P.appraisal_label(ivs)
    sid = p["speciesId"]

    # 리그명 → (cup_id, cap) — pogo_iv 의 LEAGUES 이름과 정확히 일치 (공백 없음)
    league_to_cap = {
        "리틀컵": ("all", 500), "슈퍼리그": ("all", 1500),
        "하이퍼리그": ("all", 2500), "마스터리그": ("all", 10000),
    }

    def _meta_rank_for(league_name: str):
        """전체 메타 랭킹에서 이 종의 위치. 반환: (rank, total, score) 또는 None."""
        key = league_to_cap.get(league_name)
        if not key:
            return None
        ranking = P.load_league_rankings(key[0], key[1])
        if not ranking:
            return None
        for i, e in enumerate(ranking, 1):
            if e.get("speciesId") == sid:
                return (i, len(ranking), e.get("score", 0))
        return ("권외", len(ranking), 0)

    lines = [f"**{_display(p)}** — {label} (입력 IV {ivs[0]}/{ivs[1]}/{ivs[2]})"]
    for league_name, lvl, cp, sp, rank, pct, top_iv in rows:
        if lvl is None:
            lines.append(f"  · {league_name}: 분석 불가 (CP 캡 초과)")
            continue
        top_iv_str = f"{top_iv[0]}/{top_iv[1]}/{top_iv[2]}" if top_iv else "?"
        meta = _meta_rank_for(league_name)
        meta_line = ""
        if meta:
            if meta[0] == "권외":
                meta_line = f"메타 랭킹: 권외 (전체 {meta[1]}종 밖)"
            else:
                meta_line = f"메타 랭킹: **{meta[0]}위/{meta[1]}종** (점수 {meta[2]:.1f})"
        iv_line = f"입력 IV {ivs[0]}/{ivs[1]}/{ivs[2]} 는 이 종의 4096개 IV조합 중 #{rank} ({pct:.1f}%) · 그 리그 최적 IV는 {top_iv_str}"
        block = f"  · **{league_name}**: Lv{lvl} CP{cp}"
        if meta_line:
            block += f"\n     - {meta_line}"
        block += f"\n     - {iv_line}"
        lines.append(block)
    if best:
        lines.append(f"\n_(입력 IV {ivs[0]}/{ivs[1]}/{ivs[2]} 기준 가장 잘 활용되는 리그: {best[0]}, {best[5]:.1f}%)_")
    if alts:
        lines.append(f"_다른 후보_: {', '.join(alts[:3])}")
    return "\n".join(lines)


@_tool
def find_acquisition(name: str) -> str:
    """이 포켓몬을 현재 일정상 어디서 잡을 수 있는지 알려준다 (알/레이드/필드 리서치/로켓단).

    사전 진화 단계까지 거슬러 검색한다. 예: 라프라스 자체가 알에 없어도
    진화 전 단계가 알에 있으면 함께 표시.

    Args:
        name: 한글 포켓몬 이름.

    Returns:
        입수 경로 텍스트. 현재 일정상 안 잡히면 안내 메시지.
    """
    p, _ = _find(name)
    if not p:
        return f"'{name}' 포켓몬을 찾을 수 없음."
    data = _refresh_schedule_data()
    text = P.find_acquisition_for_sid(
        p["speciesId"], GM,
        data["eggs"], data["raids"], data["rockets"], data["research"],
        SID_TO_DISPLAY,
    )
    if not text or not text.strip():
        return f"**{_display(p)}** — 현재 일정상 알/레이드/리서치/로켓에서 잡을 방법이 없는 것 같음. 야생/진화 위주로 확인 필요."
    return f"**{_display(p)}** 입수 경로:\n{text}"


@_tool
def top_counters(boss_name: str, n: int = 10, weather: str = "") -> str:
    """레이드 보스나 임의 포켓몬에 대한 카운터 TOP N (eDPS 기준).

    Args:
        boss_name: 한글 보스 이름. "레쿠쟈", "메가 갸라도스" 등.
        n: 표시 개수. 기본 10, 최대 20.
        weather: 날씨 보너스. "맑음", "비", "구름조금", "흐림", "바람", "눈", "안개" 중 하나. 빈 문자열이면 무시.

    Returns:
        카운터 포켓몬 + 추천 무브셋 + eDPS 텍스트.
    """
    p, _ = _find(boss_name)
    if not p:
        return f"'{boss_name}' 보스를 찾을 수 없음."
    n = max(1, min(20, n))
    weather_map = {
        "맑음": "clear", "비": "rain", "구름조금": "partly_cloudy", "흐림": "cloudy",
        "바람": "windy", "눈": "snow", "안개": "fog",
    }
    weather_code = weather_map.get(weather.strip(), None)
    counters = P.top_counters(
        p, GM, MOVES_BY_ID, n=n, weather=weather_code,
        include_shadow=True, include_mega=True, include_legendary=True,
    )
    if not counters:
        return f"**{_display(p)}** 카운터를 산출할 수 없음."
    lines = [f"**{_display(p)}** 카운터 TOP {len(counters)}" + (f" (날씨 {weather})" if weather_code else "")]
    for i, c in enumerate(counters, 1):
        atk = c["pokemon"]
        atk_disp = SID_TO_DISPLAY.get(atk.get("speciesId", ""), atk.get("speciesName", "?"))
        fast_ko = P.prettify_move(c["fast_id"], MOVE_KO)
        charged_ko = P.prettify_move(c["charged_id"], MOVE_KO)
        lines.append(f"{i}. {atk_disp} — {fast_ko} + {charged_ko} (eDPS {c['edps']:.1f})")
    return "\n".join(lines)


@_tool
def current_raids(region: str = "all") -> str:
    """현재 활성 레이드 보스 목록 (글로벌 + 한국).

    Args:
        region: "kr" = 한국만, "global" = 글로벌만, "all" = 전체(기본).

    Returns:
        티어별로 그룹화된 레이드 보스 텍스트.
    """
    raids = P.load_combined_raids()
    if not raids:
        return "현재 활성 레이드 데이터를 불러올 수 없음."
    region = region.lower().strip()
    if region == "kr":
        raids = [r for r in raids if r.get("_source") in ("kr", "global+kr")]
    elif region == "global":
        raids = [r for r in raids if r.get("_source") in ("global", "global+kr")]

    def _tier_order(t: str) -> int:
        order = {"5-Star": 0, "Mega": 1, "Shadow": 2, "Elite": 3, "3-Star": 4, "1-Star": 5}
        for k, v in order.items():
            if k in (t or ""):
                return v
        return 99

    raids.sort(key=lambda r: _tier_order(r.get("tier", "")))
    lines = [f"현재 활성 레이드 ({region.upper() if region != 'all' else '글로벌+한국'})"]
    current_tier = None
    for r in raids[:40]:
        tier = r.get("tier", "?")
        if tier != current_tier:
            lines.append(f"\n**[{tier}]**")
            current_tier = tier
        name_en = r.get("name", "?")
        boss_p = P.find_boss_pokemon(name_en, GM)
        name_ko = SID_TO_DISPLAY.get(boss_p.get("speciesId", ""), name_en) if boss_p else name_en
        src = r.get("_source", "")
        tag = " 🇰🇷" if src == "kr" else (" 🌐" if src == "global" else " ✓")
        lines.append(f"  · {name_ko}{tag}")
    return "\n".join(lines)


@_tool
def league_meta(league: str, top_n: int = 15) -> str:
    """리그별 메타 상위 포켓몬 랭킹.

    Args:
        league: "리틀", "슈퍼", "하이퍼", "마스터" 중 하나, 또는 시즌 컵 이름.
        top_n: 표시 개수. 기본 15, 최대 30.

    Returns:
        리그 상위 N개 포켓몬 + 점수.
    """
    top_n = max(1, min(30, top_n))
    target = league.strip().lower()
    league_map = {
        "리틀": ("all", 500), "슈퍼": ("all", 1500), "하이퍼": ("all", 2500), "마스터": ("all", 10000),
        "little": ("all", 500), "great": ("all", 1500), "ultra": ("all", 2500), "master": ("all", 10000),
    }
    cup_id, cap = None, None
    for k, v in league_map.items():
        if k in target:
            cup_id, cap = v
            break
    if cup_id is None:
        return "리그를 인식할 수 없음. '리틀/슈퍼/하이퍼/마스터' 중에서 골라줘."
    ranking = P.load_league_rankings(cup_id, cap)
    if not ranking:
        return f"{league} 랭킹 데이터 없음."
    lines = [f"**{league}리그 메타 TOP {top_n}** (CP {cap})"]
    for i, entry in enumerate(ranking[:top_n], 1):
        sid = entry.get("speciesId", "")
        score = entry.get("score", 0)
        name_ko = SID_TO_DISPLAY.get(sid, entry.get("speciesName", sid))
        lines.append(f"{i}. {name_ko} ({score:.1f})")
    return "\n".join(lines)


@_tool
def current_events(only_active: bool = True) -> str:
    """현재 진행 중이거나 곧 예정된 포켓몬 GO 이벤트 목록 (커뮤니티 데이, 스포트라이트, 시즌 이벤트 등).

    "이벤트", "커뮤니티 데이", "스포트라이트", "지금 뭐 해", "오늘 뭐 있어" 같은 질문에 호출.
    레이드 보스만 묻는 경우엔 current_raids 를 써.

    Args:
        only_active: True 면 지금 진행 중인 이벤트만, False 면 예정 포함.

    Returns:
        이벤트 목록 텍스트 (이름 + 기간 + 종류).
    """
    import datetime
    events = P.load_events() or []
    if not events:
        return "이벤트 데이터를 불러올 수 없음."
    now = datetime.datetime.now(datetime.timezone.utc)

    def _parse(s):
        if not s:
            return None
        try:
            return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    active = []
    upcoming = []
    for ev in events:
        start = _parse(ev.get("start"))
        end = _parse(ev.get("end"))
        if start and end:
            if start <= now <= end:
                active.append((ev, start, end))
            elif now < start:
                upcoming.append((ev, start, end))

    def _fmt(ev, start, end):
        name = ev.get("name", "?")
        etype = ev.get("eventType", "") or ""
        type_ko = {
            "community-day": "커뮤니티 데이", "spotlight-hour": "스포트라이트",
            "raid-day": "레이드 데이", "raid-battles": "레이드", "raid-hour": "레이드 아워",
            "research-breakthrough": "리서치 돌파", "go-battle-league": "GO 배틀 리그",
            "event": "이벤트", "season": "시즌",
        }.get(etype, etype)
        date_str = start.strftime("%m/%d") + "~" + end.strftime("%m/%d")
        return f"  · [{type_ko}] {name} ({date_str})"

    lines = []
    if active:
        lines.append("**[진행 중]**")
        for ev, s, e in active[:15]:
            lines.append(_fmt(ev, s, e))
    if not only_active and upcoming:
        upcoming.sort(key=lambda x: x[1])
        lines.append("\n**[예정]**")
        for ev, s, e in upcoming[:10]:
            lines.append(_fmt(ev, s, e))
    if not lines:
        return "현재 진행 중인 이벤트가 없어 (또는 데이터가 비어있음)."
    return "\n".join(lines)


# Gemini가 호출 가능한 도구 목록
TOOLS = [analyze_pokemon, find_acquisition, top_counters, current_raids, current_events, league_meta]
TOOL_MAP = {fn.__name__: fn for fn in TOOLS}


# ───────────── Gemini 클라이언트 + 시스템 프롬프트 ─────────────
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """너는 포켓몬 GO 도우미 봇이야. 한국 트레이너에게 한국어로 답변해.

원칙:
- 사용자의 질문 의도를 파악해서 반드시 적절한 도구(tool)를 호출해. 추측이나 일반 지식으로 답하지 마.
- 도구가 "[도구 오류]" 로 시작하는 결과를 주면, 그 오류를 그대로 전달하지 말고 사용자한테 친근하게 안내해.
- 도구 결과를 그대로 던지지 말고, 핵심을 요약하거나 친근하게 다듬어서 답해.
- 답변은 디스코드 메시지로 가니까 너무 길게 쓰지 마. 보통 5~10줄 안쪽.
- 마크다운(**, `, 리스트) 사용 가능. 이모지 적당히 OK.
- 포켓몬 이름은 항상 한글로. (예: Rayquaza ❌ → 레쿠쟈 ✅)

도구 선택 가이드:
- "X 슈퍼/하이퍼 1등 IV", "X 최적 IV", "X 100% 좋아?", "X 어느 리그 갈만?" → analyze_pokemon
- "X 어디서 잡아?", "X 알에 있어?", "X 레이드 떠?" → find_acquisition
- "X 카운터", "X 잡으려면 뭐 데려가?" → top_counters
- "오늘 레이드", "5성 뭐 있어?", "한국 레이드" → current_raids
- "이벤트", "커뮤니티 데이", "오늘 뭐 해?" → current_events
- "슈퍼/하이퍼 메타", "강한 포켓몬 순위" → league_meta

중요 — "순위" 단어의 두 가지 의미를 정확히 구분해:
- **메타 랭킹**: "X가 슈퍼리그에서 몇 등?", "X의 리그 순위" → 전체 종 중 그 종의 등수 (analyze_pokemon 결과의 "메타 랭킹: N위/총개수")
- **IV 순위**: "X 슈퍼리그 1등 IV?", "내 IV 어때?" → 그 종의 4096개 IV 조합 중 등수

사용자가 IV 를 명시 안 하고 "X 슈퍼리그 순위?" 처럼 묻는 건 거의 항상 **메타 랭킹** 을 묻는 거야. IV 순위는 IV 가 주제일 때만 답해.

analyze_pokemon 결과에 메타 랭킹이 명확히 표시되니까 (예: "메타 랭킹: 2위/1234종"), 사용자가 리그 순위 물으면 그 숫자를 그대로 전달해. "이 종 IV 순위 #2757" 같은 내용을 메타 순위인 양 답하면 안 돼.

여러 리그 한 번에 물어보면 (예: "슈퍼랑 하이퍼"), analyze_pokemon 한 번 호출하면 모든 리그 결과 다 나오니까 다시 부를 필요 없어.
"""


# ───────────── Gemini 호출 (수동 함수 호출 루프) ─────────────
# 봇 시작 후 누적 토큰 사용량 (봇 재시작 시 리셋됨 — 전체 일일 사용량은 AI Studio 대시보드 확인)
USAGE = {"calls": 0, "input": 0, "output": 0, "by_model": {}}


def _track_usage(model_name, response):
    um = getattr(response, "usage_metadata", None)
    if not um:
        return
    in_t = getattr(um, "prompt_token_count", 0) or 0
    out_t = getattr(um, "candidates_token_count", 0) or 0
    USAGE["calls"] += 1
    USAGE["input"] += in_t
    USAGE["output"] += out_t
    by = USAGE["by_model"].setdefault(model_name, {"calls": 0, "input": 0, "output": 0})
    by["calls"] += 1; by["input"] += in_t; by["output"] += out_t
    print(
        f"[usage] {model_name} +in={in_t} +out={out_t} | "
        f"누적 calls={USAGE['calls']} in={USAGE['input']:,} out={USAGE['output']:,} total={USAGE['input']+USAGE['output']:,}",
        flush=True,
    )


async def _call_gemini(contents, config):
    """503/429 시 재시도 + 모델 폴백 체인.
    각 모델당 2회 시도(1초/3초 백오프), 그래도 안 되면 다음 모델로."""
    last_err = None
    for model_name in GEMINI_MODEL_FALLBACKS:
        for attempt in range(2):
            try:
                response = await asyncio.to_thread(
                    gemini_client.models.generate_content,
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                _track_usage(model_name, response)
                return response
            except Exception as e:
                last_err = e
                msg = str(e)
                if "503" in msg or "UNAVAILABLE" in msg or "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                    wait = 1 if attempt == 0 else 3
                    print(f"[gemini] {model_name} {attempt+1}/2 장애 ({type(e).__name__}), {wait}초 후 재시도", flush=True)
                    await asyncio.sleep(wait)
                    continue
                raise
        print(f"[gemini] {model_name} 포기, 다음 모델로 폴백", flush=True)
    raise last_err if last_err else RuntimeError("모든 Gemini 모델 호출 실패")


async def ask_gemini(user_message: str, history: list | None = None) -> str:
    """자연어 질문을 받아 Gemini + tool use 루프로 답변 생성 (수동 모드).
    history: 이전 user/model 텍스트 turns (멀티턴 대화용)."""
    print(f"[user] {user_message}", flush=True)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=[
            # 파이썬 함수에서 자동 schema 추출. SDK가 docstring/타입 힌트로 변환.
            types.FunctionDeclaration.from_callable(client=gemini_client, callable=fn)
            for fn in TOOLS
        ])],
        temperature=0.7,
        # 자동 함수 호출 끄기 — 우리가 직접 처리
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents = list(history or [])
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    for hop in range(6):
        response = await _call_gemini(contents, config)
        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content or not candidate.content.parts:
            return "(답변을 생성하지 못했어. 다시 시도해줘.)"

        # 도구 호출 추출
        function_calls = [p.function_call for p in candidate.content.parts if getattr(p, "function_call", None)]

        if not function_calls:
            # 도구 호출 없음 = 최종 답변
            text = (response.text or "").strip()
            return text or "(답변을 생성하지 못했어. 다시 시도해줘.)"

        # 모델의 function_call turn 을 history 에 추가
        contents.append(candidate.content)

        # 각 도구 실행 후 결과를 function_response 로 묶어 추가
        tool_response_parts = []
        for fc in function_calls:
            fname = fc.name
            fargs = dict(fc.args) if fc.args else {}
            print(f"[gemini→tool] {fname}({fargs})", flush=True)
            fn = TOOL_MAP.get(fname)
            if fn is None:
                result = f"[알 수 없는 도구] {fname}"
            else:
                try:
                    result = await asyncio.to_thread(fn, **fargs)
                except Exception as e:
                    print(f"[tool 예외] {fname}: {type(e).__name__}: {e}", flush=True)
                    traceback.print_exc()
                    result = f"[도구 오류] {type(e).__name__}: {e}"
            tool_response_parts.append(types.Part.from_function_response(
                name=fname, response={"result": result if isinstance(result, str) else str(result)}
            ))
        contents.append(types.Content(role="tool", parts=tool_response_parts))
    return "(도구 호출이 너무 많이 반복돼서 답변을 못 만들었어.)"


# ───────────── Discord 봇 ─────────────
intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# 채널별 대화 히스토리 (멀티턴 대화). 최근 4 turns 보관.
CHANNEL_HISTORY: dict[int, list] = {}
HISTORY_MAX_TURNS = 4  # user+model 페어 4개 = 8 메시지


@bot.event
async def on_ready():
    print(f"[bot] 로그인됨: {bot.user} (서버 {len(bot.guilds)}개)", flush=True)


def _strip_mention(content: str, bot_id: int) -> str:
    """메시지에서 봇 멘션 부분 제거."""
    for mention in (f"<@{bot_id}>", f"<@!{bot_id}>"):
        content = content.replace(mention, "")
    return content.strip()


def _split_long(text: str, limit: int = 1900) -> list[str]:
    """디스코드 2000자 제한 회피용 분할."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # 줄바꿈 기준으로 자르기
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    # DM 이거나 봇을 멘션한 경우만 응답
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    if not (is_dm or is_mentioned):
        return
    if ALLOWED_CHANNEL_IDS and not is_dm and message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    content = _strip_mention(message.content, bot.user.id)
    if not content:
        await message.reply("뭘 도와줄까? 예: `라프라스 어디서 잡아?`, `레쿠쟈 카운터 알려줘`, `슈퍼리그 메타 보여줘`")
        return

    # 단축 명령어 — Gemini 안 거치고 즉시 답 (토큰 소비 0)
    lower = content.lower().strip()
    if lower in ("/usage", "/사용량", "사용량", "토큰", "/토큰"):
        lines = [
            "**🪙 봇 시작 후 누적 Gemini 토큰 사용량**",
            f"  · 호출 수: **{USAGE['calls']}회**",
            f"  · Input 토큰: **{USAGE['input']:,}**",
            f"  · Output 토큰: **{USAGE['output']:,}**",
            f"  · 합계: **{USAGE['input']+USAGE['output']:,}**",
        ]
        if USAGE["by_model"]:
            lines.append("\n**모델별:**")
            for m, v in USAGE["by_model"].items():
                lines.append(f"  · `{m}`: {v['calls']}회, in {v['input']:,} / out {v['output']:,}")
        lines.append(
            "\n_봇 재시작하면 카운터 리셋. 실제 일일/분당 사용량은 "
            "<https://aistudio.google.com/rate-limit> 에서 확인._"
        )
        await message.reply("\n".join(lines), mention_author=False)
        return
    if lower in ("/reset", "/clear", "초기화", "/초기화"):
        CHANNEL_HISTORY.pop(message.channel.id, None)
        await message.reply("대화 컨텍스트를 초기화했어. 다음 질문부터 새로 시작.", mention_author=False)
        return

    history = CHANNEL_HISTORY.get(message.channel.id, [])
    async with message.channel.typing():
        try:
            answer = await ask_gemini(content, history=history)
            # 성공 시에만 히스토리에 추가 (에러는 컨텍스트 오염 방지)
            history = history + [
                types.Content(role="user", parts=[types.Part.from_text(text=content)]),
                types.Content(role="model", parts=[types.Part.from_text(text=answer)]),
            ]
            CHANNEL_HISTORY[message.channel.id] = history[-HISTORY_MAX_TURNS * 2:]
        except Exception as e:
            print(f"[bot] Gemini 오류: {e}", flush=True)
            traceback.print_exc()
            msg = str(e)
            if "503" in msg or "UNAVAILABLE" in msg:
                answer = "⚠️ Gemini 무료 티어가 지금 혼잡해서 응답을 못 받았어. 1~2분 후 다시 물어봐줘."
            elif "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                answer = "⚠️ 무료 티어 분당 호출 한도(15회/분)에 걸렸어. 1분 뒤에 다시 시도해줘."
            else:
                answer = f"⚠️ 에러: `{type(e).__name__}: {str(e)[:200]}`"

    for chunk in _split_long(answer):
        await message.reply(chunk, mention_author=False)


if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
