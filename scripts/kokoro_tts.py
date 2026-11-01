# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["kokoro-onnx==0.6.1", "soundfile"]
# ///
"""Text on stdin -> wav file, using Kokoro. Run with: uv run --script kokoro_tts.py --voice V --out F --home DIR"""
import argparse
import sys
import urllib.request
from pathlib import Path

BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")


def ensure_models(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = folder / name
        if dest.exists():
            continue
        part = dest.with_name(name + ".part")
        print(f"Downloading {name}...", file=sys.stderr)
        urllib.request.urlretrieve(BASE + name, part)
        part.rename(dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--out", required=True)
    ap.add_argument("--home", required=True)
    a = ap.parse_args()
    text = sys.stdin.read().strip()
    if not text:
        print("no text on stdin", file=sys.stderr)
        return 2
    folder = Path(a.home) / "kokoro"
    try:
        ensure_models(folder)
        import soundfile
        from kokoro_onnx import Kokoro

        samples, rate = Kokoro(str(folder / FILES[0]), str(folder / FILES[1])).create(
            text, voice=a.voice, speed=1.0, lang="en-us")
        soundfile.write(a.out, samples, rate)
    except Exception as e:
        print(f"kokoro error: {e!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
