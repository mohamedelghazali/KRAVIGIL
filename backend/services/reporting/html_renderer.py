import logging
import os
from typing import Any, Dict, List
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

class HTMLRenderer:
    def __init__(self):
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"])
        )

    def render(self, scan_data: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
        try:
            return self.env.get_template("report.html").render(scan=scan_data, findings=findings)
        except Exception:
            logger.exception("HTML rendering failed")
            raise
