import pytest
from collections import defaultdict

from bot.controllers.debt import equalizer


@pytest.mark.parametrize(
    "balances, expected_debts_quantity",
    [
        ({1: 1000, 2: -1000}, 1),
        ({1: 2000, 2: -1000, 3: -1000}, 2),
        ({1: 1000, 2: 1000, 3: -2000}, 2),
        ({}, 0),
        ({1: 0, 2: 0}, 0),
        ({1: 500, 2: -200, 3: -300}, 2),
        ({1: 1000, 2: 1000, 3: -1000, 4: -1000}, 2),
        ({1: 2500, 2: -1000, 3: -1500}, 2),
        ({1: 2000, 2: 2000, 3: -1000, 4: -3000}, 3),
        ({1: 1000, 2: 1000, 3: 1000, 4: -3000}, 3),
        ({1: 1000, 2: 1000, 3: -500, 4: -500, 5: -1000}, 3),
        ({1: 5300, 2: 700, 3: 1000, 4: -3000, 5: -1000, 6: -3000}, 4),
    ],
)
def test_equalizer_balance_and_transaction_count(balances, expected_debts_quantity):
    result = equalizer(balances, game_id=42)

    assert len(result) == expected_debts_quantity

    net = defaultdict(int)
    for debt in result:
        net[debt.creditor_id] += debt.amount
        net[debt.debtor_id] -= debt.amount

    for user_id, amount in balances.items():
        assert net[user_id] == amount
