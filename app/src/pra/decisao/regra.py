"""A regra determinística. Ver D6 e D15.

No marco 2 o agente entrega evidência ANTES desta função; ela continua sendo
quem decide. Nada aqui consulta rede.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pra.decisao.excecoes import silenciado
from pra.modelos import (
    Achado,
    Contexto,
    EstadoVeredito,
    Evidencia,
    Resposta,
    Severidade,
    Veredito,
    chave_do_achado,
)

VERSAO_REGRA = "4"

CATEGORIA_SEGURANCA = "security"

# Os CWE em que a pergunta do agente faz sentido: um valor viaja de uma origem
# até um ponto perigoso, e "de onde ele vem" e "foi sanitizado no caminho"
# decidem se há problema. Fora daqui a pergunta não se aplica — num segredo
# escrito no código não existe valor entrando, e a resposta honesta a "isso vem
# de fora?" é "não", que silenciaria a credencial.
#
# Gerado a partir dos conjuntos congelados em 18/08/2026 e classificado um a um:
# 140 CWE distintos, 40 de fluxo. Os nove sem nome abaixo não aparecem nestes
# dois conjuntos e estão aqui por antecipação — todos são de injeção.
CWES_DE_FLUXO = frozenset(
    {
        "20",     # Improper Input Validation
        "22",     # Improper Limitation of a Pathname to a Restricted Directory ('
        "23",     # Relative Path Traversal
        "73",     # External Control of File Name or Path
        "74",     # Improper Neutralization of Special Elements in Output Used by 
        "77",     # Improper Neutralization of Special Elements used in a Command 
        "78",     # Improper Neutralization of Special Elements used in an OS Comm
        "79",     # Improper Neutralization of Input During Web Page Generation ('
        "80",     # Improper Neutralization of Script-Related HTML Tags in a Web P
        "88",     # (não aparece no conjunto atual)
        "89",     # Improper Neutralization of Special Elements used in an SQL Com
        "90",     # Improper Neutralization of Special Elements used in an LDAP Qu
        "91",     # XML Injection
        "93",     # Improper Neutralization of CRLF Sequences ('CRLF Injection')
        "94",     # Improper Control of Generation of Code ('Code Injection')
        "95",     # Improper Neutralization of Directives in Dynamically Evaluated
        "96",     # Improper Neutralization of Directives in Statically Saved Code
        "113",    # Improper Neutralization of CRLF Sequences in HTTP Headers ('HT
        "115",    # Misinterpretation of Input
        "116",    # Improper Encoding or Escaping of Output
        "117",    # (não aparece no conjunto atual)
        "134",    # Use of Externally-Controlled Format String
        "150",    # Improper Neutralization of Escape, Meta, or Control Sequences
        "155",    # Improper Neutralization of Wildcards or Matching Symbols
        "159",    # (não aparece no conjunto atual)
        "184",    # (não aparece no conjunto atual)
        "400",    # Uncontrolled Resource Consumption
        "454",    # External Initialization of Trusted Variables or Data Stores
        "470",    # Use of Externally-Controlled Input to Select Classes or Code (
        "501",    # Trust Boundary Violation
        "502",    # Deserialization of Untrusted Data
        "564",    # (não aparece no conjunto atual)
        "601",    # URL Redirection to Untrusted Site ('Open Redirect')
        "611",    # Improper Restriction of XML External Entity Reference
        "639",    # Authorization Bypass Through User-Controlled Key
        "643",    # Improper Neutralization of Data within XPath Expressions ('XPa
        "706",    # Use of Incorrectly-Resolved Name or Reference
        "776",    # Improper Restriction of Recursive Entity References in DTDs ('
        "829",    # Inclusion of Functionality from Untrusted Control Sphere
        "830",    # (não aparece no conjunto atual)
        "838",    # (não aparece no conjunto atual)
        "913",    # Improper Control of Dynamically-Managed Code Resources
        "915",    # Improperly Controlled Modification of Dynamically-Determined O
        "917",    # (não aparece no conjunto atual)
        "918",    # Server-Side Request Forgery (SSRF)
        "943",    # Improper Neutralization of Special Elements in Data Query Logi
        "1236",   # (não aparece no conjunto atual)
        "1333",   # Inefficient Regular Expression Complexity
        "1336",   # Improper Neutralization of Special Elements Used in a Template
    }
)

# Classificados como NÃO sendo de fluxo. Existe para o teste de exaustividade:
# CWE que aparece no conjunto de regras e não está em nenhum dos dois quebra a
# build, em vez de virar bloqueio silencioso. Foi assim que o 79 sumiu.
CWES_FORA_DE_FLUXO = frozenset(
    {
        "11", "16", "119", "125", "183", "190", "200", "209", "242", "250",
        "252", "262", "264", "269", "272", "276", "284", "287", "295", "297",
        "300", "306", "310", "311", "319", "320", "321", "322", "323", "326",
        "327", "328", "329", "330", "338", "341", "345", "346", "347", "352",
        "353", "362", "369", "377", "406", "415", "416", "427", "441", "444",
        "451", "476", "477", "489", "509", "521", "522", "523", "532", "538",
        "548", "553", "613", "614", "665", "667", "668", "673", "676", "681",
        "682", "688", "693", "697", "704", "732", "749", "770", "774", "778",
        "780", "787", "798", "837", "841", "862", "916", "922", "926", "939",
        "942", "1004", "1021", "1104", "1204", "1220", "1275", "1323", "1357", "1390",
    }
)

# Regras cujo `metadata.cwe` do conjunto está ERRADO. O CWE classifica conceito,
# não conserta etiqueta: `tainted-sql-string` declara CWE-89 em Go, Ruby, PHP e
# Java e CWE-704 (conversão de tipo) em Python/Flask, sendo a mesma injeção de
# SQL. O `nan-injection` também cai em 704, e ali o 704 até faz sentido — o
# problema É a conversão — mas o valor vem da requisição do mesmo jeito.
# Lista de três, não de mil: é exceção sobre um classificador, não substituto.
REGRAS_DE_FLUXO = frozenset(
    {
        "python.flask.security.injection.tainted-sql-string.tainted-sql-string",
        "python.flask.security.injection.nan-injection.nan-injection",
        "python.django.security.nan-injection.nan-injection",
    }
)


def _bloqueia(achado: Achado) -> bool:
    # ERRO bloqueia sempre. AVISO só quando a regra se declara de segurança —
    # medido no hoppr em 12/08/2026: dos 12 avisos, 4 eram de performance.
    # Categoria ausente nunca promove, mas também nunca rebaixa um ERRO.
    if achado.severidade is Severidade.ERRO:
        return True
    return achado.severidade is Severidade.AVISO and achado.categoria == CATEGORIA_SEGURANCA


def investigavel(achado: Achado) -> bool:
    """O agente só alcança achado de fluxo de dados. Ver D6.

    Lista de permissão, não de bloqueio: regra nova que ninguém classificou
    bloqueia sem investigação. O contrário — investigar o desconhecido — deixa
    o modelo silenciar famílias inteiras de achado em que as duas perguntas
    dele não querem dizer nada.
    """
    if achado.regra in REGRAS_DE_FLUXO:
        return True
    return bool(set(achado.cwes) & CWES_DE_FLUXO)


def _e_novo(achado: Achado, contexto: Contexto) -> bool:
    # Só linha ADICIONADA conta. PR que cria problema apagando linha passa:
    # limitação conhecida, documentada no README.
    if contexto.tudo_novo:
        return True
    faixas = contexto.linhas_tocadas.get(achado.caminho)
    if not faixas:
        return False
    return any(faixa.intersecta(achado.linha_inicio, achado.linha_fim) for faixa in faixas)


def silencia_por_evidencia(evidencia: Evidencia | None) -> bool:
    """A D6, sem folga. Pública porque o corpus mede exatamente esta função.

    Silenciar exige evidência POSITIVA e localizada. Ausência de evidência,
    `nao_sei`, ou prova que não aponta para lugar nenhum: tudo bloqueia. O
    único jeito de o portão afrouxar é alguém afrouxar isto aqui.
    """
    if evidencia is None:
        return False
    if evidencia.entrada_controlavel is Resposta.NAO:
        return True
    return evidencia.sanitizacao_encontrada is Resposta.SIM and evidencia.prova_valida


def decidir(
    achados: Iterable[Achado],
    contexto: Contexto,
    evidencias: Mapping[str, Evidencia] | None = None,
    degradado: bool = False,
    motivo: str | None = None,
) -> Veredito:
    bloqueantes: list[Achado] = []
    avisos: list[Achado] = []
    preexistentes: list[Achado] = []
    silenciados: list[Achado] = []
    por_evidencia: list[Achado] = []
    achadas = evidencias or {}

    for achado in achados:
        # A ordem das cláusulas é parte da decisão: a evidência só é
        # consultada depois de o achado já ser novo, não excetuado, de
        # severidade bloqueante e de uma família em que a pergunta do agente
        # se aplica. Consultá-la antes deixaria o agente alcançar aviso,
        # pré-existente e achado que ele não sabe julgar.
        if not _e_novo(achado, contexto):
            preexistentes.append(achado)
        elif silenciado(achado.regra, achado.caminho):
            silenciados.append(achado)
        elif not _bloqueia(achado):
            avisos.append(achado)
        elif investigavel(achado) and silencia_por_evidencia(
            achadas.get(chave_do_achado(achado))
        ):
            por_evidencia.append(achado)
        else:
            bloqueantes.append(achado)

    estado = EstadoVeredito.BLOQUEADO if bloqueantes else EstadoVeredito.LIBERADO

    return Veredito(
        estado=estado,
        bloqueantes=tuple(bloqueantes),
        avisos=tuple(avisos),
        preexistentes=tuple(preexistentes),
        silenciados=tuple(silenciados),
        silenciados_por_evidencia=tuple(por_evidencia),
        versao_regra=VERSAO_REGRA,
        degradado=degradado,
        motivo=motivo,
    )


def nao_conclui(motivo: str) -> Veredito:
    """Fail-closed explícito. Vira `action_required` no Check Run (D16)."""
    return Veredito(
        estado=EstadoVeredito.NAO_CONCLUI,
        bloqueantes=(),
        avisos=(),
        preexistentes=(),
        versao_regra=VERSAO_REGRA,
        motivo=motivo,
    )
