import os
import json
import logging
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Tuple, Any

from PIL import Image, ImageOps, UnidentifiedImageError

# Optional: progress bar support
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

# Optional: load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # dotenv is optional

# Helper: parse environment override values
def parse_env_value(value: str, target_type: Any):
    """Convert env string to the target type (bool, int, list, str)."""
    if value is None:
        return None
    try:
        if target_type == bool:
            v = value.strip().lower()
            return v in ("1", "true", "yes", "y", "on")
        if target_type == int:
            return int(value)
        if target_type == list:
            # try JSON list then comma-separated
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                parts = [p.strip() for p in value.split(",") if p.strip() != ""]
                # convert numeric parts to int when possible
                out = []
                for p in parts:
                    try:
                        out.append(int(p))
                    except Exception:
                        out.append(p)
                return out
        return value
    except Exception:
        return value

# Load configuration from settings.json and environment (env overrides JSON)
def load_config(config_path: str = "settings.json") -> Dict:
    """
    Load configuration from settings.json and then override with environment variables.
    Raises FileNotFoundError if settings.json missing and required env vars are absent.
    """
    schema = {
        "input_folder": str,
        "output_webp_folder": str,
        "output_thumb_folder": str,
        "quality": int,
        "method": int,
        "thumb_size": list,
        "max_workers": int,
        "preserve_exif": bool,
        "preserve_icc": bool,
        "preserve_alpha": bool,
        "force_lossless_for_alpha": bool,
        "skip_existing": bool,
        "log_file": str,
        "failed_list_file": str,
    }

    cfg: Dict[str, Any] = {}

    # 1) Load settings.json if present
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise RuntimeError("settings.json must contain a JSON object.")
    else:
        cfg = {}

    # 2) Override with environment variables (UPPERCASE keys)
    for key, typ in schema.items():
        env_name = key.upper()
        env_val = os.getenv(env_name)
        if env_val is not None:
            cfg[key] = parse_env_value(env_val, typ)
        else:
            pref = os.getenv(f"CONVERT_{env_name}")
            if pref is not None:
                cfg[key] = parse_env_value(pref, typ)

    # 3) Validate required keys
    missing = [k for k in ("input_folder", "output_webp_folder", "output_thumb_folder") if k not in cfg or cfg[k] in (None, "")]
    if missing:
        raise FileNotFoundError(
            f"Configuration incomplete. Missing keys: {missing}. "
            f"Provide these keys in 'settings.json' or via environment variables."
        )

    # 4) Normalize thumb_size to tuple
    if "thumb_size" in cfg:
        ts = cfg["thumb_size"]
        if isinstance(ts, str):
            cfg["thumb_size"] = tuple(parse_env_value(ts, list))
        elif isinstance(ts, list):
            cfg["thumb_size"] = tuple(ts)
    else:
        cfg["thumb_size"] = (400, 400)

    # 5) Provide safe fallbacks for optional settings if not provided
    cfg.setdefault("quality", 100)
    cfg.setdefault("method", 6)
    cfg.setdefault("max_workers", 4)
    cfg.setdefault("preserve_exif", True)
    cfg.setdefault("preserve_icc", True)
    cfg.setdefault("preserve_alpha", True)
    cfg.setdefault("force_lossless_for_alpha", True)
    cfg.setdefault("skip_existing", True)
    cfg.setdefault("log_file", "convert_images.log")
    cfg.setdefault("failed_list_file", "failed_files.txt")

    return cfg

