"""As duas ferramentas do harness. Ver §3 do ARQUITETURA.

São duas, não três: a `historico_git` morreu porque o código chega como tarball,
que é foto da árvore, e a pergunta que ela respondia — "essa linha entrou agora
ou é antiga?" — virou um campo de contexto, exato e sem gastar passo.

**Nenhuma delas fala com a rede.** É isso que sustenta a D20: injeção de prompt
pode fazer o modelo mentir na evidência, mas não pode fazer a Lambda falar com
o servidor de ninguém, porque quem chama o modelo é o código, num endpoint fixo.
"""

from __future__ import annotations

from pathlib import Path

# Sem teto, um arquivo de 5.000 linhas entra inteiro no contexto e estoura a
# janela no segundo passo.
TETO_LINHAS = 400
TETO_RESULTADOS = 50
LINHAS_DE_JANELA = 20
TETO_BYTES_ARQUIVO = 2 * 1024 * 1024
TETO_COLUNAS = 200

SUFIXOS_IGNORADOS = frozenset(
    (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".ico", ".woff", ".woff2")
)


class Caixa:
    """Tudo que o agente alcança. Fora daqui, ele não tem mão."""

    def __init__(self, raiz: Path):
        self._raiz = raiz.resolve()

    def _resolver(self, caminho: str) -> Path:
        """Confina na raiz.

        `resolve()` primeiro e comparação depois, nessa ordem: assim o symlink
        que aponta para fora é pego junto com o `../`. Comparar antes de
        resolver deixaria passar.
        """
        alvo = (self._raiz / caminho).resolve()
        if not alvo.is_relative_to(self._raiz):
            raise ValueError(f"caminho fora do pacote: {caminho}")
        return alvo

    def ler_arquivo(
        self, caminho: str, inicio: int | None = None, fim: int | None = None
    ) -> str:
        alvo = self._resolver(caminho)
        if not alvo.is_file():
            return f"não encontrei {caminho}"

        linhas = alvo.read_text(errors="replace").splitlines()
        primeira = max(1, inicio or 1)
        ultima = min(len(linhas), fim if fim is not None else len(linhas))
        recorte = linhas[primeira - 1 : ultima]

        aviso = ""
        if len(recorte) > TETO_LINHAS:
            recorte = recorte[:TETO_LINHAS]
            ultima = primeira + TETO_LINHAS - 1
            aviso = f"\n[truncado no teto de {TETO_LINHAS} linhas]"

        # A numeração não é enfeite: sem ela o modelo não consegue montar uma
        # prova `arquivo:linha`, e prova é o que a D6 exige para silenciar.
        numeradas = "\n".join(f"{primeira + i}: {linha}" for i, linha in enumerate(recorte))
        return f"{caminho}:{primeira}-{ultima}\n{numeradas}{aviso}"

    def janela(self, caminho: str, linha: int) -> str:
        """As ±20 linhas que o loop ganha de graça.

        Sem isto o passo 1 seria sempre "ler a linha apontada". Comprar esse
        passo por fora devolve um passo de investigação de verdade dentro do
        mesmo orçamento de 8.
        """
        return self.ler_arquivo(
            caminho, inicio=linha - LINHAS_DE_JANELA, fim=linha + LINHAS_DE_JANELA
        )

    def buscar(self, termos: list[str]) -> str:
        """Literais, não regex — divergência registrada da §3.

        Quem escreveria a regex é o modelo, e o modelo acabou de ler código do
        atacante: um `(a+)+$` planta backtrack catastrófico e prende a Lambda
        até o timeout. Nenhum uso real do loop precisa de forma — ele procura
        nomes de função e de identificador para achar chamadores.
        """
        procurados = [t for t in termos if isinstance(t, str) and t.strip()]
        if not procurados:
            return "nenhuma ocorrência: nenhum termo válido foi passado"

        achados: list[str] = []
        for arquivo in sorted(self._raiz.rglob("*")):
            if len(achados) >= TETO_RESULTADOS:
                break
            if not arquivo.is_file() or arquivo.suffix in SUFIXOS_IGNORADOS:
                continue
            if arquivo.stat().st_size > TETO_BYTES_ARQUIVO:
                continue
            achados.extend(self._no_arquivo(arquivo, procurados, len(achados)))

        if not achados:
            return f"nenhuma ocorrência de {procurados}"

        cabecalho = f"{len(achados)} ocorrência(s)"
        if len(achados) >= TETO_RESULTADOS:
            cabecalho += f" (teto de {TETO_RESULTADOS} atingido)"
        return cabecalho + "\n" + "\n".join(achados)

    def _no_arquivo(self, arquivo: Path, termos: list[str], ja_tem: int) -> list[str]:
        try:
            linhas = arquivo.read_text(errors="replace").splitlines()
        except OSError:
            return []

        relativo = arquivo.relative_to(self._raiz)
        saida: list[str] = []
        for numero, linha in enumerate(linhas, start=1):
            if ja_tem + len(saida) >= TETO_RESULTADOS:
                break
            if any(termo in linha for termo in termos):
                saida.append(f"{relativo}:{numero}: {linha.strip()[:TETO_COLUNAS]}")
        return saida

    def prova_valida(self, prova: str) -> bool:
        """O modelo declara a prova; quem verifica é o código.

        Afirmar sanitização e apontar para um arquivo que não existe é a
        mentira mais barata que uma injeção de prompt produz. Sem esta
        conferência, o campo `prova` da D6 seria decoração.
        """
        if not prova or ":" not in prova:
            return False
        caminho, _, faixa = prova.rpartition(":")
        # Faixa (`6-7`) vale tanto quanto linha única: sanitização que ocupa
        # duas linhas — o `if` e o `abort` — é citada assim, e recusar por
        # formato descartava prova CORRETA. Medido no `sanitizacao-distante`.
        # Conferir endereço e não semântica já é limitação conhecida; o formato
        # do endereço não precisa somar-se a ela.
        numeros = faixa.split("-")
        if len(numeros) > 2 or not all(n.isdigit() for n in numeros):
            return False
        try:
            alvo = self._resolver(caminho)
        except ValueError:
            return False
        if not alvo.is_file():
            return False
        total = len(alvo.read_text(errors="replace").splitlines())
        return all(1 <= int(n) <= total for n in numeros)
