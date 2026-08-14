from __future__ import annotations

import argparse

from quant.cli_commands.ai_corpus import AI_CORPUS_COMMANDS, handle_ai_corpus_command, register_ai_corpus_commands
from quant.cli_commands.data_governance import (
    DATA_GOVERNANCE_COMMANDS,
    handle_data_governance_command,
    register_data_governance_commands,
)
from quant.cli_commands.dashboard import handle_dashboard_command, register_dashboard_commands
from quant.cli_commands.intelligence import handle_intelligence_command, register_intelligence_commands
from quant.cli_commands.intraday_account import (
    INTRADAY_ACCOUNT_COMMANDS,
    handle_intraday_account_command,
    register_intraday_account_commands,
)
from quant.cli_commands.maintenance import handle_maintenance_command, register_maintenance_commands
from quant.cli_commands.output import print_manual_history_update_result
from quant.cli_commands.pipeline_run import (
    PIPELINE_RUN_COMMANDS,
    _configured_cost_scenarios,
    _parse_cost_scenario,
    handle_pipeline_run_command,
    register_pipeline_run_commands,
    run_pipeline,
    run_pipeline_cost_sensitivity,
)
from quant.cli_commands.reports import REPORT_EXPORT_COMMANDS, handle_report_export_command, register_report_export_commands
from quant.cli_commands.research import RESEARCH_COMMANDS, handle_research_command, register_research_commands
from quant.cli_commands.site import SITE_COMMANDS, handle_site_command, register_site_commands
from quant.cli_commands.strategy_research import (
    STRATEGY_RESEARCH_COMMANDS,
    _print_walk_forward_trace,
    _run_db_health_gate,
    handle_strategy_research_command,
    register_strategy_research_commands,
)
from quant.cli_commands.system import (
    handle_system_command,
    register_system_commands,
    summarize_system_maintenance_status,
)
from quant.cli_commands.delivery import (
    DELIVERY_COMMANDS,
    handle_delivery_command,
    register_delivery_commands,
    run_daily_brief_pipeline,
    run_watchlist_pipeline,
)
from quant.cli_commands.data_update import (
    DATA_UPDATE_COMMANDS,
    _format_duration,
    _print_tushare_financial_progress,
    handle_data_update_command,
    register_data_update_commands,
)
from quant.reporting.exports import (
    export_brief_account_bill as _export_brief_account_bill,
    export_execution_gate as _export_execution_gate,
    export_financial_pti as _export_financial_pti,
    export_low_turnover_bill as _export_low_turnover_bill,
    export_market_regime_report as _export_market_regime_report,
    export_oos_report as _export_oos_report,
    export_premarket as _export_premarket,
    export_universe_pit as _export_universe_pit,
)


_print_manual_history_update_result = print_manual_history_update_result


def main() -> int:
    top_level_groups = {
        "Data Import & Update": [
            "audit-etf-history",
            "backfill-adjustment-factors",
            "backfill-daily-basic",
            "backfill-etf-history",
            "backfill-index-asof",
            "backfill-tushare-financials",
            "backfill-tushare-history",
            "build-universe",
            "import-history",
            "import-index-history",
            "resolve-etf-universe",
            "sync-etf-catalog",
            "update-financials",
            "update-cross-market-reference-history",
            "update-europe-market-history",
            "update-hk-market-history",
            "update-history",
            "update-us-market-history",
        ],
        "Delivery & Reports": [
            "bill",
            "brief",
            "daily-brief",
            "market-regime",
            "oos-report",
            "premarket",
        ],
        "Governance & Research": [
            "adjustment-audit",
            "ai-corpus",
            "cost-sensitivity",
            "db-health",
            "execution-gate",
            "factor-effectiveness",
            "financial-pti",
            "index-asof-audit",
            "intelligence",
            "overfit-diagnostic",
            "run",
            "strategy-admission",
            "strategy-core-reachability-diagnostic",
            "strategy-csi300-attribution",
            "strategy-exposure-diagnostic",
            "strategy-failure-attribution",
            "strategy-filter-diagnostic",
            "strategy-fold-attribution",
            "strategy-holdings-exposure",
            "strategy-market-context",
            "strategy-missing-core-audit",
            "strategy-participation-overlay",
            "strategy-role-card",
            "universe-pti",
        ],
        "Operations": [
            "dashboard",
            "intraday-account",
            "maintain",
            "site",
            "system",
        ],
    }
    grouped_help_lines = ["Top-level command index by category:"]
    for group_name in sorted(top_level_groups):
        grouped_help_lines.append(f"  {group_name}:")
        grouped_help_lines.extend([f"    - {name}" for name in sorted(top_level_groups[group_name])])
    parser = argparse.ArgumentParser(
        description="Run Phase 0 pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "\n".join(grouped_help_lines)
            + "\n\n"
            "Nested command groups:\n"
            "  brief: account-bill, daily, daily-brief, premarket, watchlist\n"
            "  dashboard: scan\n"
            "  ai-corpus: export, fetch, query, registry\n"
            "  intelligence: collect, import-local, review-candidates, validate\n"
            "  maintain: resume, run, status, stop, supervise, tick\n"
            "  site: build, publish, sync\n"
            "  system: status\n"
        ),
    )
    sub = parser.add_subparsers(dest="cmd")
    register_pipeline_run_commands(sub)
    register_report_export_commands(sub)
    register_data_governance_commands(sub)
    register_strategy_research_commands(sub)
    register_research_commands(sub)
    register_dashboard_commands(sub)
    register_ai_corpus_commands(sub)
    register_intelligence_commands(sub)
    register_maintenance_commands(sub)
    register_system_commands(sub)
    register_site_commands(sub)
    register_delivery_commands(sub)
    register_data_update_commands(sub)
    register_intraday_account_commands(sub)

    args = parser.parse_args()
    if args.cmd in REPORT_EXPORT_COMMANDS:
        return handle_report_export_command(args, parser=parser)
    if args.cmd in DATA_GOVERNANCE_COMMANDS:
        return handle_data_governance_command(args, parser=parser)
    if args.cmd in STRATEGY_RESEARCH_COMMANDS:
        return handle_strategy_research_command(args, parser=parser)
    if args.cmd in RESEARCH_COMMANDS:
        return handle_research_command(args, parser=parser)
    if args.cmd == "dashboard":
        return handle_dashboard_command(args, parser=parser)
    if args.cmd in AI_CORPUS_COMMANDS:
        return handle_ai_corpus_command(args, parser=parser)
    if args.cmd == "intelligence":
        return handle_intelligence_command(args, parser=parser)
    if args.cmd == "maintain":
        return handle_maintenance_command(args, parser=parser)
    if args.cmd == "system":
        return handle_system_command(args, parser=parser)
    if args.cmd in SITE_COMMANDS:
        return handle_site_command(args, parser=parser)
    if args.cmd in DELIVERY_COMMANDS:
        return handle_delivery_command(args, parser=parser)
    if args.cmd in DATA_UPDATE_COMMANDS:
        return handle_data_update_command(args, parser=parser)
    if args.cmd in PIPELINE_RUN_COMMANDS:
        return handle_pipeline_run_command(args, parser=parser)
    if args.cmd in INTRADAY_ACCOUNT_COMMANDS:
        return handle_intraday_account_command(args, parser=parser)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
