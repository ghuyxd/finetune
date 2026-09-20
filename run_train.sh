#!/bin/bash
# run_train.sh — Chạy QLoRA finetune Qwen2.5-1.5B-Instruct cho task Việt-Thái
#
# Dùng:
#   cd /home/ghuyxd/finetune/LLaMA-Factory
#   bash ../run_train.sh
#
# Theo dõi:
#   tail -f saves/qwen25-1.5b-taiviet/lora/sft/trainer_log.jsonl
#   tensorboard --logdir saves/qwen25-1.5b-taiviet/lora/sft/

set -e
cd "$(dirname "$0")/LLaMA-Factory"

VENV="../.venv"
PYTHON="$VENV/bin/python"
CONFIG="examples/train_qlora/qwen25_taiviet_qlora.yaml"

echo "============================================================"
echo "  QLoRA Finetune: Qwen2.5-1.5B-Instruct → Tai Viet Chatbot"
echo "============================================================"
echo "  Config : $CONFIG"
echo "  GPU    : $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "  Python : $($PYTHON --version)"
echo ""

# Kiểm tra dataset đã được copy
if [ ! -f "data/taiviet/train.jsonl" ]; then
    echo "  [!] Dataset chưa có, copy từ ../dataset ..."
    mkdir -p data/taiviet
    cp ../dataset/train.jsonl data/taiviet/
    cp ../dataset/val.jsonl   data/taiviet/
    echo "  [OK] Đã copy dataset"
fi

echo "  Train samples: $(wc -l < data/taiviet/train.jsonl)"
echo "  Val   samples: $(wc -l < data/taiviet/val.jsonl)"
echo ""
echo "  Bắt đầu train lúc: $(date)"
echo "============================================================"

mkdir -p saves
LOG_FILE="saves/train_$(date +%Y%m%d_%H%M).log"
$VENV/bin/llamafactory-cli train "$CONFIG" 2>&1 | tee "$LOG_FILE"

echo ""
echo "============================================================"
echo "  Hoàn thành lúc: $(date)"
echo "  Model lưu tại: saves/qwen25-1.5b-taiviet/lora/sft/"
echo "============================================================"
