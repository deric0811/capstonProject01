# Chronos-2 사전 확인 (2026-11-10, 구현 4단계 전)

## 라이선스와 버전
| 항목 | 값 | 출처 |
|---|---|---|
| 모델 | `amazon/chronos-2`, 120M 파라미터, encoder-only | Hugging Face 모델 카드 |
| 모델 라이선스 | Apache-2.0 | 모델 카드, HF API 태그 `license:apache-2.0` |
| 모델 revision | `29ec3766d36d6f73f0696f85560a422f50e8498c` (lastModified 2026-06-05) | `https://huggingface.co/api/models/amazon/chronos-2` |
| 패키지 | `chronos-forecasting==2.3.2` (2026-09-08 공개, Apache-2.0) | PyPI |
| torch | `2.15.0+cpu` (CPU 전용 인덱스) | `uv.lock` |
| 설치 | `pyproject.toml`의 `chronos` 의존성 그룹. 기본 그룹과 Docker 이미지에는 넣지 않는다 | |
| 최대 context | 8192 (로드한 모델 설정에서 확인). 2002-11 ~ 2026-11 거래일은 약 6,000개라 자르지 않는다 | |

## CPU 실행 시간
- 환경: 로컬 Intel i5-8365U (4코어 8스레드), torch 4스레드, 메모리 23GB
- 측정: 검증 구간(2020년) 예측 시점 50개, prediction_length 21, 0.5 분위수, batch 50
  - (가) 상품 평균가만: 25.8초 → 1,674회(검증 약 740 + 테스트 약 934) 약 14분
  - (나) + 과거값 공변량(중품 평균가, 참여 시장 수): 85.0초 → 1,674회 약 47분
- 판단: 검증에서 (가)·(나) 둘 다, 테스트에서 고른 입력 하나를 돌려도 1시간 안팎이다. Colab 대신 로컬 CPU에서 돌린다.
- 실행 위치: 호스트의 `uv run --group chronos`
  - 같은 CPU라서 소요 시간은 Docker와 같다.
  - Docker 이미지에 torch(약 1GB)를 넣지 않기 위해서다.
  - 결과는 같은 DB(compose의 postgres)에 저장한다.
  - Chronos-2가 운영 모델로 선택되면 이미지 포함 여부를 따로 정한다.

## 사전학습 데이터
- **출처**: 기술 보고서(arXiv 2510.15821) §4, 부록 Table 6, 모델 카드, `autogluon/chronos_datasets` 데이터셋 카드
- **구성**
  - 실제 단변량 데이터: Chronos Datasets 일부와 GIFT-Eval Pretrain 일부. GIFT-Eval 테스트 부분과 겹치는 것은 뺐다.
  - 합성 데이터: TSI, TCM, KernelSynth 등. 다변량·공변량 학습은 모두 합성 데이터다.
- **2023년 이후 데이터 포함 여부**: **확인 불가.** 보고서와 카드 모두 데이터 기간이나 cutoff를 밝히지 않는다. 모델은 2025-10 보고서 이후에도 2026-06에 갱신됐다.
- **한국 농산물 가격류 포함 여부**: **확인 불가**
  - 보고서 Table 6의 도메인(Energy, Transport, Nature, Cloud Ops, Web, Various)과 데이터셋 카드의 67개 subset 이름에는 농산물·식품 가격·한국 데이터가 없다.
  - 다만 GIFT-Eval Pretrain의 세부 구성과 "Various"의 내용은 확인하지 못했다.
- **보고서 한계 항목**: 테스트 구간(2023~)이 사전학습 데이터와 겹치는지, 비슷한 가격 시계열을 봤는지 확인할 수 없다. 결과와 무관하게 보고서 한계에 적는다.
