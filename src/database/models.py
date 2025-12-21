from datetime import UTC, datetime

from sqlalchemy import BigInteger, ForeignKey, String, func, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bot.internal.context import GameStatus


class Base(DeclarativeBase):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
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


class Game(Base):
    __tablename__ = "games"

    status: Mapped[GameStatus] = mapped_column(default=GameStatus.ACTIVE)
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    host_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    total_pot: Mapped[int] = mapped_column(Integer, default=0)
    mvp_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    message_id: Mapped[int | None]
    photo_name: Mapped[str | None]
    photo_id: Mapped[str | None]
    duration: Mapped[int | None]
    ratio: Mapped[int] = mapped_column(Integer, default=1)

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
