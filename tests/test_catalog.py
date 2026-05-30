"""Tests for the built-in catalog."""

from safe_whale.catalog import CATALOG, get_by_name, search


def test_catalog_nonempty():
    assert len(CATALOG) > 0


def test_search_empty_returns_all():
    results = search("")
    assert len(results) == len(CATALOG)


def test_search_by_name():
    results = search("httpie")
    assert any(e.name == "httpie" for e in results)


def test_search_by_description():
    results = search("formatter")
    assert len(results) > 0


def test_search_no_match():
    results = search("zzznomatch999")
    assert results == []


def test_search_by_alias():
    results = search("youtube downloader")
    assert [entry.name for entry in results][:1] == ["yt-dlp"]


def test_search_filters_by_usage_pattern():
    results = search("", usage_pattern="tui_terminal")
    assert results
    assert {entry.usage_pattern for entry in results} == {"tui_terminal"}


def test_exact_search_only_matches_names_and_aliases():
    assert search("formatter", exact=True) == []
    assert any(entry.name == "httpie" for entry in search("httpie", exact=True))


def test_get_by_name_found():
    entry = get_by_name("httpie")
    assert entry is not None
    assert entry.entrypoint == "http"


def test_get_by_name_missing():
    assert get_by_name("nonexistent-pkg") is None


def test_new_tui_catalog_entries_present():
    expected = {
        "bpytop",
        "s-tui",
        "mitmproxy",
        "pudb",
        "rtv",
        "mps-youtube",
        "harlequin",
        "bpython",
        "ptpython",
        "http-prompt",
    }
    assert expected.issubset({entry.name for entry in CATALOG})
