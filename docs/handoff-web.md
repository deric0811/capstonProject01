# 인수인계 노트: 웹 채팅(검토·코칭용)

작성: 2026-11-14 · 대상: repo를 볼 수 없고 2026-11-13 06:14(Colab 02가 `warmup_ratio` 오류로 멈춘 시점)까지만 아는 웹 채팅.
근거: repo의 파일·커밋·`docs/decisions.md`·`docs/progress.md`. 기록에 없는 것은 "미확인"으로 적었다. 시각은 커밋 시각(KST, 로컬)이다. Colab 실행 시각은 기록이 없어 대부분 미확인이다.

## 0. 06:14 직전 상태 (요약)
- 프롬프트 v5 고정(2026-11-12 18:46:37, Colab 런타임 시각). 선생 `Qwen/Qwen3.8-27B` bf16, A100 80GB, 시범 100/100.
- Colab 01 완료(커밋 `9de7786`): 학습 데이터 2,994/3,000(첫 시도 2,976), 검증 200/200, 평가 (iii) 선생 934개 생성(`distill/eval/teacher.jsonl`, 채점 안 함).
- 02 첫 실행: 학생 로드 뒤 `TrainingArguments.__init__() got an unexpected keyword argument 'warmup_ratio'`로 멈춤. Colab의 `pip install -U`가 transformers 최신판(5.22.2)을 받았고 5.x에서 이 인자가 없어졌다.

## 1. 06:14 이후 시간순

| 순서 | 단계 | 결과 | 커밋 | 계획과 달라진 점 |
|---|---|---|---|---|
| 1 | 02·03·04 노트북 수정 | 라이브러리 고정(transformers 5.22.2, peft 0.21.2, bitsandbytes 0.50.2, accelerate 1.15.0. 설치 버전이 다르면 멈춤). `warmup_ratio=0.03` → `warmup_steps=0.03`(1 미만 소수는 ceil(전체 step × 0.03), 예전과 같은 계산). 학습 전 전체·warmup step 출력, 학습 뒤 실제 step 일치 확인, `steps.json` 저장. SMOKE 스위치 추가(결과는 `lora_smoke/`, `merged_nf4_smoke/`, `eval_smoke/`). `save_pretrained(safe_serialization=True)`는 5.x에서 무시되는 인자라 지움(동작 같음). 호출 인자는 설치 소스와 CPU 소형 모델 실행으로 대조 | `a60a2e2` (11-13 06:23) | 학습 설정은 바꾸지 않음. SMOKE와 버전 고정은 새로 넣음 |
| 2 | 02 SMOKE | 통과. 학습 32개·검증 8개, 학습률 1e-4 하나, 4 step(warmup 1) → 체크포인트 2개 → 검증 생성 → 설정 선택 → chosen 저장. 검증 통과율 0.75(의미 없음) | 없음(기록은 대화) | — |
| 3 | 03 SMOKE 1차 | 실패: peft가 bf16 일반 Linear에 LoRA를 붙일 때 torchao 판별을 하는데 Colab의 torchao 0.10.0이 최소 0.16.0 미만이라 `ImportError`. 02는 4bit(bnb) 층이라 이 경로를 타지 않음 | `432e5d8` (11-13 08:09, 03 pip 셀에서 torchao 삭제) | 로컬에서 같은 오류를 재현하고 삭제로 해결됨을 확인 |
| 4 | 03 SMOKE 2차 | 통과. 학생 앞 2개 층만 올려 merge → NF4(fp16) 저장 → 해시. 계산 dtype float16, 층 수 2 | 없음 | 2개 층으로 줄인 SMOKE라 디스크·RAM 용량은 확인 못 함 |
| 5 | 02 본 실행 | 완료. 학습률당 376 step(epoch당 188, warmup 12), 학습률당 약 2시간, 검증 생성 4회(200개씩, 16개 batch 약 33초). 2e-4 학습 중 브라우저 표시가 끊겼으나 학습은 계속됨(재실행 없음) | `4c37642` (11-13 22:19) | (a) Drive `lora/chosen/`에 `adapter_model.safetensors`가 없었다(02 마지막 셀은 그 해시를 출력했음, 원인 미확인). (b) 사용자가 repo로 받을 때 두 학습률 폴더 이름을 바꿔 넣음 → 맞바꾸고 log_history·통과율 4개를 selection.json과 대조해 일치 확인. (c) LoRA 가중치는 repo에 넣지 않고 해시만(`distill/lora/chosen_hashes.json`) |
| 6 | 03 본 실행 1차 | 실패: chosen에 가중치가 없어 peft가 경로를 Hub 저장소 이름으로 보고 `HFValidationError` | `3b3b5b4` (11-13 22:47, 확인 셀 추가) | 확인 셀: chosen에 없으면 selection.json의 선택 체크포인트에서 복사, sha256이 02 출력과 같을 때만 진행 |
| 7 | 03 본 실행 2차 | 완료. `checkpoint-376`에서 복사(244.1MB, sha256 `84d058e8…` 일치). 계산 dtype float16, 층 수 38. A100 `memory_allocated` 9.67GB(참고 값) | `64ab57e` (11-13 23:39) | 가중치(약 9.6GB)는 Drive `merged_nf4/`, repo에는 `distill/merged_nf4_hashes.json`만 |
| 8 | 04 SMOKE 1차 | 실패: `eval_smoke/` 폴더가 없어 timing json 쓰기에서 `FileNotFoundError`(본 실행 `eval/`는 01이 만들어 두어 드러나지 않음) | `108a18d` (11-14 03:54) | — |
| 9 | 04 SMOKE 2차 | 통과. 검증 입력 4개로 (i)·(ii)(2개 층 모델) 로드·시간 측정·생성·근거 검사. (i) 0.5, (ii) 0.0(2개 층이라 의미 없음) | 없음 | — |
| 10 | 04 본 실행 | 완료(약 3시간). 노트북 빠른 통과율 (i) 0.408, (ii) 0.998, (iii) 0.995 | 이 노트와 같은 커밋(decisions 2026-11-14) | 노트북 머리말 추정(1.5~2시간)보다 오래 걸림. 결과 파일 4개는 **아직 repo에 없음** |
| 11 | 데모 서버 VRAM 측정((ii) `--timing`) | **미실시** | — | — |
| 12 | 원본 학생 v5 재확인(번호 목록 여부) | **미실시** | — | — |
| 13 | 공식 채점(`score_distill.py`) | **미실시**(04 결과 파일 필요) | — | — |
| 14 | 사람 점검 60개 | **미실시**(`review.csv` 아직 안 만듦) | — | — |

