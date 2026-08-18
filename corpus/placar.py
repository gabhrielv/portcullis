"""A pontuação do corpus. Puro: não fala com rede, não lê arquivo.

Separado do `rodar.py` porque é o critério de aceite de qualquer mexida no
prompt ou no modelo, e critério de aceite sem teste reporta número bonito sem
avisar. O `rodar.py` fica com a I/O e a cota; aqui só entra aritmética.

Duas ideias governam o formato:

**A linha de base.** Um agente que responde `nao_sei` em tudo não silencia
nada, e num portão fail-closed isso dá recall perfeito e zero falso-negativo.
Sem a coluna da base, `15/22` parece bom; com ela fica visível quantos casos o
agente ganhou de verdade.

**Veredito não é raciocínio.** Bloquear porque entendeu e bloquear porque
desistiu são o mesmo bit no veredito. A segunda linha separa os dois, e é onde
o agente nulo quase não pontua — quase, e não zero, porque há caso em que
`nao_sei` é a leitura correta. Por isso a base é calculada, nunca afirmada.
"""

from __future__ import annotations

from pra.modelos import Evidencia, Resposta


def mede(entrada: dict) -> bool:
    """O caso consegue mudar de valor?

    Vulnerável comum não consegue: o portão bloqueia por padrão e o acerto não
    diz nada sobre o agente. Repetir esses é pagar cota por ruído.
    """
    return entrada["gabarito"] == "FALSO_POSITIVO" or bool(
        entrada.get("arma_falso_negativo")
    )


def _casa(evidencia: Evidencia, esperada: dict) -> bool:
    if evidencia.entrada_controlavel.value != esperada.get(
        "entrada_controlavel", evidencia.entrada_controlavel.value
    ):
        return False
    if evidencia.sanitizacao_encontrada.value != esperada.get(
        "sanitizacao_encontrada", evidencia.sanitizacao_encontrada.value
    ):
        return False
    if "prova_em" in esperada:
        # Só o arquivo: exigir a linha exata quebraria a cada mexida na árvore.
        arquivo = (evidencia.prova or "").rpartition(":")[0]
        return evidencia.prova_valida and arquivo == esperada["prova_em"]
    return True


def evidencia_bate(evidencia: Evidencia, aceitas: list[dict]) -> bool:
    return any(_casa(evidencia, esperada) for esperada in aceitas)


def resumir(entrada: dict, execucoes: list[dict]) -> dict:
    """Uma linha do placar, com o pior caso mandando.

    Média esconde o que importa: um portão que solta em 1 de 3 rodadas solta.
    Por isso `veredito_certo` exige acerto em TODAS, e `falso_negativo` basta
    uma. `estavel` registra a discordância entre rodadas — caso que oscila é
    achado do corpus, não erro de arredondamento.
    """
    esperado_silenciar = entrada["gabarito"] == "FALSO_POSITIVO"
    silenciou = [x["silenciou"] for x in execucoes]
    bateu = [x["raciocinio_bateu"] for x in execucoes]

    return {
        "id": entrada["id"],
        "dificuldade": entrada["dificuldade"],
        "escala": entrada.get("escala", "pequeno"),
        "gabarito": entrada["gabarito"],
        "arma_falso_negativo": bool(entrada.get("arma_falso_negativo")),
        "execucoes": execucoes,
        "veredito_certo": all(s == esperado_silenciar for s in silenciou),
        "raciocinio_certo": all(bateu),
        "falso_negativo": (not esperado_silenciar) and any(silenciou),
        "estavel": len(set(silenciou)) == 1 and len(set(bateu)) == 1,
        "passos": sum(x["passos"] for x in execucoes) / max(len(execucoes), 1),
        "tokens": sum(x["tokens"] for x in execucoes),
    }


EVIDENCIA_NULA = Evidencia(
    chave="",
    entrada_controlavel=Resposta.NAO_SEI,
    sanitizacao_encontrada=Resposta.NAO_SEI,
)


