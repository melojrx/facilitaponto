#!/usr/bin/env python
"""Pré-carrega modelos biométricos usados pelo painel e pelo fluxo de ponto."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MODELS_TO_PRELOAD = (
    ("facial_recognition", "ArcFace"),
    ("face_detector", "retinaface"),
)


def ensure_cache_dir() -> Path:
    deepface_home = Path(os.getenv("DEEPFACE_HOME", "/opt/deepface"))
    weights_dir = deepface_home / ".deepface" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    return weights_dir


def main() -> int:
    weights_dir = ensure_cache_dir()
    print(f"[biometria] cache de pesos: {weights_dir}")

    from deepface import DeepFace

    for task, model_name in MODELS_TO_PRELOAD:
        print(f"[biometria] preload {task}:{model_name}")
        DeepFace.build_model(task=task, model_name=model_name)

    print("[biometria] preload concluido")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - caminho operacional de startup
        print(f"[biometria] falha no preload: {exc}", file=sys.stderr)
        raise
