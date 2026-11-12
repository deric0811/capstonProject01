# LLM 해설 증류 사전 확인 (2026-11-10, GPU 실행 전)

선생·학생 모델 라이선스, 사고(thinking) 출력 제어, 메모리 추정, 4bit 형식을 확인한다. 확인 시점은 2026-11-10이고, 출처는 각 Hugging Face 모델 카드·LICENSE·config와 llama.cpp 저장소다.

## 1. 학생: HyperCLOVA X SEED 14B Think

### 기본 정보
- 저장소 `naver-hyperclovax/HyperCLOVAX-SEED-Think-14B`, revision `9b74e35d4c7e4ffec489f4171273caca8948a2b9`(2026-05-28 수정)
- 14.74B dense. Peri-LN(`use_post_norm`)과 μP 배율(embedding·attention·logits)을 쓴다.
  - 38층, hidden 6144, attention head 48, KV head 8(GQA), head_dim 128
  - FFN 14336, vocab 110,592. embedding과 lm_head는 따로 둔다(tie 없음).
  - context 32k
- 올라온 가중치는 **float32, 약 59GB**다. "bf16 원본"은 이 가중치를 bf16으로 읽은 것을 뜻한다.
- transformers 기본 지원은 5.9.0 이상이다(모델 카드). vLLM도 기본 지원한다.

### 라이선스 (HyperCLOVA X SEED Model License Agreement)
| 항목 | 내용 |
|---|---|
| 사용·수정·배포 | 무료 비독점 사용권이다(§2.2). 철회할 수 있다. |
| 대규모 사업자 | 월 사용자 1,000만 명 초과 사업자나 NAVER 제품과 경쟁하는 제품은 별도 허가를 받아야 한다(§4). 이 프로젝트는 해당하지 않는다. |
| 출력 | NAVER는 출력에 권리를 주장하지 않는다(§5). |
| 미세조정 모델 | Derivative Model로 허용된다. |
| 미세조정 모델 공개 시 | 이름이 "HyperCLOVA X"로 시작해야 한다. "Powered by HyperCLOVA X"를 표시하고 Notice 파일을 넣고 라이선스를 동봉해야 한다(§3.1). |
| 금지 용도 | Addendum A를 따른다. 무면허 금융 자문 등이 금지되고, AI 시스템의 위험과 한계를 사용자에게 알려야 한다. |

- 이 프로젝트에 적용하면
  - 어댑터·병합 가중치를 공개한다면 이름을 `HyperCLOVA X …`로 시작하게 하고, 대시보드에 "Powered by HyperCLOVA X"를 표시한다.
  - 화면의 "예측은 틀릴 수 있다" 문구와 참고용 안내는 위험 고지 의무와도 맞는다.
  - 매입 시점 참고 정보는 개별 투자 자문이 아니라고 본다. 다만 보고서에 한계로 적는다.

### 사고(thinking) 출력 끄기: 가능
- **방법**: chat template에서 `skip_reasoning=True`를 준다.
  - 생성 프롬프트 끝에 빈 사고 블록 `<|im_start|>assistant/think\n<|im_end|>\n<|im_start|>assistant\n`이 붙어 바로 답한다(`chat_template.jinja` revision 위와 같음).
  - vLLM·OpenAI 호환 서버에서는 `"chat_template_kwargs": {"skip_reasoning": true}`로 준다. `explain/llm.py`의 local 제공자 기본값이다.
  - 아무 값도 주지 않으면 모델이 사고 여부를 스스로 정한다(하이브리드). `force_reasoning`이 우선한다.
- **종료 토큰**: 생성은 `<|im_end|>`, `<|endofturn|>`, `<|stop|>`에서 멈추게 한다. `generation_config.json`의 `use_cache: false`는 생성할 때 `use_cache=True`로 덮어쓴다.
- **영향**: 사고 출력을 끌 수 있으므로 해설 길이와 근거 검사에는 영향이 없다.
  - 사고가 섞여 나오는 경우는 형식 검사(`<think>`, `<|` 태그 금지)에서 실패로 센다.
- **QLoRA 학습 형식**: 프롬프트를 `skip_reasoning=True` 생성 프롬프트로 만들고, 정답에 `해설 + <|im_end|><|endofturn|>`을 붙인다. 손실은 정답 부분에만 건다.

## 2. 선생: Qwen (오픈 웨이트, Apache 2.0)

| 후보 | 크기 | 라이선스 | revision | 비고 |
|---|---|---|---|---|
| **Qwen/Qwen3.8-27B** (제안) | 27.8B | Apache-2.0 | `37561816e66b5b9153b1b64c10968c18c1e6f4a0` | 2026-08-05 공개 |
| Qwen/Qwen3.8-27B-FP8 | 27.8B (FP8) | Apache-2.0 | `c3a462cc3d38cf351f3b26cbd763469eeb74ef81` | 위 모델의 FP8 |
| Qwen/Qwen3.6-27B | 27.8B | Apache-2.0 | | 이전 세대 예비 |
| Qwen/Qwen3.5-122B-A10B(-GPTQ-Int4) | 125B MoE (활성 10B) | Apache-2.0 | | 80GB에서만 가능 |
| Qwen/Qwen3.8-Flash-Next | 180B | other(자체 라이선스) | | 제외: Apache가 아님 |

- **Qwen3.8-27B 구조**
  - 이름은 dense지만 층 구성이 하이브리드다. Gated DeltaNet 3층과 Gated Attention 1층 묶음을 16번 반복한다.
  - vision encoder가 붙어 있다. 텍스트만 쓴다.
  - vLLM은 이 구조를 지원하는 최신 버전을 쓰고, 실행할 때 버전을 기록한다.
- **사고 출력 끄기**: `chat_template_kwargs={"enable_thinking": False}`(모델 카드)
- **한국어**: 모델 카드에 한국어 성능에 대한 명시는 없다. 프롬프트 시험과 평가에서 근거 검사 통과율로 확인한다.

### A100 크기별 제안
| GPU | 제안 | 가중치 메모리 | 이유 |
|---|---|---|---|
| **A100 40GB** | Qwen3.8-27B-**FP8** + vLLM | 약 29GB | bf16(약 56GB)은 들어가지 않는다. A100에는 FP8 연산기가 없어 vLLM이 W8A16(Marlin)으로 돌린다. KV cache 여유는 약 6GB라 `max_model_len 4096`으로 충분하다(입력+출력 약 1.2k 토큰). |
| **A100 80GB** | Qwen3.8-27B **bf16** + vLLM | 약 56GB | 양자화 손실이 없다. KV cache 여유는 약 16GB다. |
| A100 80GB (대안) | Qwen3.5-122B-A10B-GPTQ-Int4 | 약 65GB | 더 큰 모델이지만 KV 여유가 작고 로드가 오래 걸린다. 추천하지 않는다. |

- 40GB와 80GB 중 어느 것이 배정돼도 선생은 **Qwen3.8-27B 계열 하나**로 고정한다. 정밀도(FP8/bf16)만 GPU에 따라 다르고, 실제로 쓴 것을 기록한다.

## 3. 4bit 14B 메모리와 형식

### 추정 (가중치는 config에서 계산)
- linear 13.39B(38층 × 352.3M)
- embedding 0.68B와 lm_head 0.68B
- KV cache는 토큰당 2 × 38층 × 8 head × 128 × 2바이트 = 152KiB다. 1.5k 토큰이면 약 0.23GB.

| 형식 | 가중치 | + KV(1.5k)·CUDA 문맥(약 0.5GB) | RTX 3080 10GB(10.0GiB) |
|---|---|---|---|
| bitsandbytes NF4(이중 양자화), embedding·lm_head는 bf16(기본) | 6.9 + 2.7 = 9.6GB | 약 10.3GB (9.6GiB) | 아슬아슬하다. 화면 출력에 GPU를 함께 쓰면 넘친다. |
| **NF4 + embedding을 CPU에 둠**(device_map) | 6.9 + 1.4 = 8.3GB | 약 9.0GB (8.4GiB) | 들어간다. embedding 조회만 CPU에서 하므로 속도 손실이 작다. |
| NF4 + lm_head까지 4bit | 약 7.6GB | 약 8.3GB | 들어가지만 출력층 양자화로 품질이 떨어질 수 있다. |
| GGUF Q4_K_M(NAVER 공식 파일) | 8.92GB | 약 9.6GB | 원본 모델만 해당한다(아래). |

### GGUF(llama.cpp) 지원
- **mainline llama.cpp**: 이 구조(`hyperclovax`)가 없다. 아키텍처 목록과 `convert_hf_to_gguf.py`에서 확인했다.
- **NAVER 포크**(`NAVER-Cloud-HyperCLOVA-X/llama.cpp`, 2026-02 갱신): 추론 코드는 있다(`hcx-seed-think`, `hyperclovax` 아키텍처). 공식 GGUF `naver-ellm/HyperCLOVAX-SEED-Think-14B-GGUF`(Q4_K_M, 8.92GB)도 이 포크용이다.
- 그러나 포크의 `convert_hf_to_gguf.py`에 이 구조의 변환 코드가 없다. 그래서 **우리가 merge한 가중치를 GGUF로 바꾸는 공개 경로가 없다**.
  - 공식 GGUF의 메타데이터와 텐서 이름을 본떠 gguf-py로 직접 쓰는 방법은 가능해 보이지만 검증되지 않았다.
- **결론**: GGUF는 이번 배포 경로에서 뺀다.

### 대안 제안 (확인 필요)
- **추천**: bitsandbytes NF4(이중 양자화, 연산 bf16)에 embedding만 CPU에 둔다.
  - QLoRA와 같은 라이브러리라 변환 위험이 없다.
  - 평가 (i)·(ii)를 실제 배포 형식 그대로 A100에서 잴 수 있다.
  - merge한 bf16을 NF4로 읽어 저장(`save_pretrained`, 4bit 직렬화)하면 약 9.6GB다. Drive에는 이 파일만 둔다.
- **예비 1**: lm_head까지 4bit. VRAM이 넘칠 때만 쓴다.
- **예비 2**: ExLlamaV3(exl3, 약 4bpw). 커뮤니티 exl3 변환본(`turboderp/HyperCLOVAX-SEED-Think-14B-exl3`)이 있어 구조 지원은 확인된다. 우리 merge본 변환과 3080 동작은 확인하지 않았다.
- **VRAM 측정**: A100에서 `torch.cuda.max_memory_reserved()`로 잰 값은 대리 지표다. 3080 데모에서 다시 확인한다.

## 4. 데모 PC (RTX 3080 10GB)
> 2026-11-12 정정: 데모 서버는 RTX 2080 Ti 22GB(개조)다(decisions 2026-11-12). 아래 확인 항목은 그대로 적용하고, 다음을 더한다.
> - Turing(sm_75)은 bf16 연산을 하드웨어로 지원하지 않는다. 계산 dtype(bf16/fp16)은 `scripts/demo_gpu_check.py` 결과로 정한다.
> - bitsandbytes 4bit는 sm_75를 지원한다. FlashAttention 2는 sm_80 이상이라 쓰지 않는다(노트북도 기본 sdpa).
> - 22GB라 10GB는 하드웨어 한계가 아니라 채택 기준(spec §6.3)이다.

- 확인할 것은 OS(Windows+WSL2인지 Linux인지)와 NVIDIA 드라이버 버전이다.
- Docker GPU 지원도 확인해야 한다.
  - Linux는 NVIDIA Container Toolkit이 필요하다.
  - Windows는 Docker Desktop의 WSL2 GPU 지원이 필요하다.
  - 확인 명령: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`
- 화면 출력에 3080을 함께 쓰는지도 확인한다. 함께 쓰면 VRAM 여유가 0.3~1GB 줄어든다.
- GPU가 없는 환경에서는 `LLM_PROVIDER=auto`가 API 제공자(BYOK, `.env`의 `LLM_API_KEY`)로 대체하고, 키도 없으면 템플릿을 쓴다.

## 5. 근거 검사 (b) 금지어 목록의 한계
- 목록(`explain/grounding.py` `FORBIDDEN`)
  - 날씨: 날씨, 기상, 기후, 기온, 더위, 추위, 폭염, 한파, 냉해, 태풍, 장마, 폭우, 호우, 강우, 강수, 비(가/를/는/소식/때문/영향), 가뭄, 일조
  - 작황·물량: 작황, 생산량, 출하량, 반입량, 재배, 수확, 병해충, 산지
  - 교역·비용: 수입, 수출, 환율, 유가, 물가, 인건비, 물류비, 운송비
  - 정책·뉴스: 정책, 정부, 뉴스, 보도
  - 계절 행사: 명절, 추석, 설날, 김장, 휴가철
  - 수급: 수요, 공급, 수급, 소비 심리, 소비량, 재고
- **못 잡는 경우(거짓 통과)**
  - 다른 말로 바꾼 표현: "하늘이 맑아", "물건이 많이 들어와", "사려는 사람이 늘어"
  - 목록에 없는 원인: 코로나, 전쟁, 유통 구조 등
- **잘못 잡는 경우(거짓 실패)**
  - 원인이 아닌 주의 문구: "날씨 같은 요인은 반영되지 않았습니다"도 실패로 센다. 보수적으로 막는 쪽을 택했다. 실패하면 템플릿으로 대체되므로 틀린 근거가 나가지는 않는다.
  - "비"는 단어 앞에 다른 글자가 없을 때만 잡는다. 그래도 "비가격 요인" 같은 말은 잡을 수 있다.
- 입력에 뉴스가 들어오면(MVP 이후) 목록을 다시 정한다.
