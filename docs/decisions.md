# Decisions

결정할 때마다 아래 형식으로 한 항목씩 추가한다.

<!--
## YYYY-MM-DD: <결정 제목>
- 결정:
- 대안:
- 이유:
-->

## 2026-10-31: 웹 프레임워크 FastAPI
- 결정: FastAPI
- 대안: Flask(계획서 초기안)
- 이유: 마감까지 시간이 짧아 API 문서를 따로 작성할 여유가 없고, FastAPI는 API 문서를 자동으로 생성한다. 비동기를 지원한다.

## 2026-10-31: DB PostgreSQL
- 결정: PostgreSQL
- 대안: MySQL(계획서 초기안)
- 이유: 이 프로젝트에서는 DB 선택이 결과에 미치는 영향이 작아, 하나로 정하고 넘어간다.

## 2026-11-01: 의존성 관리 도구 uv
- 결정: uv (`pyproject.toml` + `uv.lock`)
- 대안: pip + requirements.txt
- 이유: 사용자 결정. lock 파일로 로컬과 Docker 이미지의 의존성 버전을 같게 맞출 수 있다.
