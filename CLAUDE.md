# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 목적
토마토의 3일 후·7일 후 도매/소매 전국 평균 가격과 등락률을 ML로 예측하고, LLM이 그 결과를 쉬운 문장으로 설명해 유통업자의 매입 시점·물량 판단(1순위)과 농업인의 출하 판단(2순위)을 돕는다.
캡스톤디자인 2, 1인 개발, 마감 2026-11-17경. 기준 문서는 `intent/intent.md`.

## 규칙 (intent.md Constraints 기준)
- LLM은 가격을 예측하지 않고 설명만 한다.
- 도매와 소매는 별도 모델. 예측 대상은 3일/7일 후 전국 평균 가격 + 등락률.
- 평가는 (a) 실제와 예측의 차이, (b) 상승·하락 방향 적중. 구체 지표: (미정)
- 데이터는 공공 API 우선, 크롤링은 API로 못 얻는 정보·과거 데이터 확보용 보조.
- 웹 FastAPI, DB PostgreSQL 확정. 그 외 스택(예측 모델 등)은 미정이며 임의로 가정하지 말 것.
- 시간 순서를 지키는 검증. 예측 시점에 알 수 없는 정보를 feature로 쓰지 않음.
- LLM 설명은 입력된 예측값·데이터·뉴스에만 근거.
- 크롤링 대상의 이용약관·robots 확인.
- 비밀값은 `.env`, 개인정보 문서는 repo에 넣지 않음.
<!-- disused (2026-11-05, 현장 인터뷰 산출물 미사용): - 현장 인터뷰는 참여 동의, 녹음은 별도 동의, 보고서에는 익명. -->
- API 키는 .env에서 읽고, 출력하거나 파일에 쓰지 않는다

## 작업 방식
- 일자별 계획 대신 단계별 완료 기준으로 진행한다.
- 결정은 `docs/decisions.md`에, 조사는 `docs/research/`에 기록한다.
- intent.md의 `[미정]` 항목은 사용자 확인 없이 확정하지 않는다.
- GPU 학습은 Colab A100(휘발성 세션). 결과물(모델·지표)은 파일로 repo에 가져온다.

## 명령어
- 의존성: `uv sync` · 테스트: `uv run pytest` (단일: `uv run pytest tests/test_metrics.py::test_errors_b1`)
- DB 테스트: `TEST_DATABASE_URL=postgresql://… uv run pytest tests/test_api_db.py` (없으면 skip)
- CLI: `uv run tomato db init | collect backfill|daily | train | predict | backtest --models B1,B2,lgbm --to 2026-11-04 | explain | show latest` (`DATABASE_URL` 필요). Docker: `docker compose run --rm app tomato <명령>`
- LightGBM 튜닝(검증 구간만): `uv run python scripts/tune_lgbm.py` · 2단계 사후 분석: `uv run python scripts/posthoc_stage2.py`
- Chronos-2(호스트): `uv run --group chronos …` (예: `scripts/chronos2_validate.py`, `tomato backtest --models …,chronos2`). 실제 모델 테스트: `CHRONOS_REAL=1 uv run --group chronos pytest tests/test_chronos2.py`
- `predict` 기본은 운영 모델(h = 3·7 Chronos-2, 실패 시 LightGBM). Docker 이미지에 CPU torch와 Chronos-2 가중치가 들어 있고 실행 중에는 오프라인이다
- 대시보드: `uv run uvicorn tomato.api.main:app`
- LLM 해설 증류(spec §6.1~6.3): 입력 생성 `uv run --group chronos python scripts/build_explain_inputs.py --cache <scratch>/c.npz` · 프롬프트 시험 `uv run python scripts/prompt_trial.py --out <repo 밖>` · Colab 묶음 `scripts/pack_distill_bundle.sh` · 노트북 재생성 `uv run python scripts/build_notebooks.py` · 데모 서버 GPU 확인(Docker만, 호스트 설치 금지) `docker build -t tomato-demo-gpu deploy/demo-gpu` 후 `scripts/demo_gpu_check.py` 맨 위의 `docker run` 명령 (fp16 확인 / `--timing` 채택 VRAM) · 채점 `uv run python scripts/score_distill.py` · 사람 점검 `uv run python scripts/human_review.py make|merge`
- LLM 제공자는 `.env`의 `LLM_PROVIDER`(template|local|api|auto)로만 바꾼다. 호출은 `explain/llm.py` 한 곳
