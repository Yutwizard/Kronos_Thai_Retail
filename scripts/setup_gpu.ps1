# Setup Kronos-TH for GPU testing — Phase 2 (Windows)
# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_gpu.ps1

Write-Host "=== Kronos-TH Phase 2 Setup (GPU - Windows) ==="

Write-Host "[1/5] Installing PyTorch with CUDA 12.1..."
pip install torch --index-url https://download.pytorch.org/whl/cu121

Write-Host "[2/5] Installing huggingface_hub..."
pip install "huggingface_hub>=0.20"

Write-Host "[3/5] Cloning Kronos model repo..."
if (-not (Test-Path kronos_repo)) { git clone --depth 1 https://github.com/shiyu-coder/Kronos.git kronos_repo } else { Write-Host "kronos_repo already exists, skipping clone" }
pip install -r kronos_repo/requirements.txt 2>$null

Write-Host "[4/5] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

Write-Host "[5/5] Verifying CUDA and installing remaining deps..."
pip install transformers einops scikit-learn jupyterlab
python -c @"
import torch
if torch.cuda.is_available():
    print(f'CUDA OK - {torch.cuda.get_device_name(0)}')
else:
    print('WARNING: CUDA not available. Will fall back to CPU.')
    print('If you expect a GPU, check nvidia-smi and driver installation.')
"@

Write-Host ""
Write-Host "=== Setup complete ==="
