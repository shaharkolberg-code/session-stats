"""Accuracy benchmark for the fingerprint matcher.  Run: python -m tests.benchmark"""
from imgsleuth.fingerprint import fingerprint, similarity

from .synth import TRANSFORMS, make_image

THRESHOLD = 0.68


def run(n=40):
    originals = [make_image(s) for s in range(n)]
    fps = [fingerprint(i) for i in originals]
    per_t = {}
    for name, t in TRANSFORMS.items():
        scores = [similarity(fps[k], fingerprint(t(originals[k]), crops=False))["score"] for k in range(n)]
        per_t[name] = scores
    neg = [similarity(fps[a], fingerprint(originals[b], crops=False))["score"]
           for a in range(n) for b in range(n) if a != b]
    print(f"{'edit':<28}{'recall':>8}{'min':>8}{'mean':>8}")
    tp = 0
    for name, s in per_t.items():
        hit = sum(x >= THRESHOLD for x in s)
        tp += hit
        print(f"{name:<28}{hit / n:>8.0%}{min(s):>8.3f}{sum(s) / n:>8.3f}")
    fp = sum(x >= THRESHOLD for x in neg)
    total = n * len(per_t)
    print(f"\nrecall {tp}/{total} = {tp / total:.1%}   false positives {fp}/{len(neg)} = {fp / len(neg):.2%}"
          f"   max negative score {max(neg):.3f}")
    return tp / total, fp / len(neg)


if __name__ == "__main__":
    run()
