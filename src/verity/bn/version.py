"""Version stamp of the CPT file in use."""

import hashlib
from pathlib import Path

from verity.bn.network import cpt_path_in_use


def cpt_version(path: Path | None = None) -> str:
    """SHA-256 of the bytes of cpt_learned.json if present, else cpt_priors.json."""
    return hashlib.sha256((path or cpt_path_in_use()).read_bytes()).hexdigest()
