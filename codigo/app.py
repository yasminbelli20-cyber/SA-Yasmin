import os
os.system('cls')
import sqlite3
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import db
import regras

# =====================================================================
# 1. CONFIGURAÇÃO
# =====================================================================
BASE_DIR = Path(__file__).parent

app = Flask(__name__)
app.config.update(
    DATABASE=str(BASE_DIR / "delivery.db"),
    SECRET_KEY="troque-esta-chave-em-producao",  # exigida pelo flash()
    CARREGAR_EXEMPLOS=True,                      # popula o banco na 1ª execução
)
app.teardown_appcontext(db.close_db)

# Filtros usados nos templates: {{ valor|moeda }} e {{ status|rotulo }}
app.add_template_filter(regras.centavos_para_reais, "moeda")
app.add_template_filter(lambda valor: regras.ROTULOS.get(valor, valor), "rotulo")


@app.cli.command("init-db")
def comando_init_db():
    """Recria o banco com dados de exemplo: flask --app app init-db"""
    db.init_db(com_exemplos=True)
    print("Banco de dados recriado com sucesso.")


# =====================================================================
# 2. FUNÇÕES AUXILIARES DE BANCO
# Todos os valores vindos do usuário são enviados por "?" (parâmetros),
# nunca concatenados no SQL — isso evita SQL Injection.
# =====================================================================
def consultar(sql, params=()):
    """SELECT que devolve várias linhas."""
    return db.get_db().execute(sql, params).fetchall()


def consultar_um(sql, params=()):
    """SELECT que devolve uma linha (ou None)."""
    return db.get_db().execute(sql, params).fetchone()


def executar(sql, params=()):
    """INSERT/UPDATE/DELETE com commit; desfaz tudo se der erro."""
    banco = db.get_db()
    try:
        cursor = banco.execute(sql, params)
        banco.commit()
        return cursor
    except sqlite3.Error:
        banco.rollback()
        raise


def ou_404(linha):
    """Se o registro não existe, responde 'página não encontrada'."""
    if linha is None:
        abort(404)
    return linha


def salvar(tabela, valores, id=None):
    """
    INSERT (id=None) ou UPDATE (id informado) a partir de um dicionário
    {coluna: valor}. Os nomes de tabela/coluna vêm do código (nunca do
    usuário); os valores sempre passam por parâmetros.
    """
    colunas = list(valores)
    if id is None:
        sql = (f"INSERT INTO {tabela} ({', '.join(colunas)}) "
               f"VALUES ({', '.join('?' * len(colunas))})")
        return executar(sql, tuple(valores.values()))
    sql = f"UPDATE {tabela} SET {', '.join(c + ' = ?' for c in colunas)} WHERE id = ?"
    return executar(sql, (*valores.values(), id))


def para_formulario(linha):
    """Converte uma linha do banco em dados de formulário (centavos -> '12,50')."""
    dados = dict(linha)
    for chave in list(dados):
        if chave.endswith("_centavos"):
            dados[chave[: -len("_centavos")]] = regras.centavos_para_campo(dados[chave])
    return dados


# =====================================================================
# 3. TELAS GENÉRICAS (usadas por clientes, restaurantes, produtos...)
# =====================================================================
def tela_form(*, id, tabela, titulo, campos, validar, destino, msg_duplicado, padrao=None):
    """
    Trata GET (exibir o formulário) e POST (validar e gravar) de um cadastro.
    Serve tanto para CRIAR (id=None) quanto para EDITAR (id informado).
    """
    erros = []
    if request.method == "POST":
        valores, erros = validar(request.form)
        if not erros:
            try:
                salvar(tabela, valores, id)
                flash("Cadastro salvo com sucesso.", "ok")
                return redirect(destino)
            except sqlite3.IntegrityError:
                erros.append(msg_duplicado)
        dados = request.form                       # reexibe o que foi digitado
    elif id is not None:
        linha = ou_404(consultar_um(f"SELECT * FROM {tabela} WHERE id = ?", (id,)))
        dados = para_formulario(linha)             # preenche para edição
    else:
        dados = padrao or {}
    return render_template("form.html", titulo=titulo, campos=campos(),
                           dados=dados, erros=erros, voltar=destino)


