"""沙箱安全策略单元测试"""

import pytest

from backend.sandbox.security import (
    BLOCKED_FUNCTIONS,
    BLOCKED_IMPORTS,
    BLOCKED_PATTERNS,
    ExecutionLimits,
    RiskLevel,
    SecurityCheckResult,
    SecurityPolicy,
    StaticCodeAnalyzer,
    analyze_code,
    is_code_safe,
)


class TestRiskLevel:
    """测试风险等级枚举"""

    def test_risk_level_values(self) -> None:
        """测试风险等级值"""
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestSecurityCheckResult:
    """测试安全检查结果"""

    def test_safe_result(self) -> None:
        """测试安全结果"""
        result = SecurityCheckResult(
            is_safe=True,
            risk_level=RiskLevel.SAFE,
        )
        assert result.is_safe is True
        assert result.risk_level == RiskLevel.SAFE
        assert result.issues == []
        assert result.warnings == []

    def test_unsafe_result(self) -> None:
        """测试不安全结果"""
        result = SecurityCheckResult(
            is_safe=False,
            risk_level=RiskLevel.CRITICAL,
            issues=["禁止使用 os 模块"],
            blocked_imports=["os"],
        )
        assert result.is_safe is False
        assert result.risk_level == RiskLevel.CRITICAL
        assert "禁止使用 os 模块" in result.issues
        assert "os" in result.blocked_imports

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        result = SecurityCheckResult(
            is_safe=True,
            risk_level=RiskLevel.SAFE,
            issues=[],
            warnings=["警告信息"],
        )
        d = result.to_dict()
        assert d["is_safe"] is True
        assert d["risk_level"] == "safe"
        assert d["warnings"] == ["警告信息"]


class TestExecutionLimits:
    """测试执行限制配置"""

    def test_default_limits(self) -> None:
        """测试默认限制"""
        limits = ExecutionLimits()
        assert limits.timeout == 60
        assert limits.memory_limit == "512m"
        assert limits.cpu_limit == 0.5
        assert limits.max_output_size == 1024 * 1024

    def test_custom_limits(self) -> None:
        """测试自定义限制"""
        limits = ExecutionLimits(
            timeout=120,
            memory_limit="1g",
            cpu_limit=1.0,
        )
        assert limits.timeout == 120
        assert limits.memory_limit == "1g"
        assert limits.cpu_limit == 1.0