def linha_de_base(entradas: list[dict]) -> dict:
    """O agente que responde `nao_sei` em tudo. Calculável sem gastar cota.

    Ele é o teto do que o marco 1 já entregava, e é contra ele que o marco 2
    precisa se justificar — não contra zero.

    O `raciocinio` é **medido, não cravado**. A primeira versão devolvia zero
    fixo, apoiada na ideia de que `nao_sei` nunca é a resposta certa. Deixou de
    ser verdade quando o `morto-mas-novo` passou a aceitar `nao_sei`: lá,
    "não consigo provar que ninguém chama" é a resposta honesta, e é ela que
    bloqueia. Base afirmada mente calada quando um gabarito muda; base
    derivada, não.
    """
    return {
        "veredito": sum(1 for e in entradas if e["gabarito"] == "VULNERAVEL"),
        "raciocinio": sum(
            1 for e in entradas if evidencia_bate(EVIDENCIA_NULA, e.get("evidencia_aceita", ()))
        ),
        "falso_negativos": 0,
        "ruido_removido": 0,
    }


def _fatia(linhas: list[dict], chave: str, valor: str) -> list[dict]:
    return [x for x in linhas if x[chave] == valor]


def _bloco(titulo: str, linhas: list[dict], chave: str, valores: tuple[str, ...]) -> list[str]:
    saida = []
    for valor in valores:
        deste = _fatia(linhas, chave, valor)
        if deste:
            certos = sum(x["veredito_certo"] for x in deste)
            saida.append(f"  {valor:<10} {certos}/{len(deste)}")
    return [f"  {titulo}", *saida, ""] if saida else []


def _par(rotulo: str, medido: str, base: str = "", nota: str = "") -> str:
    return f"{rotulo:<20}{medido:>10}{base:>10}   {nota}".rstrip()


def render(linhas: list[dict], entradas: list[dict]) -> str:
    base = linha_de_base(entradas)
    positivos = [x for x in linhas if x["gabarito"] == "FALSO_POSITIVO"]
    armadilhas = [x for x in linhas if x["arma_falso_negativo"]]
    total = len(linhas)

    vulneraveis = [x for x in linhas if x["gabarito"] == "VULNERAVEL"]

    veredito = sum(x["veredito_certo"] for x in linhas)
    raciocinio = sum(x["raciocinio_certo"] for x in linhas)
    ruido = sum(x["veredito_certo"] for x in positivos)
    negativos = sum(x["falso_negativo"] for x in armadilhas)
    # Nas armadilhas está o sinal; no total está o alarme. Um agente que
    # silenciasse `sqli-direto` não moveria o índice das armadilhas, e o pior
    # erro possível apareceria só como linha de lista.
    negativos_todos = sum(x["falso_negativo"] for x in vulneraveis)
    estaveis = sum(x["estavel"] for x in linhas)

    saida = [
        "",
        _par("", "medido", "base"),
        _par("veredito", f"{veredito}/{total}", f"{base['veredito']}/{total}"),
        _par(
            "raciocínio",
            f"{raciocinio}/{total}",
            f"{base['raciocinio']}/{total}",
            "<- onde o agente nulo quase não pontua",
        ),
        _par(
            "falso-negativos",
            f"{negativos}/{len(armadilhas)}",
            f"{base['falso_negativos']}/{len(armadilhas)}",
            "<- nas armadilhas, onde errar é plausível",
        ),
        _par(
            "  no corpus todo",
            f"{negativos_todos}/{len(vulneraveis)}",
            f"{base['falso_negativos']}/{len(vulneraveis)}",
            "<- o aceite exige 0 AQUI",
        ),
        _par(
            "ruído removido",
            f"{ruido}/{len(positivos)}",
            f"{base['ruido_removido']}/{len(positivos)}",
            "<- onde está o sinal",
        ),
        _par("estabilidade", f"{estaveis}/{total}"),
        "",
        _par("passos (média)", f"{sum(x['passos'] for x in linhas) / max(total, 1):.1f}"),
        _par("tokens (total)", str(sum(x["tokens"] for x in linhas))),
        "",
    ]
    saida += _bloco("por escala", linhas, "escala", ("pequeno", "grande"))
    saida += _bloco("por dificuldade", linhas, "dificuldade", ("facil", "media", "dificil"))

    ruins = [x for x in linhas if x["falso_negativo"]]
    if ruins:
        saida += ["FALSO-NEGATIVOS:"]
        saida += [f"  {x['id']}: {x['execucoes'][0].get('raciocinio', '')[:90]}" for x in ruins]
        saida += [""]

    instaveis = [x for x in linhas if not x["estavel"]]
    if instaveis:
        saida += ["INSTÁVEIS (oscilaram entre execuções):"]
        saida += [f"  {x['id']}" for x in instaveis]
        saida += [""]

    return "\n".join(saida)
