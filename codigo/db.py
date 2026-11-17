"""
Camada de acesso ao banco de dados (SQLite).

Responsabilidades:
  * abrir uma conexão por requisição (get_db) e fechá-la no final (close_db);
  * ativar as chaves estrangeiras (o SQLite as ignora por padrão!);
  * criar o banco automaticamente na primeira execução (init_db).
"""
import sqlite3
from pathlib import Path

from flask import current_app, g

BASE_DIR = Path(__file__).parent


def _executar_scripts(conexao, com_exemplos):
    """Roda schema.sql (e seed.sql, se pedido) na conexão informada."""
    conexao.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    if com_exemplos:
        conexao.executescript((BASE_DIR / "seed.sql").read_text(encoding="utf-8"))
    conexao.commit()


def get_db():
    """Devolve a conexão da requisição atual, criando-a se necessário."""
    if "db" not in g:
        caminho = Path(current_app.config["DATABASE"])
        banco_novo = not caminho.exists()

        g.db = sqlite3.connect(caminho)
        g.db.row_factory = sqlite3.Row            # permite linha["coluna"]
        g.db.execute("PRAGMA foreign_keys = ON")  # integridade referencial

        if banco_novo:                            # primeira execução
            _executar_scripts(g.db, current_app.config["CARREGAR_EXEMPLOS"])
            g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(erro=None):
    """Fecha a conexão ao final da requisição."""
    conexao = g.pop("db", None)
    if conexao is not None:
        conexao.close()


def init_db(com_exemplos=True):
    """Recria todas as tabelas (apaga os dados!). Usado pelo comando CLI."""
    _executar_scripts(get_db(), com_exemplos)