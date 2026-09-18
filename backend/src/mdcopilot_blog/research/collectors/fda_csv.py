"""FDA AI-device CSV collector: weekly poll, submission-number diff."""

import csv
import email.utils
import io
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from mdcopilot_blog.domain.enums import DateSource, DiscoveredVia, FetchStatus
from mdcopilot_blog.research.environment import ResearchEnvironment
from mdcopilot_blog.research.retriever import fetch
from mdcopilot_blog.research.signals import FeedOutcome, FeedSpec, Signal, in_window

REQUIRED_COLUMNS: tuple[str, ...] = ("Submission Number", "Date of Final Decision")
FDA_CSV_POLL_INTERVAL = timedelta(days=7)
FDA_CSV_MAX_NEW_ROWS = 20
_K_RE = re.compile(r"^K\d{6}$")
_DEN_RE = re.compile(r"^DEN\d{6}$")
_P_RE = re.compile(r"^(P\d{6})(?:/S\d+)?$")


def submission_url(number: str) -> str | None:
    if _K_RE.match(number):
        return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={number}"
    if _DEN_RE.match(number):
        return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?ID={number}"
    match = _P_RE.match(number)
    if match:
        return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id={match.group(1)}"
    return None


def _decision_date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").replace(tzinfo=UTC)
    except ValueError:
        return None


async def collect_fda_csv(env: ResearchEnvironment, feed: FeedSpec, *, now: datetime, window_days: int) -> FeedOutcome:
    state = dict(feed.state or {})
    if feed.last_fetched_at is not None and now - feed.last_fetched_at < FDA_CSV_POLL_INTERVAL:
        return FeedOutcome(
            feed=feed,
            ok=True,
            fetched=False,
            signals=[],
            error=None,
            http_status=None,
            not_modified=False,
            new_state=state,
            items_in_window=0,
        )
    etag_object = state.get("etag")
    last_modified_object = state.get("lastModified")
    result = await fetch(
        env,
        feed.url,
        header_profile=feed.header_profile,
        etag=etag_object if isinstance(etag_object, str) else None,
        last_modified=last_modified_object if isinstance(last_modified_object, str) else None,
        check_robots=False,
    )
    if result.status != FetchStatus.OK:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error=result.error,
            http_status=result.http_status,
            not_modified=False,
            new_state=state,
            items_in_window=0,
        )
    if result.not_modified:
        return FeedOutcome(
            feed=feed,
            ok=True,
            fetched=True,
            signals=[],
            error=None,
            http_status=result.http_status,
            not_modified=True,
            new_state=state,
            items_in_window=0,
        )

    text = result.body.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [name.strip() if name else "" for name in reader.fieldnames or []]
    lookup = {(name or "").lower(): name or "" for name in reader.fieldnames or []}
    missing = [column for column in REQUIRED_COLUMNS if column.lower() not in lookup]
    if missing:
        return FeedOutcome(
            feed=feed,
            ok=False,
            fetched=True,
            signals=[],
            error="FDA CSV missing columns: " + ", ".join(missing),
            http_status=result.http_status,
            not_modified=False,
            new_state=state,
            items_in_window=0,
        )
    rows: list[dict[str, Any]] = []
    for row in reader:
        normalized = {((key or "").strip()): (value or "") for key, value in row.items()}
        number = normalized.get(lookup.get("submission number", ""), "").strip()
        if not number:
            continue
        decision_raw = normalized.get(lookup.get("date of final decision", ""), "")
        device = normalized.get(lookup.get("device", ""), "").strip()
        company = normalized.get(lookup.get("company", ""), "").strip()
        rows.append(
            {
                "number": number,
                "decision": _decision_date(decision_raw),
                "device": device,
                "company": company,
            }
        )

    all_numbers = sorted({row["number"] for row in rows})
    known = state.get("knownIds")
    if not isinstance(known, list):
        new_state = {**state, "knownIds": all_numbers}
        new_state.pop("etag", None) if state.get("etag") is None else None
        if result.etag:
            new_state["etag"] = result.etag
        if result.last_modified:
            new_state["lastModified"] = result.last_modified
        return FeedOutcome(
            feed=feed,
            ok=True,
            fetched=True,
            signals=[],
            error=None,
            http_status=result.http_status,
            not_modified=False,
            new_state=new_state,
            items_in_window=0,
        )

    known_set = {str(number) for number in known}
    candidates = [row for row in rows if row["number"] not in known_set]
    candidates.sort(
        key=lambda row: (row["decision"] is None, row["decision"] or datetime.min.replace(tzinfo=UTC)), reverse=False
    )
    dated = [row for row in candidates if row["decision"] is not None]
    undated = [row for row in candidates if row["decision"] is None]
    ordered = sorted(dated, key=lambda row: row["decision"] or datetime.min.replace(tzinfo=UTC), reverse=True) + undated

    published_at: datetime | None = None
    if result.last_modified:
        try:
            published_at = email.utils.parsedate_to_datetime(result.last_modified)
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=UTC)
            published_at = published_at.astimezone(UTC)
        except (TypeError, ValueError):
            published_at = None

    signals: list[Signal] = []
    for row in ordered[:FDA_CSV_MAX_NEW_ROWS]:
        url = submission_url(row["number"])
        if url is None:
            continue
        decision_text = row["decision"].strftime("%Y-%m-%d") if row["decision"] else "decision unknown"
        signals.append(
            Signal(
                url=url,
                title=(
                    f"FDA AI-enabled device list adds {row['device'] or 'a device'} "
                    f"({row['company'] or 'unknown company'}; {row['number']}; {decision_text})"
                ),
                published_at=published_at,
                date_source=DateSource.API if published_at else DateSource.NONE,
                discovered_via=DiscoveredVia.FDA_CSV,
                feed_id=feed.id,
                external_ids={"fdaSubmissionNumber": row["number"]},
                answer_excerpt=None,
            )
        )
    kept = [signal for signal in signals if in_window(signal.published_at, now=now, window_days=window_days)]
    new_state = {
        **state,
        "knownIds": sorted(known_set | set(all_numbers)),
        "etag": result.etag or state.get("etag"),
        "lastModified": result.last_modified or state.get("lastModified"),
    }
    new_state = {key: value for key, value in new_state.items() if value is not None}
    return FeedOutcome(
        feed=feed,
        ok=True,
        fetched=True,
        signals=kept,
        error=None,
        http_status=result.http_status,
        not_modified=False,
        new_state=new_state,
        items_in_window=len(kept),
    )
