@echo off
REM ============================================================================
REM Setup Python Virtual Environment with GPU Support (CUDA 11.8)
REM ============================================================================
REM This script creates a Python virtual environment and installs all
REM dependencies with CUDA-enabled PyTorch for GPU acceleration.
REM ============================================================================

echo.
echo ============================================================================
echo Setting up Python Virtual Environment with GPU Support
echo ============================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/6] Checking Python version...
python --version

REM Check if venv exists
if exist "venv\" (
    echo.
    echo WARNING: Virtual environment already exists at 'venv\'
    echo.
    set /p RECREATE="Do you want to recreate it? (y/N): "
    if /i not "%RECREATE%"=="y" (
        echo.
        echo Skipping venv creation. Using existing venv...
        goto :activate_venv
    )
    echo.
    echo Removing existing venv...
    rmdir /s /q venv
)

echo.
echo [2/6] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created successfully!

:activate_venv
echo.
echo [3/6] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo.
echo [4/6] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo WARNING: Failed to upgrade pip, continuing anyway...
)

echo.
echo [5/6] Installing CUDA-enabled PyTorch (this may take a few minutes)...
echo Installing: torch, torchvision, torchaudio with CUDA 11.8 support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
if errorlevel 1 (
    echo ERROR: Failed to install CUDA-enabled PyTorch
    pause
    exit /b 1
)
echo PyTorch with CUDA support installed successfully!

echo.
echo [6/6] Installing other dependencies from requirements.txt...
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
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo All dependencies installed successfully!

echo.
echo ============================================================================
echo Verifying GPU Support
echo ============================================================================
echo.
python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}'); print(f'GPU Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"No GPU detected\"}')"

echo.
echo ============================================================================
echo Setup Complete!
echo ============================================================================
echo.
echo Virtual environment is ready at: venv\
echo.
echo To activate the virtual environment in the future, run:
echo   venv\Scripts\activate
echo.
echo To deactivate when done, run:
echo   deactivate
echo.
echo IMPORTANT: Make sure FFmpeg is installed on your system
echo   Windows: choco install ffmpeg  (or download from ffmpeg.org)
echo   Verify: ffmpeg -version
echo.
echo You can now run the agent with:
echo   python agent.py --file path\to\sermon.mp4
echo.
pause

