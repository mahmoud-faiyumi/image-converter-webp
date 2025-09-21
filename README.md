# 🖼️ Image Converter to WebP

A powerful Python tool that converts images to WebP format and creates thumbnails with advanced features like progress tracking, file size statistics, and multiprocessing support.

## ✨ Features

- **🔄 Batch Conversion**: Convert multiple images to WebP format
- **🖼️ Thumbnail Generation**: Automatically create WebP thumbnails
- **📊 Progress Tracking**: Real-time progress bar and statistics
- **⚡ Multiprocessing**: Fast parallel processing with configurable workers
- **📈 File Size Analytics**: Detailed compression ratios and space savings
- **🎯 Smart Skipping**: Skip already converted files for faster re-runs
- **📝 Comprehensive Logging**: Detailed logs with file size information
- **🔧 Flexible Configuration**: JSON-based settings with environment variable overrides
- **🎨 Metadata Preservation**: Keep EXIF, ICC profiles, and alpha channels
- **🎬 Animated Support**: Handle GIF and animated WebP files

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the project
# Install required dependencies
pip install Pillow

# Optional: Install enhanced features
pip install tqdm python-dotenv
```

### 2. Setup

1. **Add images** to the `imgs/Wallpaper/` folder
2. **Configure settings** in `settings.json` (optional)
3. **Run the converter**:
   ```bash
   python convert_to_webp_and_thumbs.py
   ```

### 3. Results

- **WebP files**: `imgs/Wallpaper/webp/`
- **Thumbnails**: `imgs/Wallpaper/webp_thumbs/`
- **Logs**: `convert_images.log`
- **Failed files**: `failed_files.txt`

## ⚙️ Configuration

### Settings.json

```json
{
  "input_folder": "imgs/Wallpaper",                    // Source images folder
  "output_webp_folder": "imgs/Wallpaper/webp",        // WebP output folder
  "output_thumb_folder": "imgs/Wallpaper/webp_thumbs", // Thumbnail output folder
  "quality": 100,                                      // WebP quality (1-100)
  "method": 6,                                         // Compression method (0-6)
  "thumb_size": [400, 400],                           // Thumbnail dimensions
  "max_workers": 4,                                    // Parallel workers
  "preserve_exif": true,                               // Keep EXIF metadata
  "preserve_icc": true,                                // Keep ICC color profiles
  "preserve_alpha": true,                              // Keep transparency
  "force_lossless_for_alpha": true,                    // Lossless for transparent images
  "skip_existing": true,                               // Skip up-to-date files
  "log_file": "convert_images.log",                    // Log file name
  "failed_list_file": "failed_files.txt"               // Failed files list
}
```

### Environment Variables

Override any setting using environment variables:

```bash
# Set quality via environment variable
export QUALITY=80

# Or with CONVERT_ prefix
export CONVERT_QUALITY=80

# Run the converter
python convert_to_webp_and_thumbs.py
```

## 📊 Sample Output

```
Converting images: 100%|██████████| 25/25 [00:45<00:00,  1.8file/s, Ratio=45.2%, Success=25]

============================================================
CONVERSION SUMMARY
============================================================
Files processed: 25
Files failed: 0
Processing time: 45.2 seconds
Average time per file: 1.81 seconds
Processing speed: 33.2 files/minute

----------------------------------------
FILE SIZE STATISTICS
----------------------------------------
Original total size: 125.3 MB
WebP total size: 45.2 MB
Thumbnails total size: 11.4 MB
Output total size: 56.6 MB
Space saved: 68.7 MB
Overall compression ratio: 45.2%
Space savings: 54.8%
============================================================
```

## 🎯 Supported Formats

### Input Formats
- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **GIF** (.gif) - including animated
- **WebP** (.webp) - including animated
- **BMP** (.bmp)
- **TIFF** (.tiff)

### Output Format
- **WebP** (.webp) - optimized for web use

## 🔧 Advanced Usage

### Custom Configuration

Create your own `settings.json`:

```json
{
  "input_folder": "photos/2024",
  "output_webp_folder": "webp/2024",
  "output_thumb_folder": "thumbs/2024",
  "quality": 85,
  "thumb_size": [300, 300],
  "max_workers": 8
}
```

### Batch Processing Multiple Folders

```bash
# Process different folders by changing settings
export INPUT_FOLDER="photos/vacation"
export OUTPUT_WEBP_FOLDER="webp/vacation"
python convert_to_webp_and_thumbs.py
```

### Quality Optimization

```json
{
  "quality": 80,        // Good balance of quality/size
  "method": 6,          // Best compression
  "preserve_alpha": true // Keep transparency
}
```

## 📈 Performance Tips

1. **Adjust Workers**: Set `max_workers` to your CPU core count
2. **Use SSD**: Faster storage improves I/O performance
3. **Quality Settings**: Lower quality (80-90) for faster processing
4. **Skip Existing**: Keep `skip_existing: true` for incremental updates
5. **Batch Size**: Process folders with 100-1000 images for optimal performance

## 🛠️ Dependencies

### Required
- **Python 3.7+**
- **Pillow** - Image processing library

### Optional (for enhanced features)
- **tqdm** - Progress bar support
- **python-dotenv** - Environment variable support

### Installation
```bash
# Minimal installation
pip install Pillow

# Full installation with enhancements
pip install -r requirements.txt
```

## 📁 Project Structure

```
image-converter/
├── convert_to_webp_and_thumbs.py  # Main converter script
├── settings.json                  # Configuration file
├── requirements.txt               # Python dependencies
├── convert_images.log            # Conversion logs
├── failed_files.txt              # List of failed conversions
└── imgs/
    └── Wallpaper/
        ├── webp/                 # Converted WebP files
        └── webp_thumbs/          # Generated thumbnails
```

## 🐛 Troubleshooting

### Common Issues

1. **"No images found"**
   - Ensure images are in the `input_folder` directory
   - Check file extensions are supported

2. **Import errors**
   - Install Pillow: `pip install Pillow`
   - For progress bar: `pip install tqdm`

3. **Permission errors**
   - Ensure write access to output directories
   - Check file permissions

4. **Memory issues**
   - Reduce `max_workers` for large images
   - Process smaller batches

### Log Files

- **convert_images.log**: Detailed conversion progress
- **failed_files.txt**: List of files that couldn't be converted

## 🤝 Contributing

Feel free to enhance this project:

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Test thoroughly**
5. **Submit a pull request**

## 📄 License

This project is open source. Feel free to use, modify, and distribute.

## 🎉 Acknowledgments

- **Pillow** - Excellent Python imaging library
- **tqdm** - Beautiful progress bars
- **WebP** - Google's modern image format

---

**Happy converting! 🚀**

For questions or issues, check the log files or create an issue in the repository.