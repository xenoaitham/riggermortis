"""The D-025 segmentation pass wrapper (``u2net.onnx``) — the ONE product copy.

docs/VOLUME.md / docs/WIRING.md. The adopted artifact rides the P1-1
manifest flow (checksum-pinned, user-initiated download, zero default-use
outbound); this wrapper verifies the pin at EVERY load (the corruption
catch) and exposes the declared preprocess/postprocess contract: RGB/255,
NCHW 1x3x320x320, primary sigmoid output > 0.5, NEAREST-upscaled back to
the source resolution. numpy/onnxruntime/PIL are inference extras — lazy
imports inside functions, never at module import. The S37 probe pipeline
aliases these copies (the one-copy law, docs/WIRING.md); its published
rows are the byte-identity proof.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import InferenceError
from . import models

#: The declared model input resolution (the D-025 contract).
INPUT_SIZE = 320


def u2net_session() -> tuple[Any, Any]:
    """The adopted model's session from the MANAGED path (the P1-1 flow:
    ``rigpose models download u2net``). Loud and actionable when the
    artifact is absent — the caller decides the honest-skip shape."""
    import onnxruntime as ort  # noqa: PLC0415 — the inference-extra pattern

    path = models.model_path("u2net")
    if not Path(path).is_file():
        raise InferenceError(
            "u2net is not downloaded",
            hint="run: rigpose models download u2net (the P1-1 manifest flow)",
        )
    models.verify_model("u2net")
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return sess, sess.get_inputs()[0]


def u2net_mask(sess: Any, inp: Any, rgb: Any) -> Any:
    """The declared preprocess/postprocess (the D-025 contract): RGB/255,
    NCHW 1x3x320x320, primary sigmoid output > 0.5, NEAREST-upscaled to
    the source resolution. Returns the bool HxW mask (numpy array)."""
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    pil = Image.fromarray(rgb).resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
    arr = (np.asarray(pil, dtype=np.float32) / 255.0).transpose(2, 0, 1)[None]
    out = sess.run(None, {inp.name: arr})[0]
    m = (out[0, 0] > 0.5).astype(np.uint8) * 255
    h, w = rgb.shape[0], rgb.shape[1]
    return np.asarray(Image.fromarray(m).resize((w, h), Image.NEAREST)) > 127
