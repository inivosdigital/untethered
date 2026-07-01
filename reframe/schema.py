#!/usr/bin/env python3
"""The contract between the creative LLM layer and the deterministic guard.

The model returns a :class:`ReframeProposal`; every field is required so the
structured-output schema stays strict (``additionalProperties: false``). The
model is asked only to *propose* - nothing it returns is trusted until
:mod:`reframe.guardrails` has validated each edit against the source resume.
"""
from typing import List, Literal

from pydantic import BaseModel, Field

ChangeType = Literal["relabel", "reemphasis"]
FieldName = Literal["headline", "summary", "bullet", "skills"]


class Edit(BaseModel):
    """One proposed change, anchored to a verbatim span of the source resume."""

    field: FieldName = Field(description="Which resume region this edit touches.")
    change_type: ChangeType = Field(
        description=(
            "'relabel' changes a job-title / skill label to a canonical, "
            "recruiter-searchable term. 'reemphasis' rewrites existing content to "
            "surface it more prominently. Neither may introduce new facts."
        )
    )
    source_span: str = Field(
        description="Verbatim substring of the resume this edit is anchored to."
    )
    before: str = Field(description="The current text being changed (verbatim).")
    after: str = Field(description="The proposed replacement text.")
    surfaced_keywords: List[str] = Field(
        description=(
            "Recruiter search terms, drawn from the approved target-title "
            "taxonomy, that this edit surfaces. May be empty for pure reemphasis."
        )
    )
    rationale: str = Field(
        description="Why the change is warranted, citing evidence in the resume."
    )


class ReframeProposal(BaseModel):
    """The model's full set of proposed edits for one resume + mode."""

    edits: List[Edit] = Field(description="Proposed edits; may be empty.")
