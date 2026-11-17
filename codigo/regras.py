"""
Regras de negócio e funções utilitárias do sistema de delivery.

Todas as funções aqui são PURAS (não acessam banco nem Flask), o que
as torna fáceis de testar com testes unitários (veja tests/test_regras.py).
"""
import re
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------
# Constantes do domínio
# ---------------------------------------------------------------------
STATUS = ("recebido", "preparando", "saiu_para_entrega", "entregue", "cancelado")
FORMAS_PAGAMENTO = ("pix", "cartao", "dinheiro")
VEICULOS = ("moto", "bicicleta", "carro")

# Textos amigáveis exibidos nas telas
ROTULOS = {
    "recebido": "Recebido",
    "preparando": "Em preparo",
    "saiu_para_entrega": "Saiu para entrega",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
    "pix": "Pix",
    "cartao": "Cartão",
    "dinheiro": "Dinheiro",
    "moto": "Moto",
    "bicicleta": "Bicicleta",
    "carro": "Carro",
}

# Fluxo normal do pedido: cada status só pode avançar para o próximo
_PROXIMO = {
    "recebido": "preparando",
    "preparando": "saiu_para_entrega",
    "saiu_para_entrega": "entregue",
}
# Depois que o pedido sai para entrega, não pode mais ser cancelado
_CANCELAVEIS = ("recebido", "preparando")

LIMITE_CENTAVOS = 100_000_000  # R$ 1.000.000,00 — evita valores absurdos


# ---------------------------------------------------------------------
# Fluxo de status do pedido
# ---------------------------------------------------------------------
def proximo_status(atual):
    """Próximo status do fluxo normal, ou None se o pedido já terminou."""
    return _PROXIMO.get(atual)


def pode_cancelar(atual):
    """Só é possível cancelar enquanto o pedido não saiu para entrega."""
    return atual in _CANCELAVEIS


def pode_transitar(atual, novo):
    """True se a mudança de status `atual` -> `novo` é permitida."""
    if novo == "cancelado":
        return pode_cancelar(atual)
    return _PROXIMO.get(atual) == novo


# ---------------------------------------------------------------------
# Dinheiro
# ---------------------------------------------------------------------
def reais_para_centavos(texto):
    """
    Converte um texto digitado pelo usuário em centavos (int).
    Aceita "12,50", "12.50", "R$ 1.234,56", "5". Lança ValueError se inválido.
    """
    t = str(texto).replace("R$", "").strip().replace(" ", "")
    if not t:
        raise ValueError("valor vazio")
    if "," in t:                       # formato brasileiro: 1.234,56
        t = t.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", t):
        raise ValueError(f"valor inválido: {texto!r}")
    centavos = int((Decimal(t) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if centavos > LIMITE_CENTAVOS:
        raise ValueError("valor acima do limite permitido")
    return centavos


def centavos_para_reais(centavos):
    """Formata centavos como moeda brasileira: 123456 -> 'R$ 1.234,56'."""
    reais, resto = divmod(int(centavos), 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{resto:02d}"


def centavos_para_campo(centavos):
    """Formata centavos para preencher um campo de formulário: 1250 -> '12,50'."""
    reais, resto = divmod(int(centavos), 100)
    return f"{reais},{resto:02d}"


def calcular_total(itens, taxa_entrega_centavos=0):
    """
    Total do pedido em centavos.
    `itens` é uma lista de pares (quantidade, preco_unitario_centavos).
    """
    subtotal = sum(quantidade * preco for quantidade, preco in itens)
    return subtotal + taxa_entrega_centavos


# ---------------------------------------------------------------------
# Validações de campos
# ---------------------------------------------------------------------
def validar_email(email):
    """Validação simples: algo@dominio.ext, sem espaços."""
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or "") is not None


def validar_telefone(telefone):
    """Telefone brasileiro com DDD: 10 ou 11 dígitos (ignora máscara)."""
    digitos = re.sub(r"\D", "", telefone or "")
    return len(digitos) in (10, 11)