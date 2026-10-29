"""Prose fingerprint: measure the author's samples, compare a draft against them.
Purely stylistic — deliberately separate from continuity (`ink check`)."""
import re
from .util import die, read, strip_meta

AI_TELLS = [
    "tapestry", "testament to", "palpable", "symphony of", "delve", "intricate dance", "unwavering",
    "a beacon of", "in the grand scheme", "couldn't help but", "sent shivers down", "breath she didn't know",
    "breath he didn't know", "a mix of", "the weight of", "eyes darkened", "a flicker of", "steeled himself",
    "steeled herself", "it wasn't just", "something shifted", "the air was thick", "every fiber of",
    "time seemed to slow", "a wave of", "barely above a whisper", "jaw tightened", "let out a breath",
]
TAGS = r"said|asked|replied|whispered|shouted|muttered|snapped|growled|hissed|murmured|answered|added|called|cried|demanded|sneered"

_SENT = re.compile(r"[^.!?…]+[.!?…]+[\"”’']?|[^.!?…]+$")
_QUOTE = re.compile(r"[\"“]([^\"”]*)[\"”]")


def measure(text):
    text = strip_meta(text)
    body = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    words = re.findall(r"[A-Za-z0-9’']+", body)
    W = max(1, len(words))
    sents = [s for s in (x.strip() for x in _SENT.findall(body.replace("\n", " "))) if re.search(r"[A-Za-z]", s)]
    slen = [len(re.findall(r"[A-Za-z0-9’']+", s)) for s in sents] or [0]
    paras = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    plen = [len(re.findall(r"[A-Za-z0-9’']+", p)) for p in paras] or [0]
    dwords = sum(len(re.findall(r"[A-Za-z0-9’']+", q)) for q in _QUOTE.findall(body))
    tags = re.findall(rf"\b({TAGS})\b", body, flags=re.I)
    said = sum(1 for t in tags if t.lower() == "said")
    low = body.lower()
    per_k = lambda n: round(1000 * n / W, 2)
    return {
        "words": len(words),
        "avg_sentence": round(sum(slen) / len(slen), 1),
        "short_sentences_%": round(100 * sum(1 for x in slen if x <= 6) / len(slen), 1),
        "long_sentences_%": round(100 * sum(1 for x in slen if x >= 30) / len(slen), 1),
        "avg_paragraph": round(sum(plen) / len(plen), 1),
        "dialogue_%": round(100 * dwords / W, 1),
        "said_share_%": round(100 * said / len(tags), 1) if tags else None,
        "em_dash_per_k": per_k(body.count("—") + body.count("--")),
        "semicolon_per_k": per_k(body.count(";")),
        "exclaim_per_k": per_k(body.count("!")),
        "question_per_k": per_k(body.count("?")),
        "ly_adverbs_per_k": per_k(len(re.findall(r"\b\w{3,}ly\b", low))),
        "ai_tells": {t: low.count(t) for t in AI_TELLS if t in low},
    }


def baseline(paths):
    texts = [read(p) for p in paths]
    if not texts:
        return None
    return measure("\n\n".join(texts))


# metric → (kind, tolerance). ratio: draft/base outside [1/t, t] · abs: |diff| > t · under: draft < base − t · over: draft > base × t
RULES = {"avg_sentence": ("ratio", 1.35), "short_sentences_%": ("abs", 12), "long_sentences_%": ("abs", 10),
         "avg_paragraph": ("ratio", 1.6), "dialogue_%": ("abs", 15), "said_share_%": ("under", 25),
         "em_dash_per_k": ("over", 2.0), "semicolon_per_k": ("over", 2.5), "exclaim_per_k": ("over", 2.5),
         "ly_adverbs_per_k": ("over", 1.6)}


def compare(base, draft):
    flags = []
    for k, (kind, tol) in RULES.items():
        b, d = base.get(k), draft.get(k)
        if b is None or d is None:
            continue
        if kind == "ratio" and b and not (1 / tol <= d / b <= tol):
            flags.append(f"{k}: draft {d} vs samples {b}")
        elif kind == "abs" and abs(d - b) > tol:
            flags.append(f"{k}: draft {d} vs samples {b}")
        elif kind == "under" and d < b - tol:
            flags.append(f"{k}: draft {d} vs samples {b} (fancier tags than the author uses)")
        elif kind == "over" and d > max(b * tol, b + 1.0):
            flags.append(f"{k}: draft {d} vs samples {b} (too many)")
    extra = {t: n for t, n in draft["ai_tells"].items() if n > base["ai_tells"].get(t, 0)}
    if extra:
        flags.append("AI-tell phrases not in the author's samples: " + ", ".join(f"'{t}'×{n}" for t, n in extra.items()))
    return flags


def cmd_style(a, P):
    samples = sorted(P.p("bible/samples").glob("*.md")) + sorted(P.p("bible/samples").glob("*.txt"))
    base = baseline(samples)
    from .commands import chapter_file
    target = chapter_file(P, a.file, a.chapter) if (a.file or a.chapter) else None
    if target is None:
        if not base:
            die("no samples in bible/samples/ — add the author's reference chapters first")
        print(f"── style fingerprint of {len(samples)} sample file(s), {base['words']:,} words ──")
        for k, v in base.items():
            print(f"  {k:20} {v}")
        print("  (paste the key numbers into bible/style.md so the rules are measurable)")
        return
    d = measure(read(target))
    print(f"── style: {target.name} vs samples ──")
    if not base:
        for k, v in d.items():
            print(f"  {k:20} {v}")
        print("  (no samples in bible/samples/ to compare against)")
        return
    for k in RULES:
        print(f"  {k:20} {str(d.get(k)):>8}   samples {base.get(k)}")
    flags = compare(base, d)
    print(*(["  ⚠ " + f for f in flags] or ["  ✓ within the author's range"]), sep="\n")
