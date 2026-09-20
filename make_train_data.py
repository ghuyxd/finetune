#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_train_data.py — Xây dựng dataset train từ extracted_pairs.csv

Pipeline:
  1. Đọc extracted_pairs.csv (đã có latin, tai_viet, nghia từ tất cả nguồn)
  2. Sinh nhiều mẫu ChatML đa dạng (augmentation)
  3. Xuất ra:
       - dataset/train.jsonl  (format sharegpt cho LLaMA-Factory)
       - dataset/val.jsonl
       - dataset/stats.txt

Dùng:
    python3 make_train_data.py
    python3 make_train_data.py --csv extracted_pairs.csv --ratio 0.9
"""

import argparse
import csv
import json
import random
import re
import unicodedata as ud
from pathlib import Path

HERE = Path(__file__).parent

# Import các hàm repair sẵn có
import sys
sys.path.insert(0, str(HERE))
from repair import repair_latin, repair_tavt

# ------------------------------------------------------------------
# Các mẫu prompt đa dạng (augmentation) để tránh model học vẹt
# ------------------------------------------------------------------

PROMPTS_TV_TO_VI = [
    "Nghĩa tiếng Việt của \"{tv}\" là gì?",
    "Dịch sang tiếng Việt: {tv}",
    "Từ tiếng Thái \"{tv}\" có nghĩa là gì?",
    "\"{tv}\" trong tiếng Thái nghĩa là gì?",
    "Hãy cho tôi biết nghĩa của từ Thái: {tv}",
    "Giải thích nghĩa từ tiếng Thái Việt: {tv}",
]

PROMPTS_VI_TO_TV = [
    "Dịch sang tiếng Thái (chữ Thái): {vi}",
    "\"{vi}\" trong tiếng Thái là gì?",
    "Cách viết \"{vi}\" bằng chữ Thái?",
    "Hãy dịch từ tiếng Việt sang tiếng Thái: {vi}",
    "Viết \"{vi}\" bằng chữ Thái Việt Nam:",
    "Từ tiếng Thái tương đương với \"{vi}\" là gì?",
]

PROMPTS_LATIN_TO_TV = [
    "Chuyển \"{la}\" từ Latin sang chữ Thái chuẩn:",
    "Viết \"{la}\" bằng chữ Thái Việt:",
    "Chuyển đổi từ Thái Latin \"{la}\" sang Unicode Tai Viet:",
    "\"{la}\" (Latin) viết bằng chữ Thái là gì?",
]

SYSTEM_MSG = (
    "Bạn là trợ lý thông thạo tiếng Việt và tiếng Thái (chữ Thái Việt – Tai Viet, "
    "Unicode U+AA80–U+AADF). Hãy trả lời chính xác và ngắn gọn."
)

# ------------------------------------------------------------------
# Làm sạch nghĩa tiếng Việt
# ------------------------------------------------------------------

def clean_nghia(s: str) -> str:
    """Chuẩn hóa chuỗi nghĩa: bỏ dấu chấm cuối thừa, strip khoảng trắng."""
    s = s.strip().strip(".")
    # Loại bỏ dấu ngoặc kép thừa bao quanh
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.strip()


def clean_tai_viet(s: str) -> str:
    """Chuẩn hóa chuỗi Tai Viet: repair + NFC."""
    s = repair_tavt(s.strip())
    return ud.normalize("NFC", s)


def clean_latin(s: str) -> str:
    """Chuẩn hóa Latin: repair + lower + strip."""
    s = repair_latin(s.strip().lower())
    return s


# ------------------------------------------------------------------
# Tạo mẫu sharegpt
# ------------------------------------------------------------------

def make_sample(system: str, user: str, assistant: str) -> dict:
    return {
        "conversations": [
            {"from": "system",    "value": system},
            {"from": "human",     "value": user},
            {"from": "gpt",       "value": assistant},
        ]
    }


def gen_samples(latin: str, tai_viet: str, nghia: str) -> list[dict]:
    """Sinh nhiều mẫu đa dạng từ một mục từ điển."""
    samples = []

    # --- Tai Viet -> Tiếng Việt
    for tmpl in PROMPTS_TV_TO_VI:
        q = tmpl.format(tv=tai_viet)
        samples.append(make_sample(SYSTEM_MSG, q, nghia))

    # --- Tiếng Việt -> Tai Viet  (chỉ tạo nếu nghĩa rõ ràng, không phải danh sách)
    if "," not in nghia and len(nghia) < 60:
        for tmpl in PROMPTS_VI_TO_TV:
            q = tmpl.format(vi=nghia)
            samples.append(make_sample(SYSTEM_MSG, q, tai_viet))

    # --- Latin -> Tai Viet
    for tmpl in PROMPTS_LATIN_TO_TV:
        q = tmpl.format(la=latin)
        samples.append(make_sample(SYSTEM_MSG, q, tai_viet))

    return samples


# ------------------------------------------------------------------
# Pipeline chính
# ------------------------------------------------------------------

def load_csv(csv_path: Path) -> list[dict]:
    """Đọc extracted_pairs.csv (có cột latin, tai_viet, nghia, source)."""
    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for r in reader:
            # Hỗ trợ cả extracted_pairs.csv và taiviet_dictionary_clean.csv
            if "trang_thai" in fieldnames and r.get("trang_thai") != "OK":
                continue
            latin    = clean_latin(r.get("latin", ""))
            tai_viet = clean_tai_viet(r.get("tai_viet", ""))
            nghia    = clean_nghia(r.get("nghia", ""))
            if not latin or not tai_viet or not nghia:
                continue
            rows.append({
                "latin":    latin,
                "tai_viet": tai_viet,
                "nghia":    nghia,
            })
    return rows


def build_dataset(rows: list[dict], seed: int = 42) -> list[dict]:
    all_samples = []
    for r in rows:
        all_samples.extend(gen_samples(r["latin"], r["tai_viet"], r["nghia"]))
    random.seed(seed)
    random.shuffle(all_samples)
    return all_samples


def split_and_save(
    samples: list[dict],
    out_dir: Path,
    train_ratio: float = 0.9,
):
    out_dir.mkdir(parents=True, exist_ok=True)
    n_train = int(len(samples) * train_ratio)
    train_set = samples[:n_train]
    val_set   = samples[n_train:]

    train_path = out_dir / "train.jsonl"
    val_path   = out_dir / "val.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for s in train_set:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for s in val_set:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    return train_path, val_path, len(train_set), len(val_set)


def main():
    ap = argparse.ArgumentParser(description="Tạo dataset train tiếng Thái – Việt")
    ap.add_argument("--csv",    default="taiviet_dictionary_clean.csv",
                    help="File CSV đầu vào (mặc định: taiviet_dictionary_clean.csv)")
    ap.add_argument("--outdir", default="dataset",
                    help="Thư mục xuất dataset (mặc định: dataset/)")
    ap.add_argument("--ratio",  type=float, default=0.9,
                    help="Tỉ lệ train/val (mặc định: 0.9)")
    ap.add_argument("--seed",   type=int,   default=42)
    a = ap.parse_args()

    csv_path = HERE / a.csv
    out_dir  = HERE / a.outdir

    print(f"[1/4] Đọc CSV: {csv_path}")
    rows = load_csv(csv_path)
    print(f"      Số mục hợp lệ: {len(rows)}")

    print("[2/4] Sinh mẫu training...")
    samples = build_dataset(rows, seed=a.seed)
    print(f"      Tổng mẫu: {len(samples)}")

    print("[3/4] Tách train/val và lưu...")
    train_path, val_path, n_tr, n_val = split_and_save(samples, out_dir, a.ratio)
    print(f"      Train: {n_tr} mẫu -> {train_path}")
    print(f"      Val  : {n_val} mẫu -> {val_path}")

    # Thống kê
    stats_path = out_dir / "stats.txt"
    with open(stats_path, "w", encoding="utf-8") as f:
        f.write(f"Nguồn CSV      : {csv_path}\n")
        f.write(f"Mục từ điển OK : {len(rows)}\n")
        f.write(f"Tổng mẫu       : {len(samples)}\n")
        f.write(f"Train          : {n_tr}\n")
        f.write(f"Val            : {n_val}\n")
        f.write(f"Seed           : {a.seed}\n")
        f.write(f"\n--- Mẫu đầu train.jsonl ---\n")
        first = json.loads(open(train_path, encoding="utf-8").readline())
        for turn in first["conversations"]:
            f.write(f"  [{turn['from']}]: {turn['value'][:80]}\n")

    print(f"[4/4] Thống kê -> {stats_path}")
    print("\nXong! Mẫu đầu tiên trong train.jsonl:")
    first = json.loads(open(train_path, encoding="utf-8").readline())
    for turn in first["conversations"]:
        role = turn["from"]
        val  = turn["value"]
        print(f"  [{role}]: {val}")


if __name__ == "__main__":
    main()
