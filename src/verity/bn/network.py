"""Belief-network structure and CPT loading (build spec B.5). Library: pgmpy 1.1.x.

State orderings are FIXED here and documented once; CPT JSON columns/rows follow them.
Each CPT is stored as ``values[row = child state][column = parent configuration]``:
  source_cred   (no parent)  -> shape (3, 1)
  claim_true | source_cred   -> shape (2, 3)   columns: trusted, unknown, low
  every evidence child | claim_true -> shape (k, 2)  columns: true, false
"""

import json
import warnings
from functools import lru_cache
from pathlib import Path

from pgmpy.factors.discrete import TabularCPD
from pgmpy.models import DiscreteBayesianNetwork
from pydantic import BaseModel, ConfigDict, ValidationError

from verity.errors import DataError, ModelError
from verity.schemas import BNNode

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
PRIORS_FILE = DATA_DIR / "cpt_priors.json"
LEARNED_FILE = DATA_DIR / "cpt_learned.json"

STATES: dict[BNNode, list[str]] = {
    "source_cred": ["trusted", "unknown", "low"],
    "claim_true": ["true", "false"],
    "fact_check": ["refuted", "supported", "none"],
    "corroboration": ["yes", "no"],
    "sensational": ["high", "low"],
    "specifics": ["yes", "no"],
}
EDGES: list[tuple[BNNode, BNNode]] = [
    ("source_cred", "claim_true"),
    ("claim_true", "fact_check"),
    ("claim_true", "corroboration"),
    ("claim_true", "sensational"),
    ("claim_true", "specifics"),
]
EVIDENCE_NODES: list[BNNode] = [
    "source_cred",
    "fact_check",
    "corroboration",
    "sensational",
    "specifics",
]
PARENT: dict[BNNode, BNNode | None] = {
    "source_cred": None,
    "claim_true": "source_cred",
    "fact_check": "claim_true",
    "corroboration": "claim_true",
    "sensational": "claim_true",
    "specifics": "claim_true",
}
TOLERANCE = 1e-6


class CptTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rationale: str = ""
    values: list[list[float]]


class CptFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    status: str | None = None
    dev_set_hash: str | None = None
    version: str | None = None
    tables: dict[BNNode, CptTable]


def load_cpt_file(path: Path) -> CptFile:
    try:
        cpts = CptFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        raise DataError(f"cannot read CPT file {path}: {exc}", code="cpt_unreadable") from exc
    validate_cpts(cpts)
    return cpts


def validate_cpts(cpts: CptFile) -> None:
    """Every node present, correct shape, every column sums to 1, no zero/negative cell."""
    for node, states in STATES.items():
        table = cpts.tables.get(node)
        if table is None:
            raise ModelError(f"CPT for {node} missing", code="cpt_invalid")
        parent = PARENT[node]
        cols = 1 if parent is None else len(STATES[parent])
        if len(table.values) != len(states) or any(len(r) != cols for r in table.values):
            raise ModelError(f"CPT for {node} has the wrong shape", code="cpt_invalid")
        for c in range(cols):
            column = [row[c] for row in table.values]
            if abs(sum(column) - 1.0) > TOLERANCE or min(column) <= 0.0:
                raise ModelError(f"CPT for {node} column {c} invalid: {column}", code="cpt_invalid")


def cpt_path_in_use() -> Path:
    """cpt_learned.json if present, else cpt_priors.json."""
    return LEARNED_FILE if LEARNED_FILE.exists() else PRIORS_FILE


def build_network(cpts: CptFile) -> DiscreteBayesianNetwork:
    validate_cpts(cpts)
    model = DiscreteBayesianNetwork(EDGES)
    for node, states in STATES.items():
        parent = PARENT[node]
        kwargs: dict[str, object] = {}
        if parent is not None:
            kwargs = {"evidence": [parent], "evidence_card": [len(STATES[parent])]}
        names = {node: states}
        if parent is not None:
            names[parent] = STATES[parent]
        model.add_cpds(
            TabularCPD(
                node,
                len(states),
                cpts.tables[node].values,
                state_names=names,
                **kwargs,  # type: ignore[arg-type]
            )
        )
    if not model.check_model():
        raise ModelError("belief network failed pgmpy check_model", code="network_invalid")
    return model


@lru_cache(maxsize=4)
def _network_for(path: str, mtime_ns: int) -> DiscreteBayesianNetwork:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_network(load_cpt_file(Path(path)))


def get_network(path: Path | None = None) -> DiscreteBayesianNetwork:
    """Network built from the CPT file in use (cached; rebuilt if the file changes)."""
    p = path or cpt_path_in_use()
    return _network_for(str(p), p.stat().st_mtime_ns)
