"""
EA-H5: Budget enforcement for enterprise token/cost limits.

Checks whether a pipeline run should proceed or be paused based on
configured budget limits (monthly token cap, per-project cap, cost cap).

Budget limits come from the admin_policy.budgets section of team_config.json.
Token usage data comes from the audit_log.

Usage:
    from prep.core.budget_enforcement import check_budget, BudgetStatus
    status = check_budget(project_id="proj-1", project_root=Path("/repo"))
    if not status.allowed:
        # Pause pipeline, show error to user
        print(status.reason)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetStatus:
    """Result of a budget check."""
    allowed: bool = True
    reason: str = ""
    total_tokens_used: int = 0
    monthly_limit: Optional[int] = None
    project_limit: Optional[int] = None
    cost_cap_usd: Optional[float] = None
    estimated_cost_usd: float = 0.0
    usage_percent: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "total_tokens_used": self.total_tokens_used,
            "monthly_limit": self.monthly_limit,
            "project_limit": self.project_limit,
            "cost_cap_usd": self.cost_cap_usd,
            "estimated_cost_usd": self.estimated_cost_usd,
            "usage_percent": self.usage_percent,
        }


def _get_month_start() -> float:
    """Return Unix timestamp for the start of the current month."""
    import datetime
    now = datetime.datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start.timestamp()


def check_budget(
    *,
    project_id: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> BudgetStatus:
    """Check whether current usage is within budget limits.

    Reads budget configuration from admin_policy in team_config.json
    and current usage from the audit log.

    Returns BudgetStatus with allowed=False if any limit is exceeded.
    """
    # Load admin policy to get budget config
    budgets = _load_budget_config(project_root)
    if not budgets:
        return BudgetStatus(allowed=True)

    monthly_limit = budgets.get("monthly_token_limit")
    project_limit = budgets.get("per_project_token_limit")
    cost_cap = budgets.get("monthly_cost_cap_usd")

    if not monthly_limit and not project_limit and not cost_cap:
        return BudgetStatus(allowed=True)

    # Get current month's usage from audit log
    month_start = _get_month_start()

    try:
        from prep.core.audit_log import audit_log
        usage = audit_log.get_token_usage(
            project_id=project_id if project_limit else None,
            since=month_start,
        )
    except Exception as e:
        logger.debug("Budget check: audit log unavailable: %s", e)
        return BudgetStatus(allowed=True)

    total_tokens = usage.get("total_tokens", 0)

    # Check monthly token limit
    if monthly_limit and total_tokens >= monthly_limit:
        pct = (total_tokens / monthly_limit) * 100
        reason = (
            f"Monthly token budget exceeded: {total_tokens:,} / {monthly_limit:,} tokens "
            f"({pct:.0f}%). Contact your admin to increase the budget."
        )
        _record_budget_event(total_tokens, monthly_limit, "budget_exceeded", project_id)
        return BudgetStatus(
            allowed=False,
            reason=reason,
            total_tokens_used=total_tokens,
            monthly_limit=monthly_limit,
            usage_percent=pct,
        )

    # Check per-project token limit
    if project_limit and project_id:
        project_usage = audit_log.get_token_usage(
            project_id=project_id,
            since=month_start,
        )
        project_tokens = project_usage.get("total_tokens", 0)
        if project_tokens >= project_limit:
            pct = (project_tokens / project_limit) * 100
            reason = (
                f"Project token budget exceeded: {project_tokens:,} / {project_limit:,} tokens "
                f"for project {project_id} ({pct:.0f}%)."
            )
            _record_budget_event(project_tokens, project_limit, "budget_exceeded", project_id)
            return BudgetStatus(
                allowed=False,
                reason=reason,
                total_tokens_used=project_tokens,
                project_limit=project_limit,
                usage_percent=pct,
            )

    # Check cost cap
    if cost_cap:
        try:
            from prep.core.cost_estimation import estimate_usage_cost
            cost_result = estimate_usage_cost(usage)
            estimated_cost = cost_result.get("total_estimated_cost_usd", 0.0)
            if estimated_cost >= cost_cap:
                pct = (estimated_cost / cost_cap) * 100
                reason = (
                    f"Monthly cost cap exceeded: ${estimated_cost:.2f} / ${cost_cap:.2f} "
                    f"({pct:.0f}%). Contact your admin."
                )
                _record_budget_event(total_tokens, 0, "budget_exceeded", project_id)
                return BudgetStatus(
                    allowed=False,
                    reason=reason,
                    total_tokens_used=total_tokens,
                    cost_cap_usd=cost_cap,
                    estimated_cost_usd=estimated_cost,
                    usage_percent=pct,
                )
        except Exception as e:
            logger.debug("Budget check: cost estimation failed: %s", e)

    # Check 80% threshold for warnings
    usage_pct = 0.0
    if monthly_limit:
        usage_pct = (total_tokens / monthly_limit) * 100
        if usage_pct >= 80:
            _record_budget_event(total_tokens, monthly_limit, "budget_threshold_80", project_id)

    return BudgetStatus(
        allowed=True,
        total_tokens_used=total_tokens,
        monthly_limit=monthly_limit,
        usage_percent=usage_pct,
    )


def _load_budget_config(project_root: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Load budget config from admin_policy in team_config.json."""
    if not project_root:
        return None
    try:
        from prep.core.team_config import load_team_config
        result = load_team_config(project_root)
        if not result.config or not result.config.admin_policy:
            return None
        # Budget config could be in admin_policy directly or in a budgets section
        # For now, check for budget fields at the admin_policy level
        ap = result.config.admin_policy
        # Look for budget config in the raw team_config.json
        import json
        config_path = project_root / ".runprep" / "team_config.json"
        if config_path.exists():
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            return (raw.get("admin_policy") or {}).get("budgets")
    except Exception as e:
        logger.debug("Budget config load failed: %s", e)
    return None


def _record_budget_event(
    tokens: int,
    limit: int,
    event_type: str,
    project_id: Optional[str],
) -> None:
    """Record a budget event to the audit log."""
    try:
        from prep.core.audit_log import audit_log
        audit_log.record(
            event_type,
            f"Budget event: {tokens:,} tokens (limit: {limit:,})",
            project_id=project_id,
            tokens=tokens,
            limit=limit,
        )
    except Exception:
        pass
