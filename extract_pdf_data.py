#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pdf_data.py — Trích xuất cặp (latin_thái, nghĩa_việt) từ các file PDF

Nguồn 1: Từ điển Thái - Việt (Tiếng Thái Nghệ An).pdf
  Format: latin [IPA] loại. nghĩa1; nghĩa2
  Ví dụ: "ả [ʔa1] 1 d. cô, dì"
         "a cạt [ʔa3 kaat6] d. phép rút đất của thầy Mo"

Nguồn 2: Từ-Vựng-Thai-Việt-Vung-Mường-So-Lai-Chau.pdf
  Format: latin/ chữThái(OCR lỗi): nghĩa
  Ví dụ: "ả ók/ 91 99M: choãi ra."
  -> Chỉ lấy phần latin + nghĩa, bỏ phần chữ Thái (OCR bị hỏng)

Dùng:
    python3 extract_pdf_data.py
    -> Xuất ra: extracted_pairs.csv
"""

import re
import csv
import subprocess
import unicodedata as ud
from pathlib import Path

HERE = Path(__file__).parent

# ─── Helper ──────────────────────────────────────────────────────────────────

def pdf_to_text(pdf_path: str, first_page: int = 1, last_page: int = None) -> str:
    """Dùng pdftotext (poppler) để extract text từ PDF."""
    cmd = ["pdftotext", "-layout"]
    if first_page > 1:
        cmd += ["-f", str(first_page)]
    if last_page:
        cmd += ["-l", str(last_page)]
    cmd += [pdf_path, "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return result.stdout


def clean_latin(s: str) -> str:
    """Chuẩn hóa chuỗi Latin tiếng Thái."""
    s = s.strip().lower()
    # Chuẩn hóa Unicode về NFC
    s = ud.normalize("NFC", s)
    # Bỏ dấu chấm lẻ ở đầu/cuối
    s = s.strip(".")
    return s.strip()


def clean_nghia(s: str) -> str:
    """Chuẩn hóa chuỗi nghĩa tiếng Việt."""
    s = s.strip()
    # Bỏ dấu chấm cuối, ngoặc kép thừa
    s = s.rstrip(".")
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.strip()


# ─── Nguồn 1: Từ điển Nghệ An ──────────────────────────────────────────────

# Mẫu: "từ đơn [IPA] số? loại. nghĩa"
# Chỉ lấy phần đầu (từ latin) và phần nghĩa, bỏ IPA và từ loại
RE_NGHE_AN = re.compile(
    r'^([a-záàảãạăắằẳẵặâấầẩẫậđéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ'
    r'A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ\s\-\']+?)'
    r'\s*\[.*?\]'         # IPA trong ngoặc vuông
    r'(?:\s+\d+)?'        # số thứ tự tùy chọn
    r'(?:\s+[a-z]+\.)?'   # từ loại tùy chọn (d. đg. t. v.v.)
    r'\s+(.+)$',
    re.IGNORECASE
)

# Mẫu mục phụ: "- câu ví dụ. dịch nghĩa"  -> bỏ qua
RE_EXAMPLE = re.compile(r'^\s*-\s')

# Mẫu "x. từ_khác" -> bỏ qua (chú thích xem thêm)
RE_XREF = re.compile(r'^x\.\s')


def parse_nghe_an(pdf_path: str) -> list[dict]:
    """Parse Từ điển Thái Nghệ An."""
    print(f"  Đọc: {pdf_path}")
    # Phần từ điển thực sự bắt đầu từ trang 16 (A...)
    text = pdf_to_text(pdf_path, first_page=16)
    
    pairs = []
    current_entry = None  # (latin, nghia_parts)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if RE_EXAMPLE.match(line):
            continue  # câu ví dụ, bỏ qua

        m = RE_NGHE_AN.match(line)
        if m:
            lat = clean_latin(m.group(1))
            ngh = clean_nghia(m.group(2))
            
            # Bỏ "x. ..." (chú thích xem)
            if RE_XREF.match(ngh):
                continue
            # Bỏ mục quá ngắn hoặc rõ ràng là noise
            if len(lat) < 1 or len(ngh) < 2:
                continue
            # Bỏ entry là số trang
            if lat.isdigit():
                continue
            
            pairs.append({
                "latin":  lat,
                "nghia":  ngh,
                "source": "nghe_an",
            })

    print(f"  -> {len(pairs)} cặp từ Nghệ An")
    return pairs


# ─── Nguồn 2: Từ vựng Lai Châu ─────────────────────────────────────────────

# Format: "từ_latin/ chữ_thái_OCR_hỏng: nghĩa."
# Cũng có format: "từ_latin/ chữ_thái: nghĩa."
RE_LAI_CHAU = re.compile(
    r'^([a-záàảãạăắằẳẵặâấầẩẫậđéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ'
    r'\s\-\']+?)'
    r'/'                  # dấu / phân cách
    r'\s*[^\:]+?'         # phần chữ Thái (OCR lỗi, bỏ qua)
    r':\s*'               # dấu : trước nghĩa
    r'(.+)$',
    re.IGNORECASE
)


def parse_lai_chau(pdf_path: str) -> list[dict]:
    """Parse Từ vựng Thái Việt Vùng Mường So, Lai Châu."""
    print(f"  Đọc: {pdf_path}")
    # Phần từ điển bắt đầu từ trang 14
    text = pdf_to_text(pdf_path, first_page=14)
    
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 5:
            continue
        m = RE_LAI_CHAU.match(line)
        if m:
            lat = clean_latin(m.group(1))
            ngh = clean_nghia(m.group(2))
            if len(lat) < 1 or len(ngh) < 2:
                continue
            if lat.isdigit():
                continue
            pairs.append({
                "latin":  lat,
                "nghia":  ngh,
                "source": "lai_chau",
            })

    print(f"  -> {len(pairs)} cặp từ Lai Châu")
    return pairs


# ─── Nguồn 3: CSV sẵn ────────────────────────────────────────────────────────

def load_existing_csv(csv_path: str) -> list[dict]:
    """Load taiviet_dictionary_clean.csv (đã có tai_viet chuẩn)."""
    print(f"  Đọc: {csv_path}")
    pairs = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("trang_thai") != "OK":
                continue
            lat = r.get("latin", "").strip().lower()
            tv  = r.get("tai_viet", "").strip()
            ngh = r.get("nghia", "").strip().rstrip(".")
            if lat and ngh:
                pairs.append({
                    "latin":    lat,
                    "tai_viet": tv,   # đã có sẵn, không cần convert
                    "nghia":    ngh,
                    "source":   "csv_soat_tay",
                })
    print(f"  -> {len(pairs)} cặp từ CSV soát tay")
    return pairs


# ─── Chuyển Latin → Tai Viet (tavt2.py) ─────────────────────────────────────

def convert_to_taiviet(pairs: list[dict]) -> list[dict]:
    """
    Dùng tavt2.py để chuyển latin -> Tai Viet cho các mục chưa có tai_viet.
    Ghi tạm ra file, chạy tavt2, đọc lại.
    """
    import sys
    sys.path.insert(0, str(HERE))
    from tavt2 import Converter
    from repair import repair_latin, repair_tavt
    import unicodedata as ud

    conv = Converter()
    need_convert = [p for p in pairs if not p.get("tai_viet")]
    
    print(f"  Chuyển đổi {len(need_convert)} mục Latin → Tai Viet...")
    converted = 0
    failed = 0
    
    for p in need_convert:
        lat_repaired = repair_latin(p["latin"])
        tv = conv.word(lat_repaired)
        if tv:
            p["tai_viet"] = ud.normalize("NFC", tv)
            converted += 1
        else:
            p["tai_viet"] = ""
            failed += 1

    print(f"  -> Chuyển thành công: {converted}, thất bại: {failed}")
    return pairs


# ─── Loại bỏ trùng lặp ───────────────────────────────────────────────────────

def dedup(pairs: list[dict]) -> list[dict]:
    """Loại bỏ mục trùng (latin + nghia), ưu tiên giữ bản có tai_viet."""
    seen = {}
    for p in pairs:
        key = (p["latin"].strip(), p["nghia"].strip())
        if key not in seen:
            seen[key] = p
        elif p.get("tai_viet") and not seen[key].get("tai_viet"):
            seen[key] = p  # ưu tiên bản có Tai Viet
    return list(seen.values())


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BƯỚC 1: Trích xuất data từ các nguồn")
    print("=" * 60)

    all_pairs = []

    # 1. CSV soát tay (có tai_viet sẵn)
    csv_path = HERE / "taiviet_dictionary_clean.csv"
    if csv_path.exists():
        all_pairs += load_existing_csv(str(csv_path))

    # 2. Từ điển Nghệ An
    pdf_nghe_an = HERE / "pdfs" / "Từ điển Thái - Việt (Tiếng Thái Nghệ An).pdf"
    if pdf_nghe_an.exists():
        all_pairs += parse_nghe_an(str(pdf_nghe_an))

    # 3. Từ vựng Lai Châu
    pdf_lai_chau = HERE / "pdfs" / "841056936-Từ-Vựng-Thai-Việt-Vung-Mường-So-Lai-Chau-1.pdf"
    if pdf_lai_chau.exists():
        all_pairs += parse_lai_chau(str(pdf_lai_chau))

    print(f"\nTổng trước dedup: {len(all_pairs)}")

    print("\n" + "=" * 60)
    print("BƯỚC 2: Loại bỏ trùng lặp")
    print("=" * 60)
    all_pairs = dedup(all_pairs)
    print(f"Sau dedup: {len(all_pairs)}")

    print("\n" + "=" * 60)
    print("BƯỚC 3: Chuyển đổi Latin → Tai Viet")
    print("=" * 60)
    all_pairs = convert_to_taiviet(all_pairs)

    # Lọc mục có tai_viet thành công
    valid = [p for p in all_pairs if p.get("tai_viet") and p.get("latin") and p.get("nghia")]
    no_tv = [p for p in all_pairs if not p.get("tai_viet")]
    
    print(f"\nMục có Tai Viet: {len(valid)}")
    print(f"Mục thất bại (không chuyển được): {len(no_tv)}")

    print("\n" + "=" * 60)
    print("BƯỚC 4: Lưu kết quả")
    print("=" * 60)

    out_path = HERE / "extracted_pairs.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["latin", "tai_viet", "nghia", "source"])
        w.writeheader()
        w.writerows(valid)
    print(f"Đã lưu {len(valid)} cặp -> {out_path}")

    # Lưu riêng các mục thất bại để xem lại
    fail_path = HERE / "failed_convert.csv"
    with open(fail_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["latin", "nghia", "source"])
        w.writeheader()
        for p in no_tv:
            w.writerow({"latin": p["latin"], "nghia": p["nghia"], "source": p.get("source","")})
    print(f"Mục thất bại -> {fail_path}")

    # Preview
    print("\nMẫu kết quả:")
    for p in valid[:5]:
        print(f"  [{p['source']}] {p['latin']!r:20} -> {p['tai_viet']!r:15} | {p['nghia']!r}")

    from collections import Counter
    src_counts = Counter(p["source"] for p in valid)
    print(f"\nTheo nguồn: {dict(src_counts)}")


if __name__ == "__main__":
    main()
