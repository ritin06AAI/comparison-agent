from datetime import datetime
import os
import tempfile
import pandas as pd
import streamlit as st

from utils.logger import setup_logger
from agents.qa_agent import QAComparisonAgent
from utils.excel_parser import ExcelParser
from reporting.html_report_generator import HtmlReportGenerator

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = setup_logger(__name__)

def send_email_report(recipient: str, results: list):
    """Send QA comparison results via email."""
    try:
        sender   = st.secrets["EMAIL_SENDER"]
        password = st.secrets["EMAIL_PASSWORD"]

        total  = len(results)
        passed = sum(1 for r in results if r.get("status") == "PASS")
        failed = total - passed

        rows = ""
        for r in results:
            ph           = r.get("page_health", {})
            total_issues = (
                len(r.get("content_issues", [])) +
                len(r.get("link_issues",    [])) +
                len(r.get("image_issues",   [])) +
                len(ph.get("title_issues",  [])) +
                len(ph.get("status_issues", [])) +
                len(ph.get("ssl_issues",    []))
            )
            status  = r.get("status", "N/A")
            color   = "#34d399" if status == "PASS" else "#f87171"
            rows   += f"""
            <tr>
                <td style="padding:8px; border-bottom:1px solid #1e2a3a;">{r.get("test_name", "N/A")}</td>
                <td style="padding:8px; border-bottom:1px solid #1e2a3a; color:{color};"><b>{status}</b></td>
                <td style="padding:8px; border-bottom:1px solid #1e2a3a;">{r.get("url_a", "N/A")}</td>
                <td style="padding:8px; border-bottom:1px solid #1e2a3a;">{r.get("url_b", "N/A")}</td>
                <td style="padding:8px; border-bottom:1px solid #1e2a3a;">{total_issues}</td>
            </tr>
            """

        html_body = f"""
        <html>
        <body style="font-family:Arial,sans-serif; background:#0d1117; color:#e2e8f0; padding:24px;">
            <div style="max-width:800px; margin:0 auto;">
                <h2 style="color:#f1f5f9;">🔍 QA Comparison Report</h2>
                <div style="display:flex; gap:16px; margin-bottom:24px;">
                    <div style="background:#161b27; border:1px solid #1e2a3a; border-radius:10px; padding:16px 24px; text-align:center;">
                        <div style="font-size:28px; font-weight:700; color:#f1f5f9;">{total}</div>
                        <div style="font-size:12px; color:#6b7280;">Total</div>
                    </div>
                    <div style="background:#161b27; border:1px solid #1e2a3a; border-radius:10px; padding:16px 24px; text-align:center;">
                        <div style="font-size:28px; font-weight:700; color:#34d399;">{passed}</div>
                        <div style="font-size:12px; color:#6b7280;">Passed</div>
                    </div>
                    <div style="background:#161b27; border:1px solid #1e2a3a; border-radius:10px; padding:16px 24px; text-align:center;">
                        <div style="font-size:28px; font-weight:700; color:#f87171;">{failed}</div>
                        <div style="font-size:12px; color:#6b7280;">Failed</div>
                    </div>
                </div>
                <table style="width:100%; border-collapse:collapse; background:#161b27; border:1px solid #1e2a3a; border-radius:10px;">
                    <thead>
                        <tr style="background:#1e2a3a;">
                            <th style="padding:10px; text-align:left; color:#94a3b8; font-size:12px;">Test Name</th>
                            <th style="padding:10px; text-align:left; color:#94a3b8; font-size:12px;">Status</th>
                            <th style="padding:10px; text-align:left; color:#94a3b8; font-size:12px;">URL A</th>
                            <th style="padding:10px; text-align:left; color:#94a3b8; font-size:12px;">URL B</th>
                            <th style="padding:10px; text-align:left; color:#94a3b8; font-size:12px;">Issues</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
                <p style="color:#4b5563; font-size:12px; margin-top:24px;">
                    Sent by QA Comparison Agent · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                </p>
            </div>
        </body>
        </html>
        """

        msg            = MIMEMultipart("alternative")
        msg["Subject"] = f"QA Report — {passed}/{total} Passed · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        msg["From"]    = sender
        msg["To"]      = recipient
        msg.attach(MIMEText(html_body, "html"))

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


# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QA Comparison Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px; }
    [data-testid="stSidebar"] { background: #0f1117; border-right: 1px solid #1e2130; }
    [data-testid="stSidebar"] * { color: #c8ccd8 !important; }
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
    div[data-testid="stButton"] button[kind="primary"] { background: #1d4ed8 !important; border: none !important; border-radius: 8px !important; font-size: 13px !important; font-weight: 600 !important; padding: 0.55rem 1.4rem !important; }
    div[data-testid="stButton"] button[kind="primary"]:hover { background: #2563eb !important; }
    div[data-testid="stButton"] button[kind="secondary"] { background: transparent !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; color: #94a3b8 !important; font-size: 12px !important; }
    [data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] { background: #161b27 !important; border: 1px dashed #334155 !important; border-radius: 12px !important; padding: 16px !important; }
    div[data-testid="stDataFrame"] { border: 1px solid #1e2a3a !important; border-radius: 10px !important; overflow: hidden; }
    div[data-testid="stToggle"] { accent-color: #3b82f6; }
    div[data-testid="stProgress"] > div > div { background: #3b82f6 !important; }
    .screenshot-label-a { font-size: 11px; font-weight: 600; color: #60a5fa; text-align: center; padding: 6px 0; border-bottom: 2px solid #3b82f6; margin-bottom: 8px; }
    .screenshot-label-b { font-size: 11px; font-weight: 600; color: #34d399; text-align: center; padding: 6px 0; border-bottom: 2px solid #10b981; margin-bottom: 8px; }
    .stApp { background: #0d1117; }
    .stApp > * { color: #e2e8f0; }
    div[data-testid="stSelectbox"] > div > div { background: #0d1117 !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; color: #e2e8f0 !important; }
    div[data-testid="stSelectbox"] > div > div > div { color: #e2e8f0 !important; }
    [data-baseweb="select"] * { background: #0d1117 !important; color: #e2e8f0 !important; }
    div[data-testid="stTextInput"] div[data-testid="InputInstructions"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ─── Session state defaults ──────────────────────────────────────────────────
if "mode" not in st.session_state:
    st.session_state.mode = "single"
if "results" not in st.session_state:
    st.session_state.results = []
if "report_path" not in st.session_state:
    st.session_state.report_path = None
if "history" not in st.session_state:
    st.session_state.history = []

# ─── Output folder ───────────────────────────────────────────────────────────
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
        except Exception as e:
            st.error(f"❌ Secret not found: {e}")
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
            time   = h["datetime"].split(" ")[1]
            issues = h["total_issues"]
            st.markdown(f"""
            <div style="background:#0d1117;border:1px solid #1e2a3a;border-radius:8px;padding:8px 10px;margin-bottom:6px;font-size:11px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                    <span style="color:#f1f5f9;font-weight:600;">{icon} {name}</span>
                    <span style="color:#4b5563;">{time}</span>
                </div>
                <div style="color:#6b7280;">{issues} issue(s) · {h["status"]}</div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("🗑 Clear History", width='stretch'):
            st.session_state.history = []
            st.rerun()

    st.markdown("---")
    st.caption("© 2026 QA Comparison Agent")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AREA
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
# HELPER: save history + send email (used by both single and batch)
# ═══════════════════════════════════════════════════════════════════════════════
def post_run_actions(results):
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

    # ── Send email ──────────────────────────────────────────────────────────
    if send_email == "Yes" and email_recipient:
        with st.spinner("Sending email report…"):
            success, msg = send_email_report(email_recipient, results)
            if success:
                st.success(f"📧 {msg}")
            else:
                st.error(f"📧 Email failed: {msg}")


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
        run_single = st.button("🚀  Run Comparison", type="primary", width='stretch')

    if run_single:
        if not url_a or not url_b:
            st.error("Please enter both URL A and URL B before running.")
            st.stop()

        test_cases = [{
            "TEST_NAME": test_name or "Single URL comparison",
            "URL_A": url_a,
            "URL_B": url_b,
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

                st.session_state.results    = results
                st.session_state.report_path = HtmlReportGenerator().generate(results, output_folder)

                post_run_actions(results)  # ← history + email

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

    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file:
        st.success(f"✅ **{uploaded_file.name}** uploaded successfully")

        run_col, _ = st.columns([2, 6])
        with run_col:
            run_batch = st.button("🚀  Run Batch QA", type="primary", width='stretch')

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

                    post_run_actions(results)  # ← history + email

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
results    = st.session_state.get("results", [])
report_path = st.session_state.get("report_path")

if results:
    st.divider()

    total     = len(results)
    passed    = sum(1 for r in results if r.get("status") == "PASS")
    failed    = total - passed
    pass_rate = int((passed / total) * 100) if total else 0
    all_issues = sum(
        len(r.get("content_issues", [])) +
        len(r.get("link_issues", [])) +
        len(r.get("image_issues", []))
        for r in results
    )

    if failed == 0:
        insight = f"All <strong>{total}</strong> page(s) match perfectly — no differences detected."
    else:
        insight = (
            f"Found <strong>{all_issues} issue(s)</strong> across <strong>{failed}</strong> "
            f"failing page(s) out of {total} total."
        )

    st.markdown(f"""
    <div class="ai-banner">
        <span class="ai-icon">✦</span>
        <div>{insight}</div>
    </div>
    """, unsafe_allow_html=True)

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
                    width='stretch'
                )

    st.divider()

    st.markdown('<div class="section-label">Results summary</div>', unsafe_allow_html=True)
    summary_rows = []
    for r in results:
        s = r.get("status", "N/A")
        summary_rows.append({
            "Test name":      r.get("test_name", "N/A"),
            "Status":         "✅ PASS" if s == "PASS" else "❌ FAIL",
            "URL A":          r.get("url_a", "N/A"),
            "URL B":          r.get("url_b", "N/A"),
            "Content issues": len(r.get("content_issues", [])),
            "Link issues":    len(r.get("link_issues", [])),
            "Image issues":   len(r.get("image_issues", [])),
        })
    st.dataframe(pd.DataFrame(summary_rows), width='stretch', hide_index=True)

    st.divider()

    st.markdown('<div class="section-label">Detailed issues</div>', unsafe_allow_html=True)
    filter_opt = st.radio("Show", options=["All", "Failed only", "Passed only"], horizontal=True, label_visibility="collapsed")

    for r in results:
        status_val = r.get("status", "N/A")
        if filter_opt == "Failed only" and status_val != "FAIL":
            continue
        if filter_opt == "Passed only" and status_val != "PASS":
            continue

        icon      = "✅" if status_val == "PASS" else "❌"
        test_name = r.get("test_name", "N/A")
        ci        = r.get("content_issues", [])
        li        = r.get("link_issues", [])
        ii        = r.get("image_issues", [])
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
                        st.image(shot_a, width='stretch')
                    else:
                        st.caption("Screenshot not available")
                with s2:
                    st.markdown('<div class="screenshot-label-b">URL B</div>', unsafe_allow_html=True)
                    if shot_b and os.path.exists(shot_b):
                        st.image(shot_b, width='stretch')
                    else:
                        st.caption("Screenshot not available")

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

            st.markdown("#### Link Audit")
            st.markdown('<div class="issue-section">', unsafe_allow_html=True)
            if li:
                for issue in li:
                    st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="no-issue">✓ No link issues found</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("#### Image differences")
            st.markdown('<div class="issue-section">', unsafe_allow_html=True)
            if ii:
                for issue in ii:
                    st.markdown(f'<div class="issue-item-warn">{issue}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="no-issue">✓ No image differences</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            ph = r.get("page_health", {})
            if ph:
                st.markdown("#### Page Health")

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