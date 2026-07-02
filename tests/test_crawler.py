from behavior_reader.crawler import CrawlConfig, normalize_url, parse_page


def test_parse_page_extracts_content_and_unique_links() -> None:
    html = """
    <html>
      <head>
        <title>Example Page</title>
        <meta name="description" content="A useful page">
      </head>
      <body>
        <main><h1>Heading</h1><p>Body text.</p></main>
        <a href="/docs/">Docs</a>
        <a href="/docs/#part">Same docs</a>
        <a href="mailto:test@example.com">Email</a>
      </body>
    </html>
    """
    page = parse_page(html, "https://behavior.stanford.edu/start/")

    assert page["title"] == "Example Page"
    assert page["description"] == "A useful page"
    assert "Heading\nBody text." in page["text"]
    assert page["links"] == ["https://behavior.stanford.edu/docs/"]


def test_normalize_url_handles_relative_links_and_fragments() -> None:
    assert normalize_url(
        "https://behavior.stanford.edu/docs/start/",
        "../guide/#install",
    ) == "https://behavior.stanford.edu/docs/guide/"
    assert normalize_url(
        "https://behavior.stanford.edu/",
        "/index.html",
    ) == "https://behavior.stanford.edu/"


def test_config_rejects_invalid_limits() -> None:
    try:
        CrawlConfig(max_pages=0)
    except ValueError as exc:
        assert "max_pages" in str(exc)
    else:
        raise AssertionError("Expected invalid max_pages to fail")
