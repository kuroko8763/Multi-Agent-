"""
Unit tests for Architecture Review Agent
"""

import unittest
from datetime import datetime
from agents.pr_analyzer import PRUnderstandingAgent, FileChange, PRContext
from agents.rule_checker import ArchitectureRuleAgent, RuleViolation
from agents.impact_evaluator import ImpactAssessmentAgent
from agents.review_generator import ReviewOpinionAgent
from agents.regression_planner import RegressionAdviceAgent


class TestPRUnderstandingAgent(unittest.TestCase):
    """Tests for PR Understanding Agent"""

    def setUp(self):
        self.agent = PRUnderstandingAgent()

    def test_analyze_simple_pr(self):
        """Test analyzing a simple PR"""
        pr_data = {
            'pr_number': 123,
            'title': 'Add new feature',
            'description': 'This PR adds a new feature',
            'author': 'testuser',
            'base_branch': 'main',
            'head_branch': 'feature/new-feature',
            'created_at': '2026-05-01T10:00:00',
            'files': [
                {'path': 'src/main.py', 'status': 'modified', 'diff': '+def new_func():\n+    pass'}
            ],
            'commits': [],
            'linked_issues': []
        }

        context = self.agent.analyze(pr_data)
        
        self.assertEqual(context.pr_number, 123)
        self.assertEqual(context.title, 'Add new feature')
        self.assertEqual(context.author, 'testuser')
        self.assertEqual(len(context.changed_files), 1)
        self.assertEqual(context.technical_domain, 'unknown')

    def test_detect_language(self):
        """Test language detection"""
        self.assertEqual(self.agent._detect_language('test.py'), 'python')
        self.assertEqual(self.agent._detect_language('main.js'), 'javascript')
        self.assertEqual(self.agent._detect_language('app.ts'), 'typescript')
        self.assertEqual(self.agent._detect_language('README.md'), 'unknown')

    def test_is_test_file(self):
        """Test test file detection"""
        self.assertTrue(self.agent._is_test_file('test_main.py'))
        self.assertTrue(self.agent._is_test_file('main_test.py'))
        self.assertTrue(self.agent._is_test_file('spec/app.spec.ts'))
        self.assertFalse(self.agent._is_test_file('src/main.py'))

    def test_risk_factor_detection(self):
        """Test risk factor identification"""
        pr_data = {
            'pr_number': 456,
            'title': 'Large refactor',
            'description': 'Refactoring many files',
            'author': 'developer',
            'base_branch': 'main',
            'head_branch': 'refactor/major',
            'created_at': '2026-05-01T03:00:00',  # 3 AM - off hours
            'files': [
                {'path': f'src/module_{i}.py', 'status': 'modified', 'diff': '+' * 100}
                for i in range(25)  # 25 files - large change
            ],
            'commits': [],
            'linked_issues': []  # No linked issues
        }

        context = self.agent.analyze(pr_data)
        
        self.assertIn('Large change', context.risk_factors)
        self.assertIn('Off-hours commit', context.risk_factors)
        self.assertIn('No linked issue for large change', context.risk_factors)


class TestArchitectureRuleAgent(unittest.TestCase):
    """Tests for Architecture Rule Agent"""

    def setUp(self):
        self.agent = ArchitectureRuleAgent()

    def test_hardcoded_secret_detection(self):
        """Test detection of hardcoded secrets"""
        pr_context = PRContext(
            pr_number=1,
            title='test',
            description='test',
            author='test',
            base_branch='main',
            head_branch='test',
            created_at=datetime.now()
        )
        pr_context.changed_files = [
            FileChange(
                file_path='config.py',
                change_type='modified',
                additions=0,
                deletions=0,
                diff_content='api_key = "sk_live_abcdefghij1234567890"',
                language='python',
                is_test=False,
                is_config=False,
                is_documentation=False
            )
        ]

        result = self.agent.check(pr_context, {'config.py': 'api_key = "sk_live_abcdefghij1234567890"'})
        
        self.assertGreater(len(result.violations), 0)
        sec_violations = [v for v in result.violations if v.rule_id == 'SEC001']
        self.assertGreater(len(sec_violations), 0)

    def test_compliance_score_calculation(self):
        """Test compliance score calculation"""
        result = type('Result', (), {
            'total_rules_checked': 20,
            'rules_triggered': 3,
            'violations': [
                RuleViolation('SEC001', 'Test', 'critical', 'f.py', 1, 'desc', 'evidence', 'fix'),
                RuleViolation('SEC001', 'Test', 'critical', 'f.py', 2, 'desc', 'evidence', 'fix'),
                RuleViolation('QUAL001', 'Test', 'major', 'f.py', 3, 'desc', 'evidence', 'fix'),
            ],
            'critical_issues': [],
            'warning_issues': []
        })()

        self.agent._calculate_compliance_score(result)
        
        # Should have significant penalty for critical issues
        self.assertLess(result.compliance_score, 80)


