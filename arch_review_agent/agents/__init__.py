"""
Multi-Agent Architecture Compliance Review System

长链推理流水线:
PR理解Agent → 架构规范Agent → 影响评估Agent → 评审意见Agent → 回归建议Agent

每个Agent独立运行，通过共享上下文通信
"""

from .pr_analyzer import PRUnderstandingAgent
from .rule_checker import ArchitectureRuleAgent
from .impact_evaluator import ImpactAssessmentAgent
from .review_generator import ReviewOpinionAgent
from .regression_planner import RegressionAdviceAgent

__all__ = [
    'PRUnderstandingAgent',
    'ArchitectureRuleAgent',
    'ImpactAssessmentAgent',
    'ReviewOpinionAgent',
    'RegressionAdviceAgent'
]