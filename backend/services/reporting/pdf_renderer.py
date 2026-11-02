import logging
from weasyprint import HTML

logger = logging.getLogger(__name__)

class PDFRenderer:
    def render_to_file(self, html_content: str, output_path: str) -> None:
        try:
            HTML(string=html_content).write_pdf(output_path)
            logger.info("PDF rendered to %s", output_path)
        except Exception:
            logger.exception("PDF rendering failed")
            raise
