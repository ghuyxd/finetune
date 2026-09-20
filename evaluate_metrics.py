#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate_metrics.py — Tính toán các chỉ số BLEU và chrF trên tập dữ liệu kiểm thử.
CHỈ tập trung vào 2 tác vụ thuần:
  1. Thái Việt → Tiếng Việt (TaiViet script Unicode U+AA80–U+AADF sang Tiếng Việt)
  2. Tiếng Việt → Thái Việt (Tiếng Việt sang TaiViet script)
Loại bỏ hoàn toàn các mẫu liên quan đến chữ Thái Latin.
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import sacrebleu
from tabulate import tabulate
from tqdm import tqdm

HERE = Path(__file__).parent
DEFAULT_DATASET = HERE / "dataset/val.jsonl"
DEFAULT_OLLAMA_MODEL = "taiviet-bot"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"

PROMPTS_LATIN_TO_TV = [
    "từ Latin sang chữ Thái chuẩn:",
    "bằng chữ Thái Việt:",
    "sang Unicode Tai Viet:",
    "(Latin) viết bằng chữ Thái là gì?",
]

PROMPTS_TV_TO_VI = [
    "Nghĩa tiếng Việt của",
    "Dịch sang tiếng Việt:",
    "Từ tiếng Thái \"",
    "trong tiếng Thái nghĩa là gì?",
    "Hãy cho tôi biết nghĩa của từ Thái:",
    "Giải thích nghĩa từ tiếng Thái Việt:",
]

PROMPTS_VI_TO_TV = [
    "Dịch sang tiếng Thái (chữ Thái):",
    "trong tiếng Thái là gì?",
    "Cách viết \"",
    "Hãy dịch từ tiếng Việt sang tiếng Thái:",
    "Viết \"",
    "Từ tiếng Thái tương đương với",
]


def contains_tai_viet(text: str) -> bool:
    """Kiểm tra có chứa ký tự chữ Thái Việt Unicode (U+AA80–U+AADF) hay không."""
    return any(0xAA80 <= ord(c) <= 0xAADF for c in text)


def classify_prompt(user_prompt: str, reference: str = "") -> Optional[str]:
    """
    Phân loại chỉ 2 tác vụ:
      - 'Thái Việt -> Tiếng Việt'
      - 'Tiếng Việt -> Thái Việt'
    Trả về None nếu dính tới Thái Latin.
    """
    # Loại bỏ mẫu dính tới chữ Thái Latin
    if any(p in user_prompt for p in PROMPTS_LATIN_TO_TV):
        return None
    if "latin" in user_prompt.lower():
        return None

    # Thái Việt -> Tiếng Việt: Prompt chứa chữ Thái Việt và hỏi nghĩa tiếng Việt
    if any(p in user_prompt for p in PROMPTS_TV_TO_VI) or (contains_tai_viet(user_prompt) and not contains_tai_viet(reference)):
        return "Thái Việt -> Tiếng Việt"

    # Tiếng Việt -> Thái Việt: Prompt là tiếng Việt và yêu cầu dịch sang chữ Thái
    if any(p in user_prompt for p in PROMPTS_VI_TO_TV) or (not contains_tai_viet(user_prompt) and contains_tai_viet(reference)):
        return "Tiếng Việt -> Thái Việt"

    return None


