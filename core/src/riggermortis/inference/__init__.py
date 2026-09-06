"""Optional inference layer (Phase 1).

Importing this package NEVER downloads anything and NEVER requires
``onnxruntime``/``numpy`` — those enter only via the ``[inference]`` extra and
are imported lazily by the model wrapper (P1-2). The model manager
(:mod:`riggermortis.inference.models`) itself is stdlib-only: manifest,
checksum-pinned downloads on explicit user command, offline verification.
"""
