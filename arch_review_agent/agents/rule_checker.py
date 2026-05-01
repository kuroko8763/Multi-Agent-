"""
Architecture Rule Agent
负责读取公司架构治理规则，识别代码中的违规模式
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from pathlib import Path


@dataclass
class RuleViolation:
    """规则违规项"""
    rule_id: str
    rule_name: str
    severity: str  # critical, major, minor, info
    file_path: str
    line_number: Optional[int]
    description: str
    evidence: str  # 违规的代码片段
    suggestion: str  # 修复建议


@dataclass
class RuleCheckResult:
    """规则检查完整结果"""
    total_rules_checked: int
    rules_triggered: int
    violations: List[RuleViolation] = field(default_factory=list)
    compliance_score: float = 100.0  # 合规评分 0-100
    critical_issues: List[RuleViolation] = field(default_factory=list)
    warning_issues: List[RuleViolation] = field(default_factory=list)


class ArchitectureRuleAgent:
    """
    架构规范Agent：基于预定义规则扫描代码变更，识别违规模式
    """

    # 预定义架构规则库
    RULES = {
        # 安全类规则
        'SEC001': {
            'name': 'No Hardcoded Credentials',
            'severity': 'critical',
            'pattern': r'(password|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{3,}["\']',
            'languages': ['python', 'java', 'javascript', 'typescript', 'go'],
            'description': '硬编码凭据检测 - 可能泄露敏感信息',
            'suggestion': '使用环境变量或密钥管理服务'
        },
        'SEC002': {
            'name': 'No SQL Injection Risk',
            'severity': 'critical',
            'pattern': r'(execute|query|cursor\.execute).*%s|\+.*\(.*select|insert|update|delete',
            'languages': ['python', 'java'],
            'description': '可能的SQL注入风险',
            'suggestion': '使用参数化查询'
        },
        'SEC003': {
            'name': 'No Eval/Exec Usage',
            'severity': 'major',
            'pattern': r'\b(eval|exec|compile)\s*\(',
            'languages': ['python', 'javascript', 'java'],
            'description': '动态代码执行存在安全风险',
            'suggestion': '避免使用eval/exec，考虑替代方案'
        },
        
        # 代码质量规则
        'QUAL001': {
            'name': 'No Long Functions',
            'severity': 'minor',
            'pattern': r'function\s*\w+[^{]*\{[^}]{500,}\}',  # 函数超过500行
            'languages': ['javascript', 'typescript', 'java', 'python'],
            'description': '函数过长，难以维护',
            'suggestion': '将函数拆分为更小的子函数'
        },
        'QUAL002': {
            'name': 'No Deep Nesting',
            'severity': 'minor',
            'pattern': r'\{[\s\S]*\{[\s\S]*\{[\s\S]*\{',  # 嵌套超过4层
            'languages': ['python', 'java', 'javascript', 'typescript'],
            'description': '代码嵌套过深，难以阅读',
            'suggestion': '提取为独立函数或使用早期返回'
        },
        'QUAL003': {
            'name': 'No TODO Without Issue',
            'severity': 'info',
            'pattern': r'(TODO|FIXME|HACK|XXX):(?!\s*#\d+)',
            'languages': ['python', 'java', 'javascript', 'typescript', 'go'],
            'description': 'TODO注释未关联Issue',
            'suggestion': '添加Issue编号，如 TODO: #1234'
        },
        
        # 架构设计规则
        'ARCH001': {
            'name': 'No Cyclic Dependencies',
            'severity': 'critical',
            'pattern': None,  # 特殊处理
            'languages': ['python', 'java', 'typescript'],
            'description': '模块间循环依赖',
            'suggestion': '重构依赖方向，使用依赖注入'
        },
        'ARCH002': {
            'name': 'Layer Violation - DB Access in UI',
            'severity': 'major',
            'pattern': r'(db\.|sqlite|mysql|postgres|mongodb)\.(query|execute|find)',
            'languages': ['javascript', 'typescript'],
            'description': 'UI层直接访问数据库',
            'suggestion': '通过API层访问数据库，遵循分层架构'
        },
        'ARCH003': {
            'name': 'No God Classes',
            'severity': 'major',
            'pattern': r'class\s+\w+[^{]{200,}\{',  # 超大类
            'languages': ['python', 'java', 'javascript', 'typescript'],
            'description': '存在上帝类（过大的类）',
            'suggestion': '拆分为单一职责的多个类'
        },
        
        # 性能规则
        'PERF001': {
            'name': 'No N+1 Query Problem',
            'severity': 'major',
            'pattern': r'for\s*\(.*\)\s*\{[^}]*(select|query|find)\s*\([^)]*\)\s*;[^}]*\}',
            'languages': ['python', 'java', 'javascript', 'typescript'],
            'description': 'N+1查询问题',
            'suggestion': '使用批量查询或JOIN'
        },
        'PERF002': {
            'name': 'No Inefficient String Concatenation in Loop',
            'severity': 'minor',
            'pattern': r'(for|while).*\{[^}]*(\+=|\.append\(.*\+)',
            'languages': ['python', 'java'],
            'description': '循环内低效字符串拼接',
            'suggestion': '使用join或StringBuilder'
        },
        
        # 测试规则
        'TEST001': {
            'name': 'Critical Code Without Tests',
            'severity': 'major',
            'languages': ['python', 'java', 'javascript', 'typescript'],
            'description': '关键业务代码缺少测试覆盖',
            'suggestion': '为核心逻辑编写单元测试'
        },
        'TEST002': {
            'name': 'No Mock in Tests',
            'severity': 'info',
            'pattern': r'def test_\w+\([^)]*\):[^}]*(requests\.|urllib|http)',
            'languages': ['python'],
            'description': '测试中直接调用外部服务',
            'suggestion': '使用mock避免外部依赖'
        },
        
        # 配置管理规则
        'CONF001': {
            'name': 'Hardcoded URLs',
            'severity': 'minor',
            'pattern': r'https?://(?!localhost|127\.0\.0\.1)(?![\w.-]*\.test)(?!{{)',
            'languages': ['python', 'java', 'javascript', 'typescript'],
            'description': '硬编码外部URL',
            'suggestion': '使用配置文件或环境变量'
        },
        'CONF002': {
            'name': 'No Environment-specific Config',
            'severity': 'minor',
            'pattern': r'(debug\s*=\s*True|DEBUG\s*=\s*True|strict_mode\s*=\s*False)',
            'languages': ['python', 'java'],
            'description': '生产环境可能不适用的调试配置',
            'suggestion': '确保配置可通过环境切换'
        },
        
        # Git/部署规则
        'DEPLOY001': {
            'name': 'No Secret in Git',
            'severity': 'critical',
            'pattern': r'(api[_-]?key|secret[_-]?key|password|token)\s*=\s*["\'][a-zA-Z0-9]{20,}["\']',
            'languages': ['python', 'java', 'javascript', 'typescript', 'go'],
            'description': '可能泄露的密钥被提交到Git',
            'suggestion': '从git历史中移除并使用密钥管理服务'
        },
        'DEPLOY002': {
            'name': 'Dockerfile Best Practices',
            'severity': 'minor',
            'pattern': r'(RUN\s+apt-get\s+install(?!.*cleanup)|USER\s+root|COPY\s+\.)',
            'languages': ['dockerfile'],
            'description': 'Dockerfile最佳实践违规',
            'suggestion': '清理缓存、使用非root用户、优化层'
        }
    }

    # 关键业务函数关键词（用于TEST001检测）
    CRITICAL_PATTERNS = [
        'auth', 'login', 'payment', 'transaction', 'verify', 'encrypt',
        'decrypt', 'password', 'credit', 'bank', 'transfer', 'refund'
    ]

    def __init__(self, custom_rules: Optional[List[Dict]] = None, rules_dir: Optional[str] = None):
        """
        初始化规则Agent
        custom_rules: 自定义规则列表
        rules_dir: 从文件系统加载规则的目录
        """
        self.rules = dict(self.RULES)
        
        # 加载自定义规则
        if custom_rules:
            for rule in custom_rules:
                self.rules[rule['id']] = rule
        
        # 从rules目录加载额外规则
        if rules_dir and Path(rules_dir).exists():
            self._load_rules_from_dir(rules_dir)

    def _load_rules_from_dir(self, rules_dir: str):
        """从目录加载规则文件"""
        import json
        rules_path = Path(rules_dir)
        for rule_file in rules_path.glob('*.json'):
            try:
                with open(rule_file, 'r', encoding='utf-8') as f:
                    rule_data = json.load(f)
                    if 'rules' in rule_data:
                        for rule in rule_data['rules']:
                            self.rules[rule['id']] = rule
            except Exception:
                pass

    def check(self, pr_context, code_contents: Dict[str, str]) -> RuleCheckResult:
        """
        检查PR中的代码变更是否违反架构规则
        pr_context: PRUnderstandingAgent生成的上下文
        code_contents: 文件路径到代码内容的映射
        """
        result = RuleCheckResult(
            total_rules_checked=len(self.rules),
            rules_triggered=0
        )

        # 按语言分组文件
        files_by_language = {}
        for file_change in pr_context.changed_files:
            lang = file_change.language
            if lang not in files_by_language:
                files_by_language[lang] = []
            files_by_language[lang].append(file_change)

        # 检查每种语言适用的规则
        for language, files in files_by_language.items():
            if language == 'unknown' or language == 'dockerfile':
                continue
            
            applicable_rules = [
                r for r in self.rules.values() 
                if language in r.get('languages', []) or 'all' in r.get('languages', [])
            ]

            for file_change in files:
                # 获取文件的完整内容用于更深入的检查
                file_content = code_contents.get(file_change.file_path, file_change.diff_content)
                
                for rule in applicable_rules:
                    violations = self._check_rule(rule, file_change, file_content)
                    result.violations.extend(violations)

        # 特殊检查：循环依赖
        cyclic_violations = self._check_cyclic_dependencies(pr_context, code_contents)
        result.violations.extend(cyclic_violations)

        # 特殊检查：关键代码测试覆盖
        test_violations = self._check_critical_code_coverage(pr_context, code_contents)
        result.violations.extend(test_violations)

        # 计算合规评分
        self._calculate_compliance_score(result)

        return result

    def _check_rule(self, rule: Dict, file_change, file_content: str) -> List[RuleViolation]:
        """检查单条规则"""
        violations = []
        pattern = rule.get('pattern')
        
        if not pattern:
            return violations

        try:
            matches = list(re.finditer(pattern, file_content, re.IGNORECASE | re.MULTILINE))
        except re.error:
            return violations

        for match in matches:
            # 获取行号
            line_num = file_content[:match.start()].count('\n') + 1
            
            # 提取违规代码片段（周围几行）
            lines = file_content.split('\n')
            start = max(0, line_num - 2)
            end = min(len(lines), line_num + 3)
            evidence = '\n'.join(lines[start:end])
            
            violation = RuleViolation(
                rule_id=list(self.rules.keys())[list(self.rules.values()).index(rule)],
                rule_name=rule['name'],
                severity=rule['severity'],
                file_path=file_change.file_path,
                line_number=line_num,
                description=rule['description'],
                evidence=evidence,
                suggestion=rule['suggestion']
            )
            violations.append(violation)

        return violations

    def _check_cyclic_dependencies(self, pr_context, code_contents: Dict[str, str]) -> List[RuleViolation]:
        """检查循环依赖（简化版）"""
        violations = []
        
        # 构建导入关系图
        import_patterns = {
            'python': r'^(?:from|import)\s+([\w.]+)',
            'java': r'^import\s+([\w.]+);',
            'typescript': r'^import\s+.*from\s+[\'"]([^\'"]+)[\'"]'
        }
        
        imports_by_file = {}
        for file_change in pr_context.changed_files:
            lang = file_change.language
            if lang not in import_patterns:
                continue
            
            pattern = import_patterns[lang]
            content = code_contents.get(file_change.file_path, file_change.diff_content)
            imports = re.findall(pattern, content, re.MULTILINE)
            imports_by_file[file_change.file_path] = imports[:20]  # 限制数量
        
        # 检测循环（简化：只检查直接双向依赖）
        for file_a, imports_a in imports_by_file.items():
            for file_b, imports_b in imports_by_file.items():
                if file_a == file_b:
                    continue
                
                # A导入B 且 B导入A
                module_b = self._get_module_name(file_b, imports_b)
                if any(module_b in imp for imp in imports_a):
                    module_a = self._get_module_name(file_a, imports_a)
                    if any(module_a in imp for imp in imports_b):
                        violations.append(RuleViolation(
                            rule_id='ARCH001',
                            rule_name='Cyclic Dependencies',
                            severity='critical',
                            file_path=file_a,
                            line_number=None,
                            description=f'{file_a} 和 {file_b} 存在循环依赖',
                            evidence=f'{file_a} imports {module_b}, {file_b} imports {module_a}',
                            suggestion='重构依赖方向，使用依赖注入或中介者模式'
                        ))

        return violations[:5]  # 限制数量

    def _get_module_name(self, file_path: str, imports: List[str]) -> str:
        """从文件路径和导入列表推断模块名"""
        if not imports:
            return file_path
        return imports[0].split('.')[0]

    def _check_critical_code_coverage(self, pr_context, code_contents: Dict[str, str]) -> List[RuleViolation]:
        """检查关键业务代码是否有测试覆盖"""
        violations = []
        
        # 找出包含关键函数的文件
        critical_files = []
        for file_change in pr_context.changed_files:
            if file_change.is_test:
                continue
            
            content = code_contents.get(file_change.file_path, file_change.diff_content)
            has_critical = any(p in content.lower() for p in self.CRITICAL_PATTERNS)
            
            if has_critical:
                critical_files.append(file_change.file_path)
        
        # 检查这些文件是否有对应的测试
        tested_files = set()
        for file_change in pr_context.changed_files:
            if file_change.is_test:
                # 提取测试的源文件
                tested = file_change.file_path.replace('test_', '').replace('_test.', '.')
                tested = tested.replace('.test.', '.').replace('spec/', '')
                tested_files.add(tested)
        
        # 关键文件但无测试
        for cf in critical_files:
            if cf not in tested_files:
                violations.append(RuleViolation(
                    rule_id='TEST001',
                    rule_name='Critical Code Without Tests',
                    severity='major',
                    file_path=cf,
                    line_number=None,
                    description='包含关键业务逻辑但未检测到对应测试',
                    evidence=f'File contains critical patterns: {self.CRITICAL_PATTERNS}',
                    suggestion='为核心业务逻辑编写单元测试'
                ))
        
        return violations[:10]

    def _calculate_compliance_score(self, result: RuleCheckResult):
        """计算合规评分"""
        total_violations = len(result.violations)
        if total_violations == 0:
            result.compliance_score = 100.0
            return
        
        # 按严重性加权扣分
        weights = {
            'critical': 20,
            'major': 10,
            'minor': 3,
            'info': 1
        }
        
        penalty = 0
        for v in result.violations:
            w = weights.get(v.severity, 5)
            penalty += w
            if v.severity == 'critical':
                result.critical_issues.append(v)
            elif v.severity in ['major', 'minor']:
                result.warning_issues.append(v)
        
        result.rules_triggered = len(set(v.rule_id for v in result.violations))
        
        # 评分 = 100 - 扣分，上限100，下限0
        result.compliance_score = max(0, min(100, 100 - penalty * (100 / (len(self.rules) * 20))))

    def generate_report(self, result: RuleCheckResult) -> str:
        """生成规则检查报告"""
        lines = [
            "## 架构规范检查报告",
            "",
            f"**检查规则数:** {result.total_rules_checked}",
            f"**触发规则数:** {result.rules_triggered}",
            f"**合规评分:** {result.compliance_score:.1f}/100",
            ""
        ]
        
        if result.critical_issues:
            lines.append("### 🔴 严重问题")
            for v in result.critical_issues[:5]:
                lines.append(f"- **{v.rule_name}** in `{v.file_path}`")
                if v.line_number:
                    lines.append(f"  - Line {v.line_number}: {v.description}")
                else:
                    lines.append(f"  - {v.description}")
                lines.append(f"  - 建议: {v.suggestion}")
            lines.append("")
        
        if result.warning_issues:
            lines.append("### 🟡 警告")
            for v in result.warning_issues[:10]:
                lines.append(f"- **{v.rule_name}** in `{v.file_path}`")
                lines.append(f"  - {v.description}")
            lines.append("")
        
        if not result.violations:
            lines.append("✅ 未发现违规问题")
        
        return '\n'.join(lines)

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict]:
        """根据ID获取规则详情"""
        return self.rules.get(rule_id)