#!/usr/bin/env python3
"""Download Whisper GGML models from HuggingFace."""

import argparse
import sys
import urllib.request
from pathlib import Path

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "whisper"
HUGGINGFACE_BASE = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
MODELS = {
    "tiny": "ggml-tiny.bin",
    "tiny.en": "ggml-tiny.en.bin",
    "base": "ggml-base.bin",
    "base.en": "ggml-base.en.bin",
    "small": "ggml-small.bin",
    "small.en": "ggml-small.en.bin",
    "medium": "ggml-medium.bin",
    "medium.en": "ggml-medium.en.bin",
    "large-v1": "ggml-large-v1.bin",
    "large-v2": "ggml-large-v2.bin",
    "large-v3": "ggml-large-v3.bin",
    "large-v3-turbo": "ggml-large-v3-turbo.bin",
}


def get_model_path(name: str, cache_dir: Path | None = None) -> Path:
    """Get path to model file, downloading if needed."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    if name not in MODELS:
        raise ValueError(f"Unknown model: {name}. Available: {list(MODELS.keys())}")

    filename = MODELS[name]
    model_path = cache_dir / filename

    if not model_path.exists():
        download_model(name, cache_dir)

    return model_path


def download_model(name: str, cache_dir: Path | None = None) -> Path:
    """Download a Whisper model from HuggingFace."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    if name not in MODELS:
        raise ValueError(f"Unknown model: {name}. Available: {list(MODELS.keys())}")

    filename = MODELS[name]
    url = f"{HUGGINGFACE_BASE}/{filename}"
    dest = cache_dir / filename

    if dest.exists():
        print(f"Model already exists: {dest}")
        return dest

    print(f"Downloading {name} from {url}...")
    print(f"Destination: {dest}")

    def progress_hook(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, downloaded * 100 // total_size)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\r  {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
    print("\nDone!")

    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Whisper GGML models")
    parser.add_argument(
        "model",
        nargs="?",
        default="base.en",
        choices=list(MODELS.keys()),
        help="Model to download (default: base.en)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Cache directory (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available models",
    )

    args = parser.parse_args()

    if args.list:
        print("Available models:")
        for name, filename in MODELS.items():
            print(f"  {name:20} -> {filename}")
        return 0

    try:
        path = download_model(args.model, args.cache_dir)
        print(f"Model ready: {path}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
