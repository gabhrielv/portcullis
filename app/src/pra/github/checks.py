"""Traduz um Veredito no corpo de um Check Run.

`montar_saida` é pura: recebe Veredito, devolve dict. Toda a formatação é
testável sem rede — por isso os testes dela não precisam de dublê nenhum.

Quem julga é a publicadora, nunca o analisador. O analisador produz evidência;
a decisão mora aqui do lado, e no marco 2 o agente entra entre os dois.
"""

from __future__ import annotations

import requests

from pra.modelos import Achado, EstadoVeredito, Veredito

API = "https://api.github.com"
NOME_CHECAGEM = "seguranca/pra"
# Teto da API do GitHub por requisição.
LIMITE_ANOTACOES = 50
TEMPO_LIMITE_S = 30
LIMITE_MOTIVO = 200

CONCLUSAO = {
    EstadoVeredito.LIBERADO: "success",
    EstadoVeredito.BLOQUEADO: "failure",
    EstadoVeredito.NAO_CONCLUI: "action_required",
}


def _cabecalhos(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _anotacao(achado: Achado, nivel: str) -> dict:
    return {
        "path": achado.caminho,
        "start_line": achado.linha_inicio,
        "end_line": achado.linha_fim,
        "annotation_level": nivel,
        "title": achado.regra,
        "message": achado.mensagem,
    }


def _uma_linha(texto: str) -> str:
    """O motivo pode ter passado por mensagem de exceção, e mensagem de
    exceção pode carregar nome de arquivo vindo do tarball — texto de quem
    abriu o PR. Numa linha só e com teto, ele não forja seção no painel.
    """
    return " ".join(texto.split())[:LIMITE_MOTIVO]


def _titulo(veredito: Veredito) -> str:
    if veredito.estado is EstadoVeredito.NAO_CONCLUI:
        return f"não conclui: {veredito.motivo}"[:120]

    quantidade = len(veredito.bloqueantes)
    if quantidade:
        plural = "s" if quantidade > 1 else ""
        texto = f"{quantidade} achado{plural} novo{plural} bloqueia{'m' if plural else ''}"
    else:
        texto = "nenhum achado novo bloqueia"

    if veredito.degradado:
        texto += " (modo degradado: sem triagem por IA)"
    return texto[:120]


def _tabela(achados: tuple[Achado, ...]) -> str:
    linhas = ["| Sev. | Regra | Onde |", "|---|---|---|"]
    linhas += [
        f"| {a.severidade.name} | `{a.regra}` | `{a.caminho}:{a.linha_inicio}` |"
        for a in achados
    ]
    return "\n".join(linhas)


def _secao(titulo: str, achados: tuple[Achado, ...], recolhida: bool = False) -> str:
    corpo = _tabela(achados)
    if recolhida:
        corpo = f"<details><summary>ver lista</summary>\n\n{corpo}\n</details>"
    return f"\n## {titulo}\n\n{corpo}\n"


def _resumo(veredito: Veredito, anotacoes_mostradas: int) -> str:
    partes: list[str] = []

    if veredito.bloqueantes:
        partes.append(_secao(f"Bloqueando ({len(veredito.bloqueantes)})", veredito.bloqueantes))
    if veredito.avisos:
        partes.append(_secao(f"Avisos ({len(veredito.avisos)})", veredito.avisos))
    if veredito.preexistentes:
        partes.append(
            _secao(
                f"{len(veredito.preexistentes)} pré-existente — não bloqueia",
                veredito.preexistentes,
                recolhida=True,
            )
        )
    if veredito.silenciados:
        # Silenciar não é esconder: a lista de exceções substituiu o
        # `# nosemgrep`, e um achado que sumisse do resumo seria pior que ele.
        partes.append(
            _secao(
                f"{len(veredito.silenciados)} silenciado por exceção",
                veredito.silenciados,
                recolhida=True,
            )
        )

    if veredito.silenciados_por_evidencia:
        # O `raciocinio` do modelo NÃO entra aqui: é texto livre escrito por um
        # modelo que acabou de ler código de quem abriu o PR, e este painel é
        # onde um humano decide. Só campo estruturado.
        partes.append(
            _secao(
                f"{len(veredito.silenciados_por_evidencia)} silenciado por evidência",
                veredito.silenciados_por_evidencia,
                recolhida=True,
            )
        )

    novos = len(veredito.bloqueantes) + len(veredito.avisos)
    if novos > anotacoes_mostradas:
        partes.append(
            f"\n> Mostrando {anotacoes_mostradas} de {novos} anotações "
            f"(teto da API do GitHub).\n"
        )

    # No NAO_CONCLUI o motivo já é o título; repetir aqui seria ruído.
    if veredito.motivo and veredito.estado is not EstadoVeredito.NAO_CONCLUI:
        partes.append(f"\n> {_uma_linha(veredito.motivo)}\n")

    partes.append(f"\n`regra v{veredito.versao_regra}`")
    return "\n".join(partes) if partes else f"Nenhum achado.\n\n`regra v{veredito.versao_regra}`"


def montar_saida(veredito: Veredito) -> dict:
    # Só achado novo vira anotação: o GitHub renderiza anotação inline apenas
    # em linha que o diff tocou, então pré-existente e silenciado ficariam
    # invisíveis. Eles vão para o resumo, que sempre aparece.
    anotacoes = [_anotacao(a, "failure") for a in veredito.bloqueantes]
    anotacoes += [_anotacao(a, "warning") for a in veredito.avisos]
    anotacoes = anotacoes[:LIMITE_ANOTACOES]

    return {
        "conclusion": CONCLUSAO[veredito.estado],
        "output": {
            "title": _titulo(veredito),
            "summary": _resumo(veredito, len(anotacoes)),
            "annotations": anotacoes,
        },
    }


def criar_em_progresso(token: str, owner: str, repo: str, sha: str) -> int:
    """Marca a checagem como rodando, para o PR não ficar ~4 min sem sinal."""
    resposta = requests.post(
        f"{API}/repos/{owner}/{repo}/check-runs",
        headers=_cabecalhos(token),
        json={"name": NOME_CHECAGEM, "head_sha": sha, "status": "in_progress"},
        timeout=TEMPO_LIMITE_S,
    )
    resposta.raise_for_status()
    return resposta.json()["id"]


def encontrar_checagem(token: str, owner: str, repo: str, sha: str) -> int | None:
    """Acha a checagem que a buscadora abriu, por nome e SHA.

    Buscar em vez de carregar o id no pacote mantém o contrato do pacote
    enxuto — o analisador o lê e não tem uso nenhum para esse id.
    """
    resposta = requests.get(
        f"{API}/repos/{owner}/{repo}/commits/{sha}/check-runs",
        headers=_cabecalhos(token),
        params={"check_name": NOME_CHECAGEM},
        timeout=TEMPO_LIMITE_S,
    )
    resposta.raise_for_status()
    execucoes = resposta.json().get("check_runs", [])
    return execucoes[0]["id"] if execucoes else None


def publicar(token: str, owner: str, repo: str, sha: str, veredito: Veredito) -> None:
    """Atualiza a checagem existente, ou cria uma se não houver.

    Criar com o mesmo nome e SHA não substitui a anterior — o GitHub abre outra.
    Por isso procurar primeiro, em vez de sempre criar.
    """
    corpo = {"name": NOME_CHECAGEM, "status": "completed", **montar_saida(veredito)}

    id_checagem = encontrar_checagem(token, owner, repo, sha)
    if id_checagem is None:
        resposta = requests.post(
            f"{API}/repos/{owner}/{repo}/check-runs",
            headers=_cabecalhos(token),
            json={**corpo, "head_sha": sha},
            timeout=TEMPO_LIMITE_S,
        )
    else:
        resposta = requests.patch(
            f"{API}/repos/{owner}/{repo}/check-runs/{id_checagem}",
            headers=_cabecalhos(token),
            json=corpo,
            timeout=TEMPO_LIMITE_S,
        )
    resposta.raise_for_status()