def clean_text(text: str) -> str:
    """Làm sạch nhẹ văn bản dự đoán (bỏ dấu ngoặc kép, dấu chấm phẩy thừa ở cuối)."""
    text = text.strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    # Loại bỏ dấu câu thừa ở cuối
    text = re.sub(r'[\.,;:!?]+$', '', text).strip()
    return text


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    """Đọc dữ liệu và chỉ giữ lại các mẫu Thái Việt <-> Tiếng Việt (loại bỏ Latin)."""
    samples = []
    ignored_latin = 0
    with open(dataset_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            convs = item.get("conversations", [])
            if len(convs) >= 3:
                system_msg = convs[0]["value"]
                user_msg = convs[1]["value"]
                gpt_msg = convs[2]["value"]
            elif len(convs) == 2:
                system_msg = ""
                user_msg = convs[0]["value"]
                gpt_msg = convs[1]["value"]
            else:
                continue

            cat = classify_prompt(user_msg, gpt_msg)
            if cat is None:
                ignored_latin += 1
                continue

            samples.append({
                "id": idx,
                "system": system_msg,
                "prompt": user_msg,
                "reference": gpt_msg.strip(),
                "category": cat
            })

    print(f"    -> Đã nạp {len(samples):,} mẫu thuần Thái Việt ↔ Tiếng Việt (Bỏ qua {ignored_latin:,} mẫu liên quan đến Latin)")
    return samples


def stratified_sample(samples: List[Dict[str, Any]], n_samples: int, seed: int = 42) -> List[Dict[str, Any]]:
    """Lấy mẫu ngẫu nhiên có phân tầng theo tỷ lệ 2 nhóm."""
    if n_samples >= len(samples):
        return samples

    by_cat = defaultdict(list)
    for s in samples:
        by_cat[s["category"]].append(s)

    rng = random.Random(seed)
    selected = []
    total = len(samples)

    for cat, cat_samples in by_cat.items():
        cat_ratio = len(cat_samples) / total
        k = max(1, round(n_samples * cat_ratio))
        selected.extend(rng.sample(cat_samples, min(k, len(cat_samples))))

    if len(selected) > n_samples:
        rng.shuffle(selected)
        selected = selected[:n_samples]
    elif len(selected) < n_samples:
        remaining = [s for s in samples if s not in set(id(x) for x in selected)]
        diff = n_samples - len(selected)
        selected.extend(rng.sample(remaining, min(diff, len(remaining))))

    return selected


class OllamaClient:
    def __init__(self, model_name: str, api_url: str = DEFAULT_OLLAMA_URL, timeout: int = 30):
        self.model_name = model_name
        self.api_url = api_url
        self.timeout = timeout

    def predict(self, prompt: str, system: Optional[str] = None) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 1.0,
                "num_predict": 128
            }
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.api_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    return res_json.get("response", "").strip()
            except Exception as e:
                if attempt == 2:
                    return f"[ERROR: {str(e)}]"
                time.sleep(1.0)
        return ""


def compute_metrics(hypotheses: List[str], references: List[str]) -> Dict[str, float]:
    """Tính toán tất cả các chỉ số: BLEU, chrF, chrF++, Exact Match, Contains."""
    if not hypotheses or not references:
        return {
            "count": 0,
            "bleu_standard": 0.0,
            "bleu_add_k": 0.0,
            "sentence_bleu": 0.0,
            "chrf": 0.0,
            "chrf_plus_plus": 0.0,
            "exact_match": 0.0,
            "contains_match": 0.0
        }

    n = len(hypotheses)
    refs_list = [[r for r in references]]

    # 1. SacreBLEU (Corpus BLEU chuẩn & có smoothing add-k cho câu ngắn/từ vựng)
    bleu_std = sacrebleu.corpus_bleu(hypotheses, refs_list).score
    bleu_smoothed = sacrebleu.corpus_bleu(hypotheses, refs_list, smooth_method="add-k").score

    # 2. Sentence BLEU trung bình (exp smoothed)
    sent_bleus = [
        sacrebleu.sentence_bleu(h, [r], smooth_method="exp").score
        for h, r in zip(hypotheses, references)
    ]
    avg_sent_bleu = sum(sent_bleus) / n

    # 3. chrF & chrF++ (Đặc biệt tối ưu cho chữ Thái Việt Unicode do so khớp ký tự n-gram)
    chrf = sacrebleu.corpus_chrf(hypotheses, refs_list).score
    chrf_pp = sacrebleu.corpus_chrf(hypotheses, refs_list, word_order=2).score

    # 4. Exact Match và Contains Match
    em_count = 0
    contains_count = 0
    for h, r in zip(hypotheses, references):
        h_clean = clean_text(h).lower()
        r_clean = clean_text(r).lower()
        if h_clean == r_clean:
            em_count += 1
        if r_clean in h_clean or h_clean in r_clean:
            contains_count += 1

    return {
        "count": n,
        "bleu_standard": round(bleu_std, 2),
        "bleu_add_k": round(bleu_smoothed, 2),
        "sentence_bleu": round(avg_sent_bleu, 2),
        "chrf": round(chrf, 2),
        "chrf_plus_plus": round(chrf_pp, 2),
        "exact_match": round((em_count / n) * 100, 2),
        "contains_match": round((contains_count / n) * 100, 2),
    }


