from dataclasses import dataclass

from database.models import Debt


@dataclass(slots=True)
class GameBalanceData:
    total_pot: int | None
    delta: int | None


@dataclass(slots=True)
class DebtData:
    game_id: int
    creditor_id: int
    debtor_id: int
    amount: int

    def to_model(self) -> Debt:
        return Debt(
            game_id=self.game_id,
            creditor_id=self.creditor_id,
            debtor_id=self.debtor_id,
            amount=self.amount,
        )
