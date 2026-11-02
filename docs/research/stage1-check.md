# 구현 1단계 확인 기록 (spec §11 중 1·2·3·7)

확인일: 2026-11-01 로컬(PostgreSQL 16 임시 인스턴스 + `uv run`), 2026-11-02 Docker(compose v2, `docker-compose.yml`)로 1·2·3번을 다시 확인했다.

| # | 기준 | 결과 |
|---|---|---|
| 1 | `docker compose up`으로 DB·API·대시보드 | **통과** (Docker, 2026-11-02). `/health` = `{"status":"ok","db":"ok"}`, `/` = 200 |
| 2 | 가격 있는 행과 `평균` 행이 CSV와 키·값 일치 (2026-11-02 기준 수정) | **통과** (로컬, Docker 모두). `-` 행만 2행 차이 (원인 미확인, 아래) |
| 3 | daily 실패 시 재시도와 `ingest_run` 기록 | **통과** (Docker, 외부망이 막힌 `offline` 네트워크). 로컬에서는 닫힌 포트로 확인 |
| 7 | 대시보드 5개 요소 | 확인 (`tests/test_api_db.py`, headless Chrome 스크린샷 1000px·400px) |

## 2. backfill 행 수
- 기준 변경(2026-11-02, 사용자 결정): 원래 기준은 "DB 행 수 = manifest 기준값(73,194)"이었다. `-` 행 개수가 요청 기간에 따라 달라져서 "가격이 있는 행과 `평균` 행이 CSV와 키·값 일치"로 바꿨다. `-` 행 2행 차이는 **원인 미확인**으로 남긴다.
- 명령: `tomato collect backfill --from 2002-11-01 --to 2026-10-28`. 48회 요청, 4분, 재시도 0회.
- 결과

| | DB | manifest 기준값 |
|---|---|---|
| 전체 행 | 73,192 | 73,194 |
| price NULL(`-`) | 1,008 | 1,010 |
| 가격 있는 행 | 72,184 | 72,184 |
| `평균` 행 | 12,036 | 12,036 |

- 가격이 있는 72,184행은 키와 값이 CSV와 **모두 같다**.
- 차이는 모두 가격이 `-`인 시장 행이다.
  - CSV에만 있는 행: 광주 각화도매 2020-10-27~29, 부산 남포동건어물 2025-10-27~28 (등급 2개씩, 10행). 원본 CSV 요청 기간의 **마지막 날**(2020-10-29, 2025-10-28) 직전이다.
  - DB에만 있는 행: 광주 서부도매 2019-10-28~30, 부산 남포동건어물 2024-10-28 (등급 2개씩, 8행). backfill 요청 기간의 **첫날**(2019-10-28, 2024-10-26) 직후이다.
  - 모두 요청 기간 경계 며칠 안에서 나타나고 사라진다. KAMIS가 왜 이렇게 응답하는지는 확인하지 못했다.
- 따라서 `-` 행의 개수는 요청 기간을 어떻게 나누는지에 따라 달라진다. 모델 입력인 `평균` 가격과 시장별 가격에는 영향이 없다.

## 3. 재시도 (로컬)
- `KAMIS_URL=http://127.0.0.1:9/ tomato collect daily`: 종료 코드 1
  - `ingest_run`: status=failed, attempts=3, error=`URLError: <urlopen error [Errno 111] Connection refused>`
  - 오류 메시지에 키 문자열 0건
- 단위 테스트(`tests/test_collector.py`)
  - 2번 실패 후 성공: 대기 2초, 4초
  - 3번 모두 실패: 오류 메시지에서 키가 `***`로 가려짐
- 정상 `collect daily`(2026-10-26 ~ 11-01): 60행, status=ok

## Docker 확인 (2026-11-02)
- 환경: Docker compose v2. `db`(postgres:16, named volume `pgdata`)와 `app`(`Dockerfile`로 빌드한 이미지). 포트는 127.0.0.1에만 연다.
- **1번**: `docker compose build && docker compose up -d`
  - db healthcheck 통과 후 app이 기동한다(`tomato db init` → uvicorn).
  - `/health` = `{"status":"ok","db":"ok"}`, `/` = 200
- **2번**: `docker compose run --rm app tomato collect backfill --from 2002-11-01 --to 2026-10-28`
  - 73,192행 upsert, 4분 4초, `ingest_run` 1: status=ok, attempts=1
  - `scripts/check_backfill.py`(호스트에서 컨테이너 DB에 연결)

| | CSV | DB | 결과 |
|---|---|---|---|
| 가격 있는 행 | 72,184 | 72,184 | 키·값 일치 |
| `평균` 행 | 12,036 | 12,036 | 키·값 일치 |
| `-` 행 (기준 제외) | 1,010 | 1,008 | 로컬과 같은 2행 차이 |

- **3번**: `docker compose --profile fault run --rm app-offline tomato collect daily`
  - `app-offline`은 `internal: true` 네트워크에만 붙어 DB에는 닿고 외부 인터넷은 막힌다.
  - 종료 코드 1, 약 6초(대기 2초 + 4초)
  - `ingest_run` 2: job=daily, status=failed, attempts=3, error=`URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`
  - `ingest_run.error` 전체에서 API 키·인증 ID 문자열 0건
  - 비교: 같은 명령을 정상 네트워크(`app`)에서 실행하면 2026-10-27 ~ 11-02, 60행 upsert, status=ok
- **데이터 유지**: `docker compose down`(`-v` 없이) 후 `up -d`
  - db 컨테이너의 마운트는 volume `unip-capstonedesign_pgdata` → `/var/lib/postgresql/data`
  - `price_raw` 73,228행, `ingest_run` 3행이 down 전과 같다.
  - `docker compose down -v`를 쓰면 volume이 지워진다.

## 7. 대시보드
- 표시 요소 5개를 모두 확인했다.
  - 현재 공표가 19,720원 (2026-10-30)
  - 3거래일 후 예상가와 예상 날짜 2026-11-04
  - 최근 120거래일 그래프와 예측점
  - 템플릿 설명
  - 성능 한 줄: B1, 2023년 이후 평균 오차 1,558원, MAPE 6.9%, 929회
- 확인 중 고친 것: 예측 뒤에 수집된 날짜가 있으면 예측점의 x축 위치가 어긋났다. 날짜를 합쳐 정렬하도록 고쳤다.

## B1 backtest (참고, `tomato backtest --models B1`)
| 구간 | MAE(원) | MAPE | 상승/하락 적중률 | 3분류 적중률 | n |
|---|---|---|---|---|---|
| 전체 테스트 (2023-01-02 ~ 2026-10-23 예측 시점) | 1,557.8 | 6.88% | 0% (602일) | 35.2% | 929 |
| 급등 구간 (2023-09 ~ 2024-12) | 2,192.9 | 7.77% | 0% (210일) | 35.2% | 324 |
