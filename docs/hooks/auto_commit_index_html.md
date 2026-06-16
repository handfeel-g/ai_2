# auto_commit_index_html Stop hook

## 목적
- Codex 작업이 종료될 때 `index.html`이 수정된 경우에만 자동 커밋한다.
- `index.html` 변경이 없으면 아무 작업도 하지 않는다.
- 다른 파일은 자동 커밋 대상에 포함하지 않는다.

## 파일 구조
- `.codex/hooks.json`: Codex `Stop` 이벤트에 wrapper를 연결한다.
- `.codex/rules/default.rules`: Stop hook wrapper 명령만 허용하도록 보강한다.
- `tools/hooks/auto_commit_index_html.py`: 자동 커밋 판단과 Git 작업을 수행하는 Python wrapper다.
- `docs/hooks/auto_commit_index_html.md`: 동작 설명과 검증 방법을 정리한다.

## Rules 역할
- `Stop` hook wrapper 명령만 실행 허용 범위에 둔다.
- Windows에서는 `py tools/hooks/auto_commit_index_html.py`를 사용한다.
- macOS/Linux에서는 `python3 tools/hooks/auto_commit_index_html.py`를 사용한다.
- `git add -A`, `git add .`, `git commit`, `py` 단독 실행은 자동 허용 대상이 아니다.

## Stop hook 역할
- Codex 종료 시 wrapper를 실행한다.
- wrapper는 `index.html` 변경 여부만 확인하고, 변경이 있을 때만 커밋한다.

## wrapper 동작
1. `git rev-parse --show-toplevel`로 repo root를 찾는다.
2. `.codex/logs/auto_commit_index_html.log`를 append 모드로 연다.
3. 실행 시각, repo root, Python executable, OS 정보를 기록한다.
4. Python, Git, Git repo, `index.html`, `git user.name`, `git user.email`, lock 상태를 확인한다.
5. `git status --porcelain -- index.html`로 변경 여부만 판단한다.
6. 변경이 없으면 `NO_INDEX_HTML_CHANGE`를 기록하고 종료한다.
7. 변경이 있으면 `git add -- index.html`만 수행한다.
8. `pre-commit`이 설치되어 있으면 `sys.executable -m pre_commit run --files index.html`을 실행한다.
9. `pre-commit`이 없으면 `PRE_COMMIT_NOT_INSTALLED_SKIP`를 기록하고 계속한다.
10. `pre-commit` 실패 시 `PRE_COMMIT_FAILED`를 기록하고 커밋하지 않는다.
11. 다시 `git add -- index.html`만 수행한다.
12. staged 변경이 없으면 `NO_STAGED_INDEX_HTML_CHANGE`를 기록하고 종료한다.
13. staged 변경이 있으면 `git commit -m "auto: update index.html"`을 수행한다.
14. 성공 시 `COMMIT_SUCCESS`와 commit hash를 기록한다.
15. 실패 시 `GIT_COMMIT_FAILED`와 에러를 기록한다.

## 로그 위치
- `.codex/logs/auto_commit_index_html.log`
- 로그 디렉터리는 wrapper가 자동 생성한다.
- 로그 파일은 자동 커밋 대상에 포함하지 않는다.

## trust 필요 여부
- 필요하다.
- 프로젝트 로컬 hook은 프로젝트 `.codex/` 레이어가 trusted 상태여야 로드된다.
- 또한 실제 실행 전에는 `/hooks`에서 해당 hook 정의를 검토하고 trust해야 한다.

## 테스트 방법
- 이번 턴에서는 테스트를 실행하지 않는다.
- 이후 확인 시에는 `index.html` 변경 유무에 따라 `NO_INDEX_HTML_CHANGE` 또는 `COMMIT_SUCCESS`가 기록되는지만 점검한다.
