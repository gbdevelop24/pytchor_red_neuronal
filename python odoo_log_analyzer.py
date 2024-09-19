import os
import re
import logging
import unittest
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import json
from typing import List, Dict, Any
import ast

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MANIFEST_FILES = [
    '__manifest__.py',
    '__odoo__.py',
    '__openerp__.py',
    '__terp__.py',
]

class OdooLogAnalyzer:
    def __init__(self, log_path: str, odoo_path: str):
        self.log_path = log_path
        self.odoo_path = odoo_path
        self.modules = {}  # Changed from list to dictionary
        self.error_patterns = defaultdict(int)
        self.dataset = []

    def find_modules(self, path, depth=3):
        if depth == 0:
            return

        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                manifest_path = os.path.join(item_path, '__manifest__.py')
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8', errors='replace') as f:
                            manifest_content = f.read()
                        manifest_dict = ast.literal_eval(manifest_content)  # Safer than eval()
                        self.modules[item] = {  # Use item as key in the modules dictionary
                            'name': item,
                            'path': item_path,
                            'manifest': manifest_dict,
                            'application': manifest_dict.get('application', False),
                            'depends': manifest_dict.get('depends', []),
                            'auto_install': manifest_dict.get('auto_install', False)
                        }
                    except Exception as e:
                        logger.error(f"Error reading manifest for module {item}: {str(e)}")
                else:
                    self.find_modules(item_path, depth - 1)

    def analyze_log(self) -> None:
        with open(self.log_path, 'r') as log_file:
            for line in log_file:
                self.process_log_line(line)

    def process_log_line(self, line: str) -> None:
        error_match = re.search(r'ERROR.*', line)
        if error_match:
            error = error_match.group(0)
            self.error_patterns[error] += 1
            self.dataset.append({"type": "error", "content": error})

        cron_match = re.search(r'.*Running cron.*', line)
        if cron_match:
            cron = cron_match.group(0)
            self.dataset.append({"type": "cron", "content": cron})

    def run_unit_tests(self) -> None:
        for module, info in self.modules.items():
            test_path = os.path.join(info['path'], 'tests')
            if os.path.exists(test_path):
                logger.info(f"Running tests for module: {module}")
                with ThreadPoolExecutor() as executor:
                    executor.submit(self.run_test, module, test_path)

    def run_test(self, module: str, test_path: str) -> None:
        test_loader = unittest.TestLoader()
        test_suite = test_loader.discover(test_path)
        test_runner = unittest.TextTestRunner(verbosity=2)
        result = test_runner.run(test_suite)
        self.dataset.append({
            "type": "test_result",
            "module": module,
            "tests_run": result.testsRun,
            "errors": len(result.errors),
            "failures": len(result.failures)
        })

    def generate_report(self) -> None:
        report = {
            "modules_found": [
                {
                    "name": module,
                    "path": info['path'],
                    "application": info['application'],
                    "depends": info['depends'],
                    "auto_install": info['auto_install']
                }
                for module, info in self.modules.items()
            ],
            "error_patterns": dict(self.error_patterns),
            "dataset": self.dataset
        }
        with open('odoo_analysis_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        logger.info("Report generated: odoo_analysis_report.json")

    def run(self) -> None:
        logger.info("Starting Odoo Log Analyzer")
        self.find_modules(self.odoo_path)
        logger.info(f"Found {len(self.modules)} modules")
        self.analyze_log()
        self.run_unit_tests()
        self.generate_report()
        logger.info("Analysis complete")

if __name__ == "__main__":
    ODOO_LOG_PATH = r"C:\Odoo17E\server\odoo.log"
    ODOO_INSTALLATION_PATH = r"C:\Odoo17E\server"

    analyzer = OdooLogAnalyzer(ODOO_LOG_PATH, ODOO_INSTALLATION_PATH)
    analyzer.run()