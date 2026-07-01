"""Untethered Resume Re-Frame engine.

Propose grounded re-label / re-emphasis edits with an LLM, then hard-abstain
anything a deterministic guard cannot prove against the source resume. The guard,
taxonomy, schema, engine, and diff import with no SDK dependency; only the live
proposer in :mod:`reframe.llm` imports ``anthropic`` (lazily).
"""
from reframe.engine import MODES, ReframeResult, reframe
from reframe.schema import Edit, ReframeProposal

__all__ = ["reframe", "ReframeResult", "MODES", "Edit", "ReframeProposal"]
