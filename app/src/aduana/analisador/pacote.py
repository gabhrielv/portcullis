"""Formato do pacote de trabalho — o contrato entre a buscadora e o analisador.

    entrada/{owner}/{repo}/{sha}/codigo.tar.gz
    entrada/{owner}/{repo}/{sha}/contexto.json

É esse contrato que permite montar um pacote na mão e rodar o analisador
offline, sem AWS e sem GitHub — o que o corpus da D12 exige.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from aduana.modelos import Contexto, Evento, FaixaLinhas

NOME_CODIGO = "codigo.tar.gz"
NOME_CONTEXTO = "contexto.json"
NOME_ACHADOS = "achados.json"

# Bomba de descompressão: um .tar.gz de 50 KB expande para 50 MB sem esforço.
# O filtro `data` não protege contra isso — ele cuida de caminho, não de volume.
# O teto é 300 MB porque o /tmp da Lambda tem 512 MB fixos e o tarball baixado
# divide esse espaço com a árvore extraída.
LIMITE_EXTRACAO_BYTES = 300 * 1024 * 1024


class PacoteInvalido(ValueError):
    pass


def extrair(tar: Path, destino: Path) -> Path:
    """Descompacta e devolve a pasta raiz do repositório.

    `filter='data'` é obrigatório: o tarball vem de um repositório que quem
    abriu o PR controla. Em Python 3.12 o filtro não é o padrão, e omiti-lo
    apenas emite DeprecationWarning enquanto segue vulnerável.
    """
    with tarfile.open(tar, "r:gz") as arquivo:
        total = sum(membro.size for membro in arquivo.getmembers())
        if total > LIMITE_EXTRACAO_BYTES:
            raise PacoteInvalido(f"pacote grande demais: {total} bytes descompactados")
        arquivo.extractall(path=destino, filter="data")

    raizes = [p for p in destino.iterdir() if p.is_dir()]
    if len(raizes) != 1:
        raise PacoteInvalido(
            f"esperava exatamente uma pasta raiz no tarball, achei {len(raizes)}"
        )
    return raizes[0]


def escrever_contexto(contexto: Contexto, caminho: Path) -> None:
    dados = {
        "owner": contexto.owner,
        "repo": contexto.repo,
        "head_sha": contexto.head_sha,
        "evento": contexto.evento.value,
        "numero_pr": contexto.numero_pr,
        "base_sha": contexto.base_sha,
        "tudo_novo": contexto.tudo_novo,
        "linhas_tocadas": {
            arquivo: [[f.inicio, f.fim] for f in faixas]
            for arquivo, faixas in contexto.linhas_tocadas.items()
        },
    }
    caminho.write_text(json.dumps(dados, indent=2))


def ler_contexto(caminho: Path) -> Contexto:
    try:
        dados = json.loads(caminho.read_text())
        return Contexto(
            owner=dados["owner"],
            repo=dados["repo"],
            head_sha=dados["head_sha"],
            evento=Evento(dados["evento"]),
            linhas_tocadas={
                arquivo: tuple(FaixaLinhas(inicio, fim) for inicio, fim in faixas)
                for arquivo, faixas in dados["linhas_tocadas"].items()
            },
            numero_pr=dados.get("numero_pr"),
            base_sha=dados.get("base_sha"),
            tudo_novo=dados.get("tudo_novo", False),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as erro:
        raise PacoteInvalido(f"contexto.json inválido: {erro}") from erro
