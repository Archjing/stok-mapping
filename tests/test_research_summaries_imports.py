from __future__ import annotations

import phase0.strategy_role_card as legacy_role_card
from phase0.research.summaries import StrategyRoleCardResult, run_strategy_role_card as new_role_card_runner
from phase0.research.summaries import role_card
from phase0.research.summaries.role_card import ADMISSION_PASS_ACTIONS
from phase0.research.summaries.role_card import StrategyRoleCardResult as NewRoleCardResult
from phase0.research.summaries.role_card import run_strategy_role_card
from phase0.strategy_role_card import ADMISSION_PASS_ACTIONS as legacy_admission_pass_actions
from phase0.strategy_role_card import run_strategy_role_card as legacy_role_card_runner


def test_legacy_strategy_role_card_import_aliases_new_module() -> None:
    assert legacy_role_card is role_card
    assert legacy_role_card_runner is run_strategy_role_card
    assert legacy_admission_pass_actions is ADMISSION_PASS_ACTIONS
    assert new_role_card_runner is run_strategy_role_card
    assert StrategyRoleCardResult is NewRoleCardResult
