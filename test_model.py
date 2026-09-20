#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_model.py — Test chatbot Thái-Việt sau khi finetune

Dùng:
    # Test với adapter LoRA
    python3 test_model.py

    # Test model gốc (chưa finetune, để so sánh)
    python3 test_model.py --base
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
LORA_PATH = HERE / "LLaMA-Factory/saves/qwen25-1.5b-taiviet/lora/sft"
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

SYSTEM = (
    "Bạn là trợ lý thông thạo tiếng Việt và tiếng Thái (chữ Thái Việt – Tai Viet, "
    "Unicode U+AA80–U+AADF). Hãy trả lời chính xác và ngắn gọn."
)

TEST_CASES = [
    # (câu hỏi, đáp án mong đợi)
    ("Nghĩa tiếng Việt của \"ꪮꪱ\" là gì?",          "cô"),
    ("Dịch sang tiếng Thái: cha",                    "ꪮꪱ ꪛꪱ"),
    ("\"ꪣꪴ ꪣꪽ\" trong tiếng Thái nghĩa là gì?",    "đôi lứa"),
    ("Viết \"ngủ\" bằng chữ Thái Việt:",             None),   # tự do
    ("Dịch sang tiếng Việt: ꪶꪀꪀ ꪬꪱ",              "bẹn"),
    ("Cách viết \"nước\" bằng chữ Thái?",            None),   # tự do
]


def load_model(use_lora: bool):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch

    print(f"  Loading {'base' if not use_lora else 'finetuned'} model: {BASE_MODEL}")
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    if use_lora and LORA_PATH.exists():
        from peft import PeftModel
        print(f"  Loading LoRA adapter: {LORA_PATH}")
        model = PeftModel.from_pretrained(model, str(LORA_PATH))
        model = model.merge_and_unload()
        print("  LoRA merged OK")
    elif use_lora:
        print(f"  [WARN] LoRA không tìm thấy tại {LORA_PATH}, dùng base model")

    model.eval()
    return tok, model


def chat(tok, model, question: str, max_new_tokens: int = 128) -> str:
    import torch

    messages = [
        {"role": "system",    "content": SYSTEM},
        {"role": "user",      "content": question},
    ]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tok.eos_token_id,
        )
    answer_ids = out[0][inputs["input_ids"].shape[1]:]
    return tok.decode(answer_ids, skip_special_tokens=True).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", action="store_true", help="Test base model (không dùng LoRA)")
    ap.add_argument("--interactive", "-i", action="store_true", help="Chế độ chat tương tác")
    a = ap.parse_args()

    use_lora = not a.base
    print("=" * 60)
    print(f"Test {'BASE model' if not use_lora else 'FINETUNED model'}")
    print("=" * 60)

    tok, model = load_model(use_lora)

    if a.interactive:
        print("\nChế độ tương tác (gõ 'quit' để thoát):\n")
        while True:
            q = input("Bạn: ").strip()
            if q.lower() in ("quit", "exit", "q"):
                break
            ans = chat(tok, model, q)
            print(f"Bot: {ans}\n")
        return

    # Test tự động
    print(f"\n{'─'*60}")
    correct = 0
    total_with_expected = 0
    for q, expected in TEST_CASES:
        ans = chat(tok, model, q)
        if expected:
            total_with_expected += 1
            ok = expected.lower() in ans.lower() or ans.lower() in expected.lower()
            if ok:
                correct += 1
            mark = "✓" if ok else "✗"
            print(f"\n[{mark}] Q: {q}")
            print(f"     A: {ans}")
            print(f"     Expected: {expected}")
        else:
            print(f"\n[?] Q: {q}")
            print(f"    A: {ans}")

    print(f"\n{'─'*60}")
    if total_with_expected:
        print(f"Điểm: {correct}/{total_with_expected} = {correct/total_with_expected*100:.1f}%")


if __name__ == "__main__":
    main()