class TestImpactAssessmentAgent(unittest.TestCase):
    """Tests for Impact Assessment Agent"""

    def setUp(self):
        self.agent = ImpactAssessmentAgent()

    def test_cascade_risk_high(self):
        """Test cascade risk assessment for high risk"""
        pr_context = PRContext(
            pr_number=1, title='test', description='test',
            author='test', base_branch='main', head_branch='test',
            created_at=datetime.now()
        )
        pr_context.changed_files = [
            FileChange(f'src/module_{i}.py', 'modified', 50, 10, '', 'python', False, False, False)
            for i in range(25)
        ]

        result = self.agent.assess(pr_context, {})
        
        # Large changes to many files should be high risk
        self.assertEqual(result.cascade_risk, 'high')

    def test_breaking_change_detection(self):
        """Test detection of breaking changes"""
        pr_context = PRContext(
            pr_number=1, title='test', description='test',
            author='test', base_branch='main', head_branch='test',
            created_at=datetime.now()
        )
        pr_context.changed_files = [
            FileChange(
                'migrations/001_add_users.sql',
                'added', 100, 0,
                'CREATE TABLE users (id INT, name VARCHAR(100));',
                'sql', False, False, False
            )
        ]

        result = self.agent.assess(pr_context, {})
        
        breaking = [b for b in result.breaking_changes if b['type'] == 'database_schema']
        self.assertGreater(len(breaking), 0)


class TestReviewOpinionAgent(unittest.TestCase):
    """Tests for Review Opinion Agent"""

    def setUp(self):
        self.agent = ReviewOpinionAgent()

    def test_approval_for_clean_pr(self):
        """Test that clean PR gets approved"""
        pr_context = PRContext(
            pr_number=1, title='Minor docs update', description='Update README',
            author='test', base_branch='main', head_branch='test',
            created_at=datetime.now()
        )
        pr_context.changed_files = [
            FileChange('README.md', 'modified', 10, 5, '', 'markdown', False, False, True)
        ]
        pr_context.risk_factors = []

        # Create minimal rule and impact results
        from agents.rule_checker import RuleCheckResult
        rule_result = RuleCheckResult(total_rules_checked=20, rules_triggered=0)
        rule_result.compliance_score = 100.0

        from agents.impact_evaluator import ImpactAssessmentResult
        impact_result = ImpactAssessmentResult(
            impacted_services=[], impacted_modules=[],
            cascade_risk='low', rollback_complexity='low',
            tested_surface=0.9, untested_surface=[],
            breaking_changes=[], recommendations=['✅ Impact range controllable'],
            impact_graph={}
        )

        summary = self.agent.generate(pr_context, rule_result, impact_result)
        
        self.assertEqual(summary.approval_status, 'approved')
        self.assertGreater(summary.overall_score, 80)

    def test_rejection_for_critical_issues(self):
        """Test that critical issues cause rejection"""
        pr_context = PRContext(
            pr_number=1, title='test', description='test',
            author='test', base_branch='main', head_branch='test',
            created_at=datetime.now()
        )
        pr_context.changed_files = []
        pr_context.risk_factors = []

        from agents.rule_checker import RuleCheckResult, RuleViolation
        rule_result = RuleCheckResult(total_rules_checked=20, rules_triggered=2)
        rule_result.violations = [
            RuleViolation('SEC001', 'Hardcoded Secret', 'critical', 'config.py', 1, '', '', ''),
            RuleViolation('SEC001', 'Hardcoded Secret', 'critical', 'config.py', 2, '', '', ''),
        ]
        rule_result.critical_issues = rule_result.violations
        rule_result.compliance_score = 40.0

        from agents.impact_evaluator import ImpactAssessmentResult
        impact_result = ImpactAssessmentResult(
            impacted_services=[], impacted_modules=[],
            cascade_risk='low', rollback_complexity='low',
            tested_surface=0.5, untested_surface=[],
            breaking_changes=[], recommendations=[],
            impact_graph={}
        )

        summary = self.agent.generate(pr_context, rule_result, impact_result)
        
        self.assertEqual(summary.approval_status, 'rejected')


class TestRegressionAdviceAgent(unittest.TestCase):
    """Tests for Regression Advice Agent"""

    def setUp(self):
        self.agent = RegressionAdviceAgent()

    def test_test_intensity_exhaustive(self):
        """Test exhaustive test intensity for high risk"""
        from agents.regression_planner import RiskContext
        
        risk = RiskContext(
            cascade_risk='high',
            rollback_complexity='high',
            breaking_changes=[{'type': 'api', 'severity': 'critical'}],
            compliance_score=60.0,
            untested_surface=['module1', 'module2', 'module3'] * 5
        )

        intensity = self.agent._determine_test_intensity(risk)
        self.assertEqual(intensity, 'exhaustive')

    def test_baseline_intensity_low_risk(self):
        """Test baseline test intensity for low risk"""
        from agents.regression_planner import RiskContext
        
        risk = RiskContext(
            cascade_risk='low',
            rollback_complexity='low',
            breaking_changes=[],
            compliance_score=95.0,
            untested_surface=[]
        )

        intensity = self.agent._determine_test_intensity(risk)
        self.assertEqual(intensity, 'baseline')


if __name__ == '__main__':
    unittest.main()