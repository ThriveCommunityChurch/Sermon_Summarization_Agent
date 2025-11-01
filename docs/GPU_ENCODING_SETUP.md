# GPU-Accelerated Video Encoding Setup Guide

This guide explains how to set up and use GPU-accelerated video encoding for the sermon clip generation feature.

## Overview

The video clip generation node now supports NVIDIA GPU-accelerated encoding using CUDA and NVENC (NVIDIA Video Encoder). This can provide **3-5x faster encoding** compared to CPU-based encoding while maintaining comparable quality.

### How It Works

The implementation uses a hybrid GPU/CPU approach:
1. **Decode with CUDA (GPU):** Hardware-accelerated video decoding for faster input reading
2. **Filter on CPU:** Video filters (trim, setpts, fade) operate on CPU frames
3. **Encode with NVENC (GPU):** Hardware-accelerated h264_nvenc encoding

This approach is necessary because FFMPEG's video filters (fade, trim, etc.) don't support CUDA frames directly. The GPU is used for the most intensive operations (decode/encode) while CPU handles the filtering.

### Performance Comparison

| Method | Encoding Speed | 10-Minute Video | Quality |
|--------|---------------|-----------------|---------|
| CPU (libx264) | ~1x realtime | ~10 minutes | High (CRF 23) |
| GPU (h264_nvenc) | ~3-5x realtime | ~2-3 minutes | High (CQ 23) |

---

## System Requirements

### Hardware Requirements

- **NVIDIA GPU** with NVENC support:
  - GTX 900 series or newer (Maxwell architecture+)
  - GTX 1050, 1060, 1070, 1080, 1650, 1660
  - RTX 2060, 2070, 2080, 3060, 3070, 3080, 3090, 4060, 4070, 4080, 4090
  - Quadro, Tesla, or other professional GPUs
  - Check compatibility: https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix

### Software Requirements

1. **NVIDIA Drivers**
   - Latest NVIDIA drivers installed
   - `nvidia-smi` command must be available
   - Download: https://www.nvidia.com/Download/index.aspx

2. **FFMPEG with CUDA/NVENC Support**
   - FFMPEG must be compiled with `--enable-cuda` and `--enable-nvenc`
   - See installation instructions below

3. **CUDA Toolkit** (Optional but Recommended)
   - CUDA 11.0 or newer
   - Download: https://developer.nvidia.com/cuda-downloads
   - Not strictly required, but improves performance

---

## Installation

### Windows

#### Option 1: Pre-built FFMPEG with CUDA (Recommended)

1. **Download FFMPEG with CUDA support:**
   ```powershell
   # Download from BtbN's builds (includes CUDA/NVENC)
   # Visit: https://github.com/BtbN/FFmpeg-Builds/releases
   # Download: ffmpeg-master-latest-win64-gpl-shared.zip
   ```

2. **Extract and add to PATH:**
   ```powershell
   # Extract to C:\ffmpeg
   # Add C:\ffmpeg\bin to system PATH
   ```

3. **Verify CUDA support:**
   ```powershell
   ffmpeg -hide_banner -encoders | findstr nvenc
   ```
   
   Expected output:
   ```
   V..... h264_nvenc           NVIDIA NVENC H.264 encoder
   V..... hevc_nvenc           NVIDIA NVENC hevc encoder
   ```

#### Option 2: Install via Chocolatey

```powershell
# Install Chocolatey if not already installed
# Then install FFMPEG
choco install ffmpeg-full
```

### Linux (Ubuntu/Debian)

#### Option 1: Build from Source with CUDA

```bash
# Install dependencies
sudo apt update
sudo apt install -y build-essential yasm cmake libtool libc6 libc6-dev \
  unzip wget libnuma1 libnuma-dev git

# Install NVIDIA drivers and CUDA toolkit
sudo apt install -y nvidia-driver-535 nvidia-cuda-toolkit

# Clone FFMPEG
git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg
cd ffmpeg

# Configure with CUDA/NVENC
./configure --enable-nonfree --enable-cuda-nvcc --enable-libnpp \
  --extra-cflags=-I/usr/local/cuda/include \
  --extra-ldflags=-L/usr/local/cuda/lib64 \
  --enable-nvenc

# Build and install
make -j$(nproc)
sudo make install
```

