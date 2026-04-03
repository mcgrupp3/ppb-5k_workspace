"""
Lazy-load Hailo vlm_chat Backend: resolve HEF, run describe on BGR numpy frames.

Requires the same environment as ``vision_scripts/hailo-apps`` (hailo_platform, etc.).
Set env ``HAILO_APPS_ROOT`` to ``.../vision_scripts/hailo-apps`` if imports fail after install.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def resolve_hailo_apps_root() -> Path:
    env = os.environ.get('HAILO_APPS_ROOT')
    if env:
        p = Path(env).resolve()
        if (p / 'hailo_apps').is_dir():
            return p
    here = Path(__file__).resolve()
    for ancestor in [here.parent] + list(here.parents):
        cand = ancestor / 'vision_scripts' / 'hailo-apps'
        if (cand / 'hailo_apps').is_dir():
            return cand.resolve()
    raise RuntimeError(
        'Could not find hailo-apps. Export HAILO_APPS_ROOT=/path/to/vision_scripts/hailo-apps '
        'and ensure that directory contains hailo_apps/.'
    )


def _bootstrap_imports() -> None:
    root = resolve_hailo_apps_root()
    r = str(root)
    if r not in sys.path:
        sys.path.insert(0, r)


def build_backend(
    hef_path: Optional[str] = None,
    max_tokens: int = 200,
    temperature: float = 0.1,
    seed: int = 42,
    system_prompt: str = 'You are a helpful assistant that analyzes images and answers questions about them.',
) -> Any:
    """Construct :class:`hailo_apps.python.gen_ai_apps.vlm_chat.backend.Backend`."""
    _bootstrap_imports()
    from hailo_apps.python.core.common.core import resolve_hef_path  # type: ignore
    from hailo_apps.python.core.common.defines import HAILO10H_ARCH, VLM_CHAT_APP  # type: ignore
    from hailo_apps.python.gen_ai_apps.vlm_chat.backend import Backend  # type: ignore

    path = resolve_hef_path(hef_path, app_name=VLM_CHAT_APP, arch=HAILO10H_ARCH)
    if path is None:
        raise RuntimeError('resolve_hef_path returned None; check VLM HEF / --list-models')
    return Backend(
        hef_path=str(path),
        max_tokens=max_tokens,
        temperature=temperature,
        seed=seed,
        system_prompt=system_prompt,
    )


def describe_image_bgr(
    backend: Any,
    bgr: np.ndarray,
    prompt: str,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """
    Run VLM on a BGR uint8 image (e.g. OpenCV / cv_bridge). Returns dict with answer, time.
    """
    return backend.vlm_inference(bgr, prompt, timeout_seconds)