def tela_excluir(tabela, id, destino, nome_item):
    """Exclui um registro; se houver dados vinculados, avisa em vez de quebrar."""
    try:
        executar(f"DELETE FROM {tabela} WHERE id = ?", (id,))
        flash(f"{nome_item} excluído(a) com sucesso.", "ok")
    except sqlite3.IntegrityError:
        flash(f"Não é possível excluir: {nome_item} possui registros vinculados "
              "(por exemplo, pedidos).", "erro")
    return redirect(destino)


# =====================================================================
# 4. ROTAS
# =====================================================================

# Consulta base dos pedidos: junta cliente, restaurante, entregador e
# endereço, e calcula o total (itens + taxa de entrega).
SQL_PEDIDOS = """
    SELECT p.*,
           c.nome  AS cliente,
           r.nome  AS restaurante,
           ent.nome AS entregador,
           en.rua, en.numero, en.bairro, en.cidade, en.complemento,
           COALESCE((SELECT SUM(i.quantidade * i.preco_unitario_centavos)
                     FROM item_pedido i WHERE i.pedido_id = p.id), 0)
             + p.taxa_entrega_centavos AS total_centavos
    FROM pedido p
    JOIN cliente c       ON c.id = p.cliente_id
    JOIN restaurante r   ON r.id = p.restaurante_id
    JOIN endereco en     ON en.id = p.endereco_id
    LEFT JOIN entregador ent ON ent.id = p.entregador_id
"""


# ---------------------------------------------------------------- Início
@app.route("/")
def inicio():
    resumo = {
        "clientes": consultar_um("SELECT COUNT(*) AS n FROM cliente")["n"],
        "restaurantes": consultar_um("SELECT COUNT(*) AS n FROM restaurante WHERE ativo = 1")["n"],
        "em_andamento": consultar_um(
            "SELECT COUNT(*) AS n FROM pedido WHERE status NOT IN ('entregue', 'cancelado')")["n"],
        "faturamento": sum(p["total_centavos"] for p in
                           consultar(SQL_PEDIDOS + " WHERE p.status = 'entregue'")),
    }
    recentes = consultar(SQL_PEDIDOS + " ORDER BY p.id DESC LIMIT 5")
    return render_template("index.html", resumo=resumo, pedidos=recentes)


# -------------------------------------------------------------- Clientes
def validar_cliente(f):
    erros = []
    nome = f.get("nome", "").strip()
    telefone = f.get("telefone", "").strip()
    email = f.get("email", "").strip().lower()
    if len(nome) < 3:
        erros.append("Informe o nome completo (mínimo de 3 letras).")
    if not regras.validar_telefone(telefone):
        erros.append("Telefone inválido. Use DDD + número, ex.: (11) 98888-1111.")
    if not regras.validar_email(email):
        erros.append("E-mail inválido.")
    return {"nome": nome, "telefone": telefone, "email": email}, erros


def campos_cliente():
    return [
        {"nome": "nome", "rotulo": "Nome completo", "tipo": "text"},
        {"nome": "telefone", "rotulo": "Telefone", "tipo": "tel", "ajuda": "Com DDD, ex.: (11) 98888-1111"},
        {"nome": "email", "rotulo": "E-mail", "tipo": "email"},
    ]


@app.route("/clientes")
def clientes_listar():
    q = request.args.get("q", "").strip()
    linhas = consultar("SELECT * FROM cliente WHERE nome LIKE ? OR email LIKE ? ORDER BY nome",
                       (f"%{q}%", f"%{q}%"))
    colunas = [("Nome", "nome", None), ("Telefone", "telefone", None), ("E-mail", "email", None)]
    return render_template("lista.html", titulo="Clientes", base="clientes", colunas=colunas,
                           linhas=linhas, q=q, detalhe=True, rotulo_novo="Novo cliente")


@app.route("/clientes/novo", methods=["GET", "POST"], defaults={"id": None})
@app.route("/clientes/<int:id>/editar", methods=["GET", "POST"])
def clientes_form(id):
    return tela_form(id=id, tabela="cliente", titulo="Editar cliente" if id else "Novo cliente",
                     campos=campos_cliente, validar=validar_cliente,
                     destino=url_for("clientes_listar"),
                     msg_duplicado="Já existe um cliente cadastrado com este e-mail.")


@app.post("/clientes/<int:id>/excluir")
def clientes_excluir(id):
    return tela_excluir("cliente", id, url_for("clientes_listar"), "Cliente")


