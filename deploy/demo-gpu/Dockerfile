# 데모 서버(RTX 2080 Ti 22GB, Turing sm_75) 학생 확인용 이미지. spec §6.2 계산 dtype(fp16), §6.3 채택 기준 2(VRAM).
# 호스트에는 아무것도 설치하지 않는다. torch·CUDA 런타임은 이 이미지 안에만 있다(드라이버 595.84는 CUDA 12.8 런타임 지원).
# repo는 실행 때 볼륨으로 붙인다(이미지에 넣지 않음). 사용법은 scripts/demo_gpu_check.py 맨 위.
#
#   docker build -t tomato-demo-gpu deploy/demo-gpu
FROM pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime

# transformers 5.9.0 이상이 HyperCLOVAX-SEED-Think-14B를 지원한다. 설치된 버전은 스크립트가 시작할 때 출력한다.
RUN pip install --no-cache-dir "transformers>=5.9.0,<6" "bitsandbytes>=0.46" "accelerate>=1.6"

ENV HF_HOME=/hf \
    HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /repo
ENTRYPOINT ["python", "scripts/demo_gpu_check.py"]
