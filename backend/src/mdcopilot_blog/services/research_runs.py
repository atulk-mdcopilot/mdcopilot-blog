"""Research history API projections."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.api.schemas_common import SourceRefOut
from mdcopilot_blog.api.schemas_research import FindingOut, ResearchRunDetail, ResearchRunOut
from mdcopilot_blog.db.models import FindingSource, LedgerSource, ResearchFindingRecord, ResearchRun
from mdcopilot_blog.domain.enums import ResearchRunKind
from mdcopilot_blog.services.sources import to_ledger_source_out


def to_source_ref(row: LedgerSource, *, marker: str | None) -> SourceRefOut:
    return SourceRefOut.model_validate(
        {key: marker if key == "marker" else getattr(row, key) for key in SourceRefOut.model_fields}
    )


def to_research_run_out(run: ResearchRun, *, finding_count: int) -> ResearchRunOut:
    values = {
        key: getattr(run, key)
        for key in ResearchRunOut.model_fields
        if key not in {"pillar", "source_count", "finding_count"}
    }
    return ResearchRunOut(
        **values, pillar=run.pillar_key, source_count=len(run.source_ids), finding_count=finding_count
    )


async def list_research_runs(
    db: AsyncSession,
    *,
    run_id: uuid.UUID | None,
    article_id: uuid.UUID | None,
    kind: ResearchRunKind | None,
    limit: int,
    offset: int,
) -> tuple[list[ResearchRunOut], int]:
    stmt = select(ResearchRun)
    for column, value in ((ResearchRun.run_id, run_id), (ResearchRun.article_id, article_id), (ResearchRun.kind, kind)):
        if value is not None:
            stmt = stmt.where(column == value)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(ResearchRun.created_at.desc(), ResearchRun.id.desc()).limit(limit).offset(offset)
        )
    ).all()
    counts = {
        key: count
        for key, count in (
            (
                await db.execute(
                    select(ResearchFindingRecord.research_run_id, func.count())
                    .where(ResearchFindingRecord.research_run_id.in_([r.id for r in rows]))
                    .group_by(ResearchFindingRecord.research_run_id)
                )
            ).all()
        )
    }
    return [to_research_run_out(r, finding_count=counts.get(r.id, 0)) for r in rows], total or 0


async def get_research_run_detail(db: AsyncSession, research_run_id: uuid.UUID) -> ResearchRunDetail | None:
    run = await db.get(ResearchRun, research_run_id)
    if run is None:
        return None
    source_ids = [uuid.UUID(x) for x in run.source_ids]
    rows = {r.id: r for r in await db.scalars(select(LedgerSource).where(LedgerSource.id.in_(source_ids)))}
    sources = [rows[x] for x in source_ids if x in rows]
    markers = {x: f"S{i + 1}" for i, x in enumerate(source_ids)}
    findings = []
    for finding in await db.scalars(
        select(ResearchFindingRecord)
        .where(ResearchFindingRecord.research_run_id == run.id)
        .order_by(ResearchFindingRecord.position)
    ):
        linked = (
            await db.scalars(
                select(LedgerSource)
                .join(FindingSource, FindingSource.source_id == LedgerSource.id)
                .where(FindingSource.finding_id == finding.id)
            )
        ).all()
        linked = sorted(
            linked, key=lambda r: (source_ids.index(r.id) if r.id in source_ids else len(source_ids), r.canonical_url)
        )
        values = {key: getattr(finding, key) for key in FindingOut.model_fields if key != "sources"}
        findings.append(FindingOut(**values, sources=[to_source_ref(r, marker=markers.get(r.id)) for r in linked]))
    return ResearchRunDetail(
        **to_research_run_out(run, finding_count=len(findings)).model_dump(),
        findings=findings,
        sources=[to_ledger_source_out(r) for r in sources],
    )
