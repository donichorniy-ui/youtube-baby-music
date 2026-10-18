"""Stage 2 — turn an idea into a tight, retention-optimized voiceover script."""
from __future__ import annotations

import json

from .config import load_prompt
from .knowledge import strategy_notes, style_examples
from .llm import complete
from .utils import extract_json, log


def write_script(cfg: dict, idea: dict) -> dict:
    ch = cfg["channel"]
    target = cfg["video"]["target_seconds"]
    word_budget = int(target * 2.4)      # ~2.4 spoken words/sec — lower bound
    word_budget_max = int(target * 3.0)  # upper bound for a brisk read

    disclaimer_line = ""
    dkey = ch.get("inject_disclaimer")
    if dkey:
        text = cfg["compliance"]["disclaimers"].get(dkey, "")
        if text:
            disclaimer_line = f'- End the script with this exact disclaimer: "{text}"'

    voice_ref = style_examples(ch["key"])
    notes = strategy_notes(ch["key"])
    prompt = load_prompt("script").format(
        niche=ch["niche"], name=ch["name"], tone=ch["tone"], audience=ch["audience"],
        title=idea["title"], concept=idea["concept"], hook_angle=idea.get("hook_angle", ""),
        primary_keyword=idea.get("primary_keyword", idea["title"]),
        search_question=idea.get("search_question", ""),
        style_reference=voice_ref or "(none provided — use the tone above)",
        creator_notes=notes or "(none provided)",
        target_seconds=target, word_budget=word_budget, word_budget_max=word_budget_max,
        disclaimer_line=disclaimer_line,
    )

    # Пытаемся получить сценарий. Если модель вернула пустоту — повторяем.
    for attempt in range(2):
        try:
            script = extract_json(complete(prompt, cfg, max_tokens=2000))
            if script.get("full_script"):
                wc = len(script["full_script"].split())
                log(f"script: hook + {len(script.get('beats', []))} beats, {wc} words", "ok")
                return script
        except ValueError as e:
            log(f"script attempt {attempt + 1} failed: {e}", "warn")
        if attempt == 0:
            log("retrying script generation...", "warn")

    raise RuntimeError("Scriptwriter failed to return a valid JSON script after 2 attempts.")