# Image processing for a single file (called in worker process)
def process_single_file(src_path: str, config: Dict) -> Tuple[str, Dict]:
    """
    Convert one image to WebP and create thumbnail.
    Returns (message_string, stats_dict) on success, raises on fatal error.
    """
    src = Path(src_path)
    name = src.stem
    out_webp = Path(config["output_webp_folder"]) / f"{name}.webp"
    out_thumb = Path(config["output_thumb_folder"]) / f"{name}_thumb.webp"
    
    # Get original file size
    original_size = src.stat().st_size
    stats = {
        "original_size": original_size,
        "webp_size": 0,
        "thumb_size": 0,
        "total_size": 0,
        "compression_ratio": 0.0
    }

    # Skip if outputs are up-to-date
    if config.get("skip_existing", True):
        try:
            if out_webp.exists() and out_webp.stat().st_mtime >= src.stat().st_mtime:
                # Get existing file sizes for stats
                if out_webp.exists():
                    stats["webp_size"] = out_webp.stat().st_size
                if out_thumb.exists():
                    stats["thumb_size"] = out_thumb.stat().st_size
                stats["total_size"] = stats["webp_size"] + stats["thumb_size"]
                stats["compression_ratio"] = (stats["total_size"] / original_size) * 100 if original_size > 0 else 0
                return f"Skip (webp exists and up-to-date): {src.name}", stats
        except FileNotFoundError:
            pass

    try:
        with Image.open(src_path) as img:
            # correct orientation using EXIF
            img = ImageOps.exif_transpose(img)

            src_format = (img.format or "").upper()
            is_animated = getattr(img, "is_animated", False)

            # attempt to preserve metadata
            exif_bytes = img.info.get("exif") if config.get("preserve_exif", True) else None
            icc_profile = img.info.get("icc_profile") if config.get("preserve_icc", True) else None

            # Animated -> try animated WebP
            if is_animated and src_format in ("GIF", "WEBP"):
                frames = []
                durations = []
                n_frames = getattr(img, "n_frames", 1)
                for i in range(n_frames):
                    img.seek(i)
                    frame = img.convert("RGBA")
                    frames.append(frame.copy())
                    durations.append(img.info.get("duration", 100))
                try:
                    frames[0].save(
                        out_webp.as_posix(),
                        format="WEBP",
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations,
                        loop=img.info.get("loop", 0),
                        quality=config.get("quality", 100),
                        method=config.get("method", 6),
                    )
                except TypeError:
                    # fallback without metadata if unsupported
                    frames[0].save(
                        out_webp.as_posix(),
                        format="WEBP",
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations,
                        loop=img.info.get("loop", 0),
                        quality=config.get("quality", 100),
                        method=config.get("method", 6),
                    )
            else:
                # Static image
                has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
                if has_alpha and config.get("preserve_alpha", True):
                    out_img = img.convert("RGBA")
                    save_kwargs = {"lossless": True, "method": config.get("method", 6)}
                    if icc_profile:
                        save_kwargs["icc_profile"] = icc_profile
                    if exif_bytes:
                        try:
                            save_kwargs["exif"] = exif_bytes
                        except Exception:
                            pass
                    out_img.save(out_webp.as_posix(), "WEBP", **save_kwargs)
                else:
                    out_img = img.convert("RGB")
                    save_kwargs = {"quality": config.get("quality", 100), "method": config.get("method", 6)}
                    if icc_profile:
                        save_kwargs["icc_profile"] = icc_profile
                    if exif_bytes:
                        try:
                            save_kwargs["exif"] = exif_bytes
                        except Exception:
                            pass
                    out_img.save(out_webp.as_posix(), "WEBP", **save_kwargs)

        # Get WebP file size
        if out_webp.exists():
            stats["webp_size"] = out_webp.stat().st_size

        # Create thumbnail (use first frame for animated images)
        try:
            if config.get("skip_existing", True) and out_thumb.exists() and out_thumb.stat().st_mtime >= src.stat().st_mtime:
                stats["thumb_size"] = out_thumb.stat().st_size
                stats["total_size"] = stats["webp_size"] + stats["thumb_size"]
                stats["compression_ratio"] = (stats["total_size"] / original_size) * 100 if original_size > 0 else 0
                return f"Converted (webp ready). Thumbnail skipped (up-to-date): {src.name}", stats

            with Image.open(src_path) as img2:
                img2 = ImageOps.exif_transpose(img2)
                if getattr(img2, "is_animated", False):
                    img2.seek(0)
                thumb = img2.copy()
                thumb.thumbnail(tuple(config.get("thumb_size", (400, 400))))

                has_alpha_thumb = thumb.mode in ("RGBA", "LA") or (thumb.mode == "P" and "transparency" in thumb.info)
                if has_alpha_thumb and config.get("preserve_alpha", True):
                    thumb = thumb.convert("RGBA")
                    thumb.save(out_thumb.as_posix(), "WEBP", lossless=True, method=config.get("method", 6))
                else:
                    thumb = thumb.convert("RGB")
                    thumb.save(out_thumb.as_posix(), "WEBP", quality=config.get("quality", 100), method=config.get("method", 6))
        except Exception as e_thumb:
            stats["total_size"] = stats["webp_size"]
            stats["compression_ratio"] = (stats["total_size"] / original_size) * 100 if original_size > 0 else 0
            return f"Converted: {src.name} -> {out_webp.name} (thumbnail failed: {e_thumb})", stats

        # Get final file sizes
        if out_thumb.exists():
            stats["thumb_size"] = out_thumb.stat().st_size
        stats["total_size"] = stats["webp_size"] + stats["thumb_size"]
        stats["compression_ratio"] = (stats["total_size"] / original_size) * 100 if original_size > 0 else 0

        return f"Converted: {src.name} -> {out_webp.name} | Thumb: {out_thumb.name}", stats

    except UnidentifiedImageError:
        raise RuntimeError(f"Skipped (not an image or corrupted): {src_path}")
    except Exception:
        # re-raise to be handled by the caller
        raise

# Worker wrapper for ProcessPoolExecutor
def process_file_task(args: Tuple[str, Dict]) -> Tuple[str, bool, str, Dict]:
    """Top-level worker function (safe to be pickled)."""
    src_path, config = args
    try:
        msg, stats = process_single_file(src_path, config)
        return (os.path.basename(src_path), True, msg, stats)
    except Exception as e:
        return (os.path.basename(src_path), False, str(e), {})

# Utilities: logging setup and file listing
def setup_logging(log_file: str):
    """Configure console and file logging."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # remove old handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def gather_image_files(input_folder: str):
    """Return list of image file paths in input_folder."""
    allowed = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff")
    files = []
    for entry in os.listdir(input_folder):
        if entry.lower().endswith(allowed):
            files.append(os.path.join(input_folder, entry))
    return files

def format_file_size(size_bytes: int) -> str:
    """Convert bytes to human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    # Handle negative values (space used instead of saved)
    is_negative = size_bytes < 0
    abs_size = abs(size_bytes)
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while abs_size >= 1024 and i < len(size_names) - 1:
        abs_size /= 1024.0
        i += 1
    
    if is_negative:
        return f"-{abs_size:.1f} {size_names[i]}"
    else:
        return f"{abs_size:.1f} {size_names[i]}"

