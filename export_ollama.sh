#!/bin/bash
# export_ollama.sh — Merge LoRA và đóng gói thành GGUF cho Ollama
set -e

cd "$(dirname "$0")"

echo "============================================================"
echo " 1. Merge LoRA vào Base Model (Qwen2.5-1.5B)"
echo "============================================================"
cd LLaMA-Factory
../.venv/bin/llamafactory-cli export examples/train_qlora/qwen25_taiviet_export.yaml
cd ..

echo "============================================================"
echo " 2. Clone llama.cpp để convert sang định dạng GGUF"
echo "============================================================"
if [ ! -d "llama.cpp" ]; then
    git clone https://github.com/ggerganov/llama.cpp.git
    cd llama.cpp
    uv pip install --index-strategy unsafe-best-match -r requirements.txt
    cd ..
fi

echo "============================================================"
echo " 3. Convert sang GGUF (f16)"
echo "============================================================"
.venv/bin/python3 llama.cpp/convert_hf_to_gguf.py LLaMA-Factory/saves/qwen25-1.5b-taiviet/export --outfile taiviet-chatbot-1.5b.gguf --outtype f16

echo "============================================================"
echo " 4. Tạo Modelfile và Import vào Ollama"
echo "============================================================"
cat << 'EOF' > Modelfile
FROM ./taiviet-chatbot-1.5b.gguf
SYSTEM "Bạn là trợ lý thông thạo tiếng Việt và tiếng Thái (chữ Thái Việt – Tai Viet, Unicode U+AA80–U+AADF). Hãy trả lời chính xác và ngắn gọn."
TEMPLATE """<|im_start|>system
{{ .System }}<|im_end|>
<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
"""
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
EOF

if command -v ollama >/dev/null 2>&1; then
    ollama create taiviet-bot -f Modelfile
    echo "============================================================"
    echo " HOÀN TẤT! Bạn có thể chạy bot bằng lệnh:"
    echo " ollama run taiviet-bot"
    echo "============================================================"
else
    echo "[!] Không tìm thấy lệnh 'ollama'. Vui lòng cài Ollama trước."
    echo "Sau đó tự chạy: ollama create taiviet-bot -f Modelfile"
fi
