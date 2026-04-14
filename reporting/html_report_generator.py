from datetime import datetime
from pathlib import Path
from typing import List, Dict

class HtmlReportGenerator:
    def generate(self, results: List[Dict], output_dir: str) -> str:
        Path(output_dir).mkdir(exist_ok=True, parents=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(output_dir) / f"uat_vs_prod_report_{ts}.html"

        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        overall_status = "PASS" if failed == 0 else "FAIL"

        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html><head><meta charset='utf-8'>")
        html.append("<title>Page Comparison Report</title>")
        html.append("<style>")
        html.append("""
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                background-color: #f5f7fb;
                margin: 0;
                padding: 0;
            }
            .container {
                max-width: 1100px;
                margin: 0 auto;
                padding: 20px 20px 40px;
            }
            .header {
                background: linear-gradient(135deg, #2563eb, #1e40af);
                color: white;
                padding: 20px 25px;
                border-radius: 12px;
                box-shadow: 0 10px 20px rgba(15, 23, 42, 0.3);
                margin-bottom: 24px;
            }
            .header h1 {
                margin: 0 0 8px;
                font-size: 24px;
            }
            .header p {
                margin: 2px 0;
                font-size: 13px;
                opacity: 0.9;
            }
            .badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }
            .badge-pass {
                background-color: #dcfce7;
                color: #166534;
            }
            .badge-fail {
                background-color: #fee2e2;
                color: #b91c1c;
            }
            .summary {
                background-color: white;
                border-radius: 12px;
                padding: 16px 18px;
                box-shadow: 0 4px 10px rgba(15, 23, 42, 0.08);
                margin-bottom: 20px;
            }
            .summary-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 13px;
            }
            .summary-table th {
                text-align: left;
                padding: 6px 0;
                color: #6b7280;
                font-weight: 600;
                border-bottom: 1px solid #e5e7eb;
            }
            .summary-table td {
                padding: 6px 0;
                border-bottom: 1px solid #f3f4f6;
            }
            .status-pass { color: #16a34a; font-weight: 600; }
            .status-fail { color: #dc2626; font-weight: 600; }

            .page-card {
                background-color: white;
                border-radius: 12px;
                padding: 16px 18px 12px;
                box-shadow: 0 4px 10px rgba(15, 23, 42, 0.06);
                margin-bottom: 16px;
            }
            .page-header {
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                margin-bottom: 8px;
            }
            .page-title {
                font-size: 16px;
                font-weight: 600;
                color: #111827;
            }
            .page-status-pass {
                color: #16a34a;
                font-weight: 600;
            }
            .page-status-fail {
                color: #dc2626;
                font-weight: 600;
            }
            .urls {
                font-size: 12px;
                color: #4b5563;
                margin-bottom: 8px;
            }
            .section-row {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
            }
            .section {
                flex: 1 1 250px;
                background-color: #f9fafb;
                border-radius: 8px;
                padding: 10px 12px;
                margin-top: 4px;
            }
            .section h3 {
                margin: 0 0 4px;
                font-size: 13px;
                color: #111827;
            }
            .section-status {
                font-size: 12px;
                margin: 0 0 4px;
            }
            .section-status.pass { color: #16a34a; }
            .section-status.fail { color: #dc2626; }
            .section ul {
                margin: 0;
                padding-left: 18px;
                font-size: 12px;
                color: #374151;
            }
            .section li {
                margin: 2px 0;
            }
            .footer {
                margin-top: 24px;
                font-size: 11px;
                color: #9ca3af;
                text-align: center;
            }
        """)
        html.append("</style></head><body>")
        html.append("<div class='container'>")

        # Header
        html.append("<div class='header'>")
        html.append("<h1>Page Comparison Report</h1>")
        html.append(f"<p>Generated: {datetime.now()}</p>")
        html.append(f"<p>Pages tested: {total} &middot; "
                    f"Passed: {passed} &middot; Failed: {failed}</p>")
        html.append(f"<p>Overall Status: "
                    f"<span class='badge badge-{overall_status.lower()}'>{overall_status}</span></p>")
        html.append("</div>")

        # Summary block
        html.append("<div class='summary'>")
        html.append("<table class='summary-table'>")
        html.append("<tr><th>Metric</th><th>Value</th></tr>")
        html.append(f"<tr><td>Total pages</td><td>{total}</td></tr>")
        html.append(f"<tr><td>Passed</td><td class='status-pass'>{passed}</td></tr>")
        html.append(f"<tr><td>Failed</td><td class='status-fail'>{failed}</td></tr>")
        html.append(f"<tr><td>Overall status</td>"
                    f"<td><span class='badge badge-{overall_status.lower()}'>{overall_status}</span></td></tr>")
        html.append("</table>")
        html.append("</div>")

        # Per-page cards
        for r in results:
            status_class = "page-status-pass" if r["status"] == "PASS" else "page-status-fail"
            html.append("<div class='page-card'>")
            html.append("<div class='page-header'>")
            html.append(f"<div class='page-title'>{r['test_name']}</div>")
            html.append(f"<div class='{status_class}'>{r['status']}</div>")
            html.append("</div>")

            html.append("<div class='urls'>")
            html.append(f"<div><b>URL A:</b> {r['url_a']}</div>")
            html.append(f"<div><b>URL B:</b> {r['url_b']}</div>")

            html.append("</div>")

            html.append("<div class='section-row'>")

            # Content section
            content_issues = r.get("content_issues", [])
            html.append("<div class='section'>")
            html.append("<h3>Content</h3>")
            if content_issues:
                html.append("<p class='section-status fail'>Differences found:</p><ul>")
                for d in content_issues:
                    side = "UAT only" if d["side"] == "UAT" else "Prod only"
                    html.append(f"<li>{side}: {d['text']}</li>")
                html.append("</ul>")
            else:
                html.append("<p class='section-status pass'>Content match: no text differences.</p>")
            html.append("</div>")

            # Links section
            link_issues = r.get("link_issues", [])
            html.append("<div class='section'>")
            html.append("<h3>Links</h3>")
            if link_issues:
                html.append("<p class='section-status fail'>Differences found:</p><ul>")
                for issue in link_issues:
                    html.append(f"<li>{issue}</li>")
                html.append("</ul>")
            else:
                html.append("<p class='section-status pass'>Links match: no link differences.</p>")
            html.append("</div>")

            # Images section
            image_issues = r.get("image_issues", [])
            html.append("<div class='section'>")
            html.append("<h3>Images</h3>")
            if image_issues:
                html.append("<p class='section-status fail'>Differences found:</p><ul>")
                for issue in image_issues:
                    html.append(f"<li>{issue}</li>")
                html.append("</ul>")
            else:
                html.append("<p class='section-status pass'>Images match: no image differences.</p>")
            html.append("</div>")

            html.append("</div>")  # section-row
            html.append("</div>")  # page-card

        html.append("<div class='footer'>")
        html.append("Generated by UAT vs Prod QA Agent")
        html.append("</div>")

        html.append("</div></body></html>")
        path.write_text("\n".join(html), encoding="utf-8")
        return str(path)
