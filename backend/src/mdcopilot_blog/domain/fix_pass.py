"""One bounded repair pass; evidence/configuration defects require an explicit action."""

from typing import Literal

from pydantic import BaseModel

from mdcopilot_blog.domain.contracts import GateReport, RevisionFinding
from mdcopilot_blog.domain.enums import GateId
from mdcopilot_blog.domain.gates import FIXABLE_BLOCKING


class FixPassDecision(BaseModel):
    action: Literal["ready", "fix_pass", "failed"]
    seo_rerun: bool
    findings: list[RevisionFinding]
    suggestion: Literal["regenerate_research", "change_topic", "fix_configuration"] | None


def decide_fix_pass(report: GateReport, *, fix_pass_used: bool) -> FixPassDecision:
    for result in report.results:
        if result.gate not in {gate.value for gate in GateId}:
            raise ValueError(f"unknown gate id: {result.gate}")
    failed = [r for r in report.results if not r.passed and r.severity == "blocking"]
    if report.passed:
        return FixPassDecision(action="ready", seo_rerun=False, findings=[], suggestion=None)
    suggestion = next(
        (
            value
            for key, value in (
                ("sources_present", "regenerate_research"),
                ("no_duplicate_topic", "change_topic"),
                ("disclosure_present", "fix_configuration"),
            )
            if any(r.gate == key for r in failed)
        ),
        None,
    )
    findings = [
        RevisionFinding(
            finding_id=f"gate:{r.gate}",
            origin="quality_gate",
            description=r.details,
            location="article",
            recommended_revision=None,
            required=True,
        )
        for r in failed
        if r.gate in FIXABLE_BLOCKING
    ]
    return FixPassDecision(
        action="failed" if suggestion or fix_pass_used else "fix_pass",
        seo_rerun=not (suggestion or fix_pass_used) and any(r.gate == "seo_complete" for r in failed),
        findings=findings,
        suggestion=suggestion,
    )
