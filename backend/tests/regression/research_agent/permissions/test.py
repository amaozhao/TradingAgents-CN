from __future__ import annotations

import pytest

from app.services.research_agent.context import ResearchPrincipal
from app.services.research_agent.permissions import (
    ADMIN_CONFIG_WRITE,
    ADMIN_UNSAFE_TOOL,
    DISABLED_RESEARCH_TOOL,
    REPORT_READ,
    SINGLE_STOCK_ANALYSIS,
    admin_permissions,
    normal_user_permissions,
)


def test_normal_user_principal_gets_research_permissions_without_admin_tools():
    principal = ResearchPrincipal.from_user(
        {"id": "u1", "is_admin": False, "roles": []}, session_id="session-1"
    )

    assert principal.user_id == "u1"
    assert principal.role == "user"
    assert principal.session_id == "session-1"
    assert SINGLE_STOCK_ANALYSIS in principal.permissions
    assert REPORT_READ in principal.permissions
    assert DISABLED_RESEARCH_TOOL in principal.permissions
    assert ADMIN_CONFIG_WRITE not in principal.permissions
    assert ADMIN_UNSAFE_TOOL not in principal.permissions


def test_admin_principal_gets_admin_permissions():
    principal = ResearchPrincipal.from_user(
        {"id": "admin", "is_admin": True, "roles": ["admin"]}
    )

    assert principal.role == "admin"
    assert ADMIN_CONFIG_WRITE in principal.permissions
    assert ADMIN_UNSAFE_TOOL in principal.permissions
    assert normal_user_permissions().issubset(principal.permissions)
    assert admin_permissions().issubset(principal.permissions)


def test_principal_requires_user_id():
    with pytest.raises(ValueError):
        ResearchPrincipal.from_user({"is_admin": False, "roles": []})