class TestStaticCodeAnalyzer:
    """测试静态代码分析器"""

    @pytest.fixture
    def analyzer(self) -> StaticCodeAnalyzer:
        """创建分析器实例"""
        return StaticCodeAnalyzer()

    def test_safe_code(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试安全代码"""
        code = """
x = 1 + 1
print(x)
"""
        result = analyzer.analyze(code)
        assert result.is_safe is True
        assert result.risk_level == RiskLevel.SAFE

    def test_blocked_import_os(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止导入 os"""
        code = "import os"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert result.risk_level == RiskLevel.CRITICAL
        assert "os" in result.blocked_imports

    def test_blocked_import_subprocess(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止导入 subprocess"""
        code = "import subprocess"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "subprocess" in result.blocked_imports

    def test_blocked_import_socket(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止导入 socket"""
        code = "import socket"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "socket" in result.blocked_imports

    def test_blocked_import_from(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止 from ... import"""
        code = "from os import path"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "os" in result.blocked_imports

    def test_blocked_function_exec(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止使用 exec"""
        code = "exec('print(1)')"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "exec" in result.blocked_functions

    def test_blocked_function_eval(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止使用 eval"""
        code = "eval('1 + 1')"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "eval" in result.blocked_functions

    def test_blocked_function_open(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止使用 open"""
        code = "open('test.txt')"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "open" in result.blocked_functions

    def test_blocked_import_pickle(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止导入 pickle"""
        code = "import pickle"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "pickle" in result.blocked_imports

    def test_blocked_import_requests(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试禁止导入 requests"""
        code = "import requests"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert "requests" in result.blocked_imports

    def test_safe_pandas_import(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试安全导入 pandas"""
        code = "import pandas as pd"
        result = analyzer.analyze(code)
        assert result.is_safe is True

    def test_safe_numpy_import(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试安全导入 numpy"""
        code = "import numpy as np"
        result = analyzer.analyze(code)
        assert result.is_safe is True

    def test_safe_scipy_import(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试安全导入 scipy"""
        code = "from scipy import stats"
        result = analyzer.analyze(code)
        assert result.is_safe is True

    def test_syntax_error(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试语法错误"""
        code = "this is not valid python"
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert result.risk_level == RiskLevel.CRITICAL
        assert any("语法错误" in issue for issue in result.issues)

    def test_private_attribute_warning(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试访问私有属性警告"""
        code = "obj._private_attr"
        result = analyzer.analyze(code)
        assert len(result.warnings) > 0

    def test_dunder_attribute_warning(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试访问双下划线属性警告"""
        code = "obj.__dict__"
        result = analyzer.analyze(code)
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_multiple_issues(self, analyzer: StaticCodeAnalyzer) -> None:
        """测试多个问题"""
        code = """
import os
import subprocess
exec('code')
"""
        result = analyzer.analyze(code)
        assert result.is_safe is False
        assert result.risk_level == RiskLevel.CRITICAL
        assert len(result.blocked_imports) >= 2
        assert "exec" in result.blocked_functions


class TestSecurityPolicy:
    """测试安全策略"""

    @pytest.fixture
    def policy(self) -> SecurityPolicy:
        """创建安全策略实例"""
        return SecurityPolicy()

    def test_check_code_safe(self, policy: SecurityPolicy) -> None:
        """测试检查安全代码"""
        code = "x = 1 + 1"
        result = policy.check_code(code)
        assert result.is_safe is True

    def test_check_code_unsafe(self, policy: SecurityPolicy) -> None:
        """测试检查不安全代码"""
        code = "import os"
        result = policy.check_code(code)
        assert result.is_safe is False

    def test_is_execution_allowed_safe(self, policy: SecurityPolicy) -> None:
        """测试允许执行安全代码"""
        code = "print('hello')"
        allowed, reason = policy.is_execution_allowed(code)
        assert allowed is True
        assert "通过" in reason

    def test_is_execution_allowed_unsafe(self, policy: SecurityPolicy) -> None:
        """测试禁止执行不安全代码"""
        code = "import os"
        allowed, reason = policy.is_execution_allowed(code)
        assert allowed is False
        assert "未通过" in reason

    def test_is_execution_allowed_non_strict(self) -> None:
        """测试非严格模式"""
        policy = SecurityPolicy(strict_mode=False)
        code = "obj._private"
        allowed, reason = policy.is_execution_allowed(code)
        assert allowed is True

    def test_get_limits(self, policy: SecurityPolicy) -> None:
        """测试获取执行限制"""
        limits = policy.get_limits()
        assert limits.timeout == 60
        assert limits.memory_limit == "512m"

    def test_sanitize_output(self, policy: SecurityPolicy) -> None:
        """测试清理输出"""
        long_output = "x" * (2 * 1024 * 1024)
        sanitized = policy.sanitize_output(long_output)
        assert len(sanitized) <= 1024 * 1024 + 50
        assert "[输出已截断]" in sanitized

    def test_create_safe_error_message(self, policy: SecurityPolicy) -> None:
        """测试创建安全错误信息"""
        error = "Error in /home/user/project/file.py"
        safe_error = policy.create_safe_error_message(error)
        assert "/home/user/" not in safe_error
        assert "[user]" in safe_error

    def test_create_safe_error_message_api_key(self, policy: SecurityPolicy) -> None:
        """测试隐藏 API Key"""
        error = "api_key=sk-1234567890abcdef"
        safe_error = policy.create_safe_error_message(error)
        assert "sk-1234567890abcdef" not in safe_error
        assert "[REDACTED]" in safe_error

    def test_create_safe_error_message_password(self, policy: SecurityPolicy) -> None:
        """测试隐藏密码"""
        error = "password=mysecretpassword"
        safe_error = policy.create_safe_error_message(error)
        assert "mysecretpassword" not in safe_error
        assert "[REDACTED]" in safe_error


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_analyze_code(self) -> None:
        """测试 analyze_code 函数"""
        result = analyze_code("import os")
        assert result.is_safe is False

    def test_is_code_safe_true(self) -> None:
        """测试 is_code_safe 返回 True"""
        assert is_code_safe("x = 1") is True

    def test_is_code_safe_false(self) -> None:
        """测试 is_code_safe 返回 False"""
        assert is_code_safe("import os") is False


class TestBlockedImportsList:
    """测试禁止导入列表"""

    def test_os_in_blocked(self) -> None:
        """测试 os 在禁止列表"""
        assert "os" in BLOCKED_IMPORTS

    def test_subprocess_in_blocked(self) -> None:
        """测试 subprocess 在禁止列表"""
        assert "subprocess" in BLOCKED_IMPORTS

    def test_socket_in_blocked(self) -> None:
        """测试 socket 在禁止列表"""
        assert "socket" in BLOCKED_IMPORTS

    def test_pickle_in_blocked(self) -> None:
        """测试 pickle 在禁止列表"""
        assert "pickle" in BLOCKED_IMPORTS


class TestBlockedFunctionsList:
    """测试禁止函数列表"""

    def test_exec_in_blocked(self) -> None:
        """测试 exec 在禁止列表"""
        assert "exec" in BLOCKED_FUNCTIONS

    def test_eval_in_blocked(self) -> None:
        """测试 eval 在禁止列表"""
        assert "eval" in BLOCKED_FUNCTIONS

    def test_open_in_blocked(self) -> None:
        """测试 open 在禁止列表"""
        assert "open" in BLOCKED_FUNCTIONS


class TestBlockedPatterns:
    """测试禁止模式"""

    def test_patterns_exist(self) -> None:
        """测试模式存在"""
        assert len(BLOCKED_PATTERNS) > 0

    def test_getattr_pattern(self) -> None:
        """测试 getattr 模式"""
        import re

        pattern = r"getattr\s*\("
        assert re.search(pattern, "getattr(obj, 'attr')") is not None

    def test_setattr_pattern(self) -> None:
        """测试 setattr 模式"""
        import re

        pattern = r"setattr\s*\("
        assert re.search(pattern, "setattr(obj, 'attr', value)") is not None
