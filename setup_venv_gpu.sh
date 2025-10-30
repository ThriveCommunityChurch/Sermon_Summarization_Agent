#!/bin/bash
# ============================================================================
# Setup Python Virtual Environment with GPU Support (CUDA 11.8)
# ============================================================================
# This script creates a Python virtual environment and installs all
# dependencies with CUDA-enabled PyTorch for GPU acceleration.
# ============================================================================

set -e  # Exit on error

echo ""
echo "============================================================================"
echo "Setting up Python Virtual Environment with GPU Support"
echo "============================================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ from your package manager"
    exit 1
fi

echo "[1/6] Checking Python version..."
python3 --version

# Check if venv exists
if [ -d "venv" ]; then
    echo ""
    echo "WARNING: Virtual environment already exists at 'venv/'"
    echo ""
    read -p "Do you want to recreate it? (y/N): " RECREATE
    if [[ ! "$RECREATE" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Skipping venv creation. Using existing venv..."
    else
        echo ""
        echo "Removing existing venv..."
        rm -rf venv
        echo ""
        echo "[2/6] Creating virtual environment..."
        python3 -m venv venv
        echo "Virtual environment created successfully!"
    fi
else
    echo ""
    echo "[2/6] Creating virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created successfully!"
fi

echo ""
echo "[3/6] Activating virtual environment..."
source venv/bin/activate

echo ""
echo "[4/6] Upgrading pip..."
python -m pip install --upgrade pip || echo "WARNING: Failed to upgrade pip, continuing anyway..."

echo ""
echo "[5/6] Installing CUDA-enabled PyTorch (this may take a few minutes)..."
echo "Installing: torch, torchvision, torchaudio with CUDA 11.8 support"
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
echo "PyTorch with CUDA support installed successfully!"

echo ""
echo "[6/6] Installing other dependencies from requirements.txt..."
pip install openai-whisper>=20250625
pip install langchain-openai>=0.3.30
pip install langgraph>=0.6.5
pip install langchain-core>=0.3.74
pip install tiktoken>=0.7.0
pip install python-dotenv>=1.0.0
pip install numpy>=2.2.6
pip install tqdm>=4.67.1
pip install librosa>=0.10.0
pip install pytest>=7.0.0
echo "All dependencies installed successfully!"

echo ""
echo "============================================================================"
echo "Verifying GPU Support"
echo "============================================================================"
echo ""
python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}'); print(f'GPU Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"No GPU detected\"}')"

echo ""
echo "============================================================================"
echo "Setup Complete!"
echo "============================================================================"
echo ""
echo "Virtual environment is ready at: venv/"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate when done, run:"
echo "  deactivate"
echo ""
echo "IMPORTANT: Make sure FFmpeg is installed on your system"
echo "  macOS: brew install ffmpeg"
echo "  Linux: apt install ffmpeg  (or yum install ffmpeg)"
echo "  Verify: ffmpeg -version"
echo ""
echo "You can now run the agent with:"
echo "  python agent.py --file path/to/sermon.mp4"
echo ""

