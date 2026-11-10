#!/usr/bin/env bash
# Colab 증류용 묶음: 프롬프트·근거 검사 코드, 증류 입력, 노트북 공용 코드. Drive MyDrive/tomato-distill/에 올린다.
# 비밀값(.env)과 DB는 넣지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-tomato_distill_bundle.tar.gz}"
tar czf "$out" \
  src/tomato/__init__.py src/tomato/explain/__init__.py src/tomato/explain/prompt.py src/tomato/explain/grounding.py \
  distill/inputs/train.jsonl distill/inputs/eval.jsonl \
  notebooks/distill_common.py
echo "$out ($(du -h "$out" | cut -f1)), sha256 $(sha256sum "$out" | cut -c1-16)…"
