import importlib
import importlib.metadata

import pytest

MODULES = [
    "feedparser",
    "trafilatura",
    "htmldate",
    "newspaper",
    "pypdfium2",
    "protego",
    "dateutil.parser",
    "markdown_it",
    "nh3",
    "opentelemetry.sdk.trace",
    "opentelemetry.exporter.otlp.proto.http.trace_exporter",
]


@pytest.mark.parametrize("module", MODULES)
def test_phase_2_10_modules_import(module: str) -> None:
    importlib.import_module(module)


@pytest.mark.parametrize(
    ("package", "expected"),
    [
        ("dbos", "3.0.0"),
        ("genai-prices", "0.1.7"),
        ("h2", "4.4.1"),
        ("hpack", "4.2.0"),
        ("hyperframe", "6.1.0"),
        ("feedparser", "6.0."),
        ("trafilatura", "2.2."),
        ("htmldate", "1.10."),
        ("newspaper4k", "0.9."),
        ("pypdfium2", "5.13."),
        ("protego", "0.6."),
        ("markdown-it-py", "4.2."),
        ("nh3", "0.3."),
        ("opentelemetry-sdk", "1.44."),
        ("opentelemetry-exporter-otlp-proto-http", "1.44."),
    ],
)
def test_pinned_versions(package: str, expected: str) -> None:
    version = importlib.metadata.version(package)
    if expected.count(".") == 2 and not expected.endswith("."):
        assert version == expected
    else:
        assert version.startswith(expected)


def test_live_marker_is_registered(pytestconfig: pytest.Config) -> None:
    markers = pytestconfig.getini("markers")
    assert any(str(marker).startswith("live:") for marker in markers)
