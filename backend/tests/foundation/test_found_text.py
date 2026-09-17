import pytest

from mdcopilot_blog.domain.contracts import ArticleSection, SECTION_ORDER
from mdcopilot_blog.domain.errors import ArticleStructureError
from mdcopilot_blog.domain.text import (
    ATX_HEADING_RE,
    CITATION_MARKER_RE,
    assemble_markdown,
    body_word_count,
    count_words,
    extract_markers,
    normalize_for_match,
    split_markdown,
    strip_citation_markers,
)


def test_citation_marker_regex() -> None:
    assert CITATION_MARKER_RE.findall("a [S1] b [S12] c [S0] [s3] [S01]") == ["S1", "S12"]


def test_strip_citation_markers() -> None:
    assert strip_citation_markers("Specialists wait longer [S1] than before [S2][S3].") == (
        "Specialists wait longer than before."
    )
    assert strip_citation_markers("[S1] Leading") == " Leading"
    assert strip_citation_markers("No markers.") == "No markers."


def test_count_words() -> None:
    assert count_words("It's a well-known fact’s 24/7 test [S1].") == 7
    assert count_words("") == 0
    assert count_words("— – ...") == 0


def test_extract_markers() -> None:
    assert extract_markers("A [S2] b [S1] c [S2] d [S10]") == ["S2", "S1", "S10"]
    assert extract_markers("none") == []


def test_normalize_for_match() -> None:
    assert normalize_for_match("  “Hello” WORLD’s ‘quote’\n\tend ") == "\"hello\" world's 'quote' end"


@pytest.mark.parametrize(
    ("line", "groups"),
    [
        ("## Heading", ("##", "Heading")),
        ("   ### Deep ###", ("###", "Deep")),
        ("##", ("##", None)),
    ],
)
def test_atx_heading_regex(line: str, groups: tuple[str, str | None]) -> None:
    match = ATX_HEADING_RE.match(line)
    assert match is not None
    assert match.groups() == groups


@pytest.mark.parametrize("line", ["#hashtag", "    ## four spaces", "####### seven"])
def test_atx_heading_regex_rejects(line: str) -> None:
    assert ATX_HEADING_RE.match(line) is None


GOLDEN_HEADINGS = [
    "Context",
    "Core argument",
    "Evidence",
    "MDCopilot perspective",
    "Practical implications",
    "Conclusion",
]


def golden_sections() -> list[ArticleSection]:
    sections = [ArticleSection(key=SECTION_ORDER[0], heading=None, body_markdown="  Intro [S1].  ")]
    for key, heading in zip(SECTION_ORDER[1:], GOLDEN_HEADINGS, strict=True):
        sections.append(ArticleSection(key=key, heading=heading, body_markdown=f"Body {key.value}."))
    return sections


def test_assemble_markdown_exact_output() -> None:
    assert assemble_markdown(golden_sections()) == (
        "Intro [S1].\n"
        "\n## Context\n"
        "\nBody context.\n"
        "\n## Core argument\n"
        "\nBody core_argument.\n"
        "\n## Evidence\n"
        "\nBody evidence.\n"
        "\n## MDCopilot perspective\n"
        "\nBody mdcopilot_perspective.\n"
        "\n## Practical implications\n"
        "\nBody practical_implications.\n"
        "\n## Conclusion\n"
        "\nBody conclusion.\n"
    )


def test_assemble_rejects_wrong_sections() -> None:
    sections = golden_sections()
    with pytest.raises(ArticleStructureError, match="SECTION_ORDER"):
        assemble_markdown(sections[:6])
    with pytest.raises(ArticleStructureError, match="SECTION_ORDER"):
        assemble_markdown(list(reversed(sections)))


def test_split_round_trip() -> None:
    sections = golden_sections()
    assert split_markdown(assemble_markdown(sections)) == [
        (section.heading, section.body_markdown.strip()) for section in sections
    ]
    rebuilt = [
        ArticleSection(key=key, heading=heading, body_markdown=body)
        for key, (heading, body) in zip(SECTION_ORDER, split_markdown(assemble_markdown(sections)), strict=True)
    ]
    assert assemble_markdown(rebuilt) == assemble_markdown(sections)


def test_split_round_trip_crlf() -> None:
    sections = golden_sections()
    md = assemble_markdown(sections).replace("\n", "\r\n")
    assert split_markdown(md) == [(section.heading, section.body_markdown.strip()) for section in sections]


@pytest.mark.parametrize(
    ("md", "message"),
    [
        ("Intro.\n\n## A\n\nb\n\n## C\n\nb\n\n## E\n\nb\n\n## G\n\nb\n\n## I\n\nb\n", "expected 6 H2 sections, found 5"),
        (
            "Intro.\n\n## A\n\nb\n\n## C\n\nb\n\n## E\n\nb\n\n## G\n\nb\n\n## I\n\nb\n\n## K\n\nb\n\n## M\n\nb\n",
            "found 7",
        ),
        ("Intro.\n\n### Sub\n\nb\n\n## C\n\nb\n\n## E\n\nb\n\n## G\n\nb\n\n## I\n\nb\n\n## K\n\nb\n", "heading level 3 is not allowed: ### Sub"),
        ("# Title\n\n## C\n\nb\n\n## E\n\nb\n\n## G\n\nb\n\n## I\n\nb\n\n## K\n\nb\n\n## M\n\nb\n", "heading level 1 is not allowed: # Title"),
        ("Intro.\n\n## A\n\nb\n\n## C\n\nb\n\n##\n\nb\n\n## G\n\nb\n\n## I\n\nb\n\n## K\n\nb\n", "section 3 heading is empty"),
        ("Intro.\n\n## A\n\nb\n\n## C\n\nb\n\n## E\n\nb\n\n## G\n\n\n## I\n\nb\n\n## K\n\nb\n", "section 4 body is empty"),
        ("## Context\n\nb\n\n## C\n\nb\n\n## E\n\nb\n\n## G\n\nb\n\n## I\n\nb\n\n## K\n\nb\n", "introduction body is empty"),
    ],
)
def test_split_errors(md: str, message: str) -> None:
    with pytest.raises(ArticleStructureError, match=message):
        split_markdown(md)


def test_body_word_count() -> None:
    sections = golden_sections()
    sections[0] = ArticleSection(key=SECTION_ORDER[0], heading=None, body_markdown="One two [S1].")
    sections[1] = ArticleSection(key=SECTION_ORDER[1], heading="Context", body_markdown="Three.")
    for index in range(2, len(sections)):
        sections[index] = ArticleSection(key=SECTION_ORDER[index], heading=GOLDEN_HEADINGS[index - 1], body_markdown="x")
    assert body_word_count(sections) == 2 + 1 + 5
