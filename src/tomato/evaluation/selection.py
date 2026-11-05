"""모델 선택 규칙 (spec §2). h별로 전체 테스트 구간 지표로 적용한다.

후보는 B2와 LightGBM(검증 구간에서 고른 학습 창) 하나다. docs/decisions.md 2026-11-05.
"""


def select(candidates):
    """candidates = {이름: {'mae', 'rel_mae', 'dir_acc_ud'}}, 'B2' 포함. (선택 이름, 사유 목록)을 돌려준다."""
    b2_acc = candidates["B2"]["dir_acc_ud"]
    reasons, kept = [], {}
    for name, m in candidates.items():
        if not m["rel_mae"] < 1:
            reasons.append(f"{name} 제외: 상대 MAE {m['rel_mae']:.4f} >= 1")
        elif m["dir_acc_ud"] < b2_acc:
            reasons.append(f"{name} 제외: 상승/하락 적중률 {m['dir_acc_ud']:.4f} < B2 {b2_acc:.4f}")
        else:
            kept[name] = m
    if not kept:
        return "B1", reasons + ["남는 후보가 없어 B1 채택"]
    best = min(kept, key=lambda k: kept[k]["mae"])
    return best, reasons + [f"{best} 선택: 남은 후보 중 MAE 최저 {kept[best]['mae']:.1f}원"]
