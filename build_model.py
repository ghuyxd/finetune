#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_model.py — Học bảng chuyển đổi Latin -> Tai Viet từ từ điển đã soát tay.

Chỉ dùng các dòng FIXED_MANUALLY. Vì chính các dòng này cũng có sai sót, mô hình
được làm sạch bằng TƯƠNG QUAN giữa các mục: một cặp bị loại nếu phụ âm đầu của
nó mâu thuẫn với ánh xạ đa số học được từ toàn bộ phần còn lại.

Đầu ra: model.json (bảng phụ âm / vần / thanh + từ điển âm tiết)
"""
import csv, json, sys, collections, random
import unicodedata as ud
from repair import repair_latin, repair_tavt
import tables_textbook as TB

V1SET = set("\uAAB5\uAAB6\uAAB9\uAABB\uAABC")


def wellformed(s):
    """Loại chuỗi Tai Viet không thể tồn tại: hai nguyên âm-đứng-trước liền
    nhau, nguyên âm-đứng-trước không có phụ âm theo sau, cụm không có phụ âm."""
    if not s or not any(c in CONS_OF for c in s):
        return False
    for i, c in enumerate(s):
        if c in V1SET:
            if i + 1 >= len(s) or s[i + 1] in V1SET or s[i + 1] not in CONS_OF:
                return False
    return True

CSV = sys.argv[1] if len(sys.argv) > 1 else \
    "/mnt/user-data/uploads/dictionary_entries_scored_reviewed__1_.csv"

# ---------------------------------------------------------------- ký tự Tai Viet
LOW_ROW = ("\uAA80\uAA82\uAA84\uAA86\uAA88\uAA8A\uAA8C\uAA8E\uAA90\uAA92\uAA94"
           "\uAA96\uAA98\uAA9A\uAA9C\uAA9E\uAAA0\uAAA2\uAAA4\uAAA6\uAAA8\uAAAA"
           "\uAAAC\uAAAE")
HIGH_ROW = ("\uAA81\uAA83\uAA85\uAA87\uAA89\uAA8B\uAA8D\uAA8F\uAA91\uAA93\uAA95"
            "\uAA97\uAA99\uAA9B\uAA9D\uAA9F\uAAA1\uAAA3\uAAA5\uAAA7\uAAA9\uAAAB"
            "\uAAAD\uAAAF")
NAMES = "k kh x g ng c chh s ny d t th n b p ph f m y r l v h '".split()

CONS_OF, CLASS_OF, PAIR = {}, {}, {}
for i, nm in enumerate(NAMES):
    CONS_OF[LOW_ROW[i]] = nm;  CLASS_OF[LOW_ROW[i]] = "LOW"
    CONS_OF[HIGH_ROW[i]] = nm; CLASS_OF[HIGH_ROW[i]] = "HIGH"
    PAIR[nm] = (LOW_ROW[i], HIGH_ROW[i])

TONE_CHARS = set("\uAABF\uAAC0\uAAC1\uAAC2")

# ------------------------------------------------------------- tách âm tiết Latin
TONE_DIA = {"\u0301": "sac", "\u0300": "huyen", "\u0309": "hoi",
            "\u0303": "nga", "\u0323": "nang"}
ONSETS = sorted(["ngh", "kh", "ph", "th", "ch", "nh", "ng", "gi", "tr", "qu",
                 "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r",
                 "s", "t", "v", "x", "y", "f"], key=len, reverse=True)


def strip_tone(s):
    tone, out = "ngang", []
    for ch in ud.normalize("NFD", s):
        if ch in TONE_DIA:
            tone = TONE_DIA[ch]
        else:
            out.append(ch)
    return ud.normalize("NFC", "".join(out)), tone


def split_latin(syl):
    base, tone = strip_tone(syl.lower())
    for o in ONSETS:
        if base.startswith(o) and len(base) > len(o):
            return o, base[len(o):], tone
    return "", base, tone


def canon(s):
    """Chuẩn hoá chuỗi Tai Viet: bỏ dấu thanh (nguồn dùng hệ truyền thống,
    chỉ 61/2003 âm tiết có dấu và nhiều dấu đặt sai vị trí) + bỏ ký tự lạ."""
    return "".join(c for c in s
                   if "\uAA80" <= c <= "\uAABE" or c in "\uAADB\uAADC ")


def parse_tavt(s):
    """-> (mẫu vần có ◌ thay cho phụ âm đầu, tên phụ âm, lớp) hoặc None."""
    chars = [c for c in s if c not in TONE_CHARS]
    for i, c in enumerate(chars):
        if c in CONS_OF:
            pat = "".join(chars[:i]) + "\u25CC" + "".join(chars[i + 1:])
            return pat, CONS_OF[c], CLASS_OF[c]
    return None


# ------------------------------------------------------------------- nạp dữ liệu
def load_pairs():
    out = []
    for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
        if r["Trạng Thái"] != "FIXED_MANUALLY":
            continue
        try:
            conf = float(r["Độ Tin Cậy (%)"])
        except Exception:
            conf = 0.0
        a = repair_latin(r["Từ Thái (Latinh)"]).split()
        b = repair_tavt(canon(r["Từ Thái (Unicode Chuẩn)"])).split()
        if len(a) != len(b):          # lệch số âm tiết -> không căn được
            continue
        for x, y in zip(a, b):
            x = x.lower().strip(".,;:!?()\"'")
            y = canon(y)
            if x and y and parse_tavt(y) and wellformed(y):
                out.append((x, y, conf))
    return out


# --------------------------------------------------------- làm sạch bằng tương quan
def majority(counter, floor=0.0):
    if not counter:
        return None, 0.0
    top, n = counter.most_common(1)[0]
    tot = sum(counter.values())
    return (top, n / tot) if n / tot >= floor else (None, n / tot)


def clean(pairs, rounds=3, min_support=3, min_share=0.60):
    """Loại các cặp có phụ âm đầu mâu thuẫn đa số (dấu hiệu căn sai / OCR sai)."""
    kept = list(pairs)
    dropped = []
    for _ in range(rounds):
        omap = collections.defaultdict(collections.Counter)
        rmap = collections.defaultdict(collections.Counter)
        for lat, tav, conf in kept:
            o, r, _t = split_latin(lat)
            w = 1 if conf >= 90 else 0.3
            pat, cname, _c = parse_tavt(tav)
            omap[o][cname] += w
            rmap[r][pat] += w
        new, drop = [], []
        for item in kept:
            lat, tav, conf = item
            o, r, _t = split_latin(lat)
            pat, cname, _c = parse_tavt(tav)
            bad = False
            for table, key, val in ((omap, o, cname), (rmap, r, pat)):
                c = table[key]
                top, share = majority(c)
                if sum(c.values()) >= min_support and share >= min_share and val != top:
                    bad = True
            (drop if bad else new).append(item)
        if not drop:
            break
        kept, _ = new, dropped.extend(drop)
    return kept, dropped


# ------------------------------------------------------------------- học bảng
def pick_rime(r, counter):
    """Mẫu vần: lấy đa số từ dữ liệu nếu đủ chắc, nếu không lấy bảng giáo trình."""
    top, share = majority(counter)
    n = sum(counter.values())
    book = TB.compose(r)
    if book is None:
        return top
    if n >= 2 and share >= 0.5:
        return top                      # dữ liệu có chứng cứ -> tin dữ liệu
    if book in counter:
        return book                     # giáo trình có mặt trong dữ liệu -> chọn
    return book


def learn(pairs):
    onset = collections.defaultdict(collections.Counter)
    rime = collections.defaultdict(collections.Counter)
    tone = collections.defaultdict(collections.Counter)
    tone2 = collections.defaultdict(collections.Counter)
    lex = collections.defaultdict(collections.Counter)
    for lat, tav, conf in pairs:
        pat, cname, ccls = parse_tavt(tav)
        o, r, t = split_latin(lat)
        w = 1.0 if conf >= 90 else 0.3
        onset[o][cname] += w
        rime[r][pat] += w
        tone[t][ccls] += w
        tone2[(t, o)][ccls] += w
        lex[lat][tav] += w
    coda = collections.defaultdict(collections.Counter)
    rime_top = {k: majority(v)[0] for k, v in rime.items()}
    for r, pat in rime_top.items():
        for cd in CODAS:
            if r.endswith(cd) and len(r) > len(cd):
                nuc = rime_top.get(r[:-len(cd)])
                if nuc and pat.startswith(nuc):
                    coda[cd][pat[len(nuc):]] += 1
                break
    return {
        "coda": {k: majority(v)[0] for k, v in coda.items()},
        "onset": {k: majority(v)[0] for k, v in onset.items()},
        "rime":  {k: pick_rime(k, v) for k, v in rime.items()},
        "tone":  {k: majority(v)[0] for k, v in tone.items()},
        "tone2": {f"{a}|{b}": majority(v)[0] for (a, b), v in tone2.items()
                  if sum(v.values()) >= 6 and majority(v)[1] >= 0.65},
        "lexicon": {k: majority(v)[0] for k, v in lex.items()},
        "_onset_conf": {k: round(majority(v)[1], 3) for k, v in onset.items()},
        "_rime_conf": {k: round(majority(v)[1], 3) for k, v in rime.items()},
        "_tone_conf": {k: round(majority(v)[1], 3) for k, v in tone.items()},
    }


CODAS = sorted(["ng", "nh", "ch", "p", "t", "k", "c", "m", "n", "i", "y", "o", "u", "ư"],
               key=len, reverse=True)


def compose_rime(r, model):
    """Vần chưa gặp: tách nhân + cuối, ghép từ các mảnh đã học."""
    rim = model["rime"]
    for coda in CODAS:
        if r.endswith(coda) and len(r) > len(coda):
            nuc = r[:-len(coda)]
            base = rim.get(nuc)
            tail = model.get("coda", {}).get(coda)
            if base and tail:
                return base + tail
    return None


def convert_word(latin_word, model):
    """Chuyển cả cụm: ưu tiên từ điển mức TỪ, rồi mức âm tiết, rồi quy tắc."""
    key = latin_word.lower().strip()
    if key in model.get("wordlex", {}):
        return model["wordlex"][key]
    parts = [convert(s, model) for s in key.split()]
    return None if any(p is None for p in parts) else " ".join(parts)


def convert(lat, model, use_lex=True):
    if use_lex and lat in model["lexicon"]:
        return model["lexicon"][lat]
    o, r, t = split_latin(lat)
    cname = model["onset"].get(o)
    pat = model["rime"].get(r)
    cls = model.get("tone2", {}).get(f"{t}|{o}") or model["tone"].get(t, "LOW")
    if pat is None:
        pat = TB.compose(r) or compose_rime(r, model)
    if cname is None or pat is None:
        return None
    return pat.replace("\u25CC", PAIR[cname][0 if cls == "LOW" else 1])


# ------------------------------------------------------------------- đánh giá
def evaluate(pairs, model, use_lex):
    ok = tot = miss = 0
    errs = collections.Counter()
    for lat, tav, _ in pairs:
        tot += 1
        got = convert(lat, model, use_lex)
        if got is None:
            miss += 1
            errs[f"[thiếu quy tắc] {lat}"] += 1
        elif got == tav:
            ok += 1
        else:
            errs[f"{lat}: được {got!r} / chuẩn {tav!r}"] += 1
    return ok, tot, miss, errs


def kfold_rules(pairs, k=5, seed=0):
    """CV theo TỪ VỰNG: âm tiết trong tập test không xuất hiện ở tập train."""
    vocab = sorted({p[0] for p in pairs})
    random.Random(seed).shuffle(vocab)
    folds = [set(vocab[i::k]) for i in range(k)]
    tot = ok = miss = 0
    for f in folds:
        tr = [p for p in pairs if p[0] not in f]
        te = [p for p in pairs if p[0] in f]
        m = learn(tr)
        a, b, c, _ = evaluate(te, m, use_lex=False)
        ok += a; tot += b; miss += c
    return ok, tot, miss


def main():
    raw = load_pairs()
    kept, dropped = clean(raw)
    model = learn(kept)
    # từ điển mức TỪ (cả cụm) — khử đồng tự nhờ ngữ cảnh
    wl = collections.defaultdict(collections.Counter)
    for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
        if r["Trạng Thái"] != "FIXED_MANUALLY":
            continue
        a = repair_latin(r["Từ Thái (Latinh)"].lower())
        b = repair_tavt(canon(r["Từ Thái (Unicode Chuẩn)"]))
        if a and b and len(a.split()) == len(b.split()):
            wl[a][b] += 1
    model["wordlex"] = {k: majority(v)[0] for k, v in wl.items()}
    print(f"Từ điển mức từ              : {len(model['wordlex'])} mục")

    print(f"Cặp âm tiết căn được        : {len(raw)}")
    print(f"Bị loại do mâu thuẫn tương quan: {len(dropped)}")
    print(f"Còn lại để học              : {len(kept)}  "
          f"({len({p[0] for p in kept})} âm tiết duy nhất)")
    print(f"Bảng: {len(model['onset'])} phụ âm đầu, {len(model['rime'])} vần, "
          f"{len(model['tone'])} thanh, {len(model['lexicon'])} mục từ điển")

    ok, tot, miss, errs = evaluate(kept, model, use_lex=True)
    print(f"\n[A] Có từ điển (từ đã biết)   : {ok}/{tot} = {ok/tot*100:.2f}%"
          f"   (thiếu quy tắc: {miss})")

    ok2, tot2, miss2, errs2 = evaluate(kept, model, use_lex=False)
    print(f"[B] Chỉ quy tắc, trên tập học : {ok2}/{tot2} = {ok2/tot2*100:.2f}%")

    ok3, tot3, miss3 = kfold_rules(kept)
    print(f"[C] Chỉ quy tắc, TỪ MỚI (5-fold): {ok3}/{tot3} = {ok3/tot3*100:.2f}%"
          f"   (không sinh được: {miss3})")

    json.dump(model, open("model.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open("errors.txt", "w", encoding="utf-8") as fh:
        fh.write("=== sai khi CHỈ dùng quy tắc (trên tập học) ===\n")
        for e, n in errs2.most_common():
            fh.write(f"{n:3}  {e}\n")
        fh.write("\n=== bị loại do mâu thuẫn tương quan ===\n")
        for lat, tav, conf in dropped:
            fh.write(f"{lat}\t{tav}\t{conf}\n")
    print("\nĐã ghi: model.json, errors.txt")
    print("Độ tin cậy thấp nhất của bảng thanh:",
          {k: model["_tone_conf"][k] for k in model["_tone_conf"]})


if __name__ == "__main__":
    main()
