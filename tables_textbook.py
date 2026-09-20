#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tables_textbook.py — Bảng chuẩn lấy từ giáo trình
"Học chữ viết cổ của người Thái (Sơn La) qua Tản Chụ Xiết Xương",
đối chiếu với đặc tả Unicode Tai Viet + CLDR.

Dùng làm NGUỒN CHUẨN để:
  (a) đè lên các mẫu vần học sai từ từ điển (bằng chứng mỏng / sai cấu trúc),
  (b) sinh ra các vần từ điển KHÔNG có (ưa, uôm, uôp, uyên...).

Giáo trình cho biết hai điều quan trọng:
  1. Bảng phụ âm có đúng 22 phụ âm × 2 nhóm: "tố tằm" (thấp) và "tố xủng" (cao).
     Trong chữ Việt của giáo trình, nhóm CAO viết HOA — tức chính tả của giáo
     trình mã hoá lớp thanh bằng CHỮ HOA, thứ thông tin mà chính tả dấu-thanh
     của từ điển đã làm mất.
  2. Bảng nguyên âm có 18 mục, mỗi mục ghi rõ đặt trên / đặt dưới phụ âm.
"""

# --- 22 phụ âm: chữ Việt -> (tố tằm/LOW, tố xủng/HIGH) --------------------
# Tên Unicode ghi kèm để đối chiếu; thứ tự theo bảng giáo trình.
CONSONANTS = {
    "b":  ("\uAA9A", "\uAA9B"),   # bo  / bõ   = LOW/HIGH BO
    "c":  ("\uAA80", "\uAA81"),   # co  / cõ   = LOW/HIGH KO    /k/
    "ch": ("\uAA8A", "\uAA8B"),   # cho / chõ  = LOW/HIGH CO    /tɕ/
    "d":  ("\uAAA4", "\uAAA5"),   # do  / dõ   = LOW/HIGH YO    /j/
    "đ":  ("\uAA92", "\uAA93"),   # đo  / đõ   = LOW/HIGH DO    /d/
    "g":  ("\uAA86", "\uAA87"),   # go  / gõ   = LOW/HIGH GO    (chỉ từ mượn)
    "h":  ("\uAAAC", "\uAAAD"),   # ho  / hõ   = LOW/HIGH HO
    "kh": ("\uAA84", "\uAA85"),   # kho / khõ  = LOW/HIGH KHHO  /x/
    "l":  ("\uAAA8", "\uAAA9"),   # lo  / lõ   = LOW/HIGH LO
    "m":  ("\uAAA2", "\uAAA3"),   # mo  / mõ   = LOW/HIGH MO
    "n":  ("\uAA98", "\uAA99"),   # no  / nõ   = LOW/HIGH NO
    "ng": ("\uAA88", "\uAA89"),   # ngo / ngõ  = LOW/HIGH NGO
    "nh": ("\uAA90", "\uAA91"),   # nho / nhõ  = LOW/HIGH NYO   /ɲ/
    "p":  ("\uAA9C", "\uAA9D"),   # po  / põ   = LOW/HIGH PO
    "ph": ("\uAAA0", "\uAAA1"),   # pho / phõ  = LOW/HIGH FO    /f/
    "r":  ("\uAAA6", "\uAAA7"),   # ro  / rõ   = LOW/HIGH RO    (chỉ từ mượn)
    "s":  ("\uAA8C", "\uAA8D"),   # so  / sõ   = LOW/HIGH CHO   (ô trống ở giáo trình)
    "t":  ("\uAA94", "\uAA95"),   # to  / tõ   = LOW/HIGH TO
    "th": ("\uAA96", "\uAA97"),   # tho / thõ  = LOW/HIGH THO
    "tr": ("\uAA94", "\uAA95"),   # tro / trõ  (ô trống ở giáo trình -> gộp với t)
    "v":  ("\uAAAA", "\uAAAB"),   # vo  / võ   = LOW/HIGH VO
    "x":  ("\uAA8E", "\uAA8F"),   # xo  / xõ   = LOW/HIGH SO    /s/
    "":   ("\uAAAE", "\uAAAF"),   # âm tiết mở đầu bằng nguyên âm = LOW/HIGH O
}
# biến thể chính tả dẫn về cùng một phụ âm
CONSONANTS["k"] = CONSONANTS["c"]
CONSONANTS["ngh"] = CONSONANTS["ng"]
CONSONANTS["gi"] = CONSONANTS["ch"]
CONSONANTS["f"] = CONSONANTS["ph"]
CONSONANTS["qu"] = CONSONANTS["c"]

# --- 18 nguyên âm/vần: chữ Việt -> (đứng trước, kết hợp, đứng sau) --------
# ◌ là vị trí phụ âm đầu.
NUCLEI = {
    "a":   ("", "", "\uAAB1"),            # ca      /aː/
    "ă":   ("", "\uAAB0", ""),            # (trên)  /a/
    "â":   ("", "\uAAB7", ""),            # (trên)  /ə/ ngắn  = MAI KHIT
    "e":   ("\uAAB5", "", ""),            # ke      /ɛ/
    "ê":   ("\uAAB9", "\uAAB8", ""),      # kê      /e/  digraph
    "i":   ("", "\uAAB2", ""),            # ki (trên)
    "ia":  ("", "\uAAB8", ""),            # kia     /iə/
    "iê":  ("", "\uAAB8", ""),
    "o":   ("", "\uAAB7", ""),            # /ɔ/ mở  = MAI KHIT (đóng -> LOW O, xử lý riêng)
    "ô":   ("\uAAB6", "", ""),            # cô      /o/
    "ơ":   ("\uAAB9", "\uAAB0", ""),      # cau  /ə/ digraph ꪹ◌ꪰ (theo nguồn Sơn La)
    "u":   ("", "\uAAB4", ""),            # cu (dưới)
    "ua":  ("", "", "\uAABA"),            # cua     /uə/
    "uô":  ("", "", "\uAABA"),
    "ư":   ("", "\uAAB3", ""),            # cư (trên)
    "ưa":  ("\uAAB9", "", ""),            # cưa     /ɨə/  = VOWEL UEA
    "ươ":  ("\uAAB9", "", ""),
    "y":   ("", "\uAAB2", ""),
}

# vần có chữ ghép sẵn (giáo trình liệt kê riêng)
LIGATURES = {
    "ay":  ("\uAABC", "", "", ""),        # cay  /aj/
    "au":  ("\uAAB9", "", "\uAAB1", ""),  # cau  /aw/  digraph ꪹ◌ꪱ
    "ăn":  ("", "", "\uAABD", ""),        # căn  /an/
    "ăm":  ("", "\uAABE", "", ""),        # căm  /am/
    "ăp":  ("", "\uAABE", "", "\uAA9A"),  # /ap/ = chữ ghép ăm + b
    "ăư":  ("\uAABB", "", "", ""),        # /əw/ = VOWEL AUE
    "âu":  ("\uAABB", "", "", ""),
}

# --- phụ âm cuối ---------------------------------------------------------
CODAS = {
    "p":  "\uAA9A",   # LOW BO
    "t":  "\uAA92",   # LOW DO
    "k":  "\uAA80",   # LOW KO
    "c":  "\uAA80",
    "ch": "\uAA80",
    "m":  "\uAAA3",   # HIGH MO
    "n":  "\uAA99",   # HIGH NO
    "ng": "\uAA89",   # HIGH NGO
    "nh": "\uAA89",
    "i":  "\uAAA5",   # HIGH YO  /j/
    "y":  "\uAAA5",
    "o":  "\uAAAB",   # HIGH VO  /w/
    "u":  "\uAAAB",
    "ư":  "\uAAAB",
}

# --- 5 chữ đặc biệt (giáo trình, trang "CÁC CHỮ ĐẶC BIỆT") ---------------
SPECIAL = {
    "nưng":    "\uAADC",   # thay cho "số một / chỉ một"
    "cỗn":     "\uAADB",   # thay cho "người"
    "ho hỡi":  "\uAADE",   # âm cảm thán mở đầu bài khắp
    "lải làu": "\uAADF",   # thay cho từ lặp trong từ láy
}

CODA_KEYS = sorted(CODAS, key=len, reverse=True)
NUC_KEYS = sorted(NUCLEI, key=len, reverse=True)

# Đặt dấu kết hợp TRƯỚC hay SAU phụ âm cuối. Từ điển nguồn dùng cả hai kiểu
# tuỳ nguyên âm (ꪲ trước; ꪰ ꪳ ꪴ sau) — Brase ghi nhận đúng sự dao động này.
MARK_AFTER_CODA = {"\uAAB0", "\uAAB3", "\uAAB4"}


def compose(rime):
    """Sinh mẫu vần chuẩn từ bảng giáo trình. Trả về mẫu có ◌ hoặc None."""
    if rime in LIGATURES:
        pre, mid, post, coda = LIGATURES[rime]
        return pre + "\u25CC" + mid + post + coda
    # nguyên âm đôi = nguyên âm dài trong chính tả nguồn: oo/ôô/êê/ưư -> o/ô/ê/ư
    import re as _re
    rime = _re.sub(r"(ô|ơ|ư|[aeiou])\1", r"\1", rime)
    if rime in LIGATURES:
        pre, mid, post, coda = LIGATURES[rime]
        return pre + "\u25CC" + mid + post + coda
    medial = ""
    r = rime
    for pat in ("uyê", "oa", "oă", "oe", "uâ", "uă", "uê", "uy"):
        if r.startswith(pat):
            medial = "\uAAAB"
            r = ("iê" + r[3:]) if pat == "uyê" else r[1:]
            break
    for nuc in NUC_KEYS:
        if r.startswith(nuc):
            coda_latin = r[len(nuc):]
            if coda_latin and coda_latin not in CODAS:
                continue
            pre, mid, post = NUCLEI[nuc]
            if nuc == "o" and coda_latin:       # /ɔ/ trong âm tiết đóng
                pre, mid, post = "", "", "\uAAAE"
            tail = CODAS.get(coda_latin, "")
            if mid and tail and mid in MARK_AFTER_CODA:
                return pre + "\u25CC" + medial + post + tail + mid
            return pre + "\u25CC" + medial + mid + post + tail
    return None


if __name__ == "__main__":
    for r in ["a", "ong", "ông", "ưa", "uôm", "uôp", "uyên", "ung", "ăng",
              "in", "ơng", "oong", "iêk", "ay", "au"]:
        print(f"  {r:6} -> {compose(r)}")