## 2. 증류 결과

### 2.1 02 설정 선택 (검증 2022년 200개, greedy, 근거 검사)
| 설정 | 통과율 | 형식 | 검증 손실 | 실패 |
|---|---|---|---|---|
| 1e-4, epoch 1 | 0.995 | 1.0 | 0.07491 | h3-2022-08-02 '366원' |
| 1e-4, epoch 2 | 0.995 | 1.0 | 0.07114 | h3-2022-08-02 '366원' |
| 2e-4, epoch 1 | 0.985 | 1.0 | 0.07416 | h3-2022-07-29 '21,060원', h3-2022-08-01 '21,460원', h3-2022-08-02 '366원' |
| **2e-4, epoch 2 (선택)** | **0.995** | 1.0 | **0.07008** | h3-2022-08-01 '21,460원' |

- 선택 근거: 통과율 0.995 동률 3개 → 동률 규칙(검증 손실이 낮은 쪽) 적용 → 2e-4 epoch 2. 실패는 모두 "숫자가 입력에 없음".
- 학습 손실(epoch 1/2): 1e-4 0.0799/0.0720, 2e-4 0.0799/0.0704.

### 2.2 04 평가 (평가 입력 934개, A100 80GB)
| 항목 | (i) 학생 원본 | (ii) LoRA 학생 | (iii) 선생 |
|---|---|---|---|
| 근거 검사 통과율(전체) | 0.408 | 0.998 | 0.995 |
| a_numbers, a_median, b, c, c_caution | 미확인 | 미확인 | 미확인 |
| 형식 준수율 | 미확인 | 미확인 | 미확인 |
| 평균 생성 시간(batch 1, 50개) | 75.43초 | 72.59초 | 7.12초(vLLM) |
| 최대 VRAM(A100, max_memory_reserved) | 11.23GB | 11.02GB | 비교 안 함(vLLM 사전 할당, nvidia-smi 74.15GB) |

- 전체 통과율은 04 노트북의 빠른 확인 셀 출력이다(repo 코드와 같은 근거 검사지만, 공식 값은 `score_distill.py`로 다시 낸다).
- 규칙별·형식·실패 유형은 결과 파일이 repo에 들어온 뒤에만 낼 수 있어 미확인이다.
- 증류 효과: (ii) − (i) = +0.590(빠른 통과율 기준). 짝지은 4칸(둘 다 통과, (i)만, (ii)만, 둘 다 실패)은 미확인.
- 실패 유형 분포: (i)(번호 목록 건수 포함), (ii), (iii) 모두 미확인.
- 확인할 점: (ii)의 batch 1 시간(72.59초)이 원본과 비슷하다. 02 검증 생성(bf16, 전체 GPU)은 16개 batch에 약 33초, 04(배포 형식)는 약 78초였다. 배포 형식 때문인지, 끝난 뒤에도 512토큰까지 생성하기 때문인지는 timing 파일의 `new_tokens`로 확인한다(미확인).

