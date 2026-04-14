from dotenv import load_dotenv
load_dotenv()

import argparse
from utils.logger import setup_logger
from utils.excel_parser import ExcelParser
from agents.qa_agent import QAComparisonAgent
from reporting.report_generator import ReportGenerator
from reporting.html_report_generator import HtmlReportGenerator
# remove import of ReportGenerator (docx) if you like


logger = setup_logger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Excel file path")
    parser.add_argument("--output", required=True, help="Reports output folder")
    args = parser.parse_args()

    excel = ExcelParser(args.input)
    test_cases = excel.parse()

    agent = QAComparisonAgent()
    results = []

    for tc in test_cases:
        res = agent.compare_pages(tc)
        results.append(res)

    report_path = HtmlReportGenerator().generate(results, args.output)
    logger.info(f"Report generated at: {report_path}")

if __name__ == "__main__":
    main()