# Main entry point
def main():
    config = load_config("settings.json")

    # Ensure output directories exist
    os.makedirs(config["output_webp_folder"], exist_ok=True)
    os.makedirs(config["output_thumb_folder"], exist_ok=True)

    setup_logging(config.get("log_file", "convert_images.log"))
    logging.info("Starting conversion.")
    logging.info(f"Input: {config['input_folder']}")
    logging.info(f"Output WebP: {config['output_webp_folder']}")
    logging.info(f"Output Thumbs: {config['output_thumb_folder']}")

    image_files = gather_image_files(config["input_folder"])
    if not image_files:
        logging.info("No images found. Exiting.")
        return

    tasks = [(p, config) for p in image_files]
    failed = []
    success_count = 0
    
    # Statistics tracking
    total_original_size = 0
    total_webp_size = 0
    total_thumb_size = 0
    start_time = time.time()

    max_workers = int(config.get("max_workers", 4))
    
    # Create progress bar if tqdm is available
    progress_bar = None
    if TQDM_AVAILABLE:
        progress_bar = tqdm(total=len(tasks), desc="Converting images", unit="file")
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(process_file_task, t): t[0] for t in tasks}
        for fut in as_completed(future_to_path):
            src = future_to_path[fut]
            try:
                filename, ok, message, stats = fut.result()
                if ok:
                    # Update statistics
                    if stats:
                        total_original_size += stats.get("original_size", 0)
                        total_webp_size += stats.get("webp_size", 0)
                        total_thumb_size += stats.get("thumb_size", 0)
                        
                        # Enhanced logging with file sizes
                        if "compression_ratio" in stats:
                            ratio = stats["compression_ratio"]
                            orig_size = format_file_size(stats.get("original_size", 0))
                            webp_size = format_file_size(stats.get("webp_size", 0))
                            thumb_size = format_file_size(stats.get("thumb_size", 0))
                            enhanced_msg = f"{message} | Original: {orig_size} → WebP: {webp_size} + Thumb: {thumb_size} ({ratio:.1f}%)"
                            logging.info(enhanced_msg)
                        else:
                            logging.info(message)
                    else:
                        logging.info(message)
                    success_count += 1
                else:
                    logging.warning(f"[{filename}] failed: {message}")
                    failed.append((filename, message))
                
                # Update progress bar
                if progress_bar:
                    progress_bar.update(1)
                    if stats and "compression_ratio" in stats:
                        progress_bar.set_postfix({
                            "Ratio": f"{stats['compression_ratio']:.1f}%",
                            "Success": success_count
                        })
                    
            except Exception as e:
                logging.exception(f"Task failed for {src}: {e}")
                failed.append((os.path.basename(src), str(e)))
                if progress_bar:
                    progress_bar.update(1)
    
    # Close progress bar
    if progress_bar:
        progress_bar.close()

    # Calculate final statistics
    end_time = time.time()
    processing_time = end_time - start_time
    total_output_size = total_webp_size + total_thumb_size
    overall_compression_ratio = (total_output_size / total_original_size * 100) if total_original_size > 0 else 0
    space_saved = total_original_size - total_output_size
    
    # Print comprehensive summary
    logging.info("=" * 60)
    logging.info("CONVERSION SUMMARY")
    logging.info("=" * 60)
    logging.info(f"Files processed: {success_count}")
    logging.info(f"Files failed: {len(failed)}")
    logging.info(f"Processing time: {processing_time:.1f} seconds")
    if success_count > 0:
        logging.info(f"Average time per file: {processing_time/success_count:.2f} seconds")
        logging.info(f"Processing speed: {success_count/processing_time*60:.1f} files/minute")
    
    logging.info("-" * 40)
    logging.info("FILE SIZE STATISTICS")
    logging.info("-" * 40)
    logging.info(f"Original total size: {format_file_size(total_original_size)}")
    logging.info(f"WebP total size: {format_file_size(total_webp_size)}")
    logging.info(f"Thumbnails total size: {format_file_size(total_thumb_size)}")
    logging.info(f"Output total size: {format_file_size(total_output_size)}")
    if space_saved > 0:
        logging.info(f"Space saved: {format_file_size(space_saved)}")
        savings_percent = (space_saved / total_original_size) * 100
        logging.info(f"Space savings: {savings_percent:.1f}%")
    else:
        logging.info(f"Space used: {format_file_size(abs(space_saved))}")
        usage_percent = (abs(space_saved) / total_original_size) * 100
        logging.info(f"Space increase: {usage_percent:.1f}%")
    
    logging.info(f"Overall compression ratio: {overall_compression_ratio:.1f}%")
    
    # write failed list if any
    if failed:
        failed_path = config.get("failed_list_file", "failed_files.txt")
        try:
            with open(failed_path, "w", encoding="utf-8") as f:
                for fn, reason in failed:
                    f.write(f"{fn}\t{reason}\n")
            logging.info(f"Failed files list saved to: {failed_path}")
        except Exception:
            logging.exception("Failed to write failed files list.")
    
    logging.info("=" * 60)

if __name__ == "__main__":
    main()