#### Option 2: Use NVIDIA's FFMPEG Build

```bash
# Download NVIDIA's pre-built FFMPEG
wget https://developer.download.nvidia.com/compute/redist/ffmpeg/linux-x86_64/ffmpeg-4.4-linux-x86_64.tar.xz
tar -xf ffmpeg-4.4-linux-x86_64.tar.xz
sudo cp ffmpeg-4.4-linux-x86_64/ffmpeg /usr/local/bin/
```

### Verify Installation

```bash
# Check NVIDIA GPU
nvidia-smi

# Check FFMPEG CUDA support
ffmpeg -hide_banner -encoders | grep nvenc

# Test GPU encoding
ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc -preset p4 -cq 23 output.mp4
```

---

## Configuration

### Environment Variables

Set these in your `.env` file or system environment:

```bash
# Enable/disable GPU encoding (default: true)
ENABLE_GPU_ENCODING=true

# GPU encoder preset: p1 (fastest) to p7 (slowest/best quality)
# p1: Fastest, lowest quality
# p4: Balanced (recommended)
# p7: Slowest, highest quality
GPU_ENCODER_PRESET=p4

# CUDA device index (for multi-GPU systems)
GPU_DEVICE_INDEX=0
```

### Preset Comparison

| Preset | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| p1 | Fastest | Lower | Quick previews, drafts |
| p2 | Very Fast | Medium-Low | Fast processing |
| p3 | Fast | Medium | General use |
| **p4** | **Balanced** | **Good** | **Recommended default** |
| p5 | Slow | High | High-quality output |
| p6 | Slower | Very High | Professional quality |
| p7 | Slowest | Highest | Maximum quality |

---

## Usage

### Automatic Detection

The system automatically detects GPU capability:

1. Checks if NVIDIA GPU is available (`nvidia-smi`)
2. Checks if FFMPEG has CUDA/NVENC support
3. Uses GPU encoding if both are available
4. Falls back to CPU encoding if GPU unavailable or fails

### Manual Control

```bash
# Force CPU encoding (disable GPU)
export ENABLE_GPU_ENCODING=false

# Use fastest GPU preset
export GPU_ENCODER_PRESET=p1

# Use highest quality GPU preset
export GPU_ENCODER_PRESET=p7

# Select specific GPU (multi-GPU systems)
export GPU_DEVICE_INDEX=1
```

### Running the Agent

```bash
# Run with GPU encoding (automatic)
python agent.py --file sermon.mp4

# Check metadata for GPU info
cat sermon_Summary_metadata.json | grep -A 5 "gpu_info"
```

---

## Troubleshooting

### GPU Not Detected

**Problem:** "NVIDIA GPU not detected"

**Solutions:**
1. Verify NVIDIA drivers are installed:
   ```bash
   nvidia-smi
   ```
2. Update NVIDIA drivers to latest version
3. Restart system after driver installation

### FFMPEG CUDA Support Missing

**Problem:** "FFMPEG does not have CUDA/NVENC support"

**Solutions:**
1. Verify FFMPEG has NVENC:
   ```bash
   ffmpeg -hide_banner -encoders | grep nvenc
   ```
2. Reinstall FFMPEG with CUDA support (see Installation section)
3. Use pre-built FFMPEG from BtbN (Windows) or NVIDIA (Linux)

### GPU Encoding Fails

**Problem:** GPU encoding starts but fails during processing

**Solutions:**
1. Check GPU memory usage:
   ```bash
   nvidia-smi
   ```
2. Reduce GPU load (close other GPU applications)
3. System will automatically fall back to CPU encoding
4. Check FFMPEG error logs for details

### Format Conversion Error

**Problem:** "Impossible to convert between the formats supported by the filter... src: cuda dst: yuv420p..."

**Cause:** This error occurs when FFMPEG tries to use CUDA frames with filters that don't support GPU processing.

**Solution:** This has been fixed in the implementation. The code now uses:
- `-hwaccel cuda` for GPU-accelerated decoding
- CPU-based filtering (trim, setpts, fade)
- `h264_nvenc` for GPU-accelerated encoding

If you still see this error, ensure you're using the latest version of the code.

### Quality Issues

**Problem:** GPU-encoded video has lower quality than CPU

**Solutions:**
1. Increase GPU preset (p4 → p5 → p6 → p7)
2. Adjust CQ value (lower = better quality):
   ```bash
   # Edit nodes/clip_generation_node.py
   # Change "-cq", "23" to "-cq", "20"
   ```
3. Compare file sizes (GPU should be similar to CPU)

### Multi-GPU Systems

**Problem:** Wrong GPU being used

**Solution:**
```bash
# List available GPUs
nvidia-smi -L

# Select specific GPU (0, 1, 2, etc.)
export GPU_DEVICE_INDEX=1
```

---

## Performance Optimization

### Best Practices

1. **Use Balanced Preset (p4):**
   - Good speed/quality tradeoff
   - Suitable for most use cases

2. **Monitor GPU Usage:**
   ```bash
   # Watch GPU usage in real-time
   watch -n 1 nvidia-smi
   ```

3. **Batch Processing:**
   - Process multiple videos sequentially
   - GPU stays warm, better performance

4. **Close Other GPU Applications:**
   - Close games, 3D applications
   - Free up GPU memory and compute

### Expected Performance

| Video Length | CPU Time (libx264) | GPU Time (h264_nvenc) | Speedup |
|--------------|-------------------|----------------------|---------|
| 5 minutes | ~5 minutes | ~1-2 minutes | 3-5x |
| 10 minutes | ~10 minutes | ~2-3 minutes | 3-5x |
| 30 minutes | ~30 minutes | ~6-10 minutes | 3-5x |
| 60 minutes | ~60 minutes | ~12-20 minutes | 3-5x |

*Times are approximate and depend on hardware, video complexity, and settings.*

---

## Metadata Output

The generated metadata JSON includes GPU encoding information:

```json
{
  "configuration": {
    "gpu_encoding_enabled": true,
    "gpu_encoding_attempted": true,
    "gpu_fallback_occurred": false,
    "gpu_encoder_preset": "p4"
  },
  "gpu_info": {
    "gpu_available": true,
    "ffmpeg_cuda_support": true,
    "encoding_method": "GPU (h264_nvenc)",
    "status": "GPU encoding enabled (NVIDIA GPU + FFMPEG CUDA support detected)"
  }
}
```

---

## FAQ

**Q: Will this work on AMD or Intel GPUs?**  
A: No, this implementation uses NVIDIA NVENC. AMD (VCE/AMF) and Intel (Quick Sync) require different encoders.

**Q: Does GPU encoding reduce quality?**  
A: No, at comparable settings (CQ 23 vs CRF 23), quality is very similar. GPU encoding may have slightly different compression characteristics but is generally imperceptible.

**Q: Can I use GPU for decoding too?**  
A: Yes, the implementation uses `-hwaccel cuda` for hardware-accelerated decoding, which can further improve performance.

**Q: What if I don't have an NVIDIA GPU?**  
A: The system automatically falls back to CPU encoding (libx264). No changes needed.

**Q: Does this work in Docker containers?**  
A: Yes, but requires NVIDIA Container Toolkit. See: https://github.com/NVIDIA/nvidia-docker

**Q: How much GPU memory is needed?**  
A: Typically 1-2 GB for 1080p video. 4K video may require 3-4 GB.

---

## Additional Resources

- **NVIDIA NVENC Documentation:** https://developer.nvidia.com/nvidia-video-codec-sdk
- **FFMPEG NVENC Guide:** https://docs.nvidia.com/video-technologies/video-codec-sdk/ffmpeg-with-nvidia-gpu/
- **GPU Support Matrix:** https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix
- **FFMPEG Hardware Acceleration:** https://trac.ffmpeg.org/wiki/HWAccelIntro

---

## Support

If you encounter issues:

1. Check this guide's Troubleshooting section
2. Verify system requirements are met
3. Check FFMPEG and NVIDIA driver versions
4. Review error logs in console output
5. System will automatically fall back to CPU if GPU fails