@app.route("/clientes/<int:id>")
def clientes_detalhe(id):
    cliente = ou_404(consultar_um("SELECT * FROM cliente WHERE id = ?", (id,)))
    enderecos = consultar("SELECT * FROM endereco WHERE cliente_id = ? ORDER BY id", (id,))
    pedidos = consultar(SQL_PEDIDOS + " WHERE p.cliente_id = ? ORDER BY p.id DESC", (id,))
    return render_template("cliente_detalhe.html", cliente=cliente, enderecos=enderecos, pedidos=pedidos)


# ------------------------------------------------------------- Endereços
@app.post("/clientes/<int:id>/enderecos")
def enderecos_novo(id):
    ou_404(consultar_um("SELECT id FROM cliente WHERE id = ?", (id,)))
    f = request.form
    rua, numero = f.get("rua", "").strip(), f.get("numero", "").strip()
    bairro, cidade = f.get("bairro", "").strip(), f.get("cidade", "").strip()
    complemento = f.get("complemento", "").strip() or None
    if not (rua and numero and bairro and cidade):
        flash("Preencha rua, número, bairro e cidade.", "erro")
    else:
        executar("INSERT INTO endereco (cliente_id, rua, numero, bairro, cidade, complemento) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (id, rua, numero, bairro, cidade, complemento))
        flash("Endereço adicionado.", "ok")
    return redirect(url_for("clientes_detalhe", id=id))


@app.post("/enderecos/<int:id>/excluir")
def enderecos_excluir(id):
    endereco = ou_404(consultar_um("SELECT * FROM endereco WHERE id = ?", (id,)))
    return tela_excluir("endereco", id, url_for("clientes_detalhe", id=endereco["cliente_id"]), "Endereço")


# ----------------------------------------------------------- Restaurantes
def campos_restaurante():
    categorias = consultar("SELECT id, nome FROM categoria ORDER BY nome")
    return [
        {"nome": "nome", "rotulo": "Nome do restaurante", "tipo": "text"},
        {"nome": "categoria_id", "rotulo": "Categoria", "tipo": "select",
         "opcoes": [(c["id"], c["nome"]) for c in categorias]},
        {"nome": "telefone", "rotulo": "Telefone", "tipo": "tel"},
        {"nome": "taxa_entrega", "rotulo": "Taxa de entrega (R$)", "tipo": "text", "ajuda": "Ex.: 5,00"},
        {"nome": "ativo", "rotulo": "Restaurante ativo (recebendo pedidos)", "tipo": "checkbox"},
    ]


def validar_restaurante(f):
    erros = []
    nome = f.get("nome", "").strip()
    categoria_id = f.get("categoria_id", "")
    telefone = f.get("telefone", "").strip()
    if len(nome) < 2:
        erros.append("Informe o nome do restaurante.")
    if not consultar_um("SELECT 1 FROM categoria WHERE id = ?", (categoria_id,)):
        erros.append("Selecione uma categoria válida.")
    if not regras.validar_telefone(telefone):
        erros.append("Telefone inválido. Use DDD + número.")
    try:
        taxa = regras.reais_para_centavos(f.get("taxa_entrega", ""))
    except ValueError:
        taxa = 0
        erros.append("Taxa de entrega inválida. Use o formato 5,00.")
    return {"nome": nome, "categoria_id": categoria_id, "telefone": telefone,
            "taxa_entrega_centavos": taxa, "ativo": 1 if f.get("ativo") else 0}, erros


@app.route("/restaurantes")
def restaurantes_listar():
    q = request.args.get("q", "").strip()
    linhas = consultar("""SELECT r.*, c.nome AS categoria FROM restaurante r
                          JOIN categoria c ON c.id = r.categoria_id
                          WHERE r.nome LIKE ? ORDER BY r.nome""", (f"%{q}%",))
    colunas = [("Nome", "nome", None), ("Categoria", "categoria", None),
               ("Telefone", "telefone", None), ("Taxa", "taxa_entrega_centavos", "moeda"),
               ("Ativo", "ativo", "simnao")]
    return render_template("lista.html", titulo="Restaurantes", base="restaurantes", colunas=colunas,
                           linhas=linhas, q=q, detalhe=False, rotulo_novo="Novo restaurante")


@app.route("/restaurantes/novo", methods=["GET", "POST"], defaults={"id": None})
@app.route("/restaurantes/<int:id>/editar", methods=["GET", "POST"])
def restaurantes_form(id):
    return tela_form(id=id, tabela="restaurante",
                     titulo="Editar restaurante" if id else "Novo restaurante",
                     campos=campos_restaurante, validar=validar_restaurante,
                     destino=url_for("restaurantes_listar"),
                     msg_duplicado="Não foi possível salvar o restaurante.",
                     padrao={"ativo": "1"})


@app.post("/restaurantes/<int:id>/excluir")
def restaurantes_excluir(id):
    return tela_excluir("restaurante", id, url_for("restaurantes_listar"), "Restaurante")


# --------------------------------------------------------------- Produtos
def campos_produto():
    restaurantes = consultar("SELECT id, nome FROM restaurante ORDER BY nome")
    return [
        {"nome": "restaurante_id", "rotulo": "Restaurante", "tipo": "select",
         "opcoes": [(r["id"], r["nome"]) for r in restaurantes]},
        {"nome": "nome", "rotulo": "Nome do produto", "tipo": "text"},
        {"nome": "descricao", "rotulo": "Descrição", "tipo": "textarea", "obrigatorio": False},
        {"nome": "preco", "rotulo": "Preço (R$)", "tipo": "text", "ajuda": "Ex.: 29,90"},
        {"nome": "disponivel", "rotulo": "Disponível no cardápio", "tipo": "checkbox"},
    ]


def validar_produto(f):
    erros = []
    restaurante_id = f.get("restaurante_id", "")
    nome = f.get("nome", "").strip()
    descricao = f.get("descricao", "").strip() or None
    if not consultar_um("SELECT 1 FROM restaurante WHERE id = ?", (restaurante_id,)):
        erros.append("Selecione um restaurante válido.")
    if len(nome) < 2:
        erros.append("Informe o nome do produto.")
    try:
        preco = regras.reais_para_centavos(f.get("preco", ""))
        if preco <= 0:
            erros.append("O preço deve ser maior que zero.")
    except ValueError:
        preco = 0
        erros.append("Preço inválido. Use o formato 29,90.")
    return {"restaurante_id": restaurante_id, "nome": nome, "descricao": descricao,
            "preco_centavos": preco, "disponivel": 1 if f.get("disponivel") else 0}, erros


@app.route("/produtos")
def produtos_listar():
    q = request.args.get("q", "").strip()
    linhas = consultar("""SELECT p.*, r.nome AS restaurante FROM produto p
                          JOIN restaurante r ON r.id = p.restaurante_id
                          WHERE p.nome LIKE ? OR r.nome LIKE ?
                          ORDER BY r.nome, p.nome""", (f"%{q}%", f"%{q}%"))
    colunas = [("Restaurante", "restaurante", None), ("Produto", "nome", None),
               ("Preço", "preco_centavos", "moeda"), ("Disponível", "disponivel", "simnao")]
    return render_template("lista.html", titulo="Produtos", base="produtos", colunas=colunas,
                           linhas=linhas, q=q, detalhe=False, rotulo_novo="Novo produto")


@app.route("/produtos/novo", methods=["GET", "POST"], defaults={"id": None})
@app.route("/produtos/<int:id>/editar", methods=["GET", "POST"])
def produtos_form(id):
    return tela_form(id=id, tabela="produto", titulo="Editar produto" if id else "Novo produto",
                     campos=campos_produto, validar=validar_produto,
                     destino=url_for("produtos_listar"),
                     msg_duplicado="Este restaurante já possui um produto com esse nome.",
                     padrao={"disponivel": "1"})


@app.post("/produtos/<int:id>/excluir")
def produtos_excluir(id):
    return tela_excluir("produto", id, url_for("produtos_listar"), "Produto")


# ------------------------------------------------------------ Entregadores
def campos_entregador():
    return [
        {"nome": "nome", "rotulo": "Nome completo", "tipo": "text"},
        {"nome": "telefone", "rotulo": "Telefone", "tipo": "tel"},
        {"nome": "veiculo", "rotulo": "Veículo", "tipo": "select",
         "opcoes": [(v, regras.ROTULOS[v]) for v in regras.VEICULOS]},
        {"nome": "ativo", "rotulo": "Entregador ativo", "tipo": "checkbox"},
    ]


def validar_entregador(f):
    erros = []
    nome = f.get("nome", "").strip()
    telefone = f.get("telefone", "").strip()
    veiculo = f.get("veiculo", "")
    if len(nome) < 3:
        erros.append("Informe o nome completo (mínimo de 3 letras).")
    if not regras.validar_telefone(telefone):
        erros.append("Telefone inválido. Use DDD + número.")
    if veiculo not in regras.VEICULOS:
        erros.append("Selecione um veículo.")
    return {"nome": nome, "telefone": telefone, "veiculo": veiculo,
            "ativo": 1 if f.get("ativo") else 0}, erros


@app.route("/entregadores")
def entregadores_listar():
    q = request.args.get("q", "").strip()
    linhas = consultar("SELECT * FROM entregador WHERE nome LIKE ? ORDER BY nome", (f"%{q}%",))
    colunas = [("Nome", "nome", None), ("Telefone", "telefone", None),
               ("Veículo", "veiculo", "rotulo"), ("Ativo", "ativo", "simnao")]
    return render_template("lista.html", titulo="Entregadores", base="entregadores", colunas=colunas,
                           linhas=linhas, q=q, detalhe=False, rotulo_novo="Novo entregador")


@app.route("/entregadores/novo", methods=["GET", "POST"], defaults={"id": None})
@app.route("/entregadores/<int:id>/editar", methods=["GET", "POST"])
def entregadores_form(id):
    return tela_form(id=id, tabela="entregador",
                     titulo="Editar entregador" if id else "Novo entregador",
                     campos=campos_entregador, validar=validar_entregador,
                     destino=url_for("entregadores_listar"),
                     msg_duplicado="Não foi possível salvar o entregador.",
                     padrao={"ativo": "1"})


@app.post("/entregadores/<int:id>/excluir")
def entregadores_excluir(id):
    return tela_excluir("entregador", id, url_for("entregadores_listar"), "Entregador")


# ---------------------------------------------------------------- Pedidos
@app.route("/pedidos")
def pedidos_listar():
    status = request.args.get("status", "")
    sql, params = SQL_PEDIDOS, ()
    if status in regras.STATUS:
        sql += " WHERE p.status = ?"
        params = (status,)
    pedidos = consultar(sql + " ORDER BY p.id DESC", params)
    return render_template("pedidos_lista.html", pedidos=pedidos, status=status, todos_status=regras.STATUS)


@app.route("/pedidos/novo")
def pedidos_novo():
    """Passo 1: escolher cliente e restaurante (o formulário envia por GET ao passo 2)."""
    return render_template(
        "pedido_novo.html",
        clientes=consultar("SELECT id, nome FROM cliente ORDER BY nome"),
        restaurantes=consultar("SELECT id, nome FROM restaurante WHERE ativo = 1 ORDER BY nome"))


@app.route("/pedidos/novo/itens", methods=["GET", "POST"])
def pedidos_itens():
    """Passo 2: escolher endereço, pagamento e quantidades; GET mostra, POST grava."""
    cliente = consultar_um("SELECT * FROM cliente WHERE id = ?", (request.values.get("cliente_id"),))
    restaurante = consultar_um("SELECT * FROM restaurante WHERE id = ? AND ativo = 1",
                               (request.values.get("restaurante_id"),))
    if cliente is None or restaurante is None:
        flash("Selecione um cliente e um restaurante ativo.", "erro")
        return redirect(url_for("pedidos_novo"))

    enderecos = consultar("SELECT * FROM endereco WHERE cliente_id = ? ORDER BY id", (cliente["id"],))
    if not enderecos:
        flash("Cadastre ao menos um endereço para este cliente antes de criar o pedido.", "erro")
        return redirect(url_for("clientes_detalhe", id=cliente["id"]))
    produtos = consultar("SELECT * FROM produto WHERE restaurante_id = ? AND disponivel = 1 ORDER BY nome",
                         (restaurante["id"],))

    erros = []
    if request.method == "POST":
        endereco_id = request.form.get("endereco_id", "")
        pagamento = request.form.get("forma_pagamento", "")
        if endereco_id not in [str(e["id"]) for e in enderecos]:
            erros.append("Selecione um endereço de entrega do cliente.")
        if pagamento not in regras.FORMAS_PAGAMENTO:
            erros.append("Selecione a forma de pagamento.")

        # Lê a quantidade de cada produto do cardápio (campos qtd_<id>)
        itens, quantidade_invalida = [], False
        for p in produtos:
            bruto = request.form.get(f"qtd_{p['id']}", "0").strip() or "0"
            if not bruto.isdigit() or int(bruto) > 50:
                erros.append(f"Quantidade inválida para {p['nome']} (use de 0 a 50).")
                quantidade_invalida = True
            elif int(bruto) > 0:
                itens.append((p["id"], int(bruto), p["preco_centavos"]))  # preço "congelado"
        if not itens and not quantidade_invalida:
            erros.append("Adicione ao menos um item ao pedido.")

        if not erros:
            # Pedido + itens são gravados juntos: ou grava tudo, ou nada (transação)
            banco = db.get_db()
            try:
                cursor = banco.execute(
                    "INSERT INTO pedido (cliente_id, restaurante_id, endereco_id, forma_pagamento, "
                    "taxa_entrega_centavos) VALUES (?, ?, ?, ?, ?)",
                    (cliente["id"], restaurante["id"], endereco_id, pagamento,
                     restaurante["taxa_entrega_centavos"]))
                banco.executemany(
                    "INSERT INTO item_pedido (pedido_id, produto_id, quantidade, preco_unitario_centavos) "
                    "VALUES (?, ?, ?, ?)", [(cursor.lastrowid, *item) for item in itens])
                banco.commit()
            except sqlite3.Error:
                banco.rollback()
                erros.append("Erro ao gravar o pedido. Tente novamente.")
            else:
                flash("Pedido criado com sucesso.", "ok")
                return redirect(url_for("pedidos_detalhe", id=cursor.lastrowid))

    return render_template("pedido_itens.html", cliente=cliente, restaurante=restaurante,
                           enderecos=enderecos, produtos=produtos, erros=erros,
                           dados=request.form, pagamentos=regras.FORMAS_PAGAMENTO)


@app.route("/pedidos/<int:id>")
def pedidos_detalhe(id):
    pedido = ou_404(consultar_um(SQL_PEDIDOS + " WHERE p.id = ?", (id,)))
    itens = consultar("""SELECT i.*, pr.nome AS produto,
                                i.quantidade * i.preco_unitario_centavos AS subtotal_centavos
                         FROM item_pedido i JOIN produto pr ON pr.id = i.produto_id
                         WHERE i.pedido_id = ? ORDER BY pr.nome""", (id,))
    entregadores = consultar("SELECT id, nome, veiculo FROM entregador WHERE ativo = 1 ORDER BY nome")
    return render_template("pedido_detalhe.html", pedido=pedido, itens=itens, entregadores=entregadores,
                           proximo=regras.proximo_status(pedido["status"]),
                           pode_cancelar=regras.pode_cancelar(pedido["status"]))


@app.post("/pedidos/<int:id>/status")
def pedidos_status(id):
    pedido = ou_404(consultar_um("SELECT * FROM pedido WHERE id = ?", (id,)))
    novo = request.form.get("status", "")
    if not regras.pode_transitar(pedido["status"], novo):
        flash("Mudança de status não permitida para este pedido.", "erro")
    elif novo == "saiu_para_entrega" and pedido["entregador_id"] is None:
        flash("Atribua um entregador antes de enviar o pedido para entrega.", "erro")
    else:
        executar("UPDATE pedido SET status = ? WHERE id = ?", (novo, id))
        flash(f"Status atualizado para: {regras.ROTULOS[novo]}.", "ok")
    return redirect(url_for("pedidos_detalhe", id=id))


@app.post("/pedidos/<int:id>/entregador")
def pedidos_entregador(id):
    pedido = ou_404(consultar_um("SELECT * FROM pedido WHERE id = ?", (id,)))
    entregador = consultar_um("SELECT * FROM entregador WHERE id = ? AND ativo = 1",
                              (request.form.get("entregador_id"),))
    if pedido["status"] in ("entregue", "cancelado"):
        flash("Este pedido já foi finalizado.", "erro")
    elif entregador is None:
        flash("Selecione um entregador ativo.", "erro")
    else:
        executar("UPDATE pedido SET entregador_id = ? WHERE id = ?", (entregador["id"], id))
        flash(f"Entregador {entregador['nome']} atribuído ao pedido.", "ok")
    return redirect(url_for("pedidos_detalhe", id=id))


@app.post("/pedidos/<int:id>/excluir")
def pedidos_excluir(id):
    pedido = ou_404(consultar_um("SELECT * FROM pedido WHERE id = ?", (id,)))
    if pedido["status"] != "cancelado":
        flash("Apenas pedidos cancelados podem ser excluídos. Cancele o pedido primeiro.", "erro")
        return redirect(url_for("pedidos_detalhe", id=id))
    return tela_excluir("pedido", id, url_for("pedidos_listar"), "Pedido")  # itens saem por CASCADE


if __name__ == "__main__":
    app.run(debug=True)

