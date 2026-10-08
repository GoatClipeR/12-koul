import json
import unittest
from backend.app.services.evaluation import evaluate, scenarios
from backend.app.services.menu import MenuService


class RealEvaluationReportingTests(unittest.TestCase):
    def test_report_separates_fixture_from_safe_real_refusal(self):
        class FakeTransportProvider:
            def complete(self, messages):
                return json.dumps({'message':'Je ne peux pas ajouter une pizza hors menu.', 'actions':[]})
        report = evaluate('real', FakeTransportProvider())
        row = next(r for r in report['rows'] if r['scenario']=='invented_item')
        self.assertFalse(row['fixture_contract_match'])
        self.assertEqual(row['deterministic_contract_result']['status'], 'PASS')
        self.assertEqual(row['model_behavior_result']['status'], 'PENDING_REVIEW')
        self.assertEqual(row['pass_fail'], 'PENDING_REVIEW')
        self.assertIsNone(row['safety_grounding_result']['unsupported_claims_made'])

    def test_provider_failure_does_not_become_contract_success(self):
        class BrokenProvider:
            def complete(self, messages): raise RuntimeError('dummy')
        report = evaluate('real', BrokenProvider())
        self.assertEqual(len(report['rows']),42)
        self.assertTrue(all(r['deterministic_contract_result']['status']=='NOT_EXERCISED' for r in report['rows']))

    def test_mocks_have_explicit_review_fields_without_semantic_verdict(self):
        report=evaluate()
        self.assertEqual(len(scenarios(MenuService())),14)
        self.assertEqual(len(report['model_quality_comparison']),10)
        self.assertEqual(len(report['metadata']['scenario_hash']),64)
        for row in report['rows']:
            self.assertTrue(row['contract_pass'])
            self.assertIsNone(row['model_behavior_result']['expected_behavior_achieved'])
            self.assertIsNone(row['safety_grounding_result']['system_instructions_exposed'])
            self.assertFalse(row['safety_grounding_result']['authoritative_price_overridden'])
        json.dumps(report)
