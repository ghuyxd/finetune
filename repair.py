#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair.py — Sửa các lỗi TÁCH TỪ trong chính dữ liệu "đã soát tay".

Khảo sát cho thấy phần lớn chỗ lệch giữa bộ chuyển đổi và cột "Unicode Chuẩn"
KHÔNG phải lỗi chuyển đổi mà là lỗi OCR/tách từ trong nguồn:

  1. Cột Latinh bị tách giữa âm tiết:  "b ăư m ạy"  (đúng: "băư mạy")
  2. Cột Unicode bị tách dấu phụ:      "ꪮꪱꪚ ꪤ ꪲꪙ"   (đúng: "ꪮꪱꪚ ꪤꪲꪙ")
  3. Cột Unicode bị cụt âm tiết:       "băư lem" -> chỉ có "ꪻꪚ"

Mục (1) và (2) sửa được tự động. Mục (3) không sửa được — loại khỏi phần chấm
điểm vì không có đáp án để so.
"""
import re
import unicodedata as ud

VOWEL_LETTERS = set("aăâeêioôơuưy")
# dấu phụ / nguyên âm KHÔNG bao giờ mở đầu một âm tiết Tai Viet
DEPENDENT = set("\uAAB0\uAAB2\uAAB3\uAAB4\uAAB7\uAAB8\uAABE"
                "\uAABF\uAAC0\uAAC1\uAAC2\uAAB1\uAABA\uAABD")


def has_vowel(tok):
    return any(c in VOWEL_LETTERS for c in ud.normalize("NFD", tok.lower())
               if c.isalpha())


def repair_latin(s):
    """Ghép lại các mảnh âm tiết bị tách trong cột Latinh."""
    toks = s.split()
    out = []
    i = 0
    while i < len(toks):
        t = toks[i]
        # mảnh chỉ có phụ âm -> dính vào mảnh kế tiếp
        while (not has_vowel(t)) and i + 1 < len(toks):
            i += 1
            t += toks[i]
        out.append(t)
        i += 1
    # mảnh chỉ là một nguyên âm đơn đứng sau một âm tiết -> dính vào trước
    merged = []
    for t in out:
        if merged and len(ud.normalize("NFD", t).rstrip("\u0300\u0301\u0303"
                                                        "\u0309\u0323")) <= 2 \
           and not any(c.isalpha() and c not in VOWEL_LETTERS
                       for c in ud.normalize("NFD", t.lower())) \
           and has_vowel(merged[-1]) and len(merged[-1]) <= 3:
            merged[-1] += t
        else:
            merged.append(t)
    return " ".join(merged)


def repair_tavt(s):
    """Ghép lại các mảnh bị tách trong cột Unicode Tai Viet."""
    toks = s.split()
    out = []
    for t in toks:
        if out and t and t[0] in DEPENDENT:
            out[-1] += t
        else:
            out.append(t)
    return " ".join(out)


if __name__ == "__main__":
    for a, b in [("b ăư m ạy", "băư mạy"), ("an m ạ", "an mạ"),
                 ("b ă ư ỏn", "băư ỏn"), ("áp din", "áp din")]:
        print(f"{a!r:16} -> {repair_latin(a)!r}   (mong đợi {b!r})")
    print(repr(repair_tavt("ꪮꪱꪚ ꪤ ꪲꪙ")))
