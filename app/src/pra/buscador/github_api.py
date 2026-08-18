"""Busca o código e o diff. Único lugar do sistema que LÊ repositório no GitHub.

Tarball em vez de clone: é um download HTTPS comum, então a Lambda dá conta sem
ter `git` instalado. O preço é não ter histórico, o que já estava decidido.

Duas armadilhas moram aqui, e as duas fazem o portão falhar ABERTO — deixar
passar achado que deveria bloquear, sem aviso nenhum. Ver `mapear_arquivos` e
`LIMITE_ARQUIVOS_GITHUB`.
"""

from __future__ import annotations

import re

import requests

from pra.modelos import FaixaLinhas

API = "https://api.github.com"
TEMPO_LIMITE_S = 60
POR_PAGINA = 100

# A API para de contar em 3000 arquivos. É limite dela, não da nossa paginação.
LIMITE_ARQUIVOS_GITHUB = 3000

# Faixa que cobre qualquer arquivo real, para quando o arquivo mudou mas não
# sabemos onde.
ARQUIVO_INTEIRO = (FaixaLinhas(1, 1_000_000),)

# Arquivo apagado não pode ter achado, e mapeá-lo só geraria ruído.
STATUS_MORTOS = frozenset({"removed"})

CABECALHO_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def cabecalhos(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def faixas_de_patch(patch: str) -> tuple[FaixaLinhas, ...]:
    """Faixas de linha ADICIONADAS, numeradas no arquivo novo."""
    adicionadas: list[int] = []
    linha_atual = 0

    for linha in patch.splitlines():
        cabecalho = CABECALHO_HUNK.match(linha)
        if cabecalho:
            linha_atual = int(cabecalho.group(1))
            continue
        if linha.startswith("\\"):
            # "\ No newline at end of file": é anotação do diff, não conteúdo.
            continue
        if linha.startswith("+"):
            adicionadas.append(linha_atual)
            linha_atual += 1
        elif linha.startswith("-"):
            continue  # some do arquivo novo
        else:
            linha_atual += 1

    if not adicionadas:
        return ()

    faixas: list[FaixaLinhas] = []
    inicio = anterior = adicionadas[0]
    for numero in adicionadas[1:]:
        if numero == anterior + 1:
            anterior = numero
            continue
        faixas.append(FaixaLinhas(inicio, anterior))
        inicio = anterior = numero
    faixas.append(FaixaLinhas(inicio, anterior))
    return tuple(faixas)


def mapear_arquivos(arquivos: list[dict]) -> dict[str, tuple[FaixaLinhas, ...]]:
    mapa: dict[str, tuple[FaixaLinhas, ...]] = {}
    for arquivo in arquivos:
        if arquivo.get("status") in STATUS_MORTOS:
            continue

        patch = arquivo.get("patch")
        if not patch:
            # O GitHub omitiu o diff (binário ou grande demais). O arquivo
            # MUDOU — só não sabemos onde. Tratar como não-tocado seria falhar
            # aberto, então o arquivo inteiro conta como novo.
            mapa[arquivo["filename"]] = ARQUIVO_INTEIRO
            continue

        faixas = faixas_de_patch(patch)
        if faixas:
            mapa[arquivo["filename"]] = faixas
    return mapa


def linhas_tocadas_de_pr(
    token: str, owner: str, repo: str, numero: int
) -> tuple[dict[str, tuple[FaixaLinhas, ...]], bool]:
    """Devolve (mapa, tudo_novo).

    `tudo_novo` liga quando a listagem bate no teto do GitHub: existem arquivos
    alterados que não sabemos quais são, e classificá-los como pré-existentes
    seria falhar aberto. Um PR gigante — merge de branch longa, formatação em
    massa — é justamente aquele que ninguém lê o diff.
    """
    arquivos: list[dict] = []
    pagina = 1
    while True:
        resposta = requests.get(
            f"{API}/repos/{owner}/{repo}/pulls/{numero}/files",
            headers=cabecalhos(token),
            params={"per_page": POR_PAGINA, "page": pagina},
            timeout=TEMPO_LIMITE_S,
        )
        resposta.raise_for_status()
        lote = resposta.json()
        arquivos.extend(lote)
        if len(lote) < POR_PAGINA or len(arquivos) >= LIMITE_ARQUIVOS_GITHUB:
            break
        pagina += 1

    truncado = len(arquivos) >= LIMITE_ARQUIVOS_GITHUB
    return mapear_arquivos(arquivos), truncado


def linhas_tocadas_de_push(
    token: str, owner: str, repo: str, base: str | None, head: str
) -> tuple[dict[str, tuple[FaixaLinhas, ...]], bool]:
    """Devolve (mapa, tudo_novo).

    Branch nova traz `before` zerado, e force push deixa a base inalcançável.
    Nos dois casos não dá para calcular o diff, então todo achado conta como
    novo e o portão erra para o lado de bloquear.
    """
    if not base or set(base) == {"0"}:
        return {}, True

    resposta = requests.get(
        f"{API}/repos/{owner}/{repo}/compare/{base}...{head}",
        headers=cabecalhos(token),
        timeout=TEMPO_LIMITE_S,
    )
    if resposta.status_code == 404:
        return {}, True
    resposta.raise_for_status()

    dados = resposta.json()
    arquivos = dados.get("files", [])
    # O compare também trunca, em 300 arquivos, e avisa no próprio corpo.
    truncado = len(arquivos) >= LIMITE_ARQUIVOS_GITHUB or dados.get(
        "files_truncated", False
    )
    return mapear_arquivos(arquivos), truncado


# O tarball vem de repositório que não controlamos. Um `node_modules` commitado
# ou assets grandes estouram a Lambda, e o erro que aparece é a função morrendo
# sem mensagem útil.
LIMITE_TARBALL_BYTES = 400 * 1024 * 1024


class RepositorioGrandeDemais(RuntimeError):
    pass


class _FluxoComTeto:
    """Conta os bytes enquanto eles passam e estoura ao cruzar o teto.

    Envolver o fluxo em vez de conferir `Content-Length` é o que funciona
    quando o GitHub responde em chunks e não manda o tamanho — e é o caso de
    quem manda tarball gerado na hora.
    """

    def __init__(self, origem, teto: int):
        self._origem = origem
        self._teto = teto
        self._lidos = 0

    def read(self, quantidade: int = -1) -> bytes:
        pedaco = self._origem.read(quantidade)
        self._lidos += len(pedaco)
        if self._lidos > self._teto:
            raise RepositorioGrandeDemais(
                f"tarball passou de {self._teto} bytes"
            )
        return pedaco


def fluxo_com_teto(origem, teto: int = LIMITE_TARBALL_BYTES) -> _FluxoComTeto:
    return _FluxoComTeto(origem, teto)


def tarball_para_s3(
    token: str, owner: str, repo: str, sha: str, bucket: str, chave: str
) -> None:
    """Vai direto do GitHub para o S3, sem passar pela memória da Lambda."""
    import boto3

    with requests.get(
        f"{API}/repos/{owner}/{repo}/tarball/{sha}",
        headers=cabecalhos(token),
        timeout=TEMPO_LIMITE_S,
        stream=True,
        allow_redirects=True,
    ) as resposta:
        resposta.raise_for_status()
        resposta.raw.decode_content = True
        boto3.client("s3").upload_fileobj(
            fluxo_com_teto(resposta.raw), bucket, chave
        )