def evaluate(
    dataset_path: Path,
    model_name: str,
    num_samples: Optional[int] = None,
    workers: int = 12,
    seed: int = 42,
    output_file: Optional[Path] = None
) -> Dict[str, Any]:
    print(f"\n[+] Đang nạp dữ liệu kiểm thử từ: {dataset_path}")
    all_samples = load_dataset(dataset_path)
    total_valid = len(all_samples)

    if num_samples and num_samples < total_valid:
        samples = stratified_sample(all_samples, num_samples, seed=seed)
        print(f"    -> Đang đánh giá trên mẫu phân tầng: {len(samples):,} câu")
    else:
        samples = all_samples
        print(f"    -> Đang đánh giá trên TOÀN BỘ {len(samples):,} câu thuần Thái Việt ↔ Tiếng Việt")

    # Thống kê phân bố
    counts = defaultdict(int)
    for s in samples:
        counts[s["category"]] += 1
    for cat, cnt in counts.items():
        print(f"       • {cat}: {cnt:,} mẫu ({cnt/len(samples)*100:.1f}%)")

    client = OllamaClient(model_name=model_name)

    # Kiểm tra kết nối
    print(f"\n[+] Kiểm tra model Ollama: '{model_name}'...")
    ping_resp = client.predict("test")
    if ping_resp.startswith("[ERROR:"):
        print(f"[-] LỖI: Không thể kết nối tới Ollama hoặc model '{model_name}'.")
        print(f"    Chi tiết: {ping_resp}")
        sys.exit(1)
    print(f"[OK] Model '{model_name}' đang sẵn sàng trên GPU!")

    # Chạy đa luồng
    print(f"\n[+] Đang sinh câu trả lời với {workers} workers...")
    results = [None] * len(samples)
    start_time = time.time()

    def process_item(idx_item):
        idx, item = idx_item
        pred = client.predict(item["prompt"], system=item["system"])
        return idx, pred

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_item, (i, s)): i for i, s in enumerate(samples)}
        for future in tqdm(as_completed(futures), total=len(samples), desc="Inference"):
            idx, pred = future.result()
            results[idx] = pred

    elapsed_time = time.time() - start_time
    speed = len(samples) / elapsed_time if elapsed_time > 0 else 0
    print(f"[OK] Đã xử lý {len(samples):,} câu trong {elapsed_time:.1f}s (Tốc độ: {speed:.1f} mẫu/giây)")

    # Phân loại và tính toán chỉ số
    predictions_data = []
    cat_hypotheses = defaultdict(list)
    cat_references = defaultdict(list)
    all_hypotheses = []
    all_references = []

    for item, pred in zip(samples, results):
        cat = item["category"]
        ref = item["reference"]
        cleaned_pred = clean_text(pred)

        all_hypotheses.append(cleaned_pred)
        all_references.append(ref)
        cat_hypotheses[cat].append(cleaned_pred)
        cat_references[cat].append(ref)

        predictions_data.append({
            "id": item["id"],
            "category": cat,
            "prompt": item["prompt"],
            "reference": ref,
            "prediction": pred,
            "cleaned_prediction": cleaned_pred
        })

    print("\n[+] Đang tính toán các chỉ số BLEU và chrF...")
    overall_metrics = compute_metrics(all_hypotheses, all_references)

    category_metrics = {}
    for cat in ["Thái Việt -> Tiếng Việt", "Tiếng Việt -> Thái Việt"]:
        if cat in cat_hypotheses:
            category_metrics[cat] = compute_metrics(cat_hypotheses[cat], cat_references[cat])

    # Bảng kết quả tổng hợp
    table_data = []
    rows = [("Tổng thể (Overall)", overall_metrics)]
    for cat, met in category_metrics.items():
        rows.append((cat, met))

    for name, m in rows:
        table_data.append([
            name,
            f"{m['count']:,}",
            f"{m['bleu_add_k']:.2f}",
            f"{m['sentence_bleu']:.2f}",
            f"{m['chrf']:.2f}",
            f"{m['chrf_plus_plus']:.2f}",
            f"{m['exact_match']:.2f}%",
            f"{m['contains_match']:.2f}%"
        ])

    headers = [
        "Tác vụ",
        "Số mẫu",
        "BLEU (smoothed)",
        "Sent-BLEU",
        "chrF",
        "chrF++",
        "Khớp tuyệt đối (EM)",
        "Chứa đáp án"
    ]

    summary_table = tabulate(table_data, headers=headers, tablefmt="github")
    print("\n" + "=" * 95)
    print(" KẾT QUẢ ĐÁNH GIÁ BLEU & chrF (CHỈ THÁI VIỆT VÀ TIẾNG VIỆT)")
    print("=" * 95)
    print(summary_table)
    print("=" * 95)

    # Hiển thị vài ví dụ minh họa
    print("\n--- VÍ DỤ DỰ ĐOÁN THỰC TẾ ---")
    sample_preview = predictions_data[:6]
    for idx, p in enumerate(sample_preview):
        match_icon = "✓" if clean_text(p["prediction"]).lower() == clean_text(p["reference"]).lower() else "✗"
        print(f"[{match_icon}] [{p['category']}]")
        print(f"    Q: {p['prompt']}")
        print(f"    Đáp án (Ground Truth): {p['reference']}")
        print(f"    Mô hình trả lời      : {p['prediction']}")
        print("-" * 50)

    # Lưu file kết quả
    out_payload = {
        "model": model_name,
        "dataset": str(dataset_path),
        "total_test_samples": total_valid,
        "evaluated_samples": len(samples),
        "elapsed_seconds": round(elapsed_time, 2),
        "samples_per_second": round(speed, 2),
        "overall_metrics": overall_metrics,
        "category_metrics": category_metrics,
        "table_markdown": summary_table,
        "sample_predictions": predictions_data[:50]
    }

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(out_payload, f, ensure_ascii=False, indent=2)
        print(f"\n[+] Đã lưu kết quả chi tiết tại: {output_file}")

    return out_payload


