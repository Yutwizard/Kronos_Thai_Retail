#!/bin/bash
# Setup Kronos-TH for local CPU testing — Phase 1
# Run: bash scripts/setup_cpu.sh

set -e

echo "=== Kronos-TH Phase 1 Setup (CPU) ==="

echo "[1/5] Installing PyTorch CPU..."
pip install torch --index-url https://download.pytorch.org/whl/cpu

echo "[2/5] Installing huggingface_hub..."
pip install "huggingface_hub>=0.20"

echo "[3/5] Cloning Kronos model repo..."
git clone --depth 1 https://github.com/shiyu-coder/Kronos.git kronos_repo 2>/dev/null || echo "kronos_repo already exists, skipping clone"
pip install -r kronos_repo/requirements.txt

echo "[4/5] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

echo "[5/5] Installing remaining deps..."
pip install transformers einops scikit-learn jupyterlab

echo ""
echo "=== Setup complete ==="
echo "Next: download data with python scripts/download_data.py"
echo "Then: python scripts/run_forecast_demo.py"
