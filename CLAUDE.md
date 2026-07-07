# pogo_iv — Pokémon GO 분석 도구 + 디스코드 봇

## 구성
- `pogo_iv.py` — Pokémon GO IV/PvP/PvE 분석 tkinter GUI + 분석 엔진(봇이 라이브러리로 import).
- `bot.py` — 디스코드 봇. Gemini 자연어 라우팅으로 `pogo_iv`의 도구 함수들을 호출.
- 실행 환경: **Windows / PowerShell**, Python 3.13. 의존성은 `requirements-bot.txt`.

---

## 디스코드 봇 운영

> 사용자가 **"포켓몬 봇 켜줘"**, "봇 켜줘", "디스코드 봇 실행", "봇 꺼줘" 등으로 요청하면 아래 절차를 그대로 따른다.

### 1. 켜기 — 먼저 중복 실행부터 확인 (중요)
봇이 2개 뜨면 디스코드에서 한 질문에 **중복 응답**한다. 켜기 전 반드시 확인한다:
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*bot.py*' } |
  Select-Object ProcessId, CommandLine
```
- 결과가 있으면 **이미 켜져 있음** → 새로 켜지 말고 사용자에게 알린다.
- 결과가 없으면 아래로 진행.

프로젝트 루트에서 **백그라운드로** 실행한다 (Bash/PowerShell 도구의 `run_in_background: true`):
```
python bot.py
```
- `.env`에 `GEMINI_API_KEY` / `DISCORD_BOT_TOKEN` 이 있어야 한다 (설정돼 있음. 없으면 봇이 즉시 종료).
- 실행 후 반환된 출력 파일을 Read 해서 다음 줄이 뜨는지 확인하고 사용자에게 보고한다:
  ```
  [bot] 로그인됨: 포켓몬봇#1832 (서버 N개)
  ```
  이 줄이 나오면 로그인 성공. `ServerError`/`RESUMED` 같은 로그는 게이트웨이 일시 현상이며 자동 복구되니 정상이다.
- 참고: 백그라운드로 켠 봇은 이 클로드 세션이 끝나도 계속 돈다(별도 프로세스). 끄려면 아래 절차 필요.

### 2. 로그 확인 ("봇 로그 봐줘")
`run_in_background`로 켰으면 반환된 출력 파일 경로를 Read. 읽는 법:
- `[user] ...` — 사용자가 봇에 보낸 질문
- `[gemini→tool] 이름({인자})` / `[tool] ...` — Gemini가 라우팅한 도구와 결과
- `[usage] 모델 +in=.. +out=..` — 호출당 토큰 사용량
- **단축 명령**(`사용량`, `초기화` 등)은 Gemini를 안 거치므로 로그에 안 남는다. 로그에 없다고 봇이 죽은 게 아니다.

### 3. 끄기 ("봇 꺼줘")
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*bot.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```
(이 세션에서 백그라운드 태스크로 켰다면 TaskStop으로 종료해도 된다.)

### 4. 사용량 확인
디스코드에서 봇에게 `사용량`(또는 `/usage`, `토큰`) 멘션 → 봇 시작 후 누적 토큰을 답한다(Gemini 안 거침, 토큰 0 소비). 봇 재시작 시 카운터 리셋. **실제 일일/분당 한도**는 <https://aistudio.google.com/rate-limit>.

### 모델
`bot.py`의 `GEMINI_MODEL_FALLBACKS` 순서대로 폴백: `gemini-2.5-flash-lite`(메인) → `gemini-2.5-flash` → `gemini-2.0-flash`. 무료 티어 RPD 한도가 작아 Lite를 메인으로 둠.

---

## 봇 코드 검증 (bot.py 수정 시)
디스코드 로그인 없이 도구 레이어만 검증할 수 있다. `bot.py`는 `client.run`을 `if __name__ == "__main__":` 가드로 감싸므로 **import만 하면 봇은 로그인하지 않는다.**
스크립트를 프로젝트 밖(스크래치패드 등)에 두고 실행할 때는 `PYTHONPATH`에 프로젝트 루트를 넣는다:
```powershell
$env:PYTHONPATH = (Get-Location).Path; python <스모크테스트.py>
```
`bot`을 import 후 `B.TOOLS` / `B.TOOL_MAP` 의 각 도구 함수를 직접 호출해, 예외 없이 문자열을 반환하고 `[도구 오류]`로 시작하지 않으면 통과.

---

## 변경 이력 정책
코드를 변경하면 `README.md`의 **'변경 이력'** 섹션도 함께 갱신한다(날짜별 항목 추가). 커밋/푸시는 사용자가 요청할 때만.