def main():
    parser = argparse.ArgumentParser(description="Tính toán BLEU và chrF trên tập dữ liệu kiểm thử (Thái Việt - Tiếng Việt)")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Đường dẫn file val.jsonl")
    parser.add_argument("--model", type=str, default=DEFAULT_OLLAMA_MODEL, help="Tên model trong Ollama (mặc định: taiviet-bot)")
    parser.add_argument("--samples", "-n", type=int, default=1000, help="Số lượng mẫu đánh giá (mặc định: 1000)")
    parser.add_argument("--all", action="store_true", help="Đánh giá trên toàn bộ 26.811 mẫu Thái-Việt")
    parser.add_argument("--workers", "-w", type=int, default=12, help="Số luồng gửi request song song (mặc định: 12)")
    parser.add_argument("--seed", type=int, default=42, help="Seed ngẫu nhiên")
    parser.add_argument("--output", "-o", type=Path, default=HERE / "eval_bleu_chrf_results.json", help="File lưu kết quả json")
    parser.add_argument("--show", action="store_true", help="In ngay kết quả đã lưu trước đó ra terminal mà không cần chạy lại")
    args = parser.parse_args()

    if args.show:
        if not args.output.exists():
            print(f"[-] Không tìm thấy file kết quả tại: {args.output}")
            sys.exit(1)
        with open(args.output, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("\n" + "=" * 95)
        print(" KẾT QUẢ ĐÁNH GIÁ BLEU & chrF (CHỈ THÁI VIỆT VÀ TIẾNG VIỆT)")
        print("=" * 95)
        print(data["table_markdown"])
        print("=" * 95)
        print("\n--- VÍ DỤ DỰ ĐOÁN THỰC TẾ ---")
        for p in data.get("sample_predictions", [])[:6]:
            match_icon = "✓" if clean_text(p["prediction"]).lower() == clean_text(p["reference"]).lower() else "✗"
            print(f"[{match_icon}] [{p['category']}]")
            print(f"    Q: {p['prompt']}")
            print(f"    Đáp án (Ground Truth): {p['reference']}")
            print(f"    Mô hình trả lời      : {p['prediction']}")
            print("-" * 50)
        print(f"\n[+] Kết quả lấy từ: {args.output} (Tổng số mẫu đã đánh giá: {data.get('evaluated_samples'):,})")
        return

    num_samples = None if args.all else args.samples

    evaluate(
        dataset_path=args.dataset,
        model_name=args.model,
        num_samples=num_samples,
        workers=args.workers,
        seed=args.seed,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
