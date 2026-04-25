"""
runner.py — Custom Django Test Runner + CSV Report Generator

Generates all 7 required CSV deliverable sheets:
1. Module_Test_Summary.csv
2. UC_Test_Design.csv
3. BR_Test_Design.csv
4. WF_Test_Design.csv
5. Test_Execution_Log.csv
6. Defect_Log.csv
7. Artifact_Evaluation.csv
"""

import csv
import os
import traceback
from datetime import datetime
from unittest import TestResult

import yaml
from django.test.runner import DiscoverRunner


# ── Paths ──────────────────────────────────────────────────────────────────────

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SPECS_DIR = os.path.join(_THIS_DIR, 'specs')
_REPORTS_DIR = os.path.join(_THIS_DIR, 'reports')


def _ensure_reports_dir():
    os.makedirs(_REPORTS_DIR, exist_ok=True)


def _load_yaml(filename):
    path = os.path.join(_SPECS_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _write_csv(filename, headers, rows):
    path = os.path.join(_REPORTS_DIR, filename)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
    print(f"✅ Generated: {filename}")


# ── Custom TestResult ──────────────────────────────────────────────────────────

class ReportingTestResult(TestResult):
    """Collects per-test metadata for CSV generation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_records = []
        self.tester_name = os.environ.get('TESTER_NAME', 'Tester')

    def _extract_metadata(self, test):
        return {
            'test_id': getattr(test, '_test_id', '') or '',
            'uc_id': getattr(test, '_uc_id', '') or '',
            'br_id': getattr(test, '_br_id', '') or '',
            'wf_id': getattr(test, '_wf_id', '') or '',
            'test_category': getattr(test, '_test_category', '') or '',
            'scenario': getattr(test, '_scenario', '') or '',
            'preconditions': getattr(test, '_preconditions', '') or '',
            'input_action': getattr(test, '_input_action', '') or '',
            'expected_result': getattr(test, '_expected_result', '') or '',
            'results': list(getattr(test, '_results', [])),
            'steps': list(getattr(test, '_steps', [])),
        }

    def addSuccess(self, test):
        super().addSuccess(test)
        meta = self._extract_metadata(test)
        meta['outcome'] = 'Pass'
        meta['error'] = ''
        self.test_records.append(meta)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        meta = self._extract_metadata(test)
        meta['outcome'] = 'Fail'
        meta['error'] = ''.join(traceback.format_exception(*err))
        self.test_records.append(meta)

    def addError(self, test, err):
        super().addError(test, err)
        meta = self._extract_metadata(test)
        meta['outcome'] = 'Error'
        meta['error'] = ''.join(traceback.format_exception(*err))
        self.test_records.append(meta)


# ── Report Generators ──────────────────────────────────────────────────────────

def _generate_module_test_summary(test_records, uc_specs, br_specs, wf_specs):
    """Sheet 1: Module_Test_Summary.csv"""
    
    uc_tests = [r for r in test_records if r['uc_id']]
    br_tests = [r for r in test_records if r['br_id']]
    wf_tests = [r for r in test_records if r['wf_id']]

    total_ucs = len(uc_specs.get('use_cases', []))
    total_brs = len(br_specs.get('business_rules', []))
    total_wfs = len(wf_specs.get('workflows', []))

    required_uc = total_ucs * 3
    required_br = total_brs * 2
    required_wf = total_wfs * 2

    designed_uc = len(set(r['uc_id'] for r in uc_tests))
    designed_br = len(set(r['br_id'] for r in br_tests))
    designed_wf = len(set(r['wf_id'] for r in wf_tests))

    pass_count = len([r for r in test_records if r['outcome'] == 'Pass'])
    partial_count = len([r for r in test_records if r['outcome'] == 'Partial'])
    fail_count = len([r for r in test_records if r['outcome'] in ['Fail', 'Error']])
    total_executed = pass_count + partial_count + fail_count

    strict_pass_rate = (pass_count / total_executed * 100) if total_executed > 0 else 0

    headers = ['Metric', 'Value']
    rows = [
        ['Total Use Cases', total_ucs],
        ['Total Business Rules', total_brs],
        ['Total Workflows', total_wfs],
        ['Required UC Tests', required_uc],
        ['Designed UC Tests', len(uc_tests)],
        ['Required BR Tests', required_br],
        ['Designed BR Tests', len(br_tests)],
        ['Required WF Tests', required_wf],
        ['Designed WF Tests', len(wf_tests)],
        ['UC Adequacy %', f"{(len(uc_tests) / required_uc * 100) if required_uc > 0 else 0:.1f}"],
        ['BR Adequacy %', f"{(len(br_tests) / required_br * 100) if required_br > 0 else 0:.1f}"],
        ['WF Adequacy %', f"{(len(wf_tests) / required_wf * 100) if required_wf > 0 else 0:.1f}"],
        ['Total Tests Executed', total_executed],
        ['Total Pass', pass_count],
        ['Total Partial', partial_count],
        ['Total Fail', fail_count],
        ['Strict Pass Rate %', f"{strict_pass_rate:.1f}"],
    ]

    _write_csv('Module_Test_Summary.csv', headers, rows)


def _generate_uc_test_design(test_records, uc_specs):
    """Sheet 2: UC_Test_Design.csv"""
    
    uc_tests = [r for r in test_records if r['uc_id']]

    headers = ['Test ID', 'UC ID', 'Test Category', 'Scenario', 'Preconditions', 'Input / Action', 'Expected Result']
    rows = []

    for test in sorted(uc_tests, key=lambda x: x['test_id']):
        rows.append([
            test['test_id'],
            test['uc_id'],
            test['test_category'],
            test['scenario'],
            test['preconditions'],
            test['input_action'],
            test['expected_result']
        ])

    _write_csv('UC_Test_Design.csv', headers, rows)


def _generate_br_test_design(test_records, br_specs):
    """Sheet 3: BR_Test_Design.csv"""
    
    br_tests = [r for r in test_records if r['br_id']]

    headers = ['Test ID', 'BR ID', 'Test Category', 'Input / Action', 'Expected Result']
    rows = []

    for test in sorted(br_tests, key=lambda x: x['test_id']):
        rows.append([
            test['test_id'],
            test['br_id'],
            test['test_category'],
            test['input_action'],
            test['expected_result']
        ])

    _write_csv('BR_Test_Design.csv', headers, rows)


def _generate_wf_test_design(test_records, wf_specs):
    """Sheet 4: WF_Test_Design.csv"""
    
    wf_tests = [r for r in test_records if r['wf_id']]

    headers = ['Test ID', 'WF ID', 'Test Category', 'Scenario', 'Expected Final State']
    rows = []

    for test in sorted(wf_tests, key=lambda x: x['test_id']):
        rows.append([
            test['test_id'],
            test['wf_id'],
            test['test_category'],
            test['scenario'],
            test['expected_result']
        ])

    _write_csv('WF_Test_Design.csv', headers, rows)


def _generate_test_execution_log(test_records):
    """Sheet 5: Test_Execution_Log.csv"""
    
    headers = ['Test ID', 'Source Type', 'Source ID', 'Expected Result', 'Actual Result', 'Status', 'Evidence', 'Tester']
    rows = []

    for test in sorted(test_records, key=lambda x: x['test_id']):
        source_type = ''
        source_id = ''
        
        if test['uc_id']:
            source_type = 'Use Case'
            source_id = test['uc_id']
        elif test['br_id']:
            source_type = 'Business Rule'
            source_id = test['br_id']
        elif test['wf_id']:
            source_type = 'Workflow'
            source_id = test['wf_id']

        # Collect evidence from results
        evidence = ' | '.join([f"{r.get('status')}: {r.get('evidence')}" 
                              for r in test.get('results', [])])

        rows.append([
            test['test_id'],
            source_type,
            source_id,
            test['expected_result'][:100],
            test.get('error', '')[:100],
            test['outcome'],
            evidence[:200],
            'Test Framework'
        ])

    _write_csv('Test_Execution_Log.csv', headers, rows)


def _generate_defect_log(test_records):
    """Sheet 6: Defect_Log.csv"""
    
    failed_tests = [r for r in test_records if r['outcome'] in ['Fail', 'Error', 'Partial']]

    headers = ['Defect ID', 'Related Test ID', 'Related Artifact', 'Severity', 'Description', 'Suggested Fix']
    rows = []

    defect_id = 1
    for idx, test in enumerate(failed_tests, 1):
        artifact_id = test['uc_id'] or test['br_id'] or test['wf_id']
        severity = 'High' if test['outcome'] == 'Fail' else 'Medium' if test['outcome'] == 'Partial' else 'Critical'
        
        description = f"Test {test['test_id']} failed: {test['scenario']}"
        if test['error']:
            description += f"\nError: {test['error'][:100]}"

        rows.append([
            f"DEF-{defect_id:03d}",
            test['test_id'],
            artifact_id,
            severity,
            description[:200],
            "Review test preconditions and expected results"
        ])
        defect_id += 1

    _write_csv('Defect_Log.csv', headers, rows)


def _generate_artifact_evaluation(test_records, uc_specs, br_specs, wf_specs):
    """Sheet 7: Artifact_Evaluation.csv"""
    
    headers = ['Artifact ID', 'Artifact Type', 'Tests', 'Pass', 'Partial', 'Fail', 'Final Status', 'Remarks']
    rows = []

    # Evaluate UCs
    for uc in uc_specs.get('use_cases', []):
        uc_id = uc['id']
        uc_tests = [r for r in test_records if r['uc_id'] == uc_id]
        
        if not uc_tests:
            final_status = 'Not Implemented'
        else:
            pass_c = len([r for r in uc_tests if r['outcome'] == 'Pass'])
            total = len(uc_tests)
            if pass_c == total:
                final_status = 'Implemented Correctly'
            elif pass_c > 0:
                final_status = 'Partially Implemented'
            else:
                final_status = 'Incorrectly Implemented'

        pass_c = len([r for r in uc_tests if r['outcome'] == 'Pass'])
        partial_c = len([r for r in uc_tests if r['outcome'] == 'Partial'])
        fail_c = len([r for r in uc_tests if r['outcome'] in ['Fail', 'Error']])

        rows.append([
            uc_id,
            'Use Case',
            len(uc_tests),
            pass_c,
            partial_c,
            fail_c,
            final_status,
            uc.get('title', '')
        ])

    # Evaluate BRs
    for br in br_specs.get('business_rules', []):
        br_id = br['id']
        br_tests = [r for r in test_records if r['br_id'] == br_id]

        if not br_tests:
            final_status = 'Not Enforced'
        else:
            pass_c = len([r for r in br_tests if r['outcome'] == 'Pass'])
            total = len(br_tests)
            if pass_c == total:
                final_status = 'Enforced Correctly'
            elif pass_c > 0:
                final_status = 'Partially Enforced'
            else:
                final_status = 'Incorrectly Enforced'

        pass_c = len([r for r in br_tests if r['outcome'] == 'Pass'])
        partial_c = len([r for r in br_tests if r['outcome'] == 'Partial'])
        fail_c = len([r for r in br_tests if r['outcome'] in ['Fail', 'Error']])

        rows.append([
            br_id,
            'Business Rule',
            len(br_tests),
            pass_c,
            partial_c,
            fail_c,
            final_status,
            br.get('title', '')
        ])

    # Evaluate WFs
    for wf in wf_specs.get('workflows', []):
        wf_id = wf['id']
        wf_tests = [r for r in test_records if r['wf_id'] == wf_id]

        if not wf_tests:
            final_status = 'Missing'
        else:
            pass_c = len([r for r in wf_tests if r['outcome'] == 'Pass'])
            total = len(wf_tests)
            if pass_c == total:
                final_status = 'Complete'
            elif pass_c > 0:
                final_status = 'Partial'
            else:
                final_status = 'Incorrect'

        pass_c = len([r for r in wf_tests if r['outcome'] == 'Pass'])
        partial_c = len([r for r in wf_tests if r['outcome'] == 'Partial'])
        fail_c = len([r for r in wf_tests if r['outcome'] in ['Fail', 'Error']])

        rows.append([
            wf_id,
            'Workflow',
            len(wf_tests),
            pass_c,
            partial_c,
            fail_c,
            final_status,
            wf.get('title', '')
        ])

    _write_csv('Artifact_Evaluation.csv', headers, rows)


# ── Test Runner ────────────────────────────────────────────────────────────────

class ReportingTestRunner(DiscoverRunner):
    """Django test runner that generates CSV reports."""

    def run_tests(self, test_labels, **kwargs):
        """Run tests and generate reports."""
        # Run tests with custom test result class
        result = super().run_tests(test_labels, **kwargs)

        # Get test result object
        test_result = kwargs.get('test_result', None)

        # Generate reports
        _ensure_reports_dir()
        
        uc_specs = _load_yaml('use_cases.yaml')
        br_specs = _load_yaml('business_rules.yaml')
        wf_specs = _load_yaml('workflows.yaml')

        # Collect test records
        test_records = []
        if hasattr(self, 'result_class') and issubclass(self.result_class, ReportingTestResult):
            # Try to get records from result object
            pass

        print("\n" + "="*70)
        print("📊 GENERATING TEST REPORTS")
        print("="*70)

        # For now, create empty structure (will be filled from test execution)
        if not test_records:
            # Create placeholder records from test discovery
            test_records = []

        _generate_module_test_summary(test_records, uc_specs, br_specs, wf_specs)
        _generate_uc_test_design(test_records, uc_specs)
        _generate_br_test_design(test_records, br_specs)
        _generate_wf_test_design(test_records, wf_specs)
        _generate_test_execution_log(test_records)
        _generate_defect_log(test_records)
        _generate_artifact_evaluation(test_records, uc_specs, br_specs, wf_specs)

        print("\n" + "="*70)
        print("✅ ALL REPORTS GENERATED IN:", _REPORTS_DIR)
        print("="*70)

        return result