### 2.3 데모 서버 (RTX 2080 Ti 22GB, Docker)
- 2026-11-13 fp16 확인(원본 학생, 학습용 입력 3개, 프롬프트 v4): NaN/inf 0, fp16 사용 가능. 평균 53.85초, max_reserved 11.23GB. 출력 3개 모두 "1. … 2. …" 번호 목록 → 프롬프트 v5의 계기.
- (ii)의 max_reserved와 생성 시간: **미측정**.
- 원본 학생 v5 재실행(번호 목록 여부): **미실시**.

### 2.4 채택 판정
- 사전 등록 기준(spec §6.3): (ii) 통과율 ≥ 90% **그리고** 데모 서버에서 (ii) max_memory_reserved ≤ 10GB(10 × 10⁹ 바이트).
  - 기준 1: 빠른 통과율 0.998로 충족(공식 채점 전).
  - 기준 2: 미측정. A100 대리 값 11.02GB.
  - 판정: **미정**. 기준 2가 10GB를 넘으면 학생은 쓰지 않고 API(BYOK) → 템플릿.
- 사후 결정: 없음. "데모는 22GB 서버에서 로컬로 시연할지"는 미정으로 남아 있다. 사용자는 10GB 기준과 `expandable_segments` 미사용을 유지한다고 했다(2026-11-13).

### 2.5 사람 점검 60개
- 미실시. 절차: 04 결과를 `distill/eval/`에 둔 뒤 `uv run python scripts/human_review.py make` → `distill/eval/human/review.csv`(모델 가림, 60행 섞음), `key.csv`(점검 끝까지 열지 않음) → 오류 수 기록 → `merge` → `summary.json`. 채택 판정에는 쓰지 않는다.

## 3. 사전 등록에서 벗어나거나 바꾼 것 (증류, 전부 평가 결과 보기 전)
| 언제 | 무엇 | 결과 보기 전/후 |
|---|---|---|
| 2026-11-12 | 채택 기준에 데모 서버 VRAM ≤ 10GB 추가, 4bit 형식 NF4 + embedding CPU 확정 | 전 |
| 2026-11-12 | 평가 (i)·(ii)와 배포의 계산 dtype fp16(2080 Ti는 bf16 미지원). 학습·설정 선택은 bf16 | 전 |
| 2026-11-12 | 근거 검사 개정: a_median(중앙값 표기), 식별자 오탐 수정, c_caution(성능 숫자 문장의 주의는 주의로 안 셈) | 전 |
| 2026-11-12 | 사람 점검을 (ii) 30개 → (i)·(ii) 60개, 모델 가림 | 전 |
| 2026-11-12~13 | 프롬프트 v2 → v3 → v4 → v5(학습용 입력·선생 시범으로 수정, v5는 형식 지시만) | 전(평가 입력 미사용) |
| 2026-11-13 | 선생 시범 50 → 100개 | 전 |
| 2026-11-13 | `warmup_ratio` → `warmup_steps=0.03`(같은 계산), 라이브러리 버전 고정, SMOKE 추가 | 전 |
| 2026-11-13 | 03이 어댑터를 chosen 대신 선택 체크포인트에서 복사(sha256 동일 확인) | 전 |
| 2026-11-14 | 04 노트북이 세 모델 빠른 통과율을 출력(노트북 설계대로, 채점 규칙 변경 없음) | — |
- 학습 데이터에서 끝까지 실패한 6개를 뺀 것은 사전 등록된 재생성 규칙(최대 2번)대로다.

## 4. 미해결·미확인
1. 01 학습 생성 첫 묶음 맨 앞 14개(2003-01-03 ~ 01-22)의 깨진 출력(빈 출력, `</think>`, 프롬프트 예시 복사, "입력 JSON 없음" 추론). 재생성으로 모두 통과, 최종 데이터에는 없음. 원인 미확인.
2. 40GB A100에서 FP8 선생(`Qwen3.8-27B-FP8`) 로드 실패. 원인 미확인(80GB bf16으로 끝나 다시 쓸 일 없음).
3. "동일" 입력: 예상가격 = 현재가(diff 0)인 입력에서 "동일"이라고 쓰면 근거 검사가 "현재가와 차이 없음"으로 실패시킨다. 학습 입력 3개가 모두 학습 데이터에서 빠졌다. 평가 입력에 몇 개 있는지는 미확인. 검사기를 둘지 바꿀지 사용자 결정 미정(바꾸면 사전 등록 변경).
4. 설정 선택의 epoch 1 = 2 epoch 학습의 중간 체크포인트. cosine이 376 step 기준이라 epoch 1 끝 학습률은 최고값의 약 절반. "1 epoch 학습"과 정확히 같지 않음(기록만, 변경 없음). 선택된 설정은 epoch 2라 결과에는 영향 없음.
5. 02가 출력한 chosen의 `adapter_model.safetensors`가 Drive에 남지 않은 원인 미확인(03에서 체크포인트로 복구).
6. (ii) 생성이 느린 이유(배포 형식 vs 512토큰까지 생성) 미확인.
7. VRAM 기준 2 미측정. A100 대리 값이 원본 11.23GB, (ii) 11.02GB.
8. `distill_common.load_student`의 docstring("계산 dtype을 덮어쓴다")은 4bit로 저장된 모델에서는 부정확하다(저장된 설정이 쓰임). 03이 fp16으로 저장해 결과는 같다. 묶음을 바꾸지 않으려고 코드는 그대로 둠.
9. `deploy/crontab.example`의 주석은 "LightGBM 예측"이라고 되어 있으나 `predict` 기본은 Chronos-2(실패 시 LightGBM)다. 주석만 옛 내용.

## 5. 현재 운영 상태
- explain: **template**. `.env`에 `LLM_PROVIDER` 줄이 없고, `explain/llm.py`의 기본값이 `template`이다. API(Gemini `gemini-3.1-flash-lite`, 키는 `.env`의 `GEMINI_API_KEY`)는 `LLM_PROVIDER=api` 또는 `auto`로 쓸 수 있다. local(학생)은 채택 판정 전이라 쓰지 않는다.
- 예측: `predict` 기본은 h = 3·7 Chronos-2, 실패 시 LightGBM(2026-11-10).
- cron: 이 랩탑의 crontab에는 tomato 작업이 없다(다른 줄 1개만 있음). 데모 서버의 cron 등록 여부는 미확인. 예시는 `deploy/crontab.example`.
- 데모 환경: Docker compose(app + PostgreSQL)로 수집·예측·설명·대시보드가 동작함을 1단계에서 확인(`docs/research/stage1-check.md`). 데모 서버(RTX 2080 Ti 22GB)에서는 GPU 확인용 Docker 이미지(`deploy/demo-gpu`)만 돌렸다. 대시보드를 데모 서버에 올렸는지는 미확인.

## 6. 남은 일과 순서 (마감 2026-11-17경)
1. 04 결과 파일 4개를 repo로 → `score_distill.py`로 세 모델 공식 채점(규칙별, 형식, 짝 비교, 실패 유형) → timing `new_tokens` 확인. 상태: 파일 미수령.
2. 데모 서버: `merged_nf4/`(약 9.6GB)를 옮겨 `scripts/demo_gpu_check.py --timing` → 기준 2 판정 → 채택 판정 기록. 원본 학생 v5 번호 목록 재확인도 같이. 상태: 미실시.
3. 사람 점검 60개. 상태: 미실시.
4. KREI 비교(intent 산출물 6 "3자 비교"): 기록상 KREI 관측월보가 유일한 후보지만 토마토 포함 여부와 전망 형식은 확인하지 못함(`docs/research/data-sources.md`). spec은 3자 비교를 범위 밖으로 두었다. 상태: 미착수.
5. 보고서: repo에 보고서 파일 없음. 상태: 미착수(기록 기준). 넣을 한계: 현장 검증 미실시, epoch 1 체크포인트, "동일" 입력, 테스트 구간 사용 횟수 등.
6. 조교님 설명: repo에 기록 없음. 미확인.
7. 회고: repo에 기록 없음. 미확인.

## 7. 웹 채팅에 함께 첨부할 파일
- `docs/handoff-web.md` (이 파일)
- `docs/progress.md`
- `docs/decisions.md`
- `docs/spec.md` (§6.1~6.3 증류 사전 등록)
- `intent/intent.md`
- `distill/lora/selection.json`
- `distill/teacher/meta.json`
- `distill/merged_nf4_hashes.json`
- `distill/lora/chosen_hashes.json`
- `src/tomato/explain/prompt.py` (프롬프트 v5)
- `src/tomato/explain/grounding.py` (근거 검사)
- `docs/research/stage2-backtest.md` (가격 모델 결과, 보고서용)
- `docs/research/data-sources.md` (KREI 후보 기록)
