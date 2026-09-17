"""Domain errors.

Every error keeps its constructor arguments in ``args`` so pickling round-trips (DBOS steps
receive only serialisable values, and these exceptions cross that boundary).
"""


class DomainError(Exception):
    """Base class for domain-level failures."""


class InsufficientEvidence(DomainError):
    """A research run did not reach the minimum source count."""

    def __init__(
        self, research_run_id: str, found_sources: int, required_sources: int, successful_queries: int
    ) -> None:
        super().__init__(research_run_id, found_sources, required_sources, successful_queries)
        self.research_run_id = research_run_id
        self.found_sources = found_sources
        self.required_sources = required_sources
        self.successful_queries = successful_queries

    def __str__(self) -> str:
        return (
            f"insufficient evidence for research run {self.research_run_id}: "
            f"{self.found_sources} sources (need {self.required_sources}), {self.successful_queries} successful queries"
        )


class ArticleStructureError(DomainError):
    """The article Markdown does not follow the frozen format."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class UnknownCitationMarker(DomainError):
    """An agent output cites markers that are not in the numbered source list."""

    def __init__(self, markers: list[str]) -> None:
        super().__init__(markers)
        self.markers = markers

    def __str__(self) -> str:
        return f"unknown markers: {', '.join(self.markers)}"


class PublishingDisabled(DomainError):
    """A network publish was attempted while publishing is disabled."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class OutputRejected(DomainError):
    """An ``output_check`` rejected an agent output; the gateway turns this into a model retry."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message
