from datetime import datetime
import os
import tempfile
import pandas as pd
import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from utils.logger import setup_logger
from utils.excel_parser import ExcelParser
from agents.qa_agent import QAComparisonAgent
from reporting.html_report_generator import HtmlReportGenerator

logger = setup_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════
def send_email_report(recipient: str, results: list):
    """Send QA comparison results via email with HTML report attached."""
    try:
        sender   = st.secrets["EMAIL_SENDER"]
        password = st.secrets["EMAIL_PASSWORD"]

        total  = len(results)
        passed = sum(1 for r in results if r.get("status") == "PASS")
        failed = total - passed
        pass_rate = int((passed / total) * 100) if total else 0

        url_rows = ""
        for r in results:
            ph = r.get("page_health", {})
            total_issues = (
                len(r.get("content_issues", [])) +
                len(r.get("link_issues",    [])) +
                len(r.get("image_issues",   [])) +
                len(ph.get("title_issues",  [])) +
                len(ph.get("status_issues", [])) +
                len(ph.get("ssl_issues",    []))
            )
            status       = r.get("status", "N/A")
            status_color = "#34d399" if status == "PASS" else "#f87171"
            status_bg    = "rgba(16,185,129,0.15)" if status == "PASS" else "rgba(239,68,68,0.15)"
            status_icon  = "✅" if status == "PASS" else "❌"

            url_rows += f"""
            <tr>
                <td style="padding:14px 16px;border-bottom:1px solid #1e2a3a;">
                    <div style="font-weight:600;color:#f1f5f9;font-size:13px;margin-bottom:6px;">{r.get("test_name","N/A")}</div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap;">
                        <span style="background:#1e2a3a;color:#60a5fa;font-size:11px;padding:3px 8px;border-radius:4px;font-family:monospace;">🔵 {r.get("url_a","N/A")}</span>
                        <span style="color:#4b5563;font-size:11px;padding:3px 0;">vs</span>
                        <span style="background:#1e2a3a;color:#34d399;font-size:11px;padding:3px 8px;border-radius:4px;font-family:monospace;">🟢 {r.get("url_b","N/A")}</span>
                    </div>
                </td>
                <td style="padding:14px 16px;border-bottom:1px solid #1e2a3a;text-align:center;">
                    <span style="background:{status_bg};color:{status_color};font-size:12px;font-weight:700;padding:5px 12px;border-radius:99px;">{status_icon} {status}</span>
                </td>
                <td style="padding:14px 16px;border-bottom:1px solid #1e2a3a;text-align:center;">
                    <span style="color:{'#f87171' if total_issues > 0 else '#34d399'};font-size:20px;font-weight:700;">{total_issues}</span>
                    <div style="color:#4b5563;font-size:10px;margin-top:2px;">issues</div>
                </td>
            </tr>
            """

        verdict_color  = "#34d399" if failed == 0 else "#f87171"
        verdict_bg     = "rgba(16,185,129,0.10)" if failed == 0 else "rgba(239,68,68,0.10)"
        verdict_border = "#10b981" if failed == 0 else "#ef4444"
        verdict_icon   = "✅" if failed == 0 else "❌"
        verdict_text   = "All Pages Passed" if failed == 0 else f"{failed} Page(s) Failed"
        verdict_sub    = f"All {total} comparison(s) completed successfully." if failed == 0 else f"{failed} out of {total} comparison(s) found issues."

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;padding:0;background:#0a0d14;font-family:'Segoe UI',Arial,sans-serif;">
            <div style="max-width:680px;margin:0 auto;padding:32px 16px;">
                <div style="text-align:center;margin-bottom:32px;">
                    <div style="font-size:28px;margin-bottom:8px;">🔍</div>
                    <h1 style="margin:0;font-size:22px;font-weight:700;color:#f1f5f9;">QA Comparison Agent</h1>
                    <p style="margin:6px 0 0;font-size:13px;color:#6b7280;">Report generated on {datetime.now().strftime("%B %d, %Y at %H:%M")}</p>
                </div>
                <div style="background:{verdict_bg};border:1px solid {verdict_border};border-radius:12px;padding:20px 24px;margin-bottom:24px;text-align:center;">
                    <div style="font-size:32px;margin-bottom:6px;">{verdict_icon}</div>
                    <div style="font-size:18px;font-weight:700;color:{verdict_color};margin-bottom:6px;">{verdict_text}</div>
                    <div style="font-size:13px;color:#94a3b8;">{verdict_sub}</div>
                </div>
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                    <tr>
                        <td style="padding:0 6px 0 0;">
                            <div style="background:#161b27;border:1px solid #1e2a3a;border-radius:10px;padding:16px;text-align:center;">
                                <div style="font-size:26px;font-weight:700;color:#f1f5f9;">{total}</div>
                                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-top:4px;">Total</div>
                            </div>
                        </td>
                        <td style="padding:0 6px;">
                            <div style="background:#161b27;border:1px solid #1e2a3a;border-radius:10px;padding:16px;text-align:center;">
                                <div style="font-size:26px;font-weight:700;color:#34d399;">{passed}</div>
                                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-top:4px;">Passed</div>
                            </div>
                        </td>
                        <td style="padding:0 6px;">
                            <div style="background:#161b27;border:1px solid #1e2a3a;border-radius:10px;padding:16px;text-align:center;">
                                <div style="font-size:26px;font-weight:700;color:#f87171;">{failed}</div>
                                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-top:4px;">Failed</div>
                            </div>
                        </td>
                        <td style="padding:0 0 0 6px;">
                            <div style="background:#161b27;border:1px solid #1e2a3a;border-radius:10px;padding:16px;text-align:center;">
                                <div style="font-size:26px;font-weight:700;color:#60a5fa;">{pass_rate}%</div>
                                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-top:4px;">Pass Rate</div>
                            </div>
                        </td>
                    </tr>
                </table>
                <div style="background:#161b27;border:1px solid #1e2a3a;border-radius:12px;overflow:hidden;margin-bottom:24px;">
                    <div style="padding:14px 16px;border-bottom:1px solid #1e2a3a;background:#1a2235;">
                        <span style="font-size:12px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;">Comparison Results</span>
                    </div>
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <thead>
                            <tr style="background:#1e2a3a;">
                                <th style="padding:10px 16px;text-align:left;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;">Test / URLs</th>
                                <th style="padding:10px 16px;text-align:center;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;">Status</th>
                                <th style="padding:10px 16px;text-align:center;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;">Issues</th>
                            </tr>
                        </thead>
                        <tbody>{url_rows}</tbody>
                    </table>
                </div>
                <div style="background:rgba(29,78,216,0.10);border:1px solid rgba(59,130,246,0.25);border-radius:10px;padding:14px 18px;margin-bottom:24px;">
                    <div style="font-size:13px;font-weight:600;color:#93c5fd;margin-bottom:2px;">📎 Full Report Attached</div>
                    <div style="font-size:12px;color:#6b7280;">Open <strong style="color:#94a3b8;">qa_report.html</strong> in your browser for the complete detailed report.</div>
                </div>
                <div style="text-align:center;padding-top:16px;border-top:1px solid #1e2130;">
                    <p style="font-size:11px;color:#374151;margin:0;">Sent by <strong style="color:#4b5563;">QA Comparison Agent</strong> · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg            = MIMEMultipart("mixed")
        msg["Subject"] = f"QA Comparison Agent Report — {passed}/{total} Passed · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg["From"]    = sender
        msg["To"]      = recipient
        msg.attach(MIMEText(html_body, "html"))

        report_path = st.session_state.get("report_path")
        if report_path and os.path.exists(report_path):
            with open(report_path, "rb") as f:
                attachment = MIMEBase("text", "html")
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    "Content-Disposition", "attachment",
                    filename=f"qa_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
                )
                msg.attach(attachment)

        with smtplib.SMTP("smtp.office365.com", 587, timeout=30) as server:
            server.ehlo("smtp.office365.com")
            server.starttls()
            server.ehlo("smtp.office365.com")
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())

        return True, "Email sent successfully!"

    except Exception as e:
        logger.error(f"Email error: {e}")
        return False, str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# POST RUN ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def post_run_actions(results, send_email, email_recipient):
    """Save to history and send email after any comparison run."""
    for r in results:
        ph = r.get("page_health", {})
        total_issues = (
            len(r.get("content_issues", [])) +
            len(r.get("link_issues",    [])) +
            len(r.get("image_issues",   [])) +
            len(ph.get("title_issues",  [])) +
            len(ph.get("status_issues", [])) +
            len(ph.get("ssl_issues",    []))
        )
        st.session_state.history.append({
            "datetime":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "test_name":    r.get("test_name", "N/A"),
            "url_a":        r.get("url_a", "N/A"),
            "url_b":        r.get("url_b", "N/A"),
            "status":       r.get("status", "N/A"),
            "total_issues": total_issues,
        })

    if send_email == "Yes" and email_recipient:
        with st.spinner("Sending email report…"):
            success, msg = send_email_report(email_recipient, results)
            if success:
                st.success(f"📧 {msg}")
            else:
                st.error(f"📧 Email failed: {msg}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="QA Comparison Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px; }

    [data-testid="stSidebar"] { background: #0f1117; border-right: 1px solid #1e2130; }
    [data-testid="stSidebar"] * { color: #c8ccd8 !important; }

    [data-testid="stSidebar"] div[data-testid="stSelectbox"] span,
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] div[class*="singleValue"],
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] div[class*="ValueContainer"] * {
        color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] > div > div {
        background: #0d1117 !important; border: 1px solid #2d3748 !important; border-radius: 8px !important;
    }

    [data-testid="stSidebar"] .logo-title { font-size: 15px; font-weight: 600; color: #ffffff !important; line-height: 1.2; }
    [data-testid="stSidebar"] .logo-sub { font-size: 12px; font-weight: 500; color: #cbd5e1 !important; }
    [data-testid="stSidebar"] .nav-section { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: #e2e8f0 !important; margin: 16px 0 8px 0; font-weight: 700; }

    .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1.5rem; padding-bottom: 1.25rem; border-bottom: 1px solid #1e2130; }
    .page-header h1 { font-size: 1.4rem; font-weight: 600; color: #f1f5f9; margin: 0; }
    .page-header p { font-size: 0.95rem; font-weight: 500; color: #d1d5db; margin: 6px 0 0 0; }

    .badge-ai { display: inline-block; background: linear-gradient(135deg, #1d4ed8, #0ea5e9); color: #fff; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 99px; letter-spacing: 0.04em; }

    .section-label { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #e5e7eb; margin-bottom: 10px; }

    .url-label-a { display: flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 600; color: #60a5fa; margin-bottom: 6px; }
    .url-label-b { display: flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 600; color: #34d399; margin-bottom: 6px; }
    .dot-a { width:8px; height:8px; border-radius:50%; background:#3b82f6; display:inline-block; }
    .dot-b { width:8px; height:8px; border-radius:50%; background:#10b981; display:inline-block; }

    .metric-card { background: #161b27; border: 1px solid #1e2a3a; border-radius: 12px; padding: 16px 18px; text-align: left; }
    .metric-card .mlabel { font-size: 11px; color: #6b7280; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
    .metric-card .mval { font-size: 28px; font-weight: 700; color: #f1f5f9; line-height: 1; }
    .metric-card .msub { font-size: 11px; color: #4b5563; margin-top: 4px; }
    .metric-card.pass .mval { color: #34d399; }
    .metric-card.fail .mval { color: #f87171; }
    .metric-card.warn .mval { color: #fbbf24; }

    .issue-section { background: #0d1117; border: 1px solid #1e2a3a; border-radius: 10px; padding: 14px 16px; margin-top: 8px; }
    .issue-item-a { background: rgba(59,130,246,0.08); border-left: 3px solid #3b82f6; border-radius: 0 6px 6px 0; padding: 7px 12px; font-size: 12px; color: #93c5fd; margin-bottom: 5px; }
    .issue-item-b { background: rgba(16,185,129,0.08); border-left: 3px solid #10b981; border-radius: 0 6px 6px 0; padding: 7px 12px; font-size: 12px; color: #6ee7b7; margin-bottom: 5px; }
    .issue-item-warn { background: rgba(251,191,36,0.08); border-left: 3px solid #f59e0b; border-radius: 0 6px 6px 0; padding: 7px 12px; font-size: 12px; color: #fcd34d; margin-bottom: 5px; }
    .no-issue { font-size: 12px; color: #34d399; padding: 4px 0; }

    .ai-banner { background: linear-gradient(135deg, rgba(29,78,216,0.15), rgba(14,165,233,0.10)); border: 1px solid rgba(59,130,246,0.25); border-radius: 10px; padding: 14px 16px; font-size: 13px; color: #93c5fd; margin: 1rem 0; display: flex; align-items: flex-start; gap: 10px; }
    .ai-banner .ai-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }

    .upload-zone { background: #161b27; border: 1px dashed #334155; border-radius: 12px; padding: 28px; text-align: center; color: #cbd5e1; font-size: 15px; font-weight: 500; line-height: 1.6; }
    .upload-zone b { color: #f8fafc; font-size: 16px; font-weight: 700; }
    .upload-zone code { color: #f8fafc; background: rgba(255,255,255,0.10); padding: 2px 6px; border-radius: 6px; font-size: 12px; }

    div[data-testid="stTextInput"] input { background: #0d1117 !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; color: #e2e8f0 !important; font-size: 13px !important; }
    div[data-testid="stTextInput"] label p { color: #f8fafc !important; font-size: 14px !important; font-weight: 700 !important; }
    div[data-testid="stTextInput"] input::placeholder { color: #9ca3af !important; opacity: 1 !important; }
    div[data-testid="stTextInput"] input:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important; }
    div[data-testid="stTextInput"] div[data-testid="InputInstructions"] { display: none !important; }

    div[data-testid="stButton"] button[kind="primary"] { background: #1d4ed8 !important; border: none !important; border-radius: 8px !important; font-size: 13px !important; font-weight: 600 !important; padding: 0.55rem 1.4rem !important; transition: all 0.2s !important; }
    div[data-testid="stButton"] button[kind="primary"]:hover { background: #2563eb !important; transform: translateY(-1px); }
    div[data-testid="stButton"] button[kind="secondary"] { background: transparent !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; color: #94a3b8 !important; font-size: 12px !important; }

    [data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] { background: #161b27 !important; border: 1px dashed #334155 !important; border-radius: 12px !important; padding: 16px !important; }
    [data-testid="stFileUploaderDropzone"] button { background: #2563eb !important; color: #ffffff !important; border: 1px solid #3b82f6 !important; border-radius: 8px !important; font-size: 14px !important; font-weight: 700 !important; opacity: 1 !important; -webkit-text-fill-color: #ffffff !important; }
    [data-testid="stFileUploaderDropzone"] button * { color: #ffffff !important; fill: #ffffff !important; }
    [data-testid="stFileUploaderFileName"] { color: #ffffff !important; font-size: 14px !important; font-weight: 600 !important; opacity: 1 !important; -webkit-text-fill-color: #ffffff !important; display: block !important; visibility: visible !important; }
    [data-testid="stFileUploaderFile"] { background: #161b27 !important; border: 1px solid #334155 !important; border-radius: 10px !important; color: #ffffff !important; display: block !important; }
    [data-testid="stFileUploaderFile"] * { color: #ffffff !important; fill: #ffffff !important; -webkit-text-fill-color: #ffffff !important; visibility: visible !important; }
    [data-testid="stFileDropzoneInstructions"] small, [data-testid="stFileUploaderDropzone"] small { color: #f8fafc !important; font-size: 13px !important; font-weight: 600 !important; opacity: 1 !important; -webkit-text-fill-color: #f8fafc !important; }
    [data-testid="stFileUploaderDropzone"] div, [data-testid="stFileUploaderDropzone"] p, [data-testid="stFileUploaderDropzone"] span, [data-testid="stFileUploaderDropzone"] label { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; visibility: visible !important; opacity: 1 !important; }
    [data-testid="stFileUploaderDropzone"] * { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1 !important; visibility: visible !important; }
    [data-testid="stFileUploaderDropzone"] input[type="text"] { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; background: #0d1117 !important; border: 1px solid #2d3748 !important; opacity: 1 !important; visibility: visible !important; }
    [data-testid="stFileUploader"] input[type="text"] { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1 !important; }
    [data-testid="stFileUploader"] input { color: #ffffff !important; caret-color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1 !important; }
    [data-testid="stFileUploader"] input::placeholder { color: #9ca3af !important; opacity: 0.7 !important; }
    [data-testid="stFileUploaderDropzone"] [role="button"] span { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
    [data-testid="stFileUploader"]::before, [data-testid="stFileUploader"]::after { color: #ffffff !important; }

    div[data-testid="stDataFrame"] { border: 1px solid #1e2a3a !important; border-radius: 10px !important; overflow: hidden; }
    div[data-testid="stToggle"] { accent-color: #3b82f6; }
    div[data-testid="stProgress"] > div > div { background: #3b82f6 !important; }

    .screenshot-label-a { font-size: 11px; font-weight: 600; color: #60a5fa; text-align: center; padding: 6px 0; border-bottom: 2px solid #3b82f6; margin-bottom: 8px; }
    .screenshot-label-b { font-size: 11px; font-weight: 600; color: #34d399; text-align: center; padding: 6px 0; border-bottom: 2px solid #10b981; margin-bottom: 8px; }

    .stApp { background: #0d1117; }
    .stApp > * { color: #e2e8f0; }

    div[data-testid="stSelectbox"] span,
    div[data-testid="stSelectbox"] div[class*="ValueContainer"] *,
    div[data-testid="stSelectbox"] div[class*="singleValue"],
    div[data-testid="stSelectbox"] div[class*="placeholder"] { color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important; opacity: 1 !important; }

    div[data-testid="stRadio"] label p,
    div[data-testid="stRadio"] label span,
    div[data-testid="stRadio"] div { color: #e2e8f0 !important; -webkit-text-fill-color: #e2e8f0 !important; opacity: 1 !important; }

    div[data-testid="stExpander"] { background: #161b27 !important; border: 1px solid #1e2a3a !important; border-radius: 10px !important; }
    div[data-testid="stExpander"] summary { background: #161b27 !important; border-radius: 10px !important; padding: 12px 16px !important; }
    div[data-testid="stExpander"] summary:hover { background: #1e2a3a !important; }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary p,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary svg,
    div[data-testid="stExpander"] details > summary span { color: #f1f5f9 !important; -webkit-text-fill-color: #f1f5f9 !important; opacity: 1 !important; font-weight: 600 !important; font-size: 13px !important; }
    div[data-testid="stDownloadButton"] button { background: #2563eb !important; color: #ffffff !important; border: none !important; border-radius: 8px !important; font-size: 13px !important; font-weight: 600 !important; }
    div[data-testid="stDownloadButton"] button * { color: #ffffff !important; fill: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1 !important; }
    div[data-testid="stDownloadButton"] button:hover { background: #1d4ed8 !important; }</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════
if "mode" not in st.session_state:
    st.session_state.mode = "single"
if "results" not in st.session_state:
    st.session_state.results = []
if "report_path" not in st.session_state:
    st.session_state.report_path = None
if "history" not in st.session_state:
    st.session_state.history = []

output_folder = os.path.join(tempfile.gettempdir(), "qa_comparison_reports")
os.makedirs(output_folder, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    col_logo, col_title = st.columns([1, 2.5])
    with col_logo:
        st.image("agent.jpeg", width=56)
    with col_title:
        st.markdown("""
            <div class="logo-title">Comparison Agent</div>
            <div class="logo-sub">QA Platform · v2.0</div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown('<div class="nav-section">Mode</div>', unsafe_allow_html=True)
    mode = st.radio(
        "Comparison mode",
        options=["Single URL Pair", "Batch Upload (Excel)"],
        index=0 if st.session_state.mode == "single" else 1,
        label_visibility="collapsed"
    )
    st.session_state.mode = "single" if mode == "Single URL Pair" else "batch"

    st.markdown("---")

    st.markdown('<div class="nav-section">What to compare</div>', unsafe_allow_html=True)
    check_content = st.toggle("Content diff",  value=True)
    check_links   = st.toggle("Link Audit",    value=True)
    check_images  = st.toggle("Image diff",    value=True)
    check_health  = st.toggle("Page Health",   value=True)
    check_shots   = st.toggle("Screenshots",   value=False)

    st.markdown("---")

    st.markdown('<div class="nav-section">Authentication</div>', unsafe_allow_html=True)
    requires_auth = st.toggle("Requires auth", value=False)
    if requires_auth:
        auth_user = st.text_input("Username", placeholder="user@domain.com")
        auth_pass = st.text_input("Password", type="password", placeholder="••••••••")
    else:
        auth_user = ""
        auth_pass = ""

    st.markdown("---")

    st.markdown('<div class="nav-section">Email Report</div>', unsafe_allow_html=True)
    send_email = st.selectbox(
        "Send email after comparison?",
        options=["No", "Yes"],
        label_visibility="collapsed"
    )
    if send_email == "Yes":
        email_recipient = st.text_input(
            "Recipient email",
            placeholder="team@yourcompany.com",
            label_visibility="collapsed"
        )
        try:
            _sender = st.secrets["EMAIL_SENDER"]
            st.caption(f"✅ Sending from: {_sender}")
        except Exception:
            st.error("❌ EMAIL_SENDER secret not found")
    else:
        email_recipient = None

    st.markdown("---")

    st.markdown('<div class="nav-section">Recent History</div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.caption("No comparisons run yet.")
    else:
        recent = list(reversed(st.session_state.history))[:5]
        for h in recent:
            icon   = "✅" if h["status"] == "PASS" else "❌"
            name   = h["test_name"][:22] + "…" if len(h["test_name"]) > 22 else h["test_name"]
            htime  = h["datetime"].split(" ")[1]
            issues = h["total_issues"]
            st.markdown(
                '<div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 10px;margin-bottom:6px;font-size:11px;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:3px;"><span style="color:#f1f5f9;font-weight:600;">{icon} {name}</span><span style="color:#4b5563;">{htime}</span></div>'
                f'<div style="color:#6b7280;">{issues} issue(s) · {h["status"]}</div>'
                '</div>',
                unsafe_allow_html=True
            )
        if st.button("🗑 Clear History", use_container_width=True):
            st.session_state.history = []
            st.rerun()

    st.markdown("---")
    st.caption("© 2026 QA Comparison Agent")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AREA HEADER
# ═══════════════════════════════════════════════════════════════════════════════
header_col, badge_col = st.columns([5, 1])
with header_col:
    st.markdown("""
    <div class="page-header">
        <div>
            <h1>🔍 QA Page Comparison Agent</h1>
            <p>Detect content, link, and image differences between two URLs automatically.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
with badge_col:
    st.markdown('<br><span class="badge-ai">✦ AI-powered</span>', unsafe_allow_html=True)

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# MODE: SINGLE URL PAIR
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.mode == "single":

    st.markdown('<div class="section-label">Comparison targets</div>', unsafe_allow_html=True)

    col_a, col_vs, col_b = st.columns([10, 1, 10])
    with col_a:
        st.markdown('<div class="url-label-a"><span class="dot-a"></span> URL A </div>', unsafe_allow_html=True)
        url_a = st.text_input("url_a", placeholder="https://uat.example.com/page", label_visibility="collapsed")
    with col_vs:
        st.markdown("<br><br><div style='text-align:center;color:#4b5563;font-weight:700;'>VS</div>", unsafe_allow_html=True)
    with col_b:
        st.markdown('<div class="url-label-b"><span class="dot-b"></span> URL B </div>', unsafe_allow_html=True)
        url_b = st.text_input("url_b", placeholder="https://prod.example.com/page", label_visibility="collapsed")

    test_name = st.text_input("Test name (optional)", placeholder="e.g. Homepage comparison")

    run_col, _ = st.columns([2, 6])
    with run_col:
        run_single = st.button("🚀  Run Comparison", type="primary", use_container_width=True)

    if run_single:
        if not url_a or not url_b:
            st.error("Please enter both URL A and URL B before running.")
            st.stop()

        test_cases = [{
            "TEST_NAME":   test_name or "Single URL comparison",
            "URL_A":       url_a,
            "URL_B":       url_b,
        }]
        if requires_auth:
            test_cases[0]["AUTH_TYPE"]   = "basic"
            test_cases[0]["CREDENTIALS"] = f"{auth_user}:{auth_pass}"

        screenshot_dir = None
        if check_shots:
            screenshot_dir = os.path.join(output_folder, "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)

        with st.spinner("Analysing pages…"):
            try:
                agent   = QAComparisonAgent()
                results = []
                prog    = st.progress(0)
                for i, tc in enumerate(test_cases):
                    res = agent.compare_pages(tc, screenshot_dir=screenshot_dir)
                    results.append(res)
                    prog.progress((i + 1) / len(test_cases))

                st.session_state.results     = results
                st.session_state.report_path = HtmlReportGenerator().generate(results, output_folder)

                post_run_actions(results, send_email, email_recipient)
                logger.info(f"Report at: {st.session_state.report_path}")

            except Exception as e:
                st.error(f"Error: {e}")
                logger.error(e)


# ═══════════════════════════════════════════════════════════════════════════════
# MODE: BATCH UPLOAD
# ═══════════════════════════════════════════════════════════════════════════════
else:
    st.markdown('<div class="section-label">Batch upload</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="upload-zone">
        <b>Upload your Excel test cases file (.xlsx)</b><br>
        Required columns: <code>TEST_NAME</code>, <code>URL_A</code> / <code>UAT_URL</code>, <code>URL_B</code> / <code>PROD_URL</code>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("")

# ── Sample file download ───────────────────────────────────────────────
    st.markdown('<div class="section-label">Need a template?</div>', unsafe_allow_html=True)

    sample_data = {
        "TEST_NAME": ["Homepage Comparison", "About Page", "Products Page"],
        "URL_A":     ["https://uat.example.com/", "https://uat.example.com/about", "https://uat.example.com/products"],
        "URL_B":     ["https://www.example.com/", "https://www.example.com/about", "https://www.example.com/products"],
        "PRIORITY":  ["High", "Medium", "Low"],
    }

    import io
    sample_df     = pd.DataFrame(sample_data)
    sample_buffer = io.BytesIO()
    with pd.ExcelWriter(sample_buffer, engine="openpyxl") as writer:
        sample_df.to_excel(writer, index=False, sheet_name="Test Cases")
    sample_buffer.seek(0)

    dl_col, _ = st.columns([2, 6])
    with dl_col:
        st.download_button(
            "📥 Download Sample File",
            data=sample_buffer,
            file_name="sample_test_cases.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    st.markdown("")

    # Initialize session state for file upload
    if "file_uploader_key" not in st.session_state:
        st.session_state.file_uploader_key = 0

    # Dynamic key that changes when user clicks Remove
    uploader_key = f"file_uploader_{st.session_state.file_uploader_key}"
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"], label_visibility="collapsed", key=uploader_key)

    # Remove button directly below file uploader
    if uploaded_file:
        col1, col2 = st.columns([2, 1])
        with col1:
            pass  # Empty space
        with col2:
            if st.button("Remove", type="secondary", use_container_width=True):
                st.session_state.file_uploader_key += 1
                st.rerun()

    if uploaded_file:
        st.success(f"✅ **{uploaded_file.name}** uploaded successfully")

        run_col, _ = st.columns([2, 6])
        with run_col:
            run_batch = st.button("🚀  Run Batch QA", type="primary", use_container_width=True)

        if run_batch:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            screenshot_dir = None
            if check_shots:
                screenshot_dir = os.path.join(output_folder, "screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)

            with st.spinner("Running batch comparisons…"):
                try:
                    excel      = ExcelParser(tmp_path)
                    test_cases = excel.parse()

                    if not test_cases:
                        st.warning("No test cases found. Check your Excel columns.")
                        st.stop()

                    if requires_auth:
                        for tc in test_cases:
                            tc["AUTH_TYPE"]   = "basic"
                            tc["CREDENTIALS"] = f"{auth_user}:{auth_pass}"

                    st.info(f"Found **{len(test_cases)}** test case(s). Running comparisons…")

                    agent   = QAComparisonAgent()
                    results = []
                    prog    = st.progress(0)
                    status  = st.empty()

                    for i, tc in enumerate(test_cases):
                        name = tc.get("TEST_NAME") or f"Test {i+1}"
                        status.caption(f"Running: {name}  ({i+1}/{len(test_cases)})")
                        res = agent.compare_pages(tc, screenshot_dir=screenshot_dir)
                        results.append(res)
                        prog.progress((i + 1) / len(test_cases))

                    status.caption("✅ All comparisons complete.")
                    st.session_state.results     = results
                    st.session_state.report_path = HtmlReportGenerator().generate(results, output_folder)

                    post_run_actions(results, send_email, email_recipient)
                    logger.info(f"Report at: {st.session_state.report_path}")

                except Exception as e:
                    st.error(f"Error: {e}")
                    logger.error(e)

                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
    else:
        st.info("👆 Upload your `.xlsx` file to get started with batch comparisons.")


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS SECTION
# ═══════════════════════════════════════════════════════════════════════════════
results     = st.session_state.get("results", [])
report_path = st.session_state.get("report_path")

if results:
    st.divider()

    total      = len(results)
    passed     = sum(1 for r in results if r.get("status") == "PASS")
    failed     = total - passed
    pass_rate  = int((passed / total) * 100) if total else 0
    all_issues = sum(
        len(r.get("content_issues", [])) +
        len(r.get("link_issues",    [])) +
        len(r.get("image_issues",   []))
        for r in results
    )

    insight = (
        f"All <strong>{total}</strong> page(s) match perfectly — no differences detected."
        if failed == 0 else
        f"Found <strong>{all_issues} issue(s)</strong> across <strong>{failed}</strong> "
        f"failing page(s) out of {total} total."
    )

    st.markdown(f'<div class="ai-banner"><span class="ai-icon">✦</span><div>{insight}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">Overview</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="mlabel">Total checks</div><div class="mval">{total}</div><div class="msub">pages compared</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card pass"><div class="mlabel">Passed</div><div class="mval">{passed}</div><div class="msub">{pass_rate}% pass rate</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card fail"><div class="mlabel">Failed</div><div class="mval">{failed}</div><div class="msub">need review</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card warn"><div class="mlabel">Issues found</div><div class="mval">{all_issues}</div><div class="msub">across all checks</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if report_path and os.path.exists(report_path):
        dl_col, _ = st.columns([2, 6])
        with dl_col:
            with open(report_path, "r", encoding="utf-8") as f:
                st.download_button(
                    "📥  Download HTML Report",
                    data=f.read(),
                    file_name="qa_report.html",
                    mime="text/html",
                    use_container_width=True,
                    type="primary"
                )

    st.divider()

    # ── Results Summary Cards ────────────────────────────────────────────────
    st.markdown('<div class="section-label">Results summary</div>', unsafe_allow_html=True)

    for r in results:
        s  = r.get("status", "N/A")
        ph = r.get("page_health", {})

        ci_count  = len(r.get("content_issues", []))
        li_count  = len(r.get("link_issues",    []))
        ii_count  = len(r.get("image_issues",   []))
        ti_count  = len(ph.get("title_issues",  []))
        si_count  = len(ph.get("status_issues", []))
        ssl_count = len(ph.get("ssl_issues",    []))
        total_iss = ci_count + li_count + ii_count + ti_count + si_count + ssl_count

        status_color  = "#34d399" if s == "PASS" else "#f87171"
        status_bg     = "rgba(16,185,129,0.10)" if s == "PASS" else "rgba(239,68,68,0.10)"
        status_border = "#10b981" if s == "PASS" else "#ef4444"
        status_icon   = "✅" if s == "PASS" else "❌"
        ci_color      = "#f87171" if ci_count  > 0 else "#34d399"
        li_color      = "#f87171" if li_count  > 0 else "#34d399"
        ii_color      = "#f87171" if ii_count  > 0 else "#34d399"
        ti_color      = "#f87171" if ti_count  > 0 else "#34d399"
        si_color      = "#f87171" if si_count  > 0 else "#34d399"
        ssl_color     = "#f87171" if ssl_count > 0 else "#34d399"
        tot_color     = "#f87171" if total_iss > 0 else "#34d399"
        tot_border    = "#ef4444" if total_iss > 0 else "#10b981"
        url_a_val     = r.get("url_a", "N/A")
        url_b_val     = r.get("url_b", "N/A")
        tname         = r.get("test_name", "N/A")

        card = (
            '<div style="background:#161b27;border:1px solid #1e2a3a;border-radius:12px;padding:20px;margin-bottom:14px;">'
                '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">'
                    f'<div style="font-size:15px;font-weight:700;color:#f1f5f9;">🧪 {tname}</div>'
                    f'<span style="background:{status_bg};border:1px solid {status_border};color:{status_color};font-size:12px;font-weight:700;padding:5px 14px;border-radius:99px;">{status_icon} {s}</span>'
                '</div>'
                '<div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">'
                    '<div style="flex:1;min-width:200px;background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:10px 14px;">'
                        '<div style="font-size:10px;font-weight:700;color:#60a5fa;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">● URL A</div>'
                        f'<div style="font-size:12px;color:#93c5fd;font-family:monospace;word-break:break-all;">{url_a_val}</div>'
                    '</div>'
                    '<div style="flex:1;min-width:200px;background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:10px 14px;">'
                        '<div style="font-size:10px;font-weight:700;color:#34d399;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">● URL B</div>'
                        f'<div style="font-size:12px;color:#6ee7b7;font-family:monospace;word-break:break-all;">{url_b_val}</div>'
                    '</div>'
                '</div>'
                '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
                    f'<div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 14px;text-align:center;min-width:80px;"><div style="font-size:18px;font-weight:700;color:{ci_color};">{ci_count}</div><div style="font-size:10px;color:#6b7280;margin-top:2px;">Content</div></div>'
                    f'<div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 14px;text-align:center;min-width:80px;"><div style="font-size:18px;font-weight:700;color:{li_color};">{li_count}</div><div style="font-size:10px;color:#6b7280;margin-top:2px;">Links</div></div>'
                    f'<div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 14px;text-align:center;min-width:80px;"><div style="font-size:18px;font-weight:700;color:{ii_color};">{ii_count}</div><div style="font-size:10px;color:#6b7280;margin-top:2px;">Images</div></div>'
                    f'<div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 14px;text-align:center;min-width:80px;"><div style="font-size:18px;font-weight:700;color:{ti_color};">{ti_count}</div><div style="font-size:10px;color:#6b7280;margin-top:2px;">Titles</div></div>'
                    f'<div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 14px;text-align:center;min-width:80px;"><div style="font-size:18px;font-weight:700;color:{si_color};">{si_count}</div><div style="font-size:10px;color:#6b7280;margin-top:2px;">Status</div></div>'
                    f'<div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 14px;text-align:center;min-width:80px;"><div style="font-size:18px;font-weight:700;color:{ssl_color};">{ssl_count}</div><div style="font-size:10px;color:#6b7280;margin-top:2px;">SSL</div></div>'
                    f'<div style="background:#0d1117;border:1px solid {tot_border};border-radius:8px;padding:8px 14px;text-align:center;min-width:80px;"><div style="font-size:18px;font-weight:700;color:{tot_color};">{total_iss}</div><div style="font-size:10px;color:#6b7280;margin-top:2px;">Total</div></div>'
                '</div>'
            '</div>'
        )
        st.markdown(card, unsafe_allow_html=True)

    st.divider()

    # ── Detailed Issues ──────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Detailed issues</div>', unsafe_allow_html=True)

    filter_opt = st.radio(
        "Show",
        options=["All", "Failed only", "Passed only"],
        horizontal=True,
        label_visibility="collapsed"
    )

    for r in results:
        status_val = r.get("status", "N/A")
        if filter_opt == "Failed only" and status_val != "FAIL":
            continue
        if filter_opt == "Passed only" and status_val != "PASS":
            continue

        icon      = "✅" if status_val == "PASS" else "❌"
        test_name = r.get("test_name", "N/A")
        ci        = r.get("content_issues", [])
        li        = r.get("link_issues",    [])
        ii        = r.get("image_issues",   [])
        total_iss = len(ci) + len(li) + len(ii)
        shot_a    = r.get("screenshot_a")
        shot_b    = r.get("screenshot_b")

        with st.expander(f"{icon}  {test_name}  —  {status_val}  ·  {total_iss} issue(s)"):

            ca, cb = st.columns(2)
            with ca:
                st.markdown("**URL A**")
                st.code(r.get("url_a", "N/A"), language=None)
            with cb:
                st.markdown("**URL B**")
                st.code(r.get("url_b", "N/A"), language=None)

            if check_shots:
                st.markdown("#### Screenshots")
                s1, s2 = st.columns(2)
                with s1:
                    st.markdown('<div class="screenshot-label-a">URL A</div>', unsafe_allow_html=True)
                    if shot_a and os.path.exists(shot_a):
                        st.image(shot_a, use_container_width=True)
                    else:
                        st.caption("Screenshot not available")
                with s2:
                    st.markdown('<div class="screenshot-label-b">URL B</div>', unsafe_allow_html=True)
                    if shot_b and os.path.exists(shot_b):
                        st.image(shot_b, use_container_width=True)
                    else:
                        st.caption("Screenshot not available")

            # Content
            st.markdown("#### Content differences")
            st.markdown('<div class="issue-section">', unsafe_allow_html=True)
            if ci:
                for issue in ci:
                    side  = issue.get("side", "?")
                    text  = issue.get("text", "")
                    css   = "issue-item-a" if side == "A" else "issue-item-b"
                    label = "URL A" if side == "A" else "URL B"
                    st.markdown(f'<div class="{css}"><strong>{label}</strong>: {text}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="no-issue">✓ No content differences</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Links
            st.markdown("#### Link Audit")
            st.markdown('<div class="issue-section">', unsafe_allow_html=True)
            if li:
                for issue in li:
                    st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="no-issue">✓ No link issues found</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Images
            st.markdown("#### Image differences")
            st.markdown('<div class="issue-section">', unsafe_allow_html=True)
            if ii:
                for issue in ii:
                    st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="no-issue">✓ No image differences</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Page Health
            ph = r.get("page_health", {})
            if ph:
                st.markdown("#### Page Health")

                # Status Codes
                st.markdown('<div class="issue-section">', unsafe_allow_html=True)
                st.markdown("**Status Codes**")
                sa = ph.get("status_a", 0)
                sb = ph.get("status_b", 0)
                col1, col2 = st.columns(2)
                with col1:
                    color = "#34d399" if sa == 200 else "#f87171"
                    st.markdown(f'<div class="issue-item-a">URL A — <strong style="color:{color}">{sa}</strong></div>', unsafe_allow_html=True)
                with col2:
                    color = "#34d399" if sb == 200 else "#f87171"
                    st.markdown(f'<div class="issue-item-b">URL B — <strong style="color:{color}">{sb}</strong></div>', unsafe_allow_html=True)
                for issue in ph.get("status_issues", []):
                    st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # Page Titles
                st.markdown('<div class="issue-section">', unsafe_allow_html=True)
                st.markdown("**Page Titles**")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f'<div class="issue-item-a">URL A — {ph.get("title_a", "N/A")}</div>', unsafe_allow_html=True)
                with col2:
                    st.markdown(f'<div class="issue-item-b">URL B — {ph.get("title_b", "N/A")}</div>', unsafe_allow_html=True)
                for issue in ph.get("title_issues", []):
                    st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # SSL
                st.markdown('<div class="issue-section">', unsafe_allow_html=True)
                st.markdown("**SSL Certificates**")
                ssl_a = ph.get("ssl_a", {})
                ssl_b = ph.get("ssl_b", {})
                col1, col2 = st.columns(2)
                with col1:
                    if ssl_a.get("valid"):
                        st.markdown(f'<div class="issue-item-a">URL A — ✅ Valid · Expires {ssl_a.get("expires")} ({ssl_a.get("days_left")} days)</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="issue-item-warn">URL A — ❌ {ssl_a.get("reason")}</div>', unsafe_allow_html=True)
                with col2:
                    if ssl_b.get("valid"):
                        st.markdown(f'<div class="issue-item-b">URL B — ✅ Valid · Expires {ssl_b.get("expires")} ({ssl_b.get("days_left")} days)</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="issue-item-warn">URL B — ❌ {ssl_b.get("reason")}</div>', unsafe_allow_html=True)
                for issue in ph.get("ssl_issues", []):
                    st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # Heading Structure
                st.markdown('<div class="issue-section">', unsafe_allow_html=True)
                st.markdown("**Heading Structure (H1 / H2 / H3)**")
                heads_a = ph.get("headings_a", {})
                heads_b = ph.get("headings_b", {})
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown('<div style="font-size:11px;font-weight:700;color:#60a5fa;margin-bottom:6px;">URL A</div>', unsafe_allow_html=True)
                    for level in ["h1", "h2", "h3"]:
                        items = heads_a.get(level, [])
                        if items:
                            for h in items:
                                st.markdown(f'<div class="issue-item-a"><strong>{level.upper()}</strong>: {h}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div style="font-size:11px;color:#4b5563;padding:2px 0;">No {level.upper()} found</div>', unsafe_allow_html=True)
                with col2:
                    st.markdown('<div style="font-size:11px;font-weight:700;color:#34d399;margin-bottom:6px;">URL B</div>', unsafe_allow_html=True)
                    for level in ["h1", "h2", "h3"]:
                        items = heads_b.get(level, [])
                        if items:
                            for h in items:
                                st.markdown(f'<div class="issue-item-b"><strong>{level.upper()}</strong>: {h}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div style="font-size:11px;color:#4b5563;padding:2px 0;">No {level.upper()} found</div>', unsafe_allow_html=True)
                heading_issues = ph.get("heading_issues", [])
                if heading_issues:
                    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
                    for issue in heading_issues:
                        st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="no-issue">✓ Heading structure matches</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)


# ─── Empty state ─────────────────────────────────────────────────────────────
elif not results:
    st.markdown("""
    <div style="text-align:center; padding: 80px 0 60px; color:#4b5563;">
        <div style="font-size:48px; margin-bottom:16px;">🔍</div>
        <div style="font-size:16px; font-weight:600; color:#94a3b8; margin-bottom:8px;">Ready to compare</div>
        <div style="font-size:13px; color:#6b7280; max-width:380px; margin:0 auto;">
            Enter two URLs above and click <strong style="color:#93c5fd;">Run Comparison</strong>,
            or switch to Batch mode to upload an Excel file.
        </div>
    </div>
    """, unsafe_allow_html=True)