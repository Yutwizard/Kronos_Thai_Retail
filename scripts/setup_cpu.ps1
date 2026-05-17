# Setup Kronos-TH for local CPU testing — Phase 1 (Windows)
# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_cpu.ps1

Write-Host "=== Kronos-TH Phase 1 Setup (CPU - Windows) ==="

Write-Host "[1/5] Installing PyTorch CPU..."
pip install torch --index-url https://download.pytorch.org/whl/cpu

Write-Host "[2/5] Installing huggingface_hub..."
pip install "huggingface_hub>=0.20"

Write-Host "[3/5] Cloning Kronos model repo..."
if (-not (Test-Path kronos_repo)) { git clone --depth 1 https://github.com/shiyu-coder/Kronos.git kronos_repo } else { Write-Host "kronos_repo already exists, skipping clone" }
pip install -r kronos_repo/requirements.txt 2>$null

Write-Host "[4/5] Installing project requirements..."
pip install -r requirements.txt
pip install -e .

Write-Host "[5/5] Installing remaining deps..."
pip install transformers einops scikit-learn jupyterlab

Write-Host ""
Write-Host "=== Setup complete ==="
Write-Host "Next: python scripts/download_data.py"
Write-Host "Then: python scripts/run_forecast_demo.py"
