#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavt2.py — Chuyển chữ Thái Latin -> chữ Thái Việt Nam (Tai Viet, U+AA80–U+AADF)
           bằng mô hình học từ từ điển đã soát tay (model.json).

Ba tầng, xét theo thứ tự:
  1. Từ điển mức TỪ   — cả cụm khớp nguyên văn (khử được đồng tự nhờ ngữ cảnh)
  2. Từ điển mức ÂM TIẾT — từng âm tiết đã gặp trong từ điển
  3. Quy tắc          — phụ âm đầu × vần × lớp thanh, học theo đa số

Hệ thanh: dùng hệ TRUYỀN THỐNG không đánh dấu thanh — thanh do LỚP phụ âm đầu
(LOW/HIGH) mang. Đây là hệ mà nguồn từ điển dùng (chỉ 61/2003 âm tiết có dấu
thanh, phần lớn đặt sai vị trí).

Dùng:
    python3 tavt2.py vanban.txt -o ketqua.txt -r baocao.txt
    python3 tavt2.py --csv tu_dien.csv --col "Từ Thái (Latinh)" -o ketqua.csv
    python3 tavt2.py --eval          # chạy lại đánh giá trên từ điển gốc
"""
import argparse, csv, json, os, re, sys, collections
import unicodedata as ud
import tables_textbook as TB

HERE = os.path.dirname(os.path.abspath(__file__))

LOW_ROW = ("\uAA80\uAA82\uAA84\uAA86\uAA88\uAA8A\uAA8C\uAA8E\uAA90\uAA92\uAA94"
           "\uAA96\uAA98\uAA9A\uAA9C\uAA9E\uAAA0\uAAA2\uAAA4\uAAA6\uAAA8\uAAAA"
           "\uAAAC\uAAAE")
HIGH_ROW = ("\uAA81\uAA83\uAA85\uAA87\uAA89\uAA8B\uAA8D\uAA8F\uAA91\uAA93\uAA95"
            "\uAA97\uAA99\uAA9B\uAA9D\uAA9F\uAAA1\uAAA3\uAAA5\uAAA7\uAAA9\uAAAB"
            "\uAAAD\uAAAF")
NAMES = "k kh x g ng c chh s ny d t th n b p ph f m y r l v h '".split()
PAIR = {nm: (LOW_ROW[i], HIGH_ROW[i]) for i, nm in enumerate(NAMES)}

TONE_DIA = {"\u0301": "sac", "\u0300": "huyen", "\u0309": "hoi",
            "\u0303": "nga", "\u0323": "nang"}
ONSETS = sorted(["ngh", "kh", "ph", "th", "ch", "nh", "ng", "gi", "tr", "qu",
                 "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r",
                 "s", "t", "v", "x", "y", "f"], key=len, reverse=True)
CODAS = sorted(["ng", "nh", "ch", "p", "t", "k", "c", "m", "n", "i", "y", "o",
                "u", "ư"], key=len, reverse=True)
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


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


class Converter:
    """profile='dict'    -> ưu tiên bảng học từ từ điển Sơn La (chính tả có oo/ôô/êê)
       profile='textbook'-> ưu tiên bảng giáo trình Tản Chụ Xiết Xương (nguyên âm đơn)"""

    def __init__(self, model_path=None, profile="dict"):
        self.profile = profile
        self.m = json.load(open(model_path or os.path.join(HERE, "model.json"),
                                encoding="utf-8"))
        self.stats = collections.Counter()
        self.unknown = collections.Counter()

    # --- tầng 3: quy tắc -------------------------------------------------
    def _compose_rime(self, r):
        book = TB.compose(r)
        if book:
            return book
        rim = self.m["rime"]
        for coda in CODAS:
            if r.endswith(coda) and len(r) > len(coda):
                base = rim.get(r[:-len(coda)])
                tail = self.m.get("coda", {}).get(coda)
                if base and tail:
                    return base + tail
        return None

    def by_rule(self, syl):
        o, r, t = split_latin(syl)
        cname = self.m["onset"].get(o)
        if self.profile == "textbook":
            book = TB.compose(r)
            if book and o in TB.CONSONANTS:
                cls = (self.m.get("tone2", {}).get(f"{t}|{o}")
                       or self.m["tone"].get(t, "LOW"))
                return book.replace("\u25CC",
                                    TB.CONSONANTS[o][0 if cls == "LOW" else 1])
        if cname is None and o in TB.CONSONANTS:
            pat2 = self.m["rime"].get(r) or self._compose_rime(r)
            if pat2:
                cls2 = (self.m.get("tone2", {}).get(f"{t}|{o}")
                        or self.m["tone"].get(t, "LOW"))
                return pat2.replace("\u25CC",
                                    TB.CONSONANTS[o][0 if cls2 == "LOW" else 1])
        pat = self.m["rime"].get(r) or self._compose_rime(r)
        cls = self.m.get("tone2", {}).get(f"{t}|{o}") or self.m["tone"].get(t, "LOW")
        if cname is None or pat is None:
            return None
        return pat.replace("\u25CC", PAIR[cname][0 if cls == "LOW" else 1])

    # --- tầng 2: âm tiết -------------------------------------------------
    def syllable(self, syl):
        key = syl.lower()
        if self.profile == "textbook":
            out = self.by_rule(key)
            if out:
                self.stats["rule"] += 1
                return out
        if key in self.m["lexicon"]:
            self.stats["lex_syl"] += 1
            return self.m["lexicon"][key]
        out = self.by_rule(key)
        if out is None:
            self.stats["fail"] += 1
            self.unknown[key] += 1
        else:
            self.stats["rule"] += 1
        return out

    # --- tầng 1: cả cụm --------------------------------------------------
    def word(self, latin_word):
        key = " ".join(latin_word.lower().split())
        if key in self.m.get("wordlex", {}):
            self.stats["lex_word"] += 1
            return self.m["wordlex"][key]
        parts = [self.syllable(s) for s in key.split()]
        return None if any(p is None for p in parts) else " ".join(parts)

    def text(self, text, keep_unknown=True):
        def repl(mt):
            out = self.syllable(mt.group(0))
            return mt.group(0) if out is None and keep_unknown else (out or "")
        return ud.normalize("NFC", WORD_RE.sub(repl, text))


# ------------------------------------------------------------------ đánh giá
def run_eval(csv_path):
    import build_model as B
    conv = Converter()
    rows = [r for r in csv.DictReader(open(csv_path, encoding="utf-8-sig"))
            if r["Trạng Thái"] == "FIXED_MANUALLY"]
    ok = tot = 0
    wrong, skipped = [], []
    for r in rows:
        from repair import repair_latin, repair_tavt
        lat = repair_latin(r["Từ Thái (Latinh)"].lower())
        gold = repair_tavt(B.canon(r["Từ Thái (Unicode Chuẩn)"]))
        if not lat or not gold:
            continue
        if len(gold.split()) != len(lat.split()):
            skipped.append((lat, gold))     # đáp án cụt/thừa -> không chấm được
            continue
        tot += 1
        got = conv.word(lat)
        if got is not None and " ".join(got.split()) == gold:
            ok += 1
        else:
            wrong.append((lat, got, gold))
    print(f"Toàn bộ mục FIXED_MANUALLY: {ok}/{tot} = {ok/tot*100:.2f}% khớp chính xác")
    print("Nguồn kết quả:", dict(conv.stats))
    with open(os.path.join(HERE, "eval_entries.txt"), "w", encoding="utf-8") as fh:
        for lat, got, gold in wrong:
            fh.write(f"{lat}\tđược={got}\tchuẩn={gold}\n")
    print(f"Sai: {len(wrong)} mục -> eval_entries.txt")
    print(f"Bỏ qua (đáp án trong CSV bị cụt/thừa âm tiết): {len(skipped)} mục")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("-o", "--output")
    ap.add_argument("-r", "--report")
    ap.add_argument("-m", "--model")
    ap.add_argument("-p", "--profile", choices=["dict", "textbook"], default="dict",
                    help="chính tả nguồn: 'dict'=từ điển Sơn La, 'textbook'=Tản Chụ Xiết Xương")
    ap.add_argument("--csv", help="chuyển một cột trong tệp CSV")
    ap.add_argument("--col", default="Từ Thái (Latinh)")
    ap.add_argument("--eval", nargs="?", const=os.environ.get(
        "TAVT_CSV", "/mnt/user-data/uploads/dictionary_entries_scored_reviewed__1_.csv"))
    a = ap.parse_args()

    if a.eval:
        return run_eval(a.eval)

    conv = Converter(a.model, a.profile)
    if a.csv:
        rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
        for r in rows:
            r["Tai Viet (sinh tự động)"] = conv.word(r[a.col]) or ""
        out = open(a.output or "converted.csv", "w", encoding="utf-8", newline="")
        w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    elif a.input:
        text = open(a.input, encoding="utf-8").read()
        res = conv.text(text)
        (open(a.output, "w", encoding="utf-8") if a.output else sys.stdout).write(res)
    else:
        ap.error("cần tệp đầu vào, --csv hoặc --eval")

    tot = sum(conv.stats.values()) or 1
    lines = [f"từ điển mức từ   : {conv.stats['lex_word']}",
             f"từ điển âm tiết  : {conv.stats['lex_syl']}",
             f"quy tắc          : {conv.stats['rule']}",
             f"không chuyển được: {conv.stats['fail']} ({conv.stats['fail']/tot*100:.1f}%)"]
    if conv.unknown:
        lines.append("\n--- âm tiết chưa xử lý được ---")
        lines += [f"  {v:3}  {k}" for k, v in conv.unknown.most_common(50)]
    rep = "\n".join(lines)
    if a.report:
        open(a.report, "w", encoding="utf-8").write(rep + "\n")
    print(rep, file=sys.stderr)


if __name__ == "__main__":
    main()
