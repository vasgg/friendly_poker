from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bot.config import settings
from bot.internal.context import GameStatus


class Base(DeclarativeBase):
    __abstract__ = True
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(settings.bot.TIMEZONE),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, primary_key=True
    )
    fullname: Mapped[str]
    username: Mapped[str | None] = mapped_column(String(32))
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="0")
    IBAN: Mapped[str | None]
    bank: Mapped[str | None]
    name_surname: Mapped[str | None]
    games_played: Mapped[int] = mapped_column(default=0, server_default="0")
    last_time_played: Mapped[bool] = mapped_column(default=False, server_default="0")

    games_hosted: Mapped[list["Game"]] = relationship(
        "Game",
        foreign_keys="[Game.host_id]",
        back_populates="host",
    )
    games_administered: Mapped[list["Game"]] = relationship(
        "Game",
        foreign_keys="[Game.admin_id]",
        back_populates="admin",
    )
    records: Mapped[list["Record"]] = relationship(
        "Record",
        back_populates="user",
    )
    debts_as_creditor: Mapped[list["Debt"]] = relationship(
        "Debt",
        foreign_keys="[Debt.creditor_id]",
        back_populates="creditor",
    )
    debts_as_debtor: Mapped[list["Debt"]] = relationship(
        "Debt",
        foreign_keys="[Debt.debtor_id]",
        back_populates="debtor",
    )

    def __str__(self):
        return f"{self.__class__.__name__}(id: {self.id}, fullname: {self.fullname})"

    def __repr__(self):
        return str(self)

    def get_statistics(self, session):
        result = (
            session.query(
                func.sum(Record.buy_in).label("total_buy_in"),
                func.sum(Record.buy_out).label("total_buy_out"),
                func.count(Record.id).label("games_played"),
            )
            .filter(Record.user_id == self.id)
            .one()
        )
        total_buy_in, total_buy_out, games_played = result
        return {
            "total_buy_in": total_buy_in or 0,
            "total_buy_out": total_buy_out or 0,
            "net_result": (total_buy_out or 0) - (total_buy_in or 0),
            "games_played": games_played or 0,
        }

    def get_creditor_statistics(self, session):
        debts = session.query(Debt).filter_by(creditor_id=self.id).all()
        total_loaned = sum(debt.amount for debt in debts)
        unpaid_loans = sum(debt.amount for debt in debts if not debt.is_paid)
        return {"total_loaned": total_loaned, "unpaid_loans": unpaid_loans}

    def get_debtor_statistics(self, session):
        debts = session.query(Debt).filter_by(debtor_id=self.id).all()
        total_borrowed = sum(debt.amount for debt in debts)
        unpaid_debts = sum(debt.amount for debt in debts if not debt.is_paid)
        return {"total_borrowed": total_borrowed, "unpaid_debts": unpaid_debts}


class Game(Base):
    __tablename__ = "games"

    status: Mapped[GameStatus] = mapped_column(default=GameStatus.ACTIVE)
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    host_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    total_pot: Mapped[int] = mapped_column(default=0)
    mvp_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    message_id: Mapped[int | None]
    photo_name: Mapped[str | None]
    photo_id: Mapped[str | None]
    duration: Mapped[int | None]

    admin: Mapped["User"] = relationship(
        "User",
        foreign_keys=[admin_id],
        back_populates="games_administered",
    )
    host: Mapped["User"] = relationship(
        "User",
        foreign_keys=[host_id],
        back_populates="games_hosted",
    )
    records: Mapped[list["Record"]] = relationship(
        "Record",
        back_populates="game",
        cascade="all, delete-orphan",
    )
    debts: Mapped[list["Debt"]] = relationship(
        "Debt",
        back_populates="game",
        cascade="all, delete-orphan",
    )


class Record(Base):
    __tablename__ = "records"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    buy_in: Mapped[int | None]
    buy_out: Mapped[int | None]
    net_profit: Mapped[int | None]
    ROI: Mapped[int | None]

    user: Mapped["User"] = relationship(
        "User",
        back_populates="records",
    )
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="records",
    )

    def __lt__(self, other):
        return self.buy_in < other.buy_in

    @property
    def net_result(self):
        if self.buy_in is not None and self.buy_out is not None:
            return self.buy_out - self.buy_in
        return None


class Debt(Base):
    __tablename__ = "debts"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    creditor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    debtor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    debt_message_id: Mapped[int | None]
    amount: Mapped[int]
    is_paid: Mapped[bool] = mapped_column(default=False, server_default="0")
    paid_at: Mapped[datetime | None]

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="debts",
    )
    creditor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[creditor_id],
        back_populates="debts_as_creditor",
    )
    debtor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[debtor_id],
        back_populates="debts_as_debtor",
    )
