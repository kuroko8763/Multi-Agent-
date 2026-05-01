"""
Impact Assessment Agent
负责构造调用链路图，评估改动对上下游的影响程度
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
from collections import defaultdict
from pathlib import Path


@dataclass
class ServiceEndpoint:
    """服务接口/端点"""
    path: str
    method: str  # GET, POST, etc.
    file_path: str
    line_number: int
    dependencies: List[str]  # 依赖的服务/模块


@dataclass
class DataContract:
    """数据契约（API响应/数据结构）"""
    name: str
    fields: List[str]
    used_by: List[str]  # 使用该契约的文件列表


@dataclass
class ImpactNode:
    """影响图中的一个节点"""
    identifier: str  # 文件名或模块名
    node_type: str  # 'file', 'service', 'database', 'external'
    impact_level: str  # direct, indirect, potential
    dependents: List[str]  # 依赖此节点的文件/服务
    dependencies: List[str]  # 此节点依赖的其他节点
    change_magnitude: int  # 变更规模（行数）


@dataclass
class ImpactAssessmentResult:
    """影响评估完整结果"""
    impacted_services: List[str]
    impacted_modules: List[str]
    cascade_risk: str  # high, medium, low
    rollback_complexity: str  # high, medium, low
    tested_surface: float  # 已测试覆盖的比例
    untested_surface: List[str]  # 未测试的受影响面
    breaking_changes: List[Dict]  # 可能造成的breaking变化
    recommendations: List[str]
    impact_graph: Dict[str, List[str]]  # 简化版影响图


class ImpactAssessmentAgent:
    """
    影响评估Agent：分析代码变更的上下游影响，评估级联风险
    """

    # 常见的上下游依赖标记
    UPSTREAM_MARKERS = [
        'require', 'import', 'from', 'include', 'use', 'depends_on',
        'extends', 'implements', 'composition', 'aggregation'
    ]

    DOWNSTREAM_MARKERS = [
        'export', 'public', 'api', 'endpoint', 'route', 'handler',
        'service', 'controller', 'provider', 'consumer', 'subscriber'
    ]

    # 数据库/存储标记
    STORAGE_PATTERNS = [
        r'(select|insert|update|delete|drop|create\s+table|alter\s+table)\s+',
        r'(mysql|postgres|mongodb|redis|elasticsearch|kafka)\s*:',
        r'@Table|@Entity|@Document|@Schema'
    ]

    def __init__(self, service_map: Optional[Dict[str, List[str]]] = None):
        """
        初始化影响评估Agent
        service_map: 服务名到文件路径列表的映射
        """
        self.service_map = service_map or {}
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)

    def assess(self, pr_context, code_contents: Dict[str, str]) -> ImpactAssessmentResult:
        """
        评估PR变更的影响范围
        """
        changed_files = pr_context.changed_files
        changed_file_paths = [f.file_path for f in changed_files]

        # 构建依赖图
        self._build_dependency_graph(changed_files, code_contents)

        # 找出上游依赖（什么会被这个PR影响）
        impacted_downstream = self._find_downstream_impact(changed_file_paths)

        # 找出下游依赖（这个PR依赖什么）
        impacted_upstream = self._find_upstream_impact(changed_file_paths, code_contents)

        # 识别服务边界
        impacted_services = self._identify_impacted_services(changed_file_paths)

        # 检测breaking changes
        breaking = self._detect_breaking_changes(changed_files, code_contents)

        # 评估级联风险
        cascade_risk = self._assess_cascade_risk(
            changed_files, impacted_downstream, breaking
        )

        # 评估回滚复杂度
        rollback_complexity = self._assess_rollback_complexity(
            changed_files, impacted_downstream
        )

        # 计算测试覆盖
        tested, untested = self._assess_test_coverage(
            changed_file_paths, impacted_downstream, code_contents
        )

        # 生成建议
        recommendations = self._generate_recommendations(
            cascade_risk, rollback_complexity, tested, untested, breaking
        )

        # 构建影响图
        impact_graph = self._build_impact_graph(
            changed_file_paths, impacted_downstream, impacted_upstream
        )

        return ImpactAssessmentResult(
            impacted_services=list(set(impacted_services)),
            impacted_modules=list(set(impacted_upstream + impacted_downstream)),
            cascade_risk=cascade_risk,
            rollback_complexity=rollback_complexity,
            tested_surface=tested,
            untested_surface=untested,
            breaking_changes=breaking,
            recommendations=recommendations,
            impact_graph=impact_graph
        )

    def _build_dependency_graph(self, changed_files, code_contents: Dict[str, str]):
        """构建依赖关系图"""
        import_patterns = {
            'python': r'^(?:from|import)\s+([\w.]+)',
            'java': r'^import\s+([\w.]+);',
            'typescript': r'^import\s+.*from\s+[\'"]([^\'"]+)[\'"]',
            'javascript': r'^(?:const|let|var)\s+\w+\s*=\s*require\([\'"]([^\'"]+)[\'"]',
            'go': r'^\s*"?([\w./]+)"?\s+'
        }

        for file_change in changed_files:
            file_path = file_change.file_path
            lang = file_change.language
            
            if lang not in import_patterns:
                continue

            pattern = import_patterns[lang]
            content = code_contents.get(file_path, file_change.diff_content)
            
            imports = re.findall(pattern, content, re.MULTILINE)
            for imp in imports[:30]:  # 限制数量
                imp_clean = imp.split('.')[0].split('/')[0]
                if imp_clean and imp_clean != '_':
                    self.dependency_graph[file_path].add(imp_clean)
                    self.reverse_graph[imp_clean].add(file_path)

    def _find_downstream_impact(self, changed_files: List[str]) -> List[str]:
        """找到会受变更影响的下游文件/模块"""
        impacted = set()
        
        for file_path in changed_files:
            # 如果一个文件被修改，依赖它的文件也会受影响
            if file_path in self.reverse_graph:
                impacted.update(self.reverse_graph[file_path])
            
            # 检查文件名匹配
            file_name = Path(file_path).stem
            for node, dependents in self.reverse_graph.items():
                if file_name in node or any(file_name in d for d in dependents):
                    impacted.add(node)

        return list(impacted)

    def _find_upstream_impact(self, changed_files: List[str], code_contents: Dict[str, str]) -> List[str]:
        """找到PR依赖的上游文件/模块"""
        impacted = set()
        
        for file_path in changed_files:
            if file_path in self.dependency_graph:
                impacted.update(self.dependency_graph[file_path])
        
        # 特殊检测：配置文件变更影响
        for f in changed_files:
            if self._is_config_file(f):
                impacted.update(self._get_config_consumers(f))
        
        return list(impacted)

    def _is_config_file(self, file_path: str) -> bool:
        """判断是否为配置文件"""
        config_names = ['config', 'settings', '.env', 'yaml', 'yml', 'json']
        return any(c in file_path.lower() for c in config_names)

    def _get_config_consumers(self, config_path: str) -> List[str]:
        """获取消费特定配置文件的所有文件"""
        consumers = []
        config_name = Path(config_path).name
        
        for file_path, content in self.dependency_graph.items():
            if any(config_name in str(dep) for dep in content):
                consumers.append(file_path)
        
        return consumers

    def _identify_impacted_services(self, changed_files: List[str]) -> List[str]:
        """识别受影响的微服务"""
        services = set()
        
        for file_path in changed_files:
            # 根据路径推断服务
            parts = file_path.split('/')
            if len(parts) >= 2:
                # 常见结构: services/xxx/, modules/xxx/, apps/xxx/
                if parts[0] in ['services', 'modules', 'apps', 'packages']:
                    services.add(parts[1])
                # 或者: src/xxx-service/
                elif '-service' in parts[0] or '_service' in parts[0]:
                    services.add(parts[0])
        
        # 如果有service_map，用它来映射
        for file_path in changed_files:
            for svc, files in self.service_map.items():
                if any(file_path.endswith(f) for f in files):
                    services.add(svc)
        
        return list(services)

    def _detect_breaking_changes(self, changed_files, code_contents: Dict[str, str]) -> List[Dict]:
        """检测可能的breaking changes"""
        breaking = []

        for file_change in changed_files:
            content = code_contents.get(file_change.file_path, file_change.diff_content)
            
            # API签名变更
            if self._has_api_signature_change(file_change, content):
                breaking.append({
                    'type': 'api_signature',
                    'file': file_change.file_path,
                    'severity': 'high',
                    'description': 'API函数签名可能发生变化'
                })
            
            # 数据结构字段变更
            if self._has_struct_field_change(file_change, content):
                breaking.append({
                    'type': 'data_contract',
                    'file': file_change.file_path,
                    'severity': 'high',
                    'description': '数据结构字段发生变更'
                })
            
            # 数据库Schema变更
            if self._has_db_schema_change(file_change, content):
                breaking.append({
                    'type': 'database_schema',
                    'file': file_change.file_path,
                    'severity': 'critical',
                    'description': '数据库Schema发生变更'
                })

        return breaking

    def _has_api_signature_change(self, file_change, content: str) -> bool:
        """检测API签名变更"""
        # 检测函数定义变更
        if file_change.change_type in ['modified', 'added']:
            func_patterns = [
                r'def\s+\w+\([^)]*\):',  # Python
                r'function\s+\w+\([^)]*\)',  # JS/TS
                r'async\s+\w+\s*\([^)]*\)',  # Async JS/TS
                r'public\s+\w+\s*\([^)]*\)',  # Java
            ]
            for pattern in func_patterns:
                if re.search(pattern, content):
                    return True
        return False

    def _has_struct_field_change(self, file_change, content: str) -> bool:
        """检测数据结构字段变更"""
        struct_patterns = [
            r'class\s+\w+.*\{[^}]*:',  # TypeScript interface/class
            r'@DataClass|@dataclass',  # Python dataclass
            r'type\s+\w+\s*=',  # TypeScript type
            r'interface\s+\w+',  # TypeScript interface
        ]
        for pattern in struct_patterns:
            if re.search(pattern, content):
                return True
        return False

    def _has_db_schema_change(self, file_change, content: str) -> bool:
        """检测数据库Schema变更"""
        db_patterns = [
            r'CREATE\s+TABLE', r'ALTER\s+TABLE', r'DROP\s+TABLE',
            r'CREATE\s+INDEX', r'migration', r'schema',
            r'@Table|@Entity|@Document'
        ]
        return any(re.search(p, content, re.IGNORECASE) for p in db_patterns)

    def _assess_cascade_risk(self, changed_files, impacted_downstream, breaking: List[Dict]) -> str:
        """评估级联风险"""
        score = 0
        
        # 变更文件数
        if len(changed_files) > 10:
            score += 2
        elif len(changed_files) > 5:
            score += 1
        
        # 下游影响范围
        if len(impacted_downstream) > 20:
            score += 3
        elif len(impacted_downstream) > 10:
            score += 2
        elif len(impacted_downstream) > 5:
            score += 1
        
        # Breaking changes
        critical_breaking = sum(1 for b in breaking if b.get('severity') == 'critical')
        if critical_breaking > 0:
            score += critical_breaking * 3
        high_breaking = sum(1 for b in breaking if b.get('severity') == 'high')
        if high_breaking > 0:
            score += high_breaking * 2
        
        # 核心模块变更
        core_modules = ['auth', 'payment', 'core', 'base', 'common']
        for f in changed_files:
            if any(c in f.lower() for c in core_modules):
                score += 2
                break
        
        if score >= 7:
            return 'high'
        elif score >= 4:
            return 'medium'
        else:
            return 'low'

    def _assess_rollback_complexity(self, changed_files, impacted_downstream) -> str:
        """评估回滚复杂度"""
        score = 0
        
        # 数据库变更
        for f in changed_files:
            if any(x in f.lower() for x in ['migration', 'schema', 'db']):
                score += 2
        
        # 配置文件变更
        if any(self._is_config_file(f) for f in changed_files):
            score += 1
        
        # 下游影响广度
        if len(impacted_downstream) > 15:
            score += 2
        elif len(impacted_downstream) > 5:
            score += 1
        
        # 多服务变更
        services = self._identify_impacted_services(changed_files)
        if len(services) > 3:
            score += 2
        elif len(services) > 1:
            score += 1
        
        if score >= 5:
            return 'high'
        elif score >= 3:
            return 'medium'
        else:
            return 'low'

    def _assess_test_coverage(self, changed_files, impacted_downstream, code_contents: Dict[str, str]) -> Tuple[float, List[str]]:
        """评估测试覆盖情况"""
        tested_files = set()
        untested_files = set()
        
        for f in changed_files:
            if '_test' in f or 'test_' in f or '.spec.' in f:
                # 这是测试文件，标记对应的源文件为已测试
                source = f.replace('test_', '').replace('_test', '').replace('.spec.', '.')
                tested_files.add(source)
        
        # 检查受影响文件中有多少有测试
        for downstream in impacted_downstream:
            test_file = self._find_test_file(downstream)
            if test_file and test_file in code_contents:
                tested_files.add(downstream)
            else:
                untested_files.add(downstream)
        
        total = len(tested_files) + len(untested_files)
        tested_ratio = len(tested_files) / total if total > 0 else 0.0
        
        return tested_ratio, list(untested_files)[:20]  # 限制数量

    def _find_test_file(self, source_file: str) -> Optional[str]:
        """为源文件找到对应的测试文件"""
        path = Path(source_file)
        name = path.stem
        parent = path.parent
        
        # 常见的测试文件命名
        candidates = [
            parent / f'test_{name}{path.suffix}',
            parent / f'{name}_test{path.suffix}',
            parent / f'{name}.spec{path.suffix}',
            path.parent.parent / 'tests' / path.name,
        ]
        
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        
        return None

    def _generate_recommendations(self, cascade_risk: str, rollback: str, tested: float, untested: List, breaking: List) -> List[str]:
        """生成影响评估建议"""
        recs = []
        
        if cascade_risk == 'high':
            recs.append("⚠️ 高级联风险：建议分阶段部署，先在staging环境验证")
        
        if rollback == 'high':
            recs.append("⚠️ 高回滚复杂度：建议部署前创建完整备份，并准备回滚脚本")
        
        if tested < 0.5:
            recs.append(f"📋 测试覆盖不足({tested:.0%})：建议补充 {len(untested[:5])} 个关键文件的测试")
        
        if breaking:
            recs.append(f"🚨 检测到 {len(breaking)} 个Breaking Changes：需要同步通知下游服务")
        
        if not recs:
            recs.append("✅ 影响范围可控，可以正常部署")
        
        return recs

    def _build_impact_graph(self, changed: List[str], downstream: List[str], upstream: List[str]) -> Dict[str, List[str]]:
        """构建简化版影响图"""
        return {
            'changed': changed[:10],  # 限制展示数量
            'impacts': downstream[:20],
            'depends_on': upstream[:10]
        }

    def generate_report(self, result: ImpactAssessmentResult) -> str:
        """生成影响评估报告"""
        lines = [
            "## 影响评估报告",
            "",
            f"**受影响服务:** {', '.join(result.impacted_services) if result.impacted_services else '无'}",
            f"**受影响模块:** {len(result.impacted_modules)} 个",
            f"**级联风险:** {result.cascade_risk.upper()}",
            f"**回滚复杂度:** {result.rollback_complexity.upper()}",
            f"**测试覆盖:** {result.tested_surface:.0%}",
            ""
        ]
        
        if result.breaking_changes:
            lines.append("### 🚨 Breaking Changes")
            for b in result.breaking_changes:
                lines.append(f"- [{b['severity'].upper()}] {b['file']}: {b['description']}")
            lines.append("")
        
        if result.untested_surface:
            lines.append(f"### ⚠️ 未测试的受影响面 ({len(result.untested_surface)} 个)")
            for f in result.untested_surface[:10]:
                lines.append(f"- `{f}`")
            lines.append("")
        
        if result.recommendations:
            lines.append("### 📋 建议")
            for r in result.recommendations:
                lines.append(f"- {r}")
        
        return '\n'.join(lines)