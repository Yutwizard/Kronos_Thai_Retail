#!/bin/bash
# Setup Kronos-TH for GPU testing — Phase 2 (Linux)
# Run: bash scripts/setup_gpu.sh
set -e

echo "=== Kronos-TH Phase 2 Setup (GPU - Linux) ==="

echo "[1/5] Installing PyTorch with CUDA 12.1..."
pip install torch --index-url https://download.pytorch.org/whl/cu121

echo "[2/5] Installing huggingface_hub..."
pip install "huggingface_hub>=0.20"

echo "[3/5] Cloning Kronos model repo..."
git clone --depth 1 https://github.com/shiyu-coder/Kronos.git kronos_repo 2>/dev/null || echo "kronos_repo already exists, skipping clone"
pip install -r kronos_repo/requirements.txt

echo "[4/5] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

echo "[5/5] Verifying CUDA and installing remaining deps..."
pip install transformers einops scikit-learn jupyterlab
python -c "
import torch
if torch.cuda.is_available():
    print(f'CUDA OK - {torch.cuda.get_device_name(0)}')
else:
    print('WARNING: CUDA not available. Will fall back to CPU.')
    print('If you expect a GPU, check nvidia-smi and driver installation.')
"

echo ""
echo "=== Setup complete ==="
echo "Next: python scripts/download_data.py"
echo "Then: python scripts/run_backtest.py"
