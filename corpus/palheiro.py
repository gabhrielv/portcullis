"""Gera o palheiro das variantes `-grande` do corpus.

As árvores pequenas do corpus têm de 6 a 32 linhas, e nelas a janela grátis de
±20 linhas já cobre o arquivo do alvo inteiro: o agente responde sem chamar
ferramenta nenhuma. Isso mede julgamento e não mede NAVEGAÇÃO — que é o que o
`PASSOS_MAX = 8` existe para restringir e o que decide se isto funciona num
repositório de verdade.

O enchimento é escrito para ser **inerte e competitivo**: nenhuma linha dispara
regra do semgrep (sem SQL, sem subprocess, sem pickle, sem yaml, sem request),
e os nomes competem de propósito — `validar`, `limpar`, `sanitizar` aparecem às
dezenas, para que `buscar` devolva ruído e o teto de 50 resultados seja
alcançável. Nenhum arquivo importa os módulos do caso: o palheiro não pode
mudar quem chama o quê.

Determinístico: a mesma semente gera a mesma árvore, senão o congelado de ontem
não se compara com o de hoje.

Uso:  .venv/bin/python corpus/palheiro.py <id-do-caso> [quantidade]
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CASOS = RAIZ / "casos"
PADRAO = 150

DOMINIOS = [
    "pedido", "cliente", "produto", "estoque", "fatura", "entrega", "carrinho",
    "cupom", "assinatura", "pagamento", "endereco", "categoria", "avaliacao",
    "devolucao", "remessa", "lote", "fornecedor", "deposito", "tabela", "regiao",
]
VERBOS = ["validar", "limpar", "sanitizar", "normalizar", "checar", "montar", "resolver"]
CAMPOS = ["nome", "codigo", "descricao", "referencia", "rotulo", "apelido", "slug"]


def _modelo(nome: str, campos: list[str]) -> str:
    linhas = [
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        f"class {nome.capitalize()}:",
    ]
    linhas += [f"    {c}: str" for c in campos]
    linhas += [
        "",
        "    @property",
        "    def resumo(self) -> str:",
        f'        return f"{{self.{campos[0]}}} ({{self.{campos[-1]}}})"',
    ]
    return "\n".join(linhas) + "\n"


def _util(nome: str, verbos: list[str]) -> str:
    linhas = ["PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')", "", ""]
    for verbo in verbos:
        linhas += [
            f"def {verbo}_{nome}(texto: str) -> str:",
            f'    """{verbo.capitalize()} o {nome} para uso interno do modulo."""',
            "    return ''.join(c for c in texto.lower() if c in PERMITIDOS)",
            "",
            "",
        ]
    return "\n".join(linhas).rstrip() + "\n"


def _servico(nome: str, alvos: list[str]) -> str:
    linhas = [f"from app.utils.{nome} import validar_{nome}", "", ""]
    for alvo in alvos:
        linhas += [
            f"def {alvo}_de_{nome}(itens: list[dict]) -> list[dict]:",
            f'    """Aplica o filtro de {alvo} sobre a lista ja carregada."""',
            f'    return [i for i in itens if validar_{nome}(i.get("rotulo", ""))]',
            "",
            "",
        ]
    return "\n".join(linhas).rstrip() + "\n"


def _teste(nome: str) -> str:
    return (
        f"from app.utils.{nome} import validar_{nome}\n"
        "\n"
        "\n"
        f"def test_validar_{nome}_remove_simbolo():\n"
        f'    assert validar_{nome}("a!b") == "ab"\n'
        "\n"
        "\n"
        f"def test_validar_{nome}_baixa_a_caixa():\n"
        f'    assert validar_{nome}("AB") == "ab"\n'
    )


def gerar(raiz: Path, quantidade: int = PADRAO, semente: int = 20260818) -> int:
    sorteio = random.Random(semente)
    escritos = 0
    for numero in range(quantidade):
        nome = f"{DOMINIOS[numero % len(DOMINIOS)]}_{numero:03d}"
        familia = numero % 4
        if familia == 0:
            destino = raiz / "app" / "models" / f"{nome}.py"
            corpo = _modelo(nome, sorteio.sample(CAMPOS, 3))
        elif familia == 1:
            destino = raiz / "app" / "utils" / f"{nome}.py"
            corpo = _util(nome, sorteio.sample(VERBOS, 3))
        elif familia == 2:
            destino = raiz / "app" / "services" / f"{nome}.py"
            corpo = _servico(nome, sorteio.sample(VERBOS, 2))
        else:
            destino = raiz / "tests" / f"test_{nome}.py"
            corpo = _teste(nome)

        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(corpo)
        escritos += 1
    return escritos


def principal(argumentos: list[str]) -> int:
    if not argumentos:
        print(__doc__, file=sys.stderr)
        return 2
    caso = CASOS / argumentos[0]
    quantidade = int(argumentos[1]) if len(argumentos) > 1 else PADRAO
    raiz = caso / "codigo" / "repo"
    if not raiz.is_dir():
        print(f"{caso.name}: falta codigo/repo/", file=sys.stderr)
        return 2
    print(f"{caso.name}: {gerar(raiz, quantidade)} arquivos de enchimento")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
