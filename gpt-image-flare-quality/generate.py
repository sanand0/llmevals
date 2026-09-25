# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "pillow", "pillow-avif-plugin"]
# ///

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image
import pillow_avif  # noqa: F401

MODEL = "gpt-image-2.5-flare"
DEFAULT_SIZE = "1024x1024"
QUALITIES = ("low", "medium", "high", "xhigh", "max")
ROOT = Path(__file__).parent
CACHE = ROOT / ".cache"
OUT = ROOT / "images"


def cache_key(prompt: str, quality: str, size: str, sample: int = 1) -> str:
    request = {"model": MODEL, "size": size, "quality": quality, "prompt": prompt}
    if sample > 1:
        request["sample"] = sample
    spec = json.dumps(request, sort_keys=True)
    return hashlib.sha256(spec.encode()).hexdigest()


def generate(prompt: str, quality: str, size: str) -> bytes:
    payload = {"model": MODEL, "prompt": prompt, "size": size, "quality": quality}
    r = httpx.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=None,
    )
    r.raise_for_status()
    return base64.b64decode(r.json()["data"][0]["b64_json"])


def compress(png: bytes, path: Path, quality: int = 72) -> None:
    with Image.open(io.BytesIO(png)) as im:
        im.convert("RGB").save(path, "AVIF", quality=quality, speed=6)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt_ids", nargs="*", help="Prompt IDs; default: all")
    ap.add_argument("--qualities", nargs="+", choices=QUALITIES, default=QUALITIES)
    ap.add_argument("--samples", type=int, default=1, help="Independent samples per quality; sample 1 reuses the canonical output")
    args = ap.parse_args()

    prompts = json.loads((ROOT / "prompts.json").read_text())
    selected = args.prompt_ids or list(prompts)
    unknown = set(selected) - set(prompts)
    if unknown:
        raise SystemExit(f"Unknown prompt IDs: {', '.join(sorted(unknown))}")

    CACHE.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)

    for pid in selected:
        prompt = prompts[pid]["prompt"]
        size = prompts[pid].get("size", DEFAULT_SIZE)
        avif_quality = prompts[pid].get("avif_quality", 72)
        for quality in args.qualities:
            for sample in range(1, args.samples + 1):
                key = cache_key(prompt, quality, size, sample)
                cached = CACHE / f"{key}.png"
                suffix = "" if sample == 1 else f"-{sample}"
                out = OUT / f"{pid}-{quality}{suffix}.avif"

                if cached.exists():
                    print(f"CACHE {pid:12} {quality:6} #{sample} {key[:8]}")
                    png = cached.read_bytes()
                else:
                    print(f"GET   {pid:12} {quality:6} #{sample} {key[:8]}", flush=True)
                    png = generate(prompt, quality, size)
                    cached.write_bytes(png)

                compress(png, out, avif_quality)
                print(f"  -> {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    load_dotenv(override=True)
    main()
