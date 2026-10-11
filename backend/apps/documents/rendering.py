"""HTML to PDF with WeasyPrint. Needs Pango on the machine (the Docker image installs it)."""


def html_to_pdf(html: str) -> bytes:
    # Imported here: WeasyPrint loads native libraries, and only the job that renders needs them.
    from weasyprint import HTML

    pdf: bytes = HTML(string=html).write_pdf()
    return pdf
