"""Colab 노트북 공용 코드 중 GPU 없이 검사할 수 있는 부분 (분할·이어 쓰기·SFT 손실 위치)."""
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def dc(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMATO_DISTILL_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(ROOT / "notebooks"))
    sys.modules.pop("distill_common", None)
    mod = importlib.import_module("distill_common")
    d = tmp_path / "bundle" / "distill" / "inputs"
    d.mkdir(parents=True)
    with open(d / "train.jsonl", "w") as f:
        for y in range(2003, 2023):
            for k in range(300):
                f.write(json.dumps({"id": f"h3-{y}-{k:03d}", "split": "val" if y == 2022 else "train", "input": {}}) + "\n")
    return mod


def test_subsets_are_fixed_and_split_by_time(dc):
    train, val = dc.subsets()
    assert len(train) == dc.N_TRAIN and len(val) == dc.N_VAL
    assert all(r["split"] == "train" for r in train) and all(r["id"].startswith("h3-2022") for r in val)
    assert [r["id"] for r in dc.subsets()[0]] == [r["id"] for r in train]


def test_append_and_resume(dc, tmp_path):
    p = tmp_path / "x.jsonl"
    dc.append_jsonl(p, [{"id": "a"}, {"id": "b"}])
    dc.append_jsonl(p, [{"id": "c"}])
    assert dc.done_ids(p) == {"a", "b", "c"}


class FakeTok:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt, skip_reasoning):
        assert skip_reasoning is True and add_generation_prompt is True
        return "P" * 5

    def __call__(self, text, add_special_tokens):
        return {"input_ids": [ord(c) for c in text]}


class FakePrompt:
    @staticmethod
    def messages(x):
        return []


def test_sft_loss_only_on_target(dc):
    f = dc.sft_features(FakeTok(), FakePrompt, {}, "AB")
    n_target = len("AB<|im_end|><|endofturn|>")
    assert f["labels"][:5] == [-100] * 5
    assert f["labels"][5:] == f["input_ids"][5:] and len(f["labels"]) == 5 + n_target


def test_demo_check_uses_three_fixed_training_inputs_only():
    spec = importlib.util.spec_from_file_location("demo_gpu_check", ROOT / "scripts" / "demo_gpu_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    recs = mod.check_inputs()
    assert len(recs) == 3 and all(r["split"] == "train" and r["id"] < "h3-2022" for r in recs)
    assert [r["id"] for r in mod.check_inputs()] == [r["id"] for r in recs]


def test_pilot_is_fixed_training_only_and_eval_dtype_is_fp16(dc):
    p = dc.pilot_subset()
    assert len(p) == dc.N_PILOT == 50 and all(r["split"] == "train" for r in p)
    assert [r["id"] for r in dc.pilot_subset()] == [r["id"] for r in p]
    assert dc.EVAL_COMPUTE_DTYPE == "fp16"
