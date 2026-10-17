"""HTML to PDF with WeasyPrint. Needs Pango on the machine (the Docker image installs it)."""


def html_to_pdf(html: str) -> bytes:
    # Imported here: WeasyPrint loads native libraries, and only the job that renders needs them.
    from weasyprint import HTML

    pdf: bytes = HTML(string=html).write_pdf()
    return pdf


def htmls_to_pdf(htmls: list[str]) -> bytes:
    """Several documents joined page after page in one PDF."""
    from weasyprint import HTML

    rendered = [HTML(string=html).render() for html in htmls]
    pages = [page for document in rendered for page in document.pages]
    pdf: bytes = rendered[0].copy(pages).write_pdf()
    return pdf
