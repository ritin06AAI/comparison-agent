import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os
from typing import List, Dict

from utils.logger import setup_logger
logger = setup_logger(__name__)

class HtmlEmailSender:
    def __init__(self):
        self.smtp_server = os.getenv("OUTLOOK_SMTP", "smtp.office365.com")
        self.smtp_port = int(os.getenv("OUTLOOK_PORT", "587"))
        self.from_email = os.getenv("OUTLOOK_EMAIL")
        self.from_password = os.getenv("OUTLOOK_PASSWORD")
        self.recipients = os.getenv("EMAIL_RECIPIENTS", "").split(",")

    def send(self, report_path: str, results: List[Dict]) -> bool:
        failed = sum(1 for r in results if r["status"] == "FAIL")
        overall_status = "PASS" if failed == 0 else "FAIL"

        subject = f"UAT vs Prod Report - {overall_status} - {len(results)} pages"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = ", ".join([r.strip() for r in self.recipients if r.strip()])

        # Simple HTML body
        body_html = f"""
        <html><body>
        <h2>UAT vs Production Comparison Report</h2>
        <p><b>Status:</b> {overall_status}</p>
        <p>Pages tested: {len(results)}<br>
        Passed: {len([r for r in results if r['status']=='PASS'])}<br>
        Failed: {len([r for r in results if r['status']=='FAIL'])}</p>
        <p>Full detailed report attached as HTML.</p>
        </body></html>
        """
        msg.attach(MIMEText(body_html, "html"))

        # Attach HTML report
        with open(report_path, "rb") as f:
            part = MIMEBase("text", "html")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(report_path)}"',
            )
            msg.attach(part)

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.from_email, self.from_password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Email sent to: {self.recipients}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
