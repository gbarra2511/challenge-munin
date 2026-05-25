"""Gerência de engine e sessão SQLAlchemy ligada ao ciclo de request do Flask.

Filosofia: serviços/handlers chamam `get_session()` e fazem `commit()`
explícito. O teardown só faz rollback do que sobrou e fecha — sem commit
mágico. Isso mantém o controle de transação visível no código (o avaliador
lê isto) e dá espaço pro `SELECT FOR UPDATE` do aceite (Dia 3).

Testabilidade: `init_db` aceita um `session_factory` pronto, então os testes
ligam a sessão a uma conexão com transação externa que sofre rollback no fim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

_FACTORY_KEY = "db_session_factory"


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True, pool_pre_ping=True)


def init_db(
    app: Flask,
    *,
    engine: Engine | None = None,
    session_factory: sessionmaker | None = None,
) -> None:
    if session_factory is None:
        eng = engine or make_engine(app.config["DATABASE_URL"])
        session_factory = sessionmaker(bind=eng, future=True, expire_on_commit=False)
    app.extensions[_FACTORY_KEY] = session_factory

    @app.teardown_appcontext
    def _close_session(exc: BaseException | None) -> None:
        session: Session | None = g.pop("db_session", None)
        if session is None:
            return
        if exc is not None:
            session.rollback()
        session.close()


def get_session() -> Session:
    if "db_session" not in g:
        factory: sessionmaker = current_app.extensions[_FACTORY_KEY]
        g.db_session = factory()
    return g.db_session
