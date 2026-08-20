"""Checkov sobre a Terraform do repositório analisado.

Espelha a interface do `semgrep.py` de propósito: os dois devolvem `Achado`, e
a `regra.py` não sabe nem precisa saber qual scanner produziu o quê.

**Nada aqui alcança o agente.** O Checkov não emite CWE, e `CKV_*` não está em
`REGRAS_DE_FLUXO` — então `investigavel()` recusa, e é o comportamento certo
pela D26: as duas perguntas do agente são de fluxo de dados, e "de onde vem o
valor" não quer dizer nada num bucket sem criptografia.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from pra.modelos import Achado, Severidade

# 0 = nada falhou, 1 = falhou alguma checagem. Igual ao semgrep: "achou algo"
# não é erro.
CODIGOS_DE_SUCESSO = (0, 1)

LIMITE_MENSAGEM_ERRO = 300

# O nível gratuito NÃO classifica severidade — `severity` vem `None` em todo
# achado (medido em 20/08/2026 com a 3.3.13). Classificar por conta própria
# seria inventar um eixo que a ferramenta não dá, então todo achado entra como
# ERRO e o portão decide pelo que já decide: bloqueia se estiver em linha nova
# e não houver exceção nomeada. É fail-closed, e a lista de exceções é onde as
# discordâncias legítimas ficam escritas com o motivo.
SEVERIDADE = Severidade.ERRO

CATEGORIA = "iac"

# Vai no texto do achado: silenciar por comentario no PR nao funciona, e
# quem le' o painel merece saber que alguem tentou.
PREFIXO_SKIP = "[skip ignorado]"


class CheckovFalhou(RuntimeError):
    pass


@dataclass(frozen=True)
class SaidaCheckov:
    achados: tuple[Achado, ...]
    erros: tuple[dict, ...] = ()
    versao: str = ""


def _um_achado(bruto: dict) -> Achado | None:
    faixa = bruto.get("file_line_range") or []
    if len(faixa) != 2:
        return None

    # `file_path` vem com barra inicial (`/modules/rede/main.tf`). Ela precisa
    # sair: o caminho tem que casar com `linhas_tocadas`, que é relativo à raiz
    # do repositório — sem isso, nenhum achado seria considerado novo e o
    # portão ficaria mudo em vez de bloquear.
    caminho = str(bruto.get("file_path") or "").lstrip("/")
    if not caminho:
        return None

    return Achado(
        regra=str(bruto.get("check_id") or ""),
        severidade=SEVERIDADE,
        caminho=caminho,
        linha_inicio=int(faixa[0]),
        linha_fim=int(faixa[1]),
        mensagem=str(bruto.get("check_name") or ""),
        categoria=CATEGORIA,
    )


def _marcar_skip(achado: Achado) -> Achado:
    """Quem lê o Check Run precisa saber que houve tentativa de desligar."""
    return replace(achado, mensagem=f"{PREFIXO_SKIP} {achado.mensagem}")


def parsear(saida: dict | list) -> list[Achado]:
    """Aceita dict ou lista: o Checkov devolve lista quando roda mais de um
    framework no mesmo alvo, e um dict quando roda só um."""
    blocos = saida if isinstance(saida, list) else [saida]

    achados: list[Achado] = []
    for bloco in blocos:
        if not isinstance(bloco, dict):
            continue
        resultados = bloco.get("results") or {}
        for bruto in resultados.get("failed_checks") or []:
            achado = _um_achado(bruto)
            if achado is not None:
                achados.append(achado)
        # Os pulados entram como achado. Medido em 20/08/2026: um
        # `#checkov:skip=CKV_AWS_26` escrito no arquivo tira a checagem do
        # resultado — o mesmo buraco que o `--disable-nosem` fecha no semgrep,
        # e o Checkov nao tem flag equivalente. Quem abre PR no alvo escreve
        # esse comentario; a valvula legitima e' o `excecoes.py`, que ele nao
        # alcanca. Sem isto, o portao se desliga a pedido de quem ele vigia.
        for bruto in resultados.get("skipped_checks") or []:
            achado = _um_achado(bruto)
            if achado is not None:
                achados.append(_marcar_skip(achado))
    return achados


def versao_do_conjunto(saida: dict | list) -> str:
    """A versão do Checkov entra na impressão digital junto com o hash das
    regras do semgrep. Sem ela, atualizar o scanner ficaria indistinguível de
    mudar o agente — que é o mesmo motivo da D11 para o hash das regras."""
    blocos = saida if isinstance(saida, list) else [saida]
    for bloco in blocos:
        if isinstance(bloco, dict):
            versao = (bloco.get("summary") or {}).get("checkov_version")
            if versao:
                return str(versao)
    return ""


def tem_terraform(raiz: Path) -> bool:
    """Decide se vale rodar. Sem isto, todo repositório Python pagaria o
    tempo do Checkov para ele não achar arquivo nenhum."""
    return any(raiz.rglob("*.tf"))


def rodar(raiz: Path, timeout_s: int = 300) -> SaidaCheckov:
    comando = [
        "checkov",
        "--directory",
        ".",
        "--output",
        "json",
        "--compact",
        # Nao baixa nada do Prisma Cloud. O analisador roda numa subnet sem
        # rota para a internet, entao a tentativa falharia de qualquer jeito —
        # melhor nao tentar do que gastar o timeout esperando.
        #
        # Ele NAO fecha o skip inline: isso e' feito no `parsear`, que trata
        # `skipped_checks` como achado.
        "--skip-download",
    ]
    try:
        proc = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=raiz,
            check=False,
        )
    except subprocess.TimeoutExpired as erro:
        raise CheckovFalhou(f"checkov estourou {timeout_s}s") from erro
    except FileNotFoundError as erro:
        raise CheckovFalhou("checkov não está instalado na imagem") from erro

    if proc.returncode not in CODIGOS_DE_SUCESSO:
        raise CheckovFalhou(
            f"checkov saiu com {proc.returncode}: {proc.stderr[:LIMITE_MENSAGEM_ERRO]}"
        )

    try:
        dados = json.loads(proc.stdout)
    except ValueError as erro:
        raise CheckovFalhou("checkov devolveu saída que não é JSON") from erro

    return SaidaCheckov(
        achados=tuple(parsear(dados)),
        versao=versao_do_conjunto(dados),
    )
