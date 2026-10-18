"""Stage 4 — gather one vertical visual per beat. Pixabay stock (free)."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import requests

from .config import env
from .utils import log


def gather_visuals(cfg: dict, script: dict, out_dir: Path, duration: float) -> list[Path]:
    """Return an ordered list of media files (videos/images) to cover `duration`."""
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(exist_ok=True)
    cut = cfg["video"]["cut_every_seconds"]
    needed = max(cfg["visuals"]["clips_per_video"], math.ceil(duration / cut))

    cues = [b.get("visual_cue", "").strip() for b in script.get("beats", [])
            if b.get("visual_cue")]
    style = cfg["channel"].get("visual_style", "")
    if cues:
        queries = [cues[int(i * len(cues) / needed)] for i in range(needed)]
    else:
        queries = [style] * needed

    provider = cfg["visuals"]["provider"]
    used_ids: set = set()
    paths: list[Path] = []
    for i, q in enumerate(queries):
        dest = clips_dir / f"{i:02d}"
        try:
            if provider == "pixabay":
                paths.append(_pixabay_video(q, dest, cfg, used_ids))
            else:
                raise ValueError(f"Unknown visuals.provider: {provider} (only 'pixabay' supported)")
        except Exception as e:
            log(f"visual {i} ('{q[:30]}') failed: {e}; reusing previous", "warn")
            if paths:
                paths.append(paths[-1])
    if not paths:
        raise RuntimeError("No visuals could be gathered.")
    log(f"visuals: {len(paths)} clips ({provider})", "ok")
    return paths


def _pixabay_video(query: str, dest: Path, cfg: dict, used_ids: Optional[set] = None) -> Path:
    key = env("PIXABAY_API_KEY")
    if not key:
        raise SystemExit("PIXABAY_API_KEY missing in .env")

    used_ids = used_ids if used_ids is not None else set()

    # Ищем видео на Pixabay по запросу
    r = requests.get(
        "https://pixabay.com/api/videos/",
        params={
            "key": key,
            "q": query,
            "video_type": "all",
            "per_page": 12,
            "safesearch": "true",
        },
        timeout=30,
    )
    r.raise_for_status()
    hits = r.json().get("hits", [])
    if not hits:
        raise RuntimeError("no Pixabay results")

    # Выбираем свежий результат (не использованный ранее)
    fresh = [v for v in hits if v.get("id") not in used_ids] or hits
    video = fresh[0]
    used_ids.add(video.get("id"))

    # Берём лучшее качество (large или medium)
    files = video.get("videos", {})
    best = files.get("large") or files.get("medium") or files.get("small")
    if not best or not best.get("url"):
        raise RuntimeError("no downloadable video URL")

    url = best["url"]
    out = dest.with_suffix(".mp4")
    out.write_bytes(requests.get(url, timeout=120).content)
    return out
