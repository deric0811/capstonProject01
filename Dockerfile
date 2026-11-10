FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends tzdata libgomp1 && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Seoul \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY pyproject.toml uv.lock ./
# chronos 그룹: CPU 전용 torch(uv.lock에 고정)와 chronos-forecasting
RUN uv sync --frozen --no-default-groups --group chronos --no-install-project

# Chronos-2 가중치를 revision 고정으로 이미지에 넣는다. 실행 중에는 HF_HUB_OFFLINE=1이라 다운로드하지 않는다.
# revision은 src/tomato/models/chronos2.py의 REVISION과 같아야 한다(tests/test_chronos2.py가 확인).
ENV HF_HOME=/opt/hf
ARG CHRONOS_REVISION=29ec3766d36d6f73f0696f85560a422f50e8498c
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('amazon/chronos-2', revision='${CHRONOS_REVISION}')"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY src ./src
RUN uv sync --frozen --no-default-groups --group chronos

EXPOSE 8000
CMD ["sh", "-c", "tomato db init && uvicorn tomato.api.main:app --host 0.0.0.0 --port 8000"]
