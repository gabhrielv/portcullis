# Plano de Implementação — Marco 1 (PRA)

> **Para quem executa:** siga tarefa por tarefa, na ordem. Os passos usam caixa
> (`- [ ]`) para acompanhamento. Não pule para o Marco 2 — nada de LLM aqui.
>
> 🔴 **Leia [`estudos/04-riscos-e-fixes.md`](../estudos/04-riscos-e-fixes.md) ANTES de começar.**
> Uma revisão posterior encontrou 8 furos neste plano, e **dois deles fazem o portão falhar
> aberto** — deixar passar achado que deveria bloquear, sem aviso nenhum. As correções estão
> lá com o código pronto; aplique-as nas Tarefas 8 e 9 conforme chegar nelas.

**Objetivo:** um PR no `gabhrielv/hoppr` dispara análise na AWS e o botão de merge fica cinza
se o PR introduziu um achado de severidade bloqueante.

**Arquitetura:** API Gateway → Lambda webhook → SQS → Lambda buscadora (baixa tarball + diff,
monta pacote no S3, invoca o analisador de forma assíncrona) → Lambda analisador, imagem de
container, dentro da VPC (função pura: pacote → achados) → S3 → Lambda publicadora (regra
determinística → Check Run + auditoria). Uma quinta Lambda serve
`GET /veredito/{owner}/{repo}/{sha}`.

**Stack:** Python 3.12, pytest, Semgrep (CLI), Terraform, Docker, AWS (Lambda, API Gateway
HTTP, SQS, S3, ECR, DynamoDB, SSM Parameter Store).

## Estado da execução

Atualizado em 13/08/2026. **Onde este plano divergir do que está aqui, vale o que está aqui.**

| Tarefa | Estado | Divergência do plano original |
|---|---|---|
| T1 | feito | perfis de instalação (`analisador`/`nuvem`/`dev`), `.venv` na raiz, `conftest.py` sem `sys.path` |
| T2 | feito | `VERSAO_REGRA = "2"`: `ERROR` bloqueia e `WARNING` bloqueia se `category == "security"` |
| T3 | feito | regras congeladas em `build/regras/`, `--disable-nosem`, hash do conjunto no `achados.json` |
| T4 | feito | + defesa contra bomba de descompressão, teto cabendo no `/tmp` de 512 MB da Lambda |
| T5 | feito | `excecoes.py`, `prefixo_de_regra()`, `.semgrepignore` vazio, imagem construída sem rede |
| T6 | feito, **não aplicado** | rede **sem internet gateway**, subnets privadas, módulo `alertas` (SNS + Budgets de US$1) |
| T6.5 | feito | novo: state remoto no S3, `use_lockfile`, bucket fora do Terraform |
| T7 | **feita** | 28 recursos de pé; URL automatizada; PR real no hoppr entrou na fila com os SHAs corretos |
| T8 | **feita** | Lambda de imagem, não Fargate. Análise real do hoppr rodou na nuvem: 16 achados, idênticos à linha de base local |
| T9 | **feita** | Check Run in_progress, veredito por PATCH, auditoria com hash das regras, DLQ da publicadora |
| T10 | **quase** | rota do veredito no ar e protecao de branch ativa. Falta o passo no workflow do hoppr e o README |

**A T6 nunca foi aplicada.** O primeiro `terraform apply` do projeto acontece na T7. Em
13/08/2026 as credenciais foram configuradas, o bucket de state criado e o backend migrado
para o S3 (T6.5) — falta só o GitHub App para aplicar.

**Medido na conta `523301712809` em 13/08/2026, e vale sobre qualquer número deste plano:**

| fato | consequência |
|---|---|
| Limite de concorrência da conta é **10**, não 1000 | a AWS recusa reserva que deixe menos de 100 livres, ou seja, recusa todas. `reserved_concurrent_executions = -1`. O teto da conta já faz o papel da reserva |
| A franquia de 12 meses **expirou** (conta de ~2,4 anos) | API Gateway custa US$1,00/milhão desde a primeira requisição; ECR custa US$0,10 por GB/mês, e a imagem do analisador tem ~1 GB |
| Lambda: 1M requisições e 400.000 GB-s/mês são **permanentes** | a franquia que sustenta o custo zero do analisador não expira — a troca de Fargate por Lambda continua de pé |

O ECR é **o primeiro item que cobra por existir parado**, e entra só na T8. Até lá, o stack
inteiro custa US$0,00 ocioso.

**Decisões tomadas fora deste documento** (12–13/08/2026), que valem sobre ele:

- O analisador roda em **Lambda com imagem de container**, dentro da VPC, sem rota para a
  internet. Custo zero pela franquia permanente de 400.000 GB-s; o Fargate era o único item
  pago do desenho. Some da T8: cluster ECS, task definition, execution role, task role,
  `iam:PassRole`, IP público.
- A VPC **não tem internet gateway**. O egress do SG do analisador é só para o prefix list do
  S3, na 443. A ressalva da T6 sobre "443 aberto para ECR e Logs" não se aplica mais: a Lambda
  puxa a imagem do ECR pela infraestrutura do serviço, não pela ENI dela.
- O provedor de LLM do marco 2 é **Groq**, não Cerebras (janela de contexto de 8.192 tokens
  não comporta o loop de 8 passos).
- `retention_in_days = 1` em todo grupo de log. Nunca `0` — no Terraform isso é "para sempre".
- DynamoDB **sem** point-in-time recovery.
- Tetos de concorrência: buscadora `2`, analisador `5`, webhook `5`.

**Referência de arquitetura:** `ARQUITETURA.md` (as 19 decisões) e `docs/justificativas.md`
(como cada uma foi fechada). Quando este plano disser "ver D14", é lá.

---

## Restrições globais

Valem para **todas** as tarefas. Não repetidas em cada uma.

| # | Restrição | Origem |
|---|---|---|
| G1 | **Nenhum indício de IA em commit, PR, issue ou arquivo versionado.** Sem `Co-Authored-By`, sem link de sessão, sem "Generated with", sem comentário atribuindo autoria a assistente | regra do autor, 11/08/2026 |
| G2 | **Nenhum segredo em código.** Os dois segredos (chave privada do App, segredo do webhook) vivem no SSM Parameter Store tipo `SecureString` | D11 |
| G3 | **Sem NAT Gateway e sem internet gateway.** O analisador fica em subnet privada, e a única saída dele é o prefix list do S3 na 443 | D3, revisto em 12/08/2026 |
| G4 | **Endpoint de S3 é `Gateway`, nunca `Interface`** (interface custa ~US$7,20/mês por AZ) | §9 |
| G5 | **As Lambdas que falam com o GitHub ficam FORA da VPC** (webhook, buscadora, publicadora, consulta). Dentro exigiriam NAT. **O analisador é a exceção**: ele não fala com o GitHub, então fica dentro | §9, revisto em 12/08/2026 |
| G6 | **O analisador não importa `pra.github` nem `pra.decisao`.** Ele não fala com o GitHub e não emite veredito | D14 |
| G7 | **Python 3.12.** `tarfile.extractall(..., filter='data')` é obrigatório | D14b |
| G8 | Layout `src/`; testes rodam contra o pacote instalado (`pip install -e`) | §7 |
| G9 | Commits pequenos e frequentes, prefixo convencional (`feat:`, `fix:`, `test:`, `chore:`) | — |
| G10 | Terraform: `terraform apply` sobe e `terraform destroy` derruba limpo, sempre | §6 |

**Região:** `us-east-1`. **Prefixo de nomes de recurso:** `pra`.

---

## Estrutura de arquivos

Criados ao longo do plano. Cada arquivo tem uma responsabilidade.

```
pra/
├── Makefile                              T1
├── .env.example                          T1
├── scripts/atualizar_webhook.py          T7   PATCH /app/hook/config depois do apply
├── app/
│   ├── pyproject.toml                    T1
│   ├── src/pra/
│   │   ├── __init__.py                   T1
│   │   ├── modelos.py                    T1   contratos compartilhados
│   │   ├── config.py                     T7   env vars e SSM, falha cedo
│   │   ├── decisao/
│   │   │   ├── regra.py                  T2   list[Achado] + Contexto -> Veredito
│   │   │   └── excecoes.py               T2   achados silenciados, com motivo
│   │   ├── analisador/
│   │   │   ├── semgrep.py                T3   CLI -> SaidaSemgrep
│   │   │   ├── pacote.py                 T4   tar/json -> arvore + Contexto
│   │   │   └── main.py                   T5   entrada do analisador
│   │   ├── webhook/
│   │   │   ├── assinatura.py             T7   HMAC do GitHub
│   │   │   └── handler.py                T7   Lambda: valida, enfileira, 200
│   │   ├── buscador/
│   │   │   ├── github_api.py             T8   tarball + diff
│   │   │   └── handler.py                T8   SQS -> pacote no S3 -> invoca analisador
│   │   ├── github/
│   │   │   ├── auth.py                   T7   chave privada -> JWT do App
│   │   │   │                             T9   + token de instalação
│   │   │   └── checks.py                 T9   Check Run + anotações
│   │   ├── publicador/handler.py         T9   evento S3 -> regra -> Check Run
│   │   ├── persistencia/dynamo.py        T9   registro de auditoria
│   │   └── consulta/handler.py           T10  GET /veredito/{owner}/{repo}/{sha}
│   └── tests/
│       ├── conftest.py                   T1
│       ├── fixtures/semgrep_saida.json   T3
│       ├── test_regra.py                 T2
│       ├── test_semgrep.py               T3
│       ├── test_pacote.py                T4
│       ├── test_analisador.py            T5
│       ├── test_arquitetura.py           T5   garante G6
│       ├── test_assinatura.py            T7
│       ├── test_webhook.py               T7   filtro de evento e enfileiramento
│       └── test_auth.py                  T7   claims do JWT
├── build/regras/                         T3   conjuntos do semgrep, congelados
├── docker/analisador.Dockerfile          T5
└── infra/
    ├── main.tf, variables.tf, outputs.tf, backend.tf, terraform.tfvars.example   T6
    └── modules/
        ├── alertas/    T6   SNS + assinatura por e-mail + AWS Budgets
        ├── rede/       T6   VPC sem IGW, subnets privadas, SG, gateway endpoint S3
        ├── pacotes/    T6   bucket S3 + lifecycle
        ├── fila/       T6   SQS + DLQ + alarme
        ├── dados/      T6   DynamoDB
        ├── funcoes/    T7   Lambdas de fora da VPC + API Gateway HTTP
        └── analisador/ T8   ECR + Lambda de imagem, dentro da VPC
```

---

## Tarefa 1 — Esqueleto do projeto e os modelos

O `modelos.py` é o contrato que todas as outras tarefas consomem. Ele vem primeiro porque
errar aqui obriga a mexer em tudo depois.

**Arquivos:**
- Criar: `app/pyproject.toml`, `app/src/pra/__init__.py`, `app/src/pra/modelos.py`
- Criar: `app/tests/conftest.py`, `app/tests/test_modelos.py`
- Criar: `Makefile`, `.env.example`

**Interfaces:**
- Consome: nada
- Produz: `Severidade`, `Evento`, `EstadoVeredito`, `FaixaLinhas`, `Achado`, `Contexto`,
  `Veredito` — usados por todas as tarefas seguintes

- [ ] **Passo 1: Criar `app/pyproject.toml`**

```toml
[project]
name = "PRA"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "boto3>=1.34",
    "requests>=2.31",
    "PyJWT[crypto]>=2.8",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.5"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integracao: precisa de rede ou de repositório local (desmarcado por padrão)",
]
addopts = "-m 'not integracao'"

[tool.ruff]
line-length = 100
```

> **Por que `addopts = "-m 'not integracao'"`:** os testes de integração leem o `hoppr` do
> disco e rodam o Semgrep de verdade — segundos em vez de milissegundos. O padrão roda só o
> que é instantâneo; `make teste-integracao` roda o resto.

- [ ] **Passo 2: Criar `app/src/pra/__init__.py` vazio e `app/tests/conftest.py`**

```python
# app/tests/conftest.py
import sys
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
CAMINHO_HOPPR = Path.home() / "projects" / "hoppr"

sys.path.insert(0, str(RAIZ_REPO / "app" / "src"))
```

- [ ] **Passo 3: Escrever o teste que falha**

```python
# app/tests/test_modelos.py
import pytest

from pra.modelos import (
    Achado,
    Contexto,
    Evento,
    FaixaLinhas,
    Severidade,
)


def test_faixa_detecta_sobreposicao_parcial():
    faixa = FaixaLinhas(inicio=10, fim=20)
    assert faixa.intersecta(18, 25) is True
    assert faixa.intersecta(1, 10) is True
    assert faixa.intersecta(21, 30) is False
    assert faixa.intersecta(1, 9) is False


def test_severidade_vem_do_vocabulario_do_semgrep():
    assert Severidade("ERROR") is Severidade.ERRO
    assert Severidade("WARNING") is Severidade.AVISO
    assert Severidade("INFO") is Severidade.INFO


def test_achado_e_imutavel():
    achado = Achado(
        regra="python.lang.security.audit.sqli",
        severidade=Severidade.ERRO,
        caminho="backend/app/repo/user.py",
        linha_inicio=88,
        linha_fim=88,
        mensagem="possível SQL injection",
    )
    with pytest.raises(Exception):
        achado.linha_inicio = 99


def test_contexto_de_push_nao_tem_numero_de_pr():
    ctx = Contexto(
        owner="gabhrielv",
        repo="hoppr",
        head_sha="a1b2c3",
        evento=Evento.PUSH,
        linhas_tocadas={},
    )
    assert ctx.numero_pr is None
    assert ctx.tudo_novo is False
```

- [ ] **Passo 4: Rodar e confirmar que falha**

```
cd app && python -m pytest tests/test_modelos.py -v
```
Esperado: `ModuleNotFoundError: No module named 'pra.modelos'`

- [ ] **Passo 5: Escrever `app/src/pra/modelos.py`**

```python
"""Contratos compartilhados por todos os componentes do PRA.

Nada aqui importa boto3, requests ou qualquer coisa de AWS/GitHub. Isso é
proposital: o analisador (que roda no container) importa este módulo, e ele
não pode ter dependência de nuvem nenhuma. Ver G6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severidade(Enum):
    """Vocabulário do próprio Semgrep, sem tradução.

    O marco 1 tem UM scanner. Inventar uma taxonomia própria agora seria
    adivinhar o mapeamento certo para scanners que ainda não existem —
    o mesmo erro que a §7 do ARQUITETURA.md descreve em "não existe
    scanners/base.py". A taxonomia comum nasce no marco 4, quando houver
    duas escalas de verdade para reconciliar.
    """

    ERRO = "ERROR"
    AVISO = "WARNING"
    INFO = "INFO"


class Evento(Enum):
    PULL_REQUEST = "pull_request"
    PUSH = "push"


class EstadoVeredito(Enum):
    LIBERADO = "liberado"
    BLOQUEADO = "bloqueado"
    NAO_CONCLUI = "nao_conclui"


@dataclass(frozen=True)
class FaixaLinhas:
    inicio: int
    fim: int

    def intersecta(self, inicio: int, fim: int) -> bool:
        return inicio <= self.fim and fim >= self.inicio


@dataclass(frozen=True)
class Achado:
    regra: str
    severidade: Severidade
    caminho: str
    linha_inicio: int
    linha_fim: int
    mensagem: str


@dataclass(frozen=True)
class Contexto:
    """O que a buscadora sabe e o analisador precisa.

    `linhas_tocadas` mapeia caminho -> faixas alteradas por este PR/push.
    É o dado que permite a política sensível ao diff da D15.

    `tudo_novo` liga o modo conservador: quando não dá pra calcular o diff
    (branch nova, force push, `before` zerado), TODO achado conta como novo.
    Erra pro lado de bloquear — fail-closed, coerente com a §4.
    """

    owner: str
    repo: str
    head_sha: str
    evento: Evento
    linhas_tocadas: dict[str, tuple[FaixaLinhas, ...]] = field(default_factory=dict)
    numero_pr: int | None = None
    base_sha: str | None = None
    tudo_novo: bool = False

    @property
    def id_analise(self) -> str:
        return f"{self.owner}/{self.repo}@{self.head_sha}"


@dataclass(frozen=True)
class Veredito:
    """Resultado da regra determinística. Ver D6, D15, D16.

    bloqueantes  -> achado NOVO com severidade bloqueante. Anotação `failure`.
    avisos       -> achado NOVO, severidade menor. Anotação `warning`. Não trava.
    preexistentes-> achado em linha que este PR não tocou. Só no resumo.
    """

    estado: EstadoVeredito
    bloqueantes: tuple[Achado, ...]
    avisos: tuple[Achado, ...]
    preexistentes: tuple[Achado, ...]
    versao_regra: str
    degradado: bool = False
    motivo: str | None = None
```

- [ ] **Passo 6: Rodar e confirmar que passa**

```
cd app && python -m pytest tests/test_modelos.py -v
```
Esperado: 4 passed

- [ ] **Passo 7: Criar `Makefile` na raiz**

```makefile
.PHONY: instalar teste teste-integracao lint imagem infra destruir

instalar:
	cd app && python -m pip install -e ".[dev]"

teste:
	cd app && python -m pytest -v

teste-integracao:
	cd app && python -m pytest -v -m integracao

lint:
	cd app && python -m ruff check src tests

imagem:
	docker build -f docker/analisador.Dockerfile -t pra-analisador:local .

infra:
	cd infra && terraform apply

destruir:
	cd infra && terraform destroy
```

- [ ] **Passo 8: Criar `.env.example`**

```bash
# Copie para .env e preencha. O .env está no .gitignore (G2).
AWS_REGION=us-east-1

# Preenchidos pelos outputs do Terraform
PRA_BUCKET_PACOTES=
PRA_FILA_URL=
PRA_TABELA_AUDITORIA=
PRA_CLUSTER_ECS=
PRA_TASK_DEFINITION=
PRA_SUBNETS=
PRA_SECURITY_GROUP=

# Nomes dos parâmetros no SSM — nunca os valores (G2)
PRA_PARAM_CHAVE_APP=/pra/github/chave-privada
PRA_PARAM_SEGREDO_WEBHOOK=/pra/github/segredo-webhook
PRA_GITHUB_APP_ID=
```

- [ ] **Passo 9: Commit**

```bash
git init
git add .gitignore Makefile .env.example app/ ARQUITETURA.md docs/
git commit -m "chore: esqueleto do projeto e modelos compartilhados"
```

> **Confira antes de commitar:** `git status` não pode listar `.env`, `.local/`, `*.pem`
> nem `*.tfvars`. Se listar, o `.gitignore` não está sendo aplicado.

---

## Tarefa 2 — A regra determinística (§8 passo 1)

**Esta é a peça mais importante do marco 1** e roda inteira sem AWS, sem rede e sem GitHub.
É também a peça que o marco 2 **não** vai reescrever — o agente entra *antes* dela.

**Arquivos:**
- Criar: `app/src/pra/decisao/__init__.py`, `app/src/pra/decisao/regra.py`
- Criar: `app/tests/test_regra.py`

**Interfaces:**
- Consome: `Achado`, `Contexto`, `Veredito`, `Severidade`, `EstadoVeredito` (T1)
- Produz: `decidir(achados, contexto, degradado=False, motivo=None) -> Veredito`
  e a constante `VERSAO_REGRA: str`

- [ ] **Passo 1: Escrever os testes que falham**

```python
# app/tests/test_regra.py
from pra.decisao.regra import VERSAO_REGRA, decidir
from pra.modelos import (
    Achado,
    Contexto,
    EstadoVeredito,
    Evento,
    FaixaLinhas,
    Severidade,
)

ARQUIVO = "backend/app/repo/user.py"


def achado(linha: int, severidade: Severidade = Severidade.ERRO, caminho: str = ARQUIVO):
    return Achado(
        regra="python.lang.security.audit.sqli",
        severidade=severidade,
        caminho=caminho,
        linha_inicio=linha,
        linha_fim=linha,
        mensagem="possível SQL injection",
    )


def contexto(tocadas=None, tudo_novo=False):
    return Contexto(
        owner="gabhrielv",
        repo="hoppr",
        head_sha="a1b2c3",
        evento=Evento.PULL_REQUEST,
        linhas_tocadas=tocadas or {},
        numero_pr=7,
        tudo_novo=tudo_novo,
    )


def test_achado_novo_com_severidade_bloqueante_trava():
    v = decidir([achado(88)], contexto({ARQUIVO: (FaixaLinhas(80, 95),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO
    assert len(v.bloqueantes) == 1
    assert v.preexistentes == ()


def test_achado_em_linha_nao_tocada_e_preexistente_e_nao_trava():
    v = decidir([achado(88)], contexto({ARQUIVO: (FaixaLinhas(200, 210),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert v.bloqueantes == ()
    assert len(v.preexistentes) == 1


def test_arquivo_fora_do_diff_e_preexistente():
    v = decidir([achado(88)], contexto({"outro/arquivo.py": (FaixaLinhas(1, 50),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.preexistentes) == 1


def test_achado_novo_de_severidade_menor_vira_aviso_e_nao_trava():
    v = decidir(
        [achado(88, Severidade.AVISO)],
        contexto({ARQUIVO: (FaixaLinhas(80, 95),)}),
    )
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.avisos) == 1
    assert v.bloqueantes == ()


def test_sobreposicao_parcial_conta_como_novo():
    # achado ocupa 10-15; o PR tocou 14-20. Encostou, é novo.
    a = Achado(
        regra="r",
        severidade=Severidade.ERRO,
        caminho=ARQUIVO,
        linha_inicio=10,
        linha_fim=15,
        mensagem="m",
    )
    v = decidir([a], contexto({ARQUIVO: (FaixaLinhas(14, 20),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_tudo_novo_ignora_o_diff_e_trava():
    # branch nova ou force push: não dá pra calcular diff, então tudo conta.
    v = decidir([achado(88)], contexto({}, tudo_novo=True))
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_sem_achados_libera():
    v = decidir([], contexto({ARQUIVO: (FaixaLinhas(1, 100),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert v.bloqueantes == ()
    assert v.avisos == ()
    assert v.preexistentes == ()


def test_modo_degradado_propaga_para_o_veredito():
    v = decidir(
        [achado(88)],
        contexto({ARQUIVO: (FaixaLinhas(80, 95),)}),
        degradado=True,
        motivo="cota do LLM esgotada",
    )
    assert v.degradado is True
    assert v.motivo == "cota do LLM esgotada"
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_veredito_carrega_a_versao_da_regra():
    # A D11 exige saber QUAL regra liberou aquele deploy.
    v = decidir([], contexto())
    assert v.versao_regra == VERSAO_REGRA
```

- [ ] **Passo 2: Rodar e confirmar que falha**

```
cd app && python -m pytest tests/test_regra.py -v
```
Esperado: `ModuleNotFoundError: No module named 'pra.decisao'`

- [ ] **Passo 3: Escrever `app/src/pra/decisao/regra.py`**

```python
"""A regra determinística. Ver D6 e D15.

Código do autor, não do modelo. No marco 2 o agente entrega evidência ANTES
desta função; ela continua sendo quem decide. Nada aqui consulta rede.
"""

from __future__ import annotations

from collections.abc import Iterable

from pra.modelos import (
    Achado,
    Contexto,
    EstadoVeredito,
    Severidade,
    Veredito,
)

VERSAO_REGRA = "1"

SEVERIDADES_BLOQUEANTES = frozenset({Severidade.ERRO})


def _e_novo(achado: Achado, contexto: Contexto) -> bool:
    if contexto.tudo_novo:
        return True
    faixas = contexto.linhas_tocadas.get(achado.caminho)
    if not faixas:
        return False
    return any(
        faixa.intersecta(achado.linha_inicio, achado.linha_fim) for faixa in faixas
    )


def decidir(
    achados: Iterable[Achado],
    contexto: Contexto,
    degradado: bool = False,
    motivo: str | None = None,
) -> Veredito:
    bloqueantes: list[Achado] = []
    avisos: list[Achado] = []
    preexistentes: list[Achado] = []

    for achado in achados:
        if not _e_novo(achado, contexto):
            preexistentes.append(achado)
        elif achado.severidade in SEVERIDADES_BLOQUEANTES:
            bloqueantes.append(achado)
        else:
            avisos.append(achado)

    estado = EstadoVeredito.BLOQUEADO if bloqueantes else EstadoVeredito.LIBERADO

    return Veredito(
        estado=estado,
        bloqueantes=tuple(bloqueantes),
        avisos=tuple(avisos),
        preexistentes=tuple(preexistentes),
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
```

- [ ] **Passo 4: Rodar e confirmar que passa**

```
cd app && python -m pytest tests/test_regra.py -v
```
Esperado: 9 passed

- [ ] **Passo 5: Commit**

```bash
git add app/src/pra/decisao/ app/tests/test_regra.py
git commit -m "feat: regra de decisão determinística sensível ao diff"
```

**Critério de aceite da tarefa:** `make teste` passa e a regra nunca importou nada de AWS,
GitHub ou rede. Confirme: `grep -rE "boto3|requests" app/src/pra/decisao/` não retorna nada.

---

## Tarefa 3 — Semgrep: rodar e parsear (§8 passo 2)

**Arquivos:**
- Criar: `app/src/pra/analisador/__init__.py`, `app/src/pra/analisador/semgrep.py`
- Criar: `app/tests/test_semgrep.py`, `app/tests/fixtures/semgrep_saida.json`

**Interfaces:**
- Consome: `Achado`, `Severidade` (T1)
- Produz: `parsear(saida: dict) -> list[Achado]`,
  `rodar(raiz: Path, timeout_s: int = 600) -> list[Achado]`, exceção `SemgrepFalhou`

- [ ] **Passo 1: Criar a fixture `app/tests/fixtures/semgrep_saida.json`**

Formato real de `semgrep --json`, reduzido ao que o parser usa.

```json
{
  "version": "1.86.0",
  "results": [
    {
      "check_id": "python.lang.security.audit.formatted-sql-query",
      "path": "backend/app/repo/user.py",
      "start": { "line": 88, "col": 9 },
      "end": { "line": 88, "col": 62 },
      "extra": {
        "severity": "ERROR",
        "message": "Detected possible formatted SQL query.\n",
        "metadata": { "cwe": ["CWE-89"] }
      }
    },
    {
      "check_id": "python.flask.security.audit.debug-enabled",
      "path": "backend/app/main.py",
      "start": { "line": 12, "col": 1 },
      "end": { "line": 14, "col": 20 },
      "extra": {
        "severity": "WARNING",
        "message": "Flask app appears to be run with debug=True",
        "metadata": {}
      }
    }
  ],
  "errors": [],
  "paths": { "scanned": ["backend/app/repo/user.py", "backend/app/main.py"] }
}
```

- [ ] **Passo 2: Escrever os testes que falham**

```python
# app/tests/test_semgrep.py
import json
from pathlib import Path

import pytest

from pra.analisador.semgrep import SemgrepFalhou, parsear, rodar
from pra.modelos import Severidade

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_fixture():
    return json.loads((FIXTURES / "semgrep_saida.json").read_text())


def test_parsear_extrai_todos_os_achados():
    achados = parsear(carregar_fixture())
    assert len(achados) == 2


def test_parsear_mapeia_severidade_do_semgrep():
    achados = parsear(carregar_fixture())
    assert achados[0].severidade is Severidade.ERRO
    assert achados[1].severidade is Severidade.AVISO


def test_parsear_preserva_caminho_relativo_e_faixa_de_linhas():
    a = parsear(carregar_fixture())[1]
    assert a.caminho == "backend/app/main.py"
    assert a.linha_inicio == 12
    assert a.linha_fim == 14


def test_parsear_limpa_espaco_da_mensagem():
    a = parsear(carregar_fixture())[0]
    assert a.mensagem == "Detected possible formatted SQL query."


def test_parsear_saida_vazia_devolve_lista_vazia():
    assert parsear({"results": [], "errors": []}) == []


def test_parsear_severidade_desconhecida_estoura():
    saida = {"results": [{
        "check_id": "x",
        "path": "a.py",
        "start": {"line": 1},
        "end": {"line": 1},
        "extra": {"severity": "CATASTROPHIC", "message": "m"},
    }]}
    with pytest.raises(ValueError):
        parsear(saida)


@pytest.mark.integracao
def test_rodar_encontra_achados_reais_no_hoppr():
    from conftest import CAMINHO_HOPPR

    if not CAMINHO_HOPPR.exists():
        pytest.skip("hoppr não está no disco")

    achados = rodar(CAMINHO_HOPPR / "backend")
    assert isinstance(achados, list)
    for a in achados:
        assert a.linha_inicio >= 1
        assert not a.caminho.startswith("/")
```

- [ ] **Passo 3: Rodar e confirmar que falha**

```
cd app && python -m pytest tests/test_semgrep.py -v
```
Esperado: `ModuleNotFoundError: No module named 'pra.analisador'`

- [ ] **Passo 4: Escrever `app/src/pra/analisador/semgrep.py`**

```python
"""Invoca o Semgrep como subprocesso e traduz a saída para Achado.

Não existe interface `Scanner` aqui de propósito — só há um scanner. Ver a
nota "não existe scanners/base.py" na §7 do ARQUITETURA.md.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pra.modelos import Achado, Severidade

# O Semgrep usa o código de saída para comunicar RESULTADO, não só erro:
#   0 -> rodou, nada encontrado
#   1 -> rodou, encontrou achados        <- NÃO é falha
#  >=2 -> falhou de verdade
CODIGOS_DE_SUCESSO = (0, 1)


class SemgrepFalhou(RuntimeError):
    pass


def parsear(saida: dict) -> list[Achado]:
    achados: list[Achado] = []
    for resultado in saida.get("results", []):
        extra = resultado["extra"]
        achados.append(
            Achado(
                regra=resultado["check_id"],
                severidade=Severidade(extra["severity"]),
                caminho=resultado["path"],
                linha_inicio=resultado["start"]["line"],
                linha_fim=resultado["end"]["line"],
                mensagem=extra["message"].strip(),
            )
        )
    return achados


def rodar(raiz: Path, timeout_s: int = 600) -> list[Achado]:
    comando = [
        "semgrep",
        "scan",
        "--config=auto",
        "--json",
        "--quiet",
        "--metrics=off",
        str(raiz),
    ]
    try:
        proc = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=raiz,
        )
    except subprocess.TimeoutExpired as erro:
        raise SemgrepFalhou(f"semgrep estourou {timeout_s}s") from erro

    if proc.returncode not in CODIGOS_DE_SUCESSO:
        raise SemgrepFalhou(
            f"semgrep saiu com {proc.returncode}: {proc.stderr[:500]}"
        )

    return parsear(json.loads(proc.stdout))
```

> **`--metrics=off`** impede o Semgrep de mandar telemetria pra fora. No container isso é
> obrigatório: o egress só permite S3 (G3/G4), então a telemetria travaria a execução.

- [ ] **Passo 5: Rodar e confirmar que passa**

```
cd app && python -m pytest tests/test_semgrep.py -v
```
Esperado: 6 passed, 1 deselected

- [ ] **Passo 6: Instalar o Semgrep e rodar o teste de integração**

```bash
python -m pip install semgrep
cd app && python -m pytest tests/test_semgrep.py -v -m integracao
```
Esperado: PASS, e a saída mostra achados reais do `hoppr`. **Anote quantos** — esse número
é a linha de base da dívida pré-existente que a D15 previu.

- [ ] **Passo 7: Commit**

```bash
git add app/src/pra/analisador/ app/tests/test_semgrep.py app/tests/fixtures/
git commit -m "feat: executa semgrep e parseia a saída para Achado"
```

---

## Tarefa 4 — O pacote de trabalho e a defesa contra path traversal

**Arquivos:**
- Criar: `app/src/pra/analisador/pacote.py`
- Criar: `app/tests/test_pacote.py`

**Interfaces:**
- Consome: `Contexto`, `Evento`, `FaixaLinhas` (T1)
- Produz: `NOME_CODIGO`, `NOME_CONTEXTO`, `PacoteInvalido`,
  `extrair(tar: Path, destino: Path) -> Path`,
  `ler_contexto(caminho: Path) -> Contexto`,
  `escrever_contexto(contexto: Contexto, caminho: Path) -> None`

- [ ] **Passo 1: Escrever os testes que falham**

```python
# app/tests/test_pacote.py
import io
import json
import tarfile
from pathlib import Path

import pytest

from pra.analisador.pacote import (
    PacoteInvalido,
    escrever_contexto,
    extrair,
    ler_contexto,
)
from pra.modelos import Contexto, Evento, FaixaLinhas


def montar_tar(tmp_path: Path, membros: dict[str, str], nome="codigo.tar.gz") -> Path:
    caminho = tmp_path / nome
    with tarfile.open(caminho, "w:gz") as tf:
        for nome_membro, conteudo in membros.items():
            dados = conteudo.encode()
            info = tarfile.TarInfo(name=nome_membro)
            info.size = len(dados)
            tf.addfile(info, io.BytesIO(dados))
    return caminho


def test_extrai_e_devolve_a_raiz_unica_do_tarball(tmp_path):
    # o tarball do GitHub sempre vem com uma pasta raiz owner-repo-sha/
    tar = montar_tar(tmp_path, {"gabhrielv-hoppr-a1b2c3/README.md": "oi"})
    destino = tmp_path / "saida"
    destino.mkdir()

    raiz = extrair(tar, destino)

    assert raiz.name == "gabhrielv-hoppr-a1b2c3"
    assert (raiz / "README.md").read_text() == "oi"


def test_recusa_membro_que_escapa_do_destino(tmp_path):
    # zip-slip: o tarball é controlado por quem abriu o PR (D14b)
    tar = montar_tar(tmp_path, {"../fora.txt": "invasor"})
    destino = tmp_path / "saida"
    destino.mkdir()

    with pytest.raises(tarfile.FilterError):
        extrair(tar, destino)

    assert not (tmp_path / "fora.txt").exists()


def test_recusa_membro_com_caminho_absoluto(tmp_path):
    tar = montar_tar(tmp_path, {"/etc/invadido": "invasor"})
    destino = tmp_path / "saida"
    destino.mkdir()

    with pytest.raises(tarfile.FilterError):
        extrair(tar, destino)


def test_recusa_tarball_sem_raiz_unica(tmp_path):
    tar = montar_tar(tmp_path, {"a/x.py": "1", "b/y.py": "2"})
    destino = tmp_path / "saida"
    destino.mkdir()

    with pytest.raises(PacoteInvalido):
        extrair(tar, destino)


def test_contexto_sobrevive_a_ida_e_volta_em_json(tmp_path):
    original = Contexto(
        owner="gabhrielv",
        repo="hoppr",
        head_sha="a1b2c3",
        evento=Evento.PULL_REQUEST,
        linhas_tocadas={"backend/app/main.py": (FaixaLinhas(10, 20), FaixaLinhas(40, 41))},
        numero_pr=7,
        base_sha="0f0f0f",
    )
    caminho = tmp_path / "contexto.json"

    escrever_contexto(original, caminho)
    lido = ler_contexto(caminho)

    assert lido == original


def test_contexto_com_json_invalido_estoura(tmp_path):
    caminho = tmp_path / "contexto.json"
    caminho.write_text('{"owner": "gabhrielv"}')

    with pytest.raises(PacoteInvalido):
        ler_contexto(caminho)
```

- [ ] **Passo 2: Rodar e confirmar que falha**

```
cd app && python -m pytest tests/test_pacote.py -v
```
Esperado: `ImportError: cannot import name 'extrair'`

- [ ] **Passo 3: Escrever `app/src/pra/analisador/pacote.py`**

```python
"""Formato do pacote de trabalho — o contrato entre a buscadora e o analisador.

    entrada/{owner}/{repo}/{sha}/codigo.tar.gz
    entrada/{owner}/{repo}/{sha}/contexto.json

Esse contrato é o que permite o corpus da D12 montar um pacote na mão e rodar
o analisador offline, sem AWS e sem GitHub.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from pra.modelos import Contexto, Evento, FaixaLinhas

NOME_CODIGO = "codigo.tar.gz"
NOME_CONTEXTO = "contexto.json"
NOME_ACHADOS = "achados.json"


class PacoteInvalido(ValueError):
    pass


def extrair(tar: Path, destino: Path) -> Path:
    """Descompacta e devolve a pasta raiz do repositório.

    `filter='data'` é obrigatório (G7): o tarball vem de um repositório que
    quem abriu o PR controla, e sem o filtro um membro chamado `../x` escreve
    fora do destino. Em Python 3.12 o filtro NÃO é o padrão — omitir só emite
    DeprecationWarning e continua vulnerável.
    """
    with tarfile.open(tar, "r:gz") as arquivo:
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
    except (KeyError, ValueError, TypeError) as erro:
        raise PacoteInvalido(f"contexto.json inválido: {erro}") from erro
```

- [ ] **Passo 4: Rodar e confirmar que passa**

```
cd app && python -m pytest tests/test_pacote.py -v
```
Esperado: 6 passed

- [ ] **Passo 5: Commit**

```bash
git add app/src/pra/analisador/pacote.py app/tests/test_pacote.py
git commit -m "feat: formato do pacote de trabalho com defesa contra path traversal"
```

---

## Tarefa 5 — O analisador como função pura, no Docker (§8 passo 3)

Fim do que roda sem AWS. Ao terminar esta tarefa você tem **metade do valor do marco 1**
demonstrável na sua máquina.

**Arquivos:**
- Criar: `app/src/pra/analisador/main.py`
- Criar: `app/tests/test_analisador.py`, `app/tests/test_arquitetura.py`
- Criar: `docker/analisador.Dockerfile`

**Interfaces:**
- Consome: `rodar` (T3), `extrair`, `ler_contexto`, `NOME_CODIGO`, `NOME_CONTEXTO`,
  `NOME_ACHADOS` (T4), `Achado` (T1)
- Produz: `analisar(dir_entrada: Path, dir_saida: Path) -> Path`, e o formato
  `achados.json` que a Lambda publicadora (T9) consome

- [ ] **Passo 1: Escrever os testes que falham**

```python
# app/tests/test_analisador.py
import json
from pathlib import Path

import pytest

from pra.analisador import main as analisador
from pra.analisador.pacote import NOME_CONTEXTO, escrever_contexto
from pra.modelos import Achado, Contexto, Evento, FaixaLinhas, Severidade
from test_pacote import montar_tar


def montar_pacote(tmp_path: Path) -> Path:
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    montar_tar(
        entrada,
        {"gabhrielv-hoppr-a1b2c3/app.py": "x = 1\n"},
        nome="codigo.tar.gz",
    )
    escrever_contexto(
        Contexto(
            owner="gabhrielv",
            repo="hoppr",
            head_sha="a1b2c3",
            evento=Evento.PULL_REQUEST,
            linhas_tocadas={"app.py": (FaixaLinhas(1, 1),)},
            numero_pr=7,
        ),
        entrada / NOME_CONTEXTO,
    )
    return entrada


def test_analisar_escreve_achados_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        analisador,
        "rodar",
        lambda raiz, **kw: [
            Achado("r1", Severidade.ERRO, "app.py", 1, 1, "achei")
        ],
    )
    entrada = montar_pacote(tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()

    caminho = analisador.analisar(entrada, saida)
    dados = json.loads(caminho.read_text())

    assert dados["ok"] is True
    assert dados["head_sha"] == "a1b2c3"
    assert len(dados["achados"]) == 1
    assert dados["achados"][0]["severidade"] == "ERROR"
    assert dados["achados"][0]["caminho"] == "app.py"


def test_caminho_do_achado_e_relativo_a_raiz_do_repo(tmp_path, monkeypatch):
    # o semgrep devolve caminho absoluto do container; a publicadora precisa
    # do caminho relativo pra anotar a linha certa no GitHub
    monkeypatch.setattr(
        analisador,
        "rodar",
        lambda raiz, **kw: [
            Achado("r1", Severidade.ERRO, str(raiz / "app.py"), 1, 1, "achei")
        ],
    )
    entrada = montar_pacote(tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()

    dados = json.loads(analisador.analisar(entrada, saida).read_text())
    assert dados["achados"][0]["caminho"] == "app.py"


def test_falha_do_scanner_vira_ok_false_e_nao_explode(tmp_path, monkeypatch):
    from pra.analisador.semgrep import SemgrepFalhou

    def explodir(raiz, **kw):
        raise SemgrepFalhou("semgrep saiu com 2")

    monkeypatch.setattr(analisador, "rodar", explodir)
    entrada = montar_pacote(tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()

    dados = json.loads(analisador.analisar(entrada, saida).read_text())

    assert dados["ok"] is False
    assert "semgrep" in dados["erro"]
    assert dados["achados"] == []
```

```python
# app/tests/test_arquitetura.py
"""Garante a restrição G6 mecanicamente, não por disciplina.

O container não pode falar com o GitHub nem emitir veredito (D14). Se alguém
adicionar um import desses, este teste quebra.
"""

from pathlib import Path

PROIBIDOS = ("pra.github", "pra.decisao", "pra.persistencia")
PASTA_ANALISADOR = (
    Path(__file__).resolve().parents[1] / "src" / "PRA" / "analisador"
)


def test_analisador_nao_importa_github_nem_decisao():
    for arquivo in PASTA_ANALISADOR.rglob("*.py"):
        conteudo = arquivo.read_text()
        for proibido in PROIBIDOS:
            assert proibido not in conteudo, (
                f"{arquivo.name} importa {proibido} — viola a separação da D14"
            )
```

- [ ] **Passo 2: Rodar e confirmar que falha**

```
cd app && python -m pytest tests/test_analisador.py tests/test_arquitetura.py -v
```
Esperado: `ImportError: cannot import name 'main'`

- [ ] **Passo 3: Escrever `app/src/pra/analisador/main.py`**

```python
"""Entrada do container. FUNÇÃO PURA: pacote entra, achados saem.

Não conhece GitHub, não conhece a regra de decisão, não emite veredito.
Isso é a D14 virando código — e o test_arquitetura.py garante que continue.

Uso:
    python -m pra.analisador.main /entrada /saida
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from pra.analisador.pacote import (
    NOME_ACHADOS,
    NOME_CODIGO,
    NOME_CONTEXTO,
    extrair,
    ler_contexto,
)
from pra.analisador.semgrep import SemgrepFalhou, rodar
from pra.modelos import Achado


def _relativizar(caminho: str, raiz: Path) -> str:
    try:
        return str(Path(caminho).resolve().relative_to(raiz.resolve()))
    except ValueError:
        return caminho


def _serializar(achado: Achado, raiz: Path) -> dict:
    return {
        "regra": achado.regra,
        "severidade": achado.severidade.value,
        "caminho": _relativizar(achado.caminho, raiz),
        "linha_inicio": achado.linha_inicio,
        "linha_fim": achado.linha_fim,
        "mensagem": achado.mensagem,
    }


def analisar(dir_entrada: Path, dir_saida: Path) -> Path:
    contexto = ler_contexto(dir_entrada / NOME_CONTEXTO)

    with tempfile.TemporaryDirectory() as temporario:
        raiz = extrair(dir_entrada / NOME_CODIGO, Path(temporario))

        erro: str | None = None
        achados: list[Achado] = []
        try:
            achados = rodar(raiz)
        except SemgrepFalhou as falha:
            erro = str(falha)

        resultado = {
            "ok": erro is None,
            "erro": erro,
            "owner": contexto.owner,
            "repo": contexto.repo,
            "head_sha": contexto.head_sha,
            "achados": [_serializar(a, raiz) for a in achados],
        }

    destino = dir_saida / NOME_ACHADOS
    destino.write_text(json.dumps(resultado, indent=2))
    return destino


def principal() -> int:
    if len(sys.argv) != 3:
        print("uso: main.py <dir_entrada> <dir_saida>", file=sys.stderr)
        return 2
    analisar(Path(sys.argv[1]), Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
```

> **Por que `ok: false` em vez de exceção:** o container que morre com stack trace não deixa
> a publicadora saber o que houve. Escrever `ok:false` transforma a falha do scanner no
> `action_required` da D16 — que trava o merge, mas com mensagem útil.

- [ ] **Passo 4: Rodar e confirmar que passa**

```
cd app && python -m pytest tests/ -v
```
Esperado: todos passam

- [ ] **Passo 5: Criar `docker/analisador.Dockerfile`**

```dockerfile
FROM python:3.12-slim

# semgrep traz as próprias regras; git NÃO é instalado de propósito —
# o container não clona nada (D14).
RUN pip install --no-cache-dir semgrep==1.86.0

WORKDIR /opt/pra
COPY app/pyproject.toml ./
COPY app/src ./src
RUN pip install --no-cache-dir .

# Baixa as regras do registry AGORA, na build. Em runtime o egress só
# permite S3 (G3), então `--config=auto` não conseguiria buscá-las.
ENV SEMGREP_RULES_CACHE_DIR=/opt/semgrep-regras
RUN mkdir -p /opt/semgrep-regras \
    && semgrep --config=auto --metrics=off --dryrun /opt/pra/src || true

# roda como não-root: ele lê código de estranho
RUN useradd --create-home --uid 10001 analista
USER analista

ENTRYPOINT ["python", "-m", "pra.analisador.main"]
CMD ["/entrada", "/saida"]
```

- [ ] **Passo 6: Construir a imagem e rodar num pacote montado à mão**

```bash
make imagem

# monta um pacote de mentira
mkdir -p /tmp/pra/{entrada,saida}
cd /tmp/pra && mkdir -p gabhrielv-hoppr-a1b2c3 && \
  printf 'import sqlite3\ndef f(c, i):\n    c.execute("SELECT * FROM u WHERE id = " + i)\n' \
  > gabhrielv-hoppr-a1b2c3/vuln.py && \
  tar czf entrada/codigo.tar.gz gabhrielv-hoppr-a1b2c3 && \
  cat > entrada/contexto.json <<'JSON'
{"owner":"gabhrielv","repo":"hoppr","head_sha":"a1b2c3","evento":"pull_request",
 "numero_pr":7,"base_sha":null,"tudo_novo":false,
 "linhas_tocadas":{"vuln.py":[[1,3]]}}
JSON

docker run --rm --network=none \
  -v /tmp/pra/entrada:/entrada:ro \
  -v /tmp/pra/saida:/saida \
  pra-analisador:local

cat /tmp/pra/saida/achados.json
```

**Critério de aceite:** `achados.json` traz `"ok": true` e ao menos um achado em `vuln.py`.
O `--network=none` prova que o analisador roda **sem rede nenhuma** — é a §3 verificável na
sua máquina antes de existir AWS.

- [ ] **Passo 7: Commit**

```bash
git add app/src/pra/analisador/main.py app/tests/test_analisador.py \
        app/tests/test_arquitetura.py docker/
git commit -m "feat: analisador como função pura, com imagem sem rede"
```

---

## Tarefa 6 — Terraform: rede, pacotes, fila e dados (§8 passo 4)

> ✅ **Escrita e validada, ainda não aplicada.** O que está no `infra/` diverge do texto abaixo
> em cinco pontos, e o que vale é o `infra/`:
>
> 1. **Não existe internet gateway nem subnet pública.** As subnets são privadas e a única
>    rota de saída é o gateway endpoint do S3. A segunda regra de egress ("443 para ECR e
>    Logs") e a caixa de decisão que a acompanha **não se aplicam mais** — o analisador virou
>    Lambda, e a Lambda puxa a imagem do ECR pela infraestrutura do serviço, não pela ENI.
>    A promessa da §3 ficou mais forte do que o plano previa: dá para mostrar na tela que não
>    existe rota para a internet.
> 2. Existe um módulo `alertas`: tópico SNS com e-mail. O **AWS Budgets saiu do Terraform**
>    em 13/08/2026 — orçamento gerenciado pelo stack sumiria no `destroy`, e a conta já tinha
>    três orçamentos quando a AWS só dá dois grátis. Ficou o `My Zero-Spend Budget` que a
>    própria AWS criou (US$1/mês, aviso acima de US$0,01 de gasto real), fora do Terraform.
> 3. A fila tem alarme de CloudWatch na DLQ, apontando para o tópico.
> 4. A tabela **não** tem point-in-time recovery (é cobrado por GB).
> 5. `aws_region` expõe `.region`, não `.name`, no provider 6.x.
>
> O passo 8 (destruir e subir de novo) fica para o fim da T7, quando existir algo de ponta a
> ponta para reconstruir.

Primeira tarefa que gasta dinheiro. Todas as decisões de custo da §9 moram aqui.

**Arquivos:**
- Criar: `infra/{main,variables,outputs,backend}.tf`, `infra/terraform.tfvars.example`
- Criar: `infra/modules/rede/{main,variables,outputs}.tf`
- Criar: `infra/modules/pacotes/{main,variables,outputs}.tf`
- Criar: `infra/modules/fila/{main,variables,outputs}.tf`
- Criar: `infra/modules/dados/{main,variables,outputs}.tf`

**Interfaces:**
- Consome: nada de Python
- Produz outputs consumidos por T7/T8: `id_vpc`, `ids_subnets_publicas`,
  `id_sg_analisador`, `nome_bucket_pacotes`, `arn_bucket_pacotes`, `url_fila`,
  `arn_fila`, `nome_tabela`, `arn_tabela`

- [ ] **Passo 1: Instalar o Terraform e a CLI da AWS**

```bash
# Terraform
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor \
  -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install

aws configure           # chave de um usuário IAM seu, não a root
aws sts get-caller-identity
```

**Antes de seguir, crie um AWS Budget de US$5 com alerta por e-mail** (D3). Leva 2 minutos
no console e é a única proteção contra um erro de configuração virar fatura.

- [ ] **Passo 2: Escrever `infra/modules/rede/main.tf`**

```hcl
variable "prefixo" { type = string }
variable "cidr_vpc" {
  type    = string
  default = "10.0.0.0/16"
}

data "aws_availability_zones" "disponiveis" {
  state = "available"
}

resource "aws_vpc" "principal" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.prefixo}-vpc" }
}

resource "aws_internet_gateway" "principal" {
  vpc_id = aws_vpc.principal.id
  tags   = { Name = "${var.prefixo}-igw" }
}

# SUBNETS PÚBLICAS de propósito. Subnet privada exigiria NAT Gateway
# (~US$32/mês) ou 3 interface endpoints (~US$21/mês). Ver §9 e G3.
resource "aws_subnet" "publicas" {
  count                   = 2
  vpc_id                  = aws_vpc.principal.id
  cidr_block              = cidrsubnet(var.cidr_vpc, 8, count.index)
  availability_zone       = data.aws_availability_zones.disponiveis.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.prefixo}-publica-${count.index}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.principal.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.principal.id
  }
  tags = { Name = "${var.prefixo}-rt-publica" }
}

resource "aws_route_table_association" "publicas" {
  count          = length(aws_subnet.publicas)
  subnet_id      = aws_subnet.publicas[count.index].id
  route_table_id = aws_route_table.publica.id
}

# GATEWAY endpoint, não interface. Gateway é de graça; interface custa
# ~US$7,20/mês por AZ. S3 e DynamoDB são os únicos dois com gateway. G4.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.principal.id
  service_name      = "com.amazonaws.${data.aws_region.atual.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.publica.id]
  tags              = { Name = "${var.prefixo}-endpoint-s3" }
}

data "aws_region" "atual" {}

data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${data.aws_region.atual.name}.s3"
}

# O security group É a promessa da §3 virando configuração verificável.
resource "aws_security_group" "analisador" {
  name        = "${var.prefixo}-analisador"
  description = "Analisador: sem entrada; saida apenas para S3 e ECR"
  vpc_id      = aws_vpc.principal.id
  tags        = { Name = "${var.prefixo}-analisador" }
}

# NENHUMA regra de entrada. O container não serve nada.

# Saída para S3 pelo prefix list — é assim que "sem rota pra github.com"
# deixa de ser prosa e vira regra que dá pra mostrar na tela (D14).
resource "aws_vpc_security_group_egress_rule" "s3" {
  security_group_id = aws_security_group.analisador.id
  prefix_list_id    = data.aws_prefix_list.s3.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "S3 via gateway endpoint"
}

# ECR e CloudWatch Logs não têm prefix list. Como a task fica em subnet
# pública, essas chamadas saem pelo IGW e precisam de 443 aberto.
# É o preço de não pagar US$21/mês em interface endpoints (§9).
resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.analisador.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "ECR pull e CloudWatch Logs"
}

output "id_vpc" { value = aws_vpc.principal.id }
output "ids_subnets_publicas" { value = aws_subnet.publicas[*].id }
output "id_sg_analisador" { value = aws_security_group.analisador.id }
```

> **Leia isto, é a decisão de IAM/rede mais importante do marco 1.**
> A segunda regra de saída abre 443 pra qualquer destino — o que, lido de forma literal,
> permitiria o container alcançar `github.com`. Isso **enfraquece** a promessa da §3 e você
> precisa saber disso ao defender o projeto. As três saídas honestas:
> 1. **Aceitar** e apoiar a promessa no fato de que o container **não tem o token** — sem
>    credencial, alcançar o GitHub não dá acesso a repositório privado nenhum.
> 2. **Pagar** ~US$21/mês em interface endpoints (ECR API, ECR DKR, Logs) e fechar tudo.
> 3. **Registrar como dívida** e fechar no marco 4.
>
> Escolha 1 no marco 1 e **escreva a justificativa no README** — "o container tem rota, mas
> não tem credencial" é uma frase verdadeira e defensável; "o container não tem rede" não é.

- [ ] **Passo 3: Escrever `infra/modules/pacotes/main.tf`**

```hcl
variable "prefixo" { type = string }
variable "dias_retencao" {
  type    = number
  default = 7
}

resource "aws_s3_bucket" "pacotes" {
  bucket        = "${var.prefixo}-pacotes-${data.aws_caller_identity.atual.account_id}"
  force_destroy = true
  tags          = { Name = "${var.prefixo}-pacotes" }
}

data "aws_caller_identity" "atual" {}

resource "aws_s3_bucket_public_access_block" "pacotes" {
  bucket                  = aws_s3_bucket.pacotes.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "pacotes" {
  bucket = aws_s3_bucket.pacotes.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# O código-fonte não precisa durar. Quem precisa durar é a auditoria (D11),
# e ela vive no DynamoDB.
resource "aws_s3_bucket_lifecycle_configuration" "pacotes" {
  bucket = aws_s3_bucket.pacotes.id
  rule {
    id     = "expirar-pacotes"
    status = "Enabled"
    filter {}
    expiration { days = var.dias_retencao }
  }
}

output "nome_bucket_pacotes" { value = aws_s3_bucket.pacotes.id }
output "arn_bucket_pacotes" { value = aws_s3_bucket.pacotes.arn }
```

- [ ] **Passo 4: Escrever `infra/modules/fila/main.tf`**

```hcl
variable "prefixo" { type = string }

resource "aws_sqs_queue" "mortas" {
  name                      = "${var.prefixo}-mortas"
  message_retention_seconds = 1209600 # 14 dias, o máximo
}

resource "aws_sqs_queue" "analises" {
  name = "${var.prefixo}-analises"

  # A buscadora baixa tarball e chama RunTask. 5 min de folga.
  visibility_timeout_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.mortas.arn
    maxReceiveCount     = 3
  })
}

output "url_fila" { value = aws_sqs_queue.analises.url }
output "arn_fila" { value = aws_sqs_queue.analises.arn }
output "arn_fila_mortas" { value = aws_sqs_queue.mortas.arn }
```

> **Por que fila de mensagens mortas desde o começo:** sem ela, uma mensagem que sempre falha
> é reprocessada para sempre — e como cada tentativa dispara uma task do Fargate, isso é o
> único jeito de o marco 1 gerar fatura inesperada.

- [ ] **Passo 5: Escrever `infra/modules/dados/main.tf`**

```hcl
variable "prefixo" { type = string }

# Chave composta por causa da D18: multi-repo desde o marco 1.
# PK = owner#repo, SK = sha. Trocar isso depois exigiria migrar dados.
resource "aws_dynamodb_table" "auditoria" {
  name         = "${var.prefixo}-auditoria"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "repo"
  range_key    = "sha"

  attribute {
    name = "repo"
    type = "S"
  }
  attribute {
    name = "sha"
    type = "S"
  }

  point_in_time_recovery { enabled = true }
  tags = { Name = "${var.prefixo}-auditoria" }
}

output "nome_tabela" { value = aws_dynamodb_table.auditoria.name }
output "arn_tabela" { value = aws_dynamodb_table.auditoria.arn }
```

- [ ] **Passo 6: Escrever `infra/main.tf`, `variables.tf`, `outputs.tf`, `backend.tf`**

```hcl
# infra/backend.tf
# No primeiro apply deixe COMENTADO — o bucket de state ainda não existe.
# Descomente depois e rode `terraform init -migrate-state`.
# terraform {
#   backend "s3" {
#     bucket       = "pra-tfstate-SEU_ID_DE_CONTA"
#     key          = "marco-1/terraform.tfstate"
#     region       = "us-east-1"
#     use_lockfile = true
#   }
# }
```

```hcl
# infra/variables.tf
variable "prefixo" {
  type    = string
  default = "PRA"
}

variable "regiao" {
  type    = string
  default = "us-east-1"
}
```

```hcl
# infra/main.tf
terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.regiao
  default_tags {
    tags = {
      Projeto   = "PRA"
      Terraform = "true"
    }
  }
}

module "rede" {
  source  = "./modules/rede"
  prefixo = var.prefixo
}

module "pacotes" {
  source  = "./modules/pacotes"
  prefixo = var.prefixo
}

module "fila" {
  source  = "./modules/fila"
  prefixo = var.prefixo
}

module "dados" {
  source  = "./modules/dados"
  prefixo = var.prefixo
}
```

```hcl
# infra/outputs.tf
output "ids_subnets_publicas" { value = module.rede.ids_subnets_publicas }
output "id_sg_analisador" { value = module.rede.id_sg_analisador }
output "nome_bucket_pacotes" { value = module.pacotes.nome_bucket_pacotes }
output "url_fila" { value = module.fila.url_fila }
output "nome_tabela" { value = module.dados.nome_tabela }
```

- [ ] **Passo 7: Aplicar e conferir**

```bash
cd infra
terraform init
terraform plan       # LEIA o plano inteiro antes de aplicar
terraform apply
terraform output
```

**Critério de aceite — confira os três, um por um:**

```bash
# 1. NÃO existe NAT Gateway (seria ~US$32/mês)
aws ec2 describe-nat-gateways --filter Name=state,Values=available \
  --query 'NatGateways[].NatGatewayId' --output text
# esperado: vazio

# 2. O endpoint de S3 é Gateway, não Interface
aws ec2 describe-vpc-endpoints \
  --query 'VpcEndpoints[].[ServiceName,VpcEndpointType]' --output table
# esperado: com.amazonaws.us-east-1.s3 | Gateway

# 3. O SG do analisador não tem NENHUMA regra de entrada
aws ec2 describe-security-groups --group-ids $(terraform output -raw id_sg_analisador) \
  --query 'SecurityGroups[0].IpPermissions' --output text
# esperado: vazio
```

- [ ] **Passo 8: Derrubar e subir de novo**

```bash
terraform destroy
terraform apply
```
Isso prova o atributo de qualidade "reconstruir o ambiente do zero" (§6). Cronometre: precisa
ficar abaixo de 15 minutos.

- [ ] **Passo 9: Commit**

```bash
git add infra/
git commit -m "feat: infraestrutura base — rede sem NAT, bucket, fila e tabela"
```

---

## Tarefa 6.5 — State remoto no S3

Não estava no plano. Entrou em 13/08/2026, antes do primeiro `apply`.

**O problema:** o `terraform.tfstate` é o mapa entre o que está escrito no `.tf` e o que existe
de verdade na AWS. Com ele em arquivo local, o ciclo `apply` … trabalha … `destroy` tem um
ponto único de falha: se o arquivo sumir entre os dois, os recursos ficam **órfãos** — de pé na
conta, invisíveis para o Terraform, achados só pela fatura ou catando no console. A partir da
T7 são ~15 recursos, um deles uma URL pública.

**Por que agora e não no fim:** o risco cresce com o número de recursos, e migrar depois é o
mesmo trabalho. Custo: US$0,00 — o state tem alguns KB, e `use_lockfile = true` faz o lock por
escrita condicional no próprio S3, sem a tabela DynamoDB que os tutoriais antigos mandam criar.

**Por que o bucket nasce fora do Terraform:** se o stack gerenciasse o bucket do próprio state,
o `destroy` apagaria o mapa junto com o território. Ele é criado uma vez, na mão, e sobrevive a
todos os ciclos.

- [ ] **Passo 1: Criar o bucket**

```bash
CONTA=$(aws sts get-caller-identity --query Account --output text)
BUCKET="pra-tfstate-${CONTA}"

aws s3api create-bucket --bucket "$BUCKET" --region us-east-1
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
# Versionamento é a rede de proteção: state corrompido volta para a versão anterior.
aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled
```

- [ ] **Passo 2: Descomentar `infra/backend.tf`** com o nome real e rodar `terraform init`

Como ainda não existe state local, não há `-migrate-state`: o primeiro `init` já nasce remoto.

**Critério de aceite:** `terraform init` responde `Successfully configured the backend "s3"`, e
depois do primeiro apply `aws s3 ls s3://$BUCKET/marco-1/` mostra o `terraform.tfstate`.

---

## Tarefa 7 — GitHub App, webhook e API Gateway (§8 passo 5)

> **Reescrita em 13/08/2026.** As decisões abaixo foram tomadas antes de executar e substituem
> o que o plano original dizia.

| Decisão | Escolha | Motivo |
|---|---|---|
| Empacotamento | **um zip só** para as quatro Lambdas de fora da VPC, **sem boto3** | boto3 já vem no runtime `python3.12`; `requests` e `PyJWT` não. ~13 MB, um build, um hash |
| Teto de rajada | `reserved_concurrent_executions = 5` **e** throttle de 10 req/s (rajada 20) no estágio | as duas são grátis; a URL é pública e o Budgets avisa depois do gasto |
| URL do webhook | **automatizada** via `PATCH /app/hook/config` | cada `apply` cria um API Gateway novo; sem isso são dois cliques manuais por sessão, até a T10 |
| `github/auth.py` | **só o JWT do App** nesta tarefa | o token de instalação só dá para exercitar de verdade na T8, quando alguém baixar um tarball com ele |
| Log | `retention_in_days = 1` | regra de custo do projeto; `0` significa "para sempre" |
| Log de acesso do API Gateway | **não** | custa CloudWatch e não responde nada que o log da Lambda não responda |

**Arquivos:**
- Criar: `app/src/pra/config.py`
- Criar: `app/src/pra/webhook/{__init__,assinatura,handler}.py`
- Criar: `app/src/pra/github/{__init__,auth}.py`
- Criar: `app/tests/{test_assinatura,test_webhook,test_auth}.py`
- Criar: `scripts/atualizar_webhook.py`
- Criar: `infra/modules/funcoes/{main,variables,outputs}.tf`
- Modificar: `infra/main.tf`, `infra/variables.tf`, `infra/outputs.tf`,
  `infra/terraform.tfvars.example`, `Makefile`

**Interfaces:**
- Consome: `url_fila`, `arn_fila` (T6)
- Produz: `conferir_assinatura(corpo, cabecalho, segredo) -> bool`,
  `webhook.handler.lambda_handler`, `github.auth.jwt_do_app(app_id, chave_pem) -> str`,
  e o output `url_webhook`

### Passo 1 — Credenciais da AWS

Usuário IAM comum, **não** a root. Chave de acesso, e então:

```bash
aws configure
aws sts get-caller-identity     # tem que responder com o ID da conta
```

### Passo 2 — Criar o GitHub App (navegador)

Em **Settings → Developer settings → GitHub Apps → New GitHub App**:

| Campo | Valor |
|---|---|
| Nome | `pra` |
| Homepage | qualquer URL sua |
| Webhook | **Active**, URL `https://exemplo.invalido/placeholder` |
| Webhook secret | `openssl rand -hex 32`, e **guarde** |
| Permissões → Repository → Checks | Read and write |
| Permissões → Repository → Contents | Read-only |
| Permissões → Repository → Pull requests | Read-only |
| Eventos | `Pull request`, `Push` |
| Onde pode ser instalado | Only on this account |

> **Por que uma URL de mentira em vez de deixar em branco:** com o webhook ativo o GitHub exige
> uma URL. O placeholder é substituído pelo `make url-webhook` no passo 10 — é justamente para
> isso que a automação existe.

Depois: **Generate a private key** (baixa um `.pem`) e anote o **App ID**. Instale o App no
`gabhrielv/hoppr`. **Não** ative proteção de branch — isso é a T10.

### Passo 3 — Guardar os dois segredos no SSM

```bash
aws ssm put-parameter --name /pra/github/segredo-webhook \
  --type SecureString --value "SEGREDO_QUE_VOCE_GEROU"

aws ssm put-parameter --name /pra/github/chave-privada \
  --type SecureString --value "$(cat ~/Downloads/pra.*.private-key.pem)"

shred -u ~/Downloads/pra.*.private-key.pem
```

> **Por que na mão e não em Terraform:** um `aws_ssm_parameter` com o valor guardaria o segredo
> em texto puro dentro do `terraform.tfstate` — que agora vive num bucket. Segredo em arquivo é
> exatamente o que a G2 proíbe. O Terraform só ganha permissão de **ler** o parâmetro, por ARN.
> Efeito colateral bom: os segredos sobrevivem ao `destroy`, então não se recria o App a cada
> sessão. Efeito colateral ruim: parâmetro ausente só aparece em tempo de execução — por isso o
> `make url-webhook` roda logo depois do apply, ele é o primeiro a tocar na chave privada.

Parâmetro padrão do SSM é grátis (o tipo *advanced* custa US$0,05/mês cada) e `SecureString` usa
a chave gerenciada `aws/ssm`, também grátis — chave própria do KMS custaria US$1/mês.

### Passo 4 — HMAC, teste primeiro

`app/tests/test_assinatura.py` cobre: assinatura válida passa; assinatura de outro segredo
falha; corpo alterado falha; cabeçalho ausente falha; cabeçalho sem o prefixo `sha256=` falha;
cabeçalho com lixo falha sem explodir.

`app/src/pra/webhook/assinatura.py` usa `hmac.compare_digest` — comparar com `==` vaza, pelo
tempo de resposta, quantos bytes iniciais o atacante acertou.

### Passo 5 — `config.py` e o handler, teste primeiro

`app/tests/test_webhook.py` cobre o que tem lógica de verdade:

- assinatura inválida → **401**, e **nada** é enfileirado;
- corpo em base64 (`isBase64Encoded: true`) com assinatura válida → enfileira;
- `ping` → 200 `pong`;
- evento fora de `{pull_request, push}` → 200, nada enfileirado;
- `pull_request` com ação `closed` → nada; com `opened`/`synchronize`/`reopened` → enfileira;
- `push` em branch que não é a padrão → nada;
- `push` com `deleted: true` → nada;
- o corpo da mensagem enfileirada tem `owner`, `repo`, `head_sha`, `base_sha`, `evento` e
  `numero_pr`.

> 🔴 **`isBase64Encoded` é o detalhe que faz o portão nunca disparar.** O API Gateway pode
> entregar o corpo codificado em base64. O HMAC do GitHub é calculado sobre os **bytes
> originais**; assinar a string base64 faz **toda** requisição legítima devolver 401, e nenhuma
> análise acontece. Decodificar antes de conferir é obrigatório.

```python
corpo_bruto = evento_lambda.get("body") or ""
if evento_lambda.get("isBase64Encoded"):
    corpo = base64.b64decode(corpo_bruto)
else:
    corpo = corpo_bruto.encode()
```

O cliente do SQS é criado no módulo e trocado por um dublê nos testes; o segredo vem de
`config.parametro_ssm`, com `@cache` para não pagar uma chamada por invocação — o cache vive
enquanto o container da Lambda vive, e o segredo não muda.

### Passo 6 — `github/auth.py`, teste primeiro

`app/tests/test_auth.py` gera um par de chaves RSA no próprio teste, chama `jwt_do_app` e
**decodifica de volta** para conferir os claims. Sem rede.

| claim | valor | por quê |
|---|---|---|
| `iss` | o App ID | é assim que o GitHub sabe qual chave pública usar |
| `iat` | agora **menos 60 s** | relógio da Lambda adiantado faria o GitHub recusar por "emitido no futuro" |
| `exp` | no máximo `iat + 600` | teto do GitHub; passar disso é recusado |

### Passo 7 — `scripts/atualizar_webhook.py` e `make url-webhook`

Fica em `scripts/` e **não** dentro do pacote: é ferramenta de operação, não código que roda em
Lambda nenhuma — não faz sentido no zip.

```
terraform output url_webhook
      ↓
chave privada do SSM  →  jwt_do_app()  →  PATCH /app/hook/config  {"url": ...}
```

```makefile
url-webhook:
	$(PY) scripts/atualizar_webhook.py \
	  --app-id $$(cd infra && $(TF) output -raw github_app_id) \
	  --url $$(cd infra && $(TF) output -raw url_webhook)
```

**Critério de aceite:** o script responde 200 e a página de configuração do App mostra a URL
nova. Ele também é o primeiro consumidor da chave privada — se o `.pem` foi colado errado no
SSM, é aqui que se descobre, e não na T9.

### Passo 8 — `infra/modules/funcoes/`

Só a Lambda do webhook por enquanto; as outras entram em T8/T9/T10, no mesmo módulo e no mesmo
zip. As variáveis das tarefas seguintes já são declaradas para não mexer no wiring depois —
**menos as de ECS** (`nome_cluster`, `arn_task_definition`), que morreram com a troca de Fargate
por Lambda.

Política de IAM escrita na mão, não gerenciada: `sqs:SendMessage` **naquela** fila,
`ssm:GetParameter` em `/pra/github/*`, e os três verbos de log. Mais nada.

```hcl
resource "aws_lambda_function" "webhook" {
  function_name = "${var.prefixo}-webhook"
  role          = aws_iam_role.webhook.arn
  handler       = "pra.webhook.handler.lambda_handler"
  runtime       = "python3.12"
  filename      = var.caminho_zip
  # Sem isto o Terraform não percebe que o código mudou e não redeploya.
  source_code_hash = filebase64sha256(var.caminho_zip)
  timeout          = 10   # o GitHub desiste em ~10 s (§6)
  memory_size      = 256  # não é por CPU, é por cold start caber nos 10 s

  # Teto de rajada: o excedente é recusado em vez de virar fatura. Webhook
  # recusado não é reenviado pelo GitHub, então a análise não acontece — e o
  # Check Run nunca reporta, o que mantém o merge travado. Falha fechada.
  reserved_concurrent_executions = 5

  environment {
    variables = {
      PRA_FILA_URL              = var.url_fila
      PRA_PARAM_SEGREDO_WEBHOOK = "/pra/github/segredo-webhook"
    }
  }
}

resource "aws_apigatewayv2_stage" "padrao" {
  api_id      = aws_apigatewayv2_api.principal.id
  name        = "$default"
  auto_deploy = true

  # Recusa na porta, antes de a Lambda existir. O padrão da conta é 10.000/s.
  default_route_settings {
    throttling_rate_limit  = 10
    throttling_burst_limit = 20
  }
}
```

O grupo de log é declarado explicitamente com `retention_in_days = 1`, e a política **não** dá
`logs:CreateLogGroup`: quem cria é o Terraform, com retenção definida. Se a Lambda pudesse
criar, criaria com retenção infinita no dia em que alguém apagasse o grupo. O `depends_on`
garante a ordem — Lambda invocada antes do grupo existir cria ele sozinha, e o `apply` seguinte
falha com "already exists".

> ⚠️ **Se o `apply` falhar com `below its minimum value of [100]`:** conta nova da AWS às vezes
> vem com limite de concorrência de 10 em vez de 1000, e aí **qualquer** reserva é recusada — a
> AWS exige deixar 100 execuções sem reservar. A variável `concorrencia_webhook` existe para
> isso: `-1` desliga a reserva e mantém o resto de pé. O throttle do API Gateway continua
> valendo, então a porta não fica sem trava nenhuma.

### Passo 9 — Wiring e empacotamento

`infra/variables.tf` ganha `github_app_id` (não é segredo — a chave privada é que é);
`infra/outputs.tf` ganha `url_webhook` e `github_app_id`; `infra/terraform.tfvars.example`
ganha a linha correspondente.

O `make pacote-lambda` remove a **árvore inteira** do boto3, não só o pacote de cima
(`botocore`, `s3transfer`, `jmespath`, `dateutil`, `six`, e os `.dist-info` correspondentes).

> **Por que a árvore inteira, e não só `boto3/`:** dentro da Lambda, `/var/task` (o seu zip)
> vem **antes** de `/var/runtime` no `sys.path`. Um `jmespath` ou `dateutil` solto no zip seria
> carregado pelo boto3 do runtime, possivelmente numa versão diferente da que ele espera —
> um bug que só aparece em produção. Remover tudo deixa o runtime usar as cópias dele,
> coerentes entre si.

Medido em 13/08/2026: **6,5 MB** compactado, 22 MB descompactado — teto da AWS é 50 MB e
250 MB. O binário nativo do `cryptography` sai como `cp312-x86_64-linux`, que casa com o
runtime `python3.12`; construir num host de outra arquitetura quebraria isso em silêncio.

**Verificação sem AWS**, antes de qualquer apply:

```bash
PYTHONPATH=build/lambda python -c "import pra.webhook.handler"
```

Se o layout do zip estiver errado, falha aqui — e não com `Unable to import module` no
CloudWatch, que é onde esse erro normalmente aparece.

### Passo 10 — Subir e provar

```bash
make pacote-lambda
cd infra && terraform apply
make url-webhook          # conserta a URL no GitHub App
```

O GitHub manda um `ping` assim que a URL muda. Depois abra um PR de teste no `hoppr`.

**Critério de aceite — os quatro:**

```bash
# 1. o evento chegou e foi enfileirado
aws logs tail /aws/lambda/pra-webhook --since 5m

# 2. a mensagem está na fila
aws sqs get-queue-attributes --attribute-names ApproximateNumberOfMessages \
  --queue-url $(cd infra && terraform output -raw url_fila)

# 3. assinatura é conferida de verdade
curl -si -X POST "$(cd infra && terraform output -raw url_webhook)" \
  -H "X-GitHub-Event: push" -d '{"malicioso":true}' | head -1
# esperado: HTTP/2 401

# 4. o state está no bucket, não no disco
aws s3 ls s3://pra-tfstate-$(aws sts get-caller-identity --query Account --output text)/marco-1/
```

### Passo 11 — Commits

Pequenos, na ordem em que foram construídos: assinatura → config e handler → JWT → script e
Makefile → Terraform.

---

## Tarefa 8 — A buscadora e o Fargate (§8 passo 6)

> ⚠️ **Desatualizada.** Esta tarefa está escrita para ECS Fargate. A decisão de 12/08/2026
> trocou o analisador por uma **Lambda com imagem de container**, dentro da VPC. Some daqui:
> cluster ECS, task definition, execution role, task role, `iam:PassRole` e IP público. Entra:
> ECR com política de ciclo de vida guardando 1 imagem, `lambda:InvokeFunction` assíncrono,
> `reserved_concurrent_executions = 5` e o limite de 512 MB em `/tmp` (o teto de extração já
> foi ajustado na T4). Será reescrita quando chegar a vez dela, como a T7 foi.

**Arquivos:**
- Criar: `app/src/pra/github/{__init__,auth}.py`
- Criar: `app/src/pra/buscador/{__init__,github_api,handler}.py`
- Criar: `app/tests/test_github_api.py`
- Criar: `infra/modules/analisador/{main,variables,outputs}.tf`
- Modificar: `infra/modules/funcoes/main.tf` (adiciona a Lambda buscadora)

**Interfaces:**
- Consome: `FaixaLinhas`, `Contexto`, `Evento` (T1), `escrever_contexto`, `NOME_CODIGO`,
  `NOME_CONTEXTO` (T4), outputs de T6
- Produz: `token_de_instalacao(app_id, chave_pem, owner, repo) -> str`,
  `baixar_tarball(token, owner, repo, sha) -> bytes`,
  `linhas_tocadas_de_pr(token, owner, repo, numero) -> dict[str, tuple[FaixaLinhas, ...]]`,
  `linhas_tocadas_de_push(token, owner, repo, base, head) -> tuple[dict, bool]`

- [ ] **Passo 1: Escrever o teste que falha (parser de patch)**

O ponto delicado é ler o *unified diff* que o GitHub devolve e extrair as linhas **do arquivo
novo** que foram adicionadas.

```python
# app/tests/test_github_api.py
from pra.buscador.github_api import faixas_de_patch
from pra.modelos import FaixaLinhas

PATCH = """@@ -10,7 +10,9 @@ def buscar(conn, ident):
 def buscar(conn, ident):
-    return conn.execute("SELECT 1")
+    q = "SELECT * FROM users WHERE id = " + ident
+    return conn.execute(q)
 
 def outra():
@@ -40,3 +42,4 @@ def fim():
     pass
+MAIS = 1
"""


def test_extrai_faixas_de_linhas_adicionadas():
    faixas = faixas_de_patch(PATCH)
    assert FaixaLinhas(11, 12) in faixas
    assert FaixaLinhas(45, 45) in faixas


def test_linha_removida_nao_conta():
    # a linha `-` some do arquivo novo; não há o que anotar nela
    faixas = faixas_de_patch("@@ -1,2 +1,1 @@\n-antigo\n contexto\n")
    assert faixas == ()


def test_patch_vazio_devolve_vazio():
    assert faixas_de_patch("") == ()


def test_faixas_adjacentes_sao_unidas():
    faixas = faixas_de_patch("@@ -1,0 +1,3 @@\n+a\n+b\n+c\n")
    assert faixas == (FaixaLinhas(1, 3),)
```

- [ ] **Passo 2: Rodar e confirmar que falha**

```
cd app && python -m pytest tests/test_github_api.py -v
```

- [ ] **Passo 3: Escrever `app/src/pra/github/auth.py`**

```python
"""Chave privada do App -> token de instalação.

O token dura 1 hora e vale só pra instalação que o pediu. Quem o carrega são
as Lambdas — o container NUNCA vê esse valor (D14).
"""

from __future__ import annotations

import time

import jwt
import requests

API = "https://api.github.com"
TEMPO_LIMITE = 30


def _jwt_do_app(app_id: str, chave_pem: str) -> str:
    agora = int(time.time())
    payload = {"iat": agora - 60, "exp": agora + 540, "iss": app_id}
    return jwt.encode(payload, chave_pem, algorithm="RS256")


def token_de_instalacao(app_id: str, chave_pem: str, owner: str, repo: str) -> str:
    cabecalhos = {
        "Authorization": f"Bearer {_jwt_do_app(app_id, chave_pem)}",
        "Accept": "application/vnd.github+json",
    }

    instalacao = requests.get(
        f"{API}/repos/{owner}/{repo}/installation",
        headers=cabecalhos,
        timeout=TEMPO_LIMITE,
    )
    instalacao.raise_for_status()
    id_instalacao = instalacao.json()["id"]

    token = requests.post(
        f"{API}/app/installations/{id_instalacao}/access_tokens",
        headers=cabecalhos,
        timeout=TEMPO_LIMITE,
    )
    token.raise_for_status()
    return token.json()["token"]
```

- [ ] **Passo 4: Escrever `app/src/pra/buscador/github_api.py`**

```python
"""Busca o código e o diff. É o único lugar do sistema que fala com o GitHub
para LER repositório.

Tarball em vez de clone: é um download HTTPS comum, então uma Lambda dá conta
sem ter `git` instalado (D14). O preço é não ter histórico — decidido e
registrado em D14d.
"""

from __future__ import annotations

import re

import requests

from pra.modelos import FaixaLinhas

API = "https://api.github.com"
TEMPO_LIMITE = 60

CABECALHO_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _cabecalhos(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def faixas_de_patch(patch: str) -> tuple[FaixaLinhas, ...]:
    """Extrai as faixas de linha ADICIONADAS, numeradas no arquivo novo."""
    linhas_adicionadas: list[int] = []
    linha_atual = 0

    for linha in patch.splitlines():
        cabecalho = CABECALHO_HUNK.match(linha)
        if cabecalho:
            linha_atual = int(cabecalho.group(1))
            continue
        if linha.startswith("+"):
            linhas_adicionadas.append(linha_atual)
            linha_atual += 1
        elif linha.startswith("-"):
            continue  # some do arquivo novo
        else:
            linha_atual += 1

    if not linhas_adicionadas:
        return ()

    faixas: list[FaixaLinhas] = []
    inicio = anterior = linhas_adicionadas[0]
    for numero in linhas_adicionadas[1:]:
        if numero == anterior + 1:
            anterior = numero
            continue
        faixas.append(FaixaLinhas(inicio, anterior))
        inicio = anterior = numero
    faixas.append(FaixaLinhas(inicio, anterior))
    return tuple(faixas)


def _mapear_arquivos(arquivos: list[dict]) -> dict[str, tuple[FaixaLinhas, ...]]:
    mapa: dict[str, tuple[FaixaLinhas, ...]] = {}
    for arquivo in arquivos:
        patch = arquivo.get("patch")
        if not patch:
            continue  # binário ou grande demais; o GitHub omite
        faixas = faixas_de_patch(patch)
        if faixas:
            mapa[arquivo["filename"]] = faixas
    return mapa


def linhas_tocadas_de_pr(
    token: str, owner: str, repo: str, numero: int
) -> dict[str, tuple[FaixaLinhas, ...]]:
    arquivos: list[dict] = []
    pagina = 1
    while True:
        resposta = requests.get(
            f"{API}/repos/{owner}/{repo}/pulls/{numero}/files",
            headers=_cabecalhos(token),
            params={"per_page": 100, "page": pagina},
            timeout=TEMPO_LIMITE,
        )
        resposta.raise_for_status()
        lote = resposta.json()
        arquivos.extend(lote)
        if len(lote) < 100:
            break
        pagina += 1
    return _mapear_arquivos(arquivos)


def linhas_tocadas_de_push(
    token: str, owner: str, repo: str, base: str, head: str
) -> tuple[dict[str, tuple[FaixaLinhas, ...]], bool]:
    """Devolve (mapa, tudo_novo).

    `tudo_novo=True` quando não dá pra calcular o diff — branch nova (base
    zerada) ou force push. Aí todo achado conta como novo e o portão erra pro
    lado de bloquear, coerente com o fail-closed da §4.
    """
    if not base or set(base) == {"0"}:
        return {}, True

    resposta = requests.get(
        f"{API}/repos/{owner}/{repo}/compare/{base}...{head}",
        headers=_cabecalhos(token),
        timeout=TEMPO_LIMITE,
    )
    if resposta.status_code == 404:
        return {}, True
    resposta.raise_for_status()
    return _mapear_arquivos(resposta.json().get("files", [])), False


def baixar_tarball(token: str, owner: str, repo: str, sha: str) -> bytes:
    resposta = requests.get(
        f"{API}/repos/{owner}/{repo}/tarball/{sha}",
        headers=_cabecalhos(token),
        timeout=TEMPO_LIMITE,
        allow_redirects=True,  # o endpoint responde 302 pra uma URL assinada
    )
    resposta.raise_for_status()
    return resposta.content
```

- [ ] **Passo 5: Rodar e confirmar que passa**

```
cd app && python -m pytest tests/test_github_api.py -v
```
Esperado: 4 passed

- [ ] **Passo 6: Escrever `app/src/pra/buscador/handler.py`**

```python
"""Lambda buscadora: SQS -> pacote no S3 -> ecs:RunTask.

Esta função TEM o token do GitHub e NÃO lê o código que baixa. O container
lê o código e NÃO tem o token. Essa é a separação de privilégio da D14 — se
alguém juntar as duas responsabilidades aqui, a defesa some.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import boto3

from pra.analisador.pacote import NOME_CODIGO, NOME_CONTEXTO, escrever_contexto
from pra.buscador.github_api import (
    baixar_tarball,
    linhas_tocadas_de_pr,
    linhas_tocadas_de_push,
)
from pra.config import obrigatoria, parametro_ssm
from pra.github.auth import token_de_instalacao
from pra.modelos import Contexto, Evento

s3 = boto3.client("s3")
ecs = boto3.client("ecs")


def _prefixo(trabalho: dict) -> str:
    return f"entrada/{trabalho['owner']}/{trabalho['repo']}/{trabalho['head_sha']}"


def _montar_contexto(trabalho: dict, token: str) -> Contexto:
    if trabalho["evento"] == "pull_request":
        tocadas = linhas_tocadas_de_pr(
            token, trabalho["owner"], trabalho["repo"], trabalho["numero_pr"]
        )
        tudo_novo = False
    else:
        tocadas, tudo_novo = linhas_tocadas_de_push(
            token,
            trabalho["owner"],
            trabalho["repo"],
            trabalho["base_sha"],
            trabalho["head_sha"],
        )

    return Contexto(
        owner=trabalho["owner"],
        repo=trabalho["repo"],
        head_sha=trabalho["head_sha"],
        evento=Evento(trabalho["evento"]),
        linhas_tocadas=tocadas,
        numero_pr=trabalho.get("numero_pr"),
        base_sha=trabalho.get("base_sha"),
        tudo_novo=tudo_novo,
    )


def _processar(trabalho: dict) -> None:
    bucket = obrigatoria("PRA_BUCKET_PACOTES")
    prefixo = _prefixo(trabalho)

    token = token_de_instalacao(
        obrigatoria("PRA_GITHUB_APP_ID"),
        parametro_ssm(obrigatoria("PRA_PARAM_CHAVE_APP")),
        trabalho["owner"],
        trabalho["repo"],
    )

    tarball = baixar_tarball(
        token, trabalho["owner"], trabalho["repo"], trabalho["head_sha"]
    )
    s3.put_object(Bucket=bucket, Key=f"{prefixo}/{NOME_CODIGO}", Body=tarball)

    contexto = _montar_contexto(trabalho, token)
    with tempfile.TemporaryDirectory() as temporario:
        caminho = Path(temporario) / NOME_CONTEXTO
        escrever_contexto(contexto, caminho)
        s3.upload_file(str(caminho), bucket, f"{prefixo}/{NOME_CONTEXTO}")

    ecs.run_task(
        cluster=obrigatoria("PRA_CLUSTER_ECS"),
        taskDefinition=obrigatoria("PRA_TASK_DEFINITION"),
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": obrigatoria("PRA_SUBNETS").split(","),
                "securityGroups": [obrigatoria("PRA_SECURITY_GROUP")],
                # Subnet pública exige IP público pra alcançar o ECR.
                # Cobrado por hora: ~US$0,0004 por execução de 5 min (§9).
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "analisador",
                    "environment": [
                        {"name": "PRA_BUCKET_PACOTES", "value": bucket},
                        {"name": "PRA_PREFIXO", "value": prefixo},
                    ],
                }
            ]
        },
    )


def lambda_handler(evento_lambda: dict, _contexto) -> dict:
    for registro in evento_lambda["Records"]:
        _processar(json.loads(registro["body"]))
    return {"processados": len(evento_lambda["Records"])}
```

- [ ] **Passo 7: Adaptar o container para ler/escrever no S3**

O `analisar()` continua puro. Um invólucro fino faz a I/O — assim o corpus (D12) chama
`analisar()` direto, sem AWS.

```python
# acrescente ao final de app/src/pra/analisador/main.py

def principal_s3() -> int:
    """Entrada usada no Fargate. O invólucro de I/O fica AQUI, não em analisar()."""
    import os

    import boto3

    from pra.analisador.pacote import NOME_ACHADOS

    s3 = boto3.client("s3")
    bucket = os.environ["PRA_BUCKET_PACOTES"]
    prefixo = os.environ["PRA_PREFIXO"]

    with tempfile.TemporaryDirectory() as temporario:
        entrada = Path(temporario) / "entrada"
        saida = Path(temporario) / "saida"
        entrada.mkdir()
        saida.mkdir()

        for nome in (NOME_CODIGO, NOME_CONTEXTO):
            s3.download_file(bucket, f"{prefixo}/{nome}", str(entrada / nome))

        resultado = analisar(entrada, saida)
        destino = prefixo.replace("entrada/", "saida/", 1)
        s3.upload_file(str(resultado), bucket, f"{destino}/{NOME_ACHADOS}")

    return 0
```

E troque o `ENTRYPOINT` do Dockerfile:

```dockerfile
ENTRYPOINT ["python", "-c", "import sys; from pra.analisador.main import principal_s3; sys.exit(principal_s3())"]
```

> **G6 continua valendo:** `boto3` não é `pra.github` nem `pra.decisao`. O container
> fala com S3, não com GitHub, e não emite veredito. Rode `make teste` pra confirmar que o
> `test_arquitetura.py` continua passando.

- [ ] **Passo 8: Escrever `infra/modules/analisador/main.tf`**

```hcl
variable "prefixo" { type = string }
variable "arn_bucket_pacotes" { type = string }

data "aws_region" "atual" {}
data "aws_caller_identity" "atual" {}

resource "aws_ecr_repository" "analisador" {
  name                 = "${var.prefixo}-analisador"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecs_cluster" "principal" {
  name = "${var.prefixo}-cluster"
}

resource "aws_cloudwatch_log_group" "analisador" {
  name              = "/ecs/${var.prefixo}-analisador"
  retention_in_days = 14
}

# ---------------------------------------------------------------------------
# DUAS roles diferentes. A confusão entre elas é o erro nº 1 de quem começa
# no ECS, e vale entender:
#
#   execution role -> usada pelo AGENTE DO ECS, fora do container. Puxa a
#                     imagem do ECR e manda log pro CloudWatch. O processo
#                     dentro do container NÃO tem essas permissões.
#   task role      -> assumida pelo PROCESSO DENTRO do container. É a que o
#                     boto3 do analisador usa.
#
# É por isso que a §3 pode prometer log sem furar a promessa de privilégio
# mínimo: quem escreve log não é o container.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "execucao" {
  name = "${var.prefixo}-execucao"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execucao" {
  role       = aws_iam_role.execucao.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name = "${var.prefixo}-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# A task role da D14b: lê UM prefixo, escreve OUTRO. Nada além disso.
# Sem ssm:*, sem dynamodb:*, sem sqs:*. Se o analisador precisar de mais
# alguma coisa um dia, isso é sinal de que ele deixou de ser função pura.
resource "aws_iam_role_policy" "task" {
  name = "${var.prefixo}-task"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${var.arn_bucket_pacotes}/entrada/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${var.arn_bucket_pacotes}/saida/*"
      }
    ]
  })
}

resource "aws_ecs_task_definition" "analisador" {
  family                   = "${var.prefixo}-analisador"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.execucao.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "analisador"
      image     = "${aws_ecr_repository.analisador.repository_url}:latest"
      essential = true

      # A imagem é só-leitura; o código descompacta em /tmp, que é o
      # volume efêmero declarado abaixo (§3).
      readonlyRootFilesystem = true
      mountPoints = [{
        sourceVolume  = "temporario"
        containerPath = "/tmp"
        readOnly      = false
      }]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.analisador.name
          "awslogs-region"        = data.aws_region.atual.name
          "awslogs-stream-prefix" = "analisador"
        }
      }
    }
  ])

  volume {
    name = "temporario"
  }
}

output "url_ecr" { value = aws_ecr_repository.analisador.repository_url }
output "nome_cluster" { value = aws_ecs_cluster.principal.name }
output "arn_task_definition" { value = aws_ecs_task_definition.analisador.arn }
output "arn_role_task" { value = aws_iam_role.task.arn }
output "arn_role_execucao" { value = aws_iam_role.execucao.arn }
```

Ligue o módulo em `infra/main.tf`, e passe as saídas dele para o módulo `funcoes`:

```hcl
module "analisador" {
  source             = "./modules/analisador"
  prefixo            = var.prefixo
  arn_bucket_pacotes = module.pacotes.arn_bucket_pacotes
}
```

Acrescente ao bloco `module "funcoes"` que já existe:

```hcl
  nome_cluster        = module.analisador.nome_cluster
  arn_task_definition = module.analisador.arn_task_definition
  ids_subnets         = module.rede.ids_subnets_publicas
  id_security_group   = module.rede.id_sg_analisador
  arn_role_task       = module.analisador.arn_role_task
  arn_role_execucao   = module.analisador.arn_role_execucao
```

E declare as duas novas em `infra/modules/funcoes/variables.tf`:

```hcl
variable "arn_role_task" { type = string }
variable "arn_role_execucao" { type = string }
```

- [ ] **Passo 9: Escrever a Lambda buscadora em `infra/modules/funcoes/main.tf`**

```hcl
resource "aws_iam_role" "buscadora" {
  name = "${var.prefixo}-buscadora"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "buscadora" {
  name = "${var.prefixo}-buscadora"
  role = aws_iam_role.buscadora.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = var.arn_fila
      },
      {
        # Escreve SÓ em entrada/. Não consegue ler nem escrever em saida/ —
        # a buscadora não tem nada a ver com resultado de análise.
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${var.arn_bucket_pacotes}/entrada/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = var.arn_task_definition
      },
      {
        # iam:PassRole é a permissão que quase todo mundo esquece e que
        # produz o AccessDenied mais confuso do ECS. Chamar RunTask entrega
        # duas roles à task; a AWS exige permissão explícita pra "passar"
        # cada uma. O Condition amarra isso ao ECS: mesmo que alguém roube
        # essa credencial, ela não passa role pra mais nada.
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [var.arn_role_task, var.arn_role_execucao]
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${data.aws_region.atual.name}:${data.aws_caller_identity.atual.account_id}:parameter/pra/github/*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${data.aws_region.atual.name}:${data.aws_caller_identity.atual.account_id}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "buscadora" {
  function_name    = "${var.prefixo}-buscadora"
  role             = aws_iam_role.buscadora.arn
  handler          = "pra.buscador.handler.lambda_handler"
  runtime          = "python3.12"
  filename         = var.caminho_zip
  source_code_hash = filebase64sha256(var.caminho_zip)
  timeout          = 120 # baixar tarball + 2 chamadas de API
  memory_size      = 1024

  environment {
    variables = {
      PRA_BUCKET_PACOTES  = var.nome_bucket_pacotes
      PRA_CLUSTER_ECS     = var.nome_cluster
      PRA_TASK_DEFINITION = var.arn_task_definition
      PRA_SUBNETS         = join(",", var.ids_subnets)
      PRA_SECURITY_GROUP  = var.id_security_group
      PRA_GITHUB_APP_ID   = var.github_app_id
      PRA_PARAM_CHAVE_APP = "/pra/github/chave-privada"
    }
  }
}

resource "aws_cloudwatch_log_group" "buscadora" {
  name              = "/aws/lambda/${aws_lambda_function.buscadora.function_name}"
  retention_in_days = 14
}

# batch_size = 1: um PR por invocação. Se um falhar, só ele volta pra fila.
resource "aws_lambda_event_source_mapping" "fila" {
  event_source_arn = var.arn_fila
  function_name    = aws_lambda_function.buscadora.arn
  batch_size       = 1
}
```

> **O `visibility_timeout_seconds = 300` da fila (T6) precisa ser maior que o `timeout = 120`
> da Lambda.** Se for menor, o SQS reentrega a mensagem enquanto a primeira ainda está
> rodando — duas tasks do Fargate pro mesmo PR, duas vezes a conta.

- [ ] **Passo 10: Publicar a imagem e aplicar**

Acrescente ao `Makefile`:

```makefile
publicar-imagem:
	$(eval ECR := $(shell cd infra && terraform output -raw url_ecr))
	aws ecr get-login-password | docker login --username AWS --password-stdin $(ECR)
	docker build -f docker/analisador.Dockerfile -t $(ECR):latest .
	docker push $(ECR):latest
```

```bash
cd infra && terraform apply     # cria o ECR primeiro
make publicar-imagem
cd infra && terraform apply     # agora a task definition acha a imagem
```

- [ ] **Passo 11: Abrir um PR de verdade e conferir**

```bash
aws logs tail /ecs/pra-analisador --follow
```

Abra um PR no `hoppr`. **Critério de aceite:**

```bash
BUCKET=$(cd infra && terraform output -raw nome_bucket_pacotes)
aws s3 ls "s3://$BUCKET/entrada/gabhrielv/hoppr/" --recursive
aws s3 ls "s3://$BUCKET/saida/gabhrielv/hoppr/" --recursive
```

Os dois precisam listar arquivos. Baixe o `achados.json` e confirme `"ok": true`.

**Prova de que a separação de privilégio funciona** — rode dentro da task (ou confie no IAM):
a task role não tem `s3:GetObject` em `saida/*` nem `PutObject` em `entrada/*`. Confirme lendo
a política:

```bash
aws iam get-role-policy --role-name pra-task --policy-name pra-task
```

- [ ] **Passo 12: Commit**

```bash
git add app/src/pra/github/ app/src/pra/buscador/ \
        app/src/pra/analisador/main.py app/tests/test_github_api.py \
        docker/ infra/ Makefile
git commit -m "feat: buscadora monta pacote no S3 e dispara o analisador no Fargate"
```

---

## Tarefa 9 — Publicadora, Check Run e auditoria (§8 passo 7)

**Arquivos:**
- Criar: `app/src/pra/github/checks.py`
- Criar: `app/src/pra/persistencia/{__init__,dynamo}.py`
- Criar: `app/src/pra/publicador/{__init__,handler}.py`
- Criar: `app/tests/test_checks.py`
- Modificar: `infra/modules/funcoes/main.tf`, `infra/modules/pacotes/main.tf`

**Interfaces:**
- Consome: `decidir`, `nao_conclui`, `VERSAO_REGRA` (T2), `Veredito` (T1),
  `token_de_instalacao` (T8), `NOME_ACHADOS` (T4)
- Produz: `montar_saida(veredito) -> dict`, `publicar(...) -> None`,
  `gravar_auditoria(...) -> None`

- [ ] **Passo 1: Escrever o teste que falha**

```python
# app/tests/test_checks.py
from pra.github.checks import LIMITE_ANOTACOES, montar_saida
from pra.modelos import Achado, EstadoVeredito, Severidade, Veredito

VERSAO = "1"


def achado(n: int, severidade=Severidade.ERRO):
    return Achado("r", severidade, f"a{n}.py", n, n, f"achado {n}")


def veredito(bloqueantes=(), avisos=(), preexistentes=(), estado=None, **kw):
    return Veredito(
        estado=estado or (EstadoVeredito.BLOQUEADO if bloqueantes else EstadoVeredito.LIBERADO),
        bloqueantes=bloqueantes,
        avisos=avisos,
        preexistentes=preexistentes,
        versao_regra=VERSAO,
        **kw,
    )


def test_bloqueado_vira_failure():
    saida = montar_saida(veredito(bloqueantes=(achado(1),)))
    assert saida["conclusion"] == "failure"
    assert "1 achado" in saida["output"]["title"]


def test_liberado_vira_success():
    assert montar_saida(veredito())["conclusion"] == "success"


def test_nao_conclui_vira_action_required():
    # D16: distinguir "achei" de "não consegui" muda o comportamento do dev
    v = veredito(estado=EstadoVeredito.NAO_CONCLUI, motivo="semgrep saiu com 2")
    saida = montar_saida(v)
    assert saida["conclusion"] == "action_required"
    assert "semgrep" in saida["output"]["title"]


def test_apenas_achados_novos_viram_anotacao():
    # D16: anotação só renderiza inline em linha do diff. Pré-existente
    # em arquivo não tocado não apareceria — vai pro resumo.
    saida = montar_saida(
        veredito(bloqueantes=(achado(1),), avisos=(achado(2),), preexistentes=(achado(3),))
    )
    caminhos = {a["path"] for a in saida["output"]["annotations"]}
    assert caminhos == {"a1.py", "a2.py"}


def test_niveis_de_anotacao_separam_bloqueante_de_aviso():
    saida = montar_saida(veredito(bloqueantes=(achado(1),), avisos=(achado(2),)))
    niveis = {a["path"]: a["annotation_level"] for a in saida["output"]["annotations"]}
    assert niveis["a1.py"] == "failure"
    assert niveis["a2.py"] == "warning"


def test_trunca_em_cinquenta_e_diz_no_resumo():
    bloqueantes = tuple(achado(n) for n in range(1, 74))
    saida = montar_saida(veredito(bloqueantes=bloqueantes))
    assert len(saida["output"]["annotations"]) == LIMITE_ANOTACOES
    assert "50 de 73" in saida["output"]["summary"]


def test_preexistentes_aparecem_no_resumo():
    saida = montar_saida(veredito(preexistentes=(achado(9),)))
    assert "1 pré-existente" in saida["output"]["summary"]


def test_modo_degradado_aparece_no_titulo():
    saida = montar_saida(veredito(bloqueantes=(achado(1),), degradado=True))
    assert "degradado" in saida["output"]["title"]
```

- [ ] **Passo 2: Rodar e confirmar que falha**

```
cd app && python -m pytest tests/test_checks.py -v
```

- [ ] **Passo 3: Escrever `app/src/pra/github/checks.py`**

```python
"""Traduz um Veredito no corpo de um Check Run. Ver D16.

`montar_saida` é pura — recebe Veredito, devolve dict. Toda a formatação é
testável sem rede, e é por isso que os testes acima não precisam de mock.
"""

from __future__ import annotations

import requests

from pra.modelos import Achado, EstadoVeredito, Veredito

API = "https://api.github.com"
NOME_CHECAGEM = "seguranca/pra"
LIMITE_ANOTACOES = 50  # limite da API por requisição
TEMPO_LIMITE = 30

NIVEL = {"bloqueante": "failure", "aviso": "warning"}

CONCLUSAO = {
    EstadoVeredito.LIBERADO: "success",
    EstadoVeredito.BLOQUEADO: "failure",
    EstadoVeredito.NAO_CONCLUI: "action_required",
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


def _titulo(veredito: Veredito) -> str:
    if veredito.estado is EstadoVeredito.NAO_CONCLUI:
        return f"não conclui: {veredito.motivo}"

    if veredito.bloqueantes:
        quantidade = len(veredito.bloqueantes)
        plural = "s" if quantidade > 1 else ""
        texto = f"{quantidade} achado{plural} novo{plural} bloqueia{'m' if quantidade > 1 else ''}"
    else:
        texto = "nenhum achado novo bloqueia"

    if veredito.degradado:
        texto += " (modo degradado: sem triagem por IA)"
    return texto


def _tabela(achados: tuple[Achado, ...]) -> str:
    linhas = ["| Sev. | Achado | Onde |", "|---|---|---|"]
    for achado in achados:
        linhas.append(
            f"| {achado.severidade.name} | {achado.regra} | "
            f"`{achado.caminho}:{achado.linha_inicio}` |"
        )
    return "\n".join(linhas)


def _resumo(veredito: Veredito, total_anotacoes: int) -> str:
    partes: list[str] = []

    if veredito.bloqueantes:
        partes.append(f"## Bloqueando ({len(veredito.bloqueantes)})\n")
        partes.append(_tabela(veredito.bloqueantes))
    if veredito.avisos:
        partes.append(f"\n## Avisos ({len(veredito.avisos)})\n")
        partes.append(_tabela(veredito.avisos))
    if veredito.preexistentes:
        partes.append(
            f"\n## {len(veredito.preexistentes)} pré-existente"
            f"{'s' if len(veredito.preexistentes) > 1 else ''} — não bloqueia\n"
        )
        partes.append(
            "<details><summary>ver lista</summary>\n\n"
            + _tabela(veredito.preexistentes)
            + "\n</details>"
        )

    novos = len(veredito.bloqueantes) + len(veredito.avisos)
    if novos > total_anotacoes:
        partes.append(
            f"\n> Mostrando {total_anotacoes} de {novos} anotações "
            f"(limite da API do GitHub)."
        )

    partes.append(f"\n`regra v{veredito.versao_regra}`")
    return "\n".join(partes) if partes else "Nenhum achado."


def montar_saida(veredito: Veredito) -> dict:
    anotacoes = [_anotacao(a, NIVEL["bloqueante"]) for a in veredito.bloqueantes]
    anotacoes += [_anotacao(a, NIVEL["aviso"]) for a in veredito.avisos]
    anotacoes = anotacoes[:LIMITE_ANOTACOES]

    return {
        "conclusion": CONCLUSAO[veredito.estado],
        "output": {
            "title": _titulo(veredito),
            "summary": _resumo(veredito, len(anotacoes)),
            "annotations": anotacoes,
        },
    }


def publicar(token: str, owner: str, repo: str, sha: str, veredito: Veredito) -> None:
    corpo = {
        "name": NOME_CHECAGEM,
        "head_sha": sha,
        "status": "completed",
        **montar_saida(veredito),
    }
    resposta = requests.post(
        f"{API}/repos/{owner}/{repo}/check-runs",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json=corpo,
        timeout=TEMPO_LIMITE,
    )
    resposta.raise_for_status()
```

- [ ] **Passo 4: Rodar e confirmar que passa**

```
cd app && python -m pytest tests/test_checks.py -v
```
Esperado: 8 passed

- [ ] **Passo 5: Escrever `app/src/pra/persistencia/dynamo.py`**

```python
"""Registro de auditoria imutável. Ver D11.

Precisa responder: "por que esse deploy passou no dia 14?".
"""

from __future__ import annotations

from datetime import datetime, timezone

import boto3

from pra.modelos import Achado, Veredito

dynamo = boto3.resource("dynamodb")


def _serializar(achado: Achado) -> dict:
    return {
        "regra": achado.regra,
        "severidade": achado.severidade.value,
        "caminho": achado.caminho,
        "linha_inicio": achado.linha_inicio,
        "linha_fim": achado.linha_fim,
    }


def gravar_auditoria(
    tabela: str, owner: str, repo: str, sha: str, veredito: Veredito
) -> None:
    dynamo.Table(tabela).put_item(
        Item={
            "repo": f"{owner}#{repo}",
            "sha": sha,
            "veredito": veredito.estado.value,
            "versao_regra": veredito.versao_regra,
            "degradado": veredito.degradado,
            "motivo": veredito.motivo,
            "bloqueantes": [_serializar(a) for a in veredito.bloqueantes],
            "avisos": [_serializar(a) for a in veredito.avisos],
            "preexistentes": [_serializar(a) for a in veredito.preexistentes],
            "horario": datetime.now(timezone.utc).isoformat(),
        }
    )
```

- [ ] **Passo 6: Escrever `app/src/pra/publicador/handler.py`**

```python
"""Lambda publicadora: evento do S3 -> regra -> Check Run + auditoria.

A REGRA MORA AQUI, não no container. O container produz evidência; quem
julga é quem publica (D14). No marco 2 o agente entra entre os dois.
"""

from __future__ import annotations

import json
import urllib.parse

import boto3

from pra.config import obrigatoria, parametro_ssm
from pra.decisao.regra import decidir, nao_conclui
from pra.github.auth import token_de_instalacao
from pra.github.checks import publicar
from pra.modelos import Achado, Contexto, Evento, FaixaLinhas, Severidade
from pra.persistencia.dynamo import gravar_auditoria

s3 = boto3.client("s3")


def _achado_de(dados: dict) -> Achado:
    return Achado(
        regra=dados["regra"],
        severidade=Severidade(dados["severidade"]),
        caminho=dados["caminho"],
        linha_inicio=dados["linha_inicio"],
        linha_fim=dados["linha_fim"],
        mensagem=dados["mensagem"],
    )


def _contexto_do_pacote(bucket: str, prefixo_entrada: str) -> Contexto:
    objeto = s3.get_object(Bucket=bucket, Key=f"{prefixo_entrada}/contexto.json")
    dados = json.loads(objeto["Body"].read())
    return Contexto(
        owner=dados["owner"],
        repo=dados["repo"],
        head_sha=dados["head_sha"],
        evento=Evento(dados["evento"]),
        linhas_tocadas={
            arquivo: tuple(FaixaLinhas(i, f) for i, f in faixas)
            for arquivo, faixas in dados["linhas_tocadas"].items()
        },
        numero_pr=dados.get("numero_pr"),
        base_sha=dados.get("base_sha"),
        tudo_novo=dados.get("tudo_novo", False),
    )


def _processar(bucket: str, chave: str) -> None:
    prefixo_saida = chave.rsplit("/", 1)[0]
    prefixo_entrada = prefixo_saida.replace("saida/", "entrada/", 1)

    resultado = json.loads(
        s3.get_object(Bucket=bucket, Key=chave)["Body"].read()
    )
    contexto = _contexto_do_pacote(bucket, prefixo_entrada)

    if resultado["ok"]:
        achados = [_achado_de(d) for d in resultado["achados"]]
        veredito = decidir(achados, contexto)
    else:
        veredito = nao_conclui(resultado["erro"])

    token = token_de_instalacao(
        obrigatoria("PRA_GITHUB_APP_ID"),
        parametro_ssm(obrigatoria("PRA_PARAM_CHAVE_APP")),
        contexto.owner,
        contexto.repo,
    )

    publicar(token, contexto.owner, contexto.repo, contexto.head_sha, veredito)
    gravar_auditoria(
        obrigatoria("PRA_TABELA_AUDITORIA"),
        contexto.owner,
        contexto.repo,
        contexto.head_sha,
        veredito,
    )


def lambda_handler(evento_lambda: dict, _contexto) -> dict:
    for registro in evento_lambda["Records"]:
        bucket = registro["s3"]["bucket"]["name"]
        chave = urllib.parse.unquote_plus(registro["s3"]["object"]["key"])
        _processar(bucket, chave)
    return {"processados": len(evento_lambda["Records"])}
```

- [ ] **Passo 7: Ligar a notificação do S3 no Terraform**

> ⚠️ **A notificação vai no `infra/main.tf`, na raiz — NÃO dentro do módulo `pacotes`.**
> Se ela ficasse lá dentro, o módulo `pacotes` precisaria do ARN da publicadora e o módulo
> `funcoes` precisa do ARN do bucket: **ciclo entre módulos**, e o Terraform recusa com
> `Cycle: module.pacotes -> module.funcoes -> module.pacotes`. Na raiz, os dois outputs já
> existem e não há ciclo. Este é o padrão para qualquer ligação bidirecional entre módulos.

Acrescente ao `infra/main.tf`:

```hcl
resource "aws_s3_bucket_notification" "saida" {
  bucket = module.pacotes.nome_bucket_pacotes

  lambda_function {
    lambda_function_arn = module.funcoes.arn_lambda_publicadora
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "saida/"
    filter_suffix       = "achados.json"
  }

  # sem isto, o S3 tenta invocar antes de a permissão existir e o apply falha
  depends_on = [module.funcoes]
}
```

> **O filtro por prefixo é o que impede o loop infinito:** sem `filter_prefix = "saida/"`, o
> `put_object` que a buscadora faz em `entrada/` dispararia a publicadora, que não teria
> resultado pra ler. Com dezenas de invocações por PR. É o erro clássico de notificação de S3.

E a Lambda publicadora em `infra/modules/funcoes/main.tf`:

```hcl
resource "aws_iam_role" "publicadora" {
  name = "${var.prefixo}-publicadora"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_lambda_function" "publicadora" {
  function_name    = "${var.prefixo}-publicadora"
  role             = aws_iam_role.publicadora.arn
  handler          = "pra.publicador.handler.lambda_handler"
  runtime          = "python3.12"
  filename         = var.caminho_zip
  source_code_hash = filebase64sha256(var.caminho_zip)
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      PRA_TABELA_AUDITORIA = var.nome_tabela
      PRA_GITHUB_APP_ID    = var.github_app_id
      PRA_PARAM_CHAVE_APP  = "/pra/github/chave-privada"
    }
  }
}

resource "aws_cloudwatch_log_group" "publicadora" {
  name              = "/aws/lambda/${aws_lambda_function.publicadora.function_name}"
  retention_in_days = 14
}

output "arn_lambda_publicadora" { value = aws_lambda_function.publicadora.arn }
```

E a política mínima dela:

```hcl
resource "aws_iam_role_policy" "publicadora" {
  name = "${var.prefixo}-publicadora"
  role = aws_iam_role.publicadora.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${var.arn_bucket_pacotes}/saida/*", "${var.arn_bucket_pacotes}/entrada/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = var.arn_tabela
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${data.aws_region.atual.name}:${data.aws_caller_identity.atual.account_id}:parameter/pra/github/*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${data.aws_region.atual.name}:${data.aws_caller_identity.atual.account_id}:*"
      }
    ]
  })
}

resource "aws_lambda_permission" "s3_publicadora" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.publicadora.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.arn_bucket_pacotes
}
```

> **Repare que a publicadora NÃO tem `dynamodb:UpdateItem` nem `DeleteItem`.** "Registro
> imutável" (D11) não é uma promessa de prosa — é uma política de IAM que só permite
> `PutItem`. Vale mencionar em entrevista.

- [ ] **Passo 8: Aplicar e abrir um PR de verdade**

```bash
make pacote-lambda && cd infra && terraform apply
aws logs tail /aws/lambda/pra-publicadora --follow
```

**Critério de aceite:** abra um PR no `hoppr` e veja, na aba **Checks**, a checagem
`seguranca/pra`. Se o PR tocou uma linha com achado de severidade `ERROR`, ela fica
vermelha e **a anotação aparece na linha, na aba Files changed**.

Confira a auditoria:

```bash
aws dynamodb get-item --table-name pra-auditoria \
  --key '{"repo":{"S":"gabhrielv#hoppr"},"sha":{"S":"SEU_SHA"}}'
```

- [ ] **Passo 9: Commit**

```bash
git add app/src/pra/github/checks.py app/src/pra/persistencia/ \
        app/src/pra/publicador/ app/tests/test_checks.py infra/
git commit -m "feat: publicadora aplica a regra, publica Check Run e grava auditoria"
```

---

## Tarefa 10 — Consulta de veredito e proteção de branch (§8 passo 8)

A tarefa que fecha o marco. **O passo 5 é o que você grava.**

**Arquivos:**
- Criar: `app/src/pra/consulta/{__init__,handler}.py`
- Modificar: `infra/modules/funcoes/main.tf`
- Criar: `README.md`

**Interfaces:**
- Consome: `nome_tabela` (T6), `arn_execucao_api` (T7)
- Produz: rota `GET /veredito/{owner}/{repo}/{sha}`

- [ ] **Passo 1: Escrever `app/src/pra/consulta/handler.py`**

```python
"""GET /veredito/{owner}/{repo}/{sha} — o que o job de deploy consulta.

Fail-closed por construção: SHA sem registro devolve 404. O passo do deploy
falha, e é isso que cobre push direto e bypass de administrador (D10).
"""

from __future__ import annotations

import json

import boto3

from pra.config import obrigatoria

dynamo = boto3.resource("dynamodb")


def lambda_handler(evento_lambda: dict, _contexto) -> dict:
    parametros = evento_lambda.get("pathParameters") or {}
    owner = parametros.get("owner")
    repo = parametros.get("repo")
    sha = parametros.get("sha")

    if not all((owner, repo, sha)):
        return {"statusCode": 400, "body": json.dumps({"erro": "parâmetros faltando"})}

    tabela = dynamo.Table(obrigatoria("PRA_TABELA_AUDITORIA"))
    resposta = tabela.get_item(Key={"repo": f"{owner}#{repo}", "sha": sha})
    item = resposta.get("Item")

    if item is None:
        return {
            "statusCode": 404,
            "body": json.dumps({"veredito": "desconhecido", "liberado": False}),
        }

    liberado = item["veredito"] == "liberado"
    return {
        "statusCode": 200 if liberado else 403,
        "body": json.dumps(
            {
                "veredito": item["veredito"],
                "liberado": liberado,
                "versao_regra": item["versao_regra"],
                "horario": item["horario"],
            }
        ),
    }
```

- [ ] **Passo 2: Adicionar a Lambda e a rota no Terraform**

Acrescente a `infra/modules/funcoes/main.tf`:

```hcl
resource "aws_iam_role" "consulta" {
  name = "${var.prefixo}-consulta"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Esta é a função exposta publicamente na internet. A política é a menor
# de todas de propósito: só LÊ a tabela. Não escreve nada, não fala com o
# GitHub, não lê segredo nenhum.
resource "aws_iam_role_policy" "consulta" {
  name = "${var.prefixo}-consulta"
  role = aws_iam_role.consulta.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = var.arn_tabela
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${data.aws_region.atual.name}:${data.aws_caller_identity.atual.account_id}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "consulta" {
  function_name    = "${var.prefixo}-consulta"
  role             = aws_iam_role.consulta.arn
  handler          = "pra.consulta.handler.lambda_handler"
  runtime          = "python3.12"
  filename         = var.caminho_zip
  source_code_hash = filebase64sha256(var.caminho_zip)
  timeout          = 10
  memory_size      = 256

  environment {
    variables = {
      PRA_TABELA_AUDITORIA = var.nome_tabela
    }
  }
}

resource "aws_cloudwatch_log_group" "consulta" {
  name              = "/aws/lambda/${aws_lambda_function.consulta.function_name}"
  retention_in_days = 14
}

resource "aws_apigatewayv2_integration" "consulta" {
  api_id                 = aws_apigatewayv2_api.principal.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.consulta.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "consulta" {
  api_id    = aws_apigatewayv2_api.principal.id
  route_key = "GET /veredito/{owner}/{repo}/{sha}"
  target    = "integrations/${aws_apigatewayv2_integration.consulta.id}"
}

resource "aws_lambda_permission" "api_consulta" {
  statement_id  = "AllowAPIGatewayInvokeConsulta"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.consulta.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.principal.execution_arn}/*/*"
}

output "url_api" { value = aws_apigatewayv2_stage.padrao.invoke_url }
```

> **A D11 fala em "HTTPS + token" e este endpoint está aberto.** No marco 1 isso é aceitável
> porque a resposta não revela nada além de "liberado/bloqueado" para um SHA que o
> consultante já precisa conhecer. Registre como dívida: o token entra quando o repositório
> alvo deixar de ser só seu. Se quiser fechar já, `aws_apigatewayv2_authorizer` do tipo
> `REQUEST` com uma Lambda que compara um header contra o SSM resolve em ~1 h.

- [ ] **Passo 3: Aplicar e testar a consulta**

Agora sim, acrescente a `infra/outputs.tf`:

```hcl
output "url_api" { value = module.funcoes.url_api }
```

```bash
make pacote-lambda && cd infra && terraform apply
URL=$(terraform output -raw url_api)

# SHA que já foi analisado
curl -i "$URL/veredito/gabhrielv/hoppr/SEU_SHA"

# SHA que nunca existiu -> 404, liberado: false
curl -i "$URL/veredito/gabhrielv/hoppr/0000000000000000000000000000000000000000"
```

**Critério de aceite:** o SHA inexistente devolve **404 com `liberado: false`**. Esse é o
fail-closed da D10 verificável com um comando.

- [ ] **Passo 4: Adicionar o passo de conferência no workflow do `hoppr`**

No repositório `hoppr`, antes do deploy:

```yaml
      - name: Conferir veredito do PRA
        run: |
          resposta=$(curl -s -o corpo.json -w "%{http_code}" \
            "${{ secrets.PRA_URL }}/veredito/${{ github.repository_owner }}/hoppr/${{ github.sha }}")
          cat corpo.json
          if [ "$resposta" != "200" ]; then
            echo "::error::veredito não liberado (HTTP $resposta)"
            exit 1
          fi
```

- [ ] **Passo 5: Ligar a proteção de branch — e gravar**

No `hoppr`, em **Settings → Branches → Add branch protection rule**:

| Campo | Valor |
|---|---|
| Branch name pattern | `main` |
| Require status checks to pass before merging | ✅ |
| Status checks that are required | `seguranca/pra` |

> A checagem só aparece na lista depois de ter rodado **ao menos uma vez** naquele
> repositório. Se não estiver lá, abra um PR qualquer primeiro.

**Grave agora, nesta ordem:**

1. Abra um PR no `hoppr` que introduza uma vulnerabilidade óbvia numa linha nova
2. A checagem aparece como `in_progress`
3. Ela fica vermelha, com a anotação na linha
4. **O botão de merge fica cinza**
5. Corrija a linha e faça push
6. A checagem fica verde e o botão de merge habilita

- [ ] **Passo 6: Verificar o atributo de qualidade "robô fora do ar"**

```bash
# desliga a buscadora: nenhuma análise nova completa
aws lambda put-function-concurrency \
  --function-name pra-buscadora --reserved-concurrent-executions 0
```

Abra um PR. A checagem nunca fica verde e **o merge continua travado**. Isso é a frase da D10
— *"quem bloqueia é o GitHub, não você"* — virando demonstração. Depois:

```bash
aws lambda delete-function-concurrency --function-name pra-buscadora
```

- [ ] **Passo 7: Escrever o `README.md`**

Deve conter, no mínimo:
- o que é, em 3 frases
- o diagrama do fluxo (copie da §7 do `ARQUITETURA.md`)
- **os números medidos**: achados pré-existentes no `hoppr`, tempo de uma análise ponta a
  ponta, custo mensal real da fatura
- a justificativa do egress 443 aberto (ver o aviso da T6 passo 2)
- link para `ARQUITETURA.md` e `docs/justificativas.md`

**G1 vale aqui também:** nenhuma menção a assistente de IA.

- [ ] **Passo 8: Commit e fechamento do marco**

```bash
git add app/src/pra/consulta/ infra/ README.md
git commit -m "feat: consulta de veredito e proteção de branch"
```

**O marco 1 só está fechado com as três coisas (D19):**

- [ ] rodando de verdade — o botão de merge fica cinza num PR real
- [ ] README com os números medidos
- [ ] gravação de 60–90 s

---

## Onde este plano deliberadamente não vai

| Fora de escopo | Onde entra |
|---|---|
| Qualquer chamada a LLM | Marco 2 |
| `ClienteLLM`, agente, ferramentas, orçamento | Marco 2 |
| Corpus de 20 casos | Marco 2 (escrito **antes** do prompt — D12) |
| Step Functions | Marco 3 |
| Checkov, Trivy, gitleaks | Marco 4 |
| `.pra.yml` por repo | Marco 4+ (D18) |
| Modo degradado ligado por cota | Marco 2 (no marco 1 **tudo** é o modo degradado — D17) |

---

## Registro de decisões que este plano tomou

Coisas que o `ARQUITETURA.md` não especificava e que precisaram de uma escolha aqui.
**Se discordar de alguma, é decisão de arquitetura e volta pra discussão.**

| # | Decisão | Motivo |
|---|---|---|
| 1 | `Severidade` usa o vocabulário do Semgrep (`ERROR`/`WARNING`/`INFO`), sem taxonomia própria | Um scanner só. Taxonomia comum nasce no marco 4, quando houver duas escalas pra reconciliar. Mesma lógica de "não existe `scanners/base.py`" (§7) |
| 2 | Só `ERROR` bloqueia no marco 1 | O `hoppr` vai ter `WARNING` demais; bloquear neles faria o portão nascer inútil, que é o que a D15 tenta evitar |
| 3 | `tudo_novo` liga em branch nova e force push | Não dá pra calcular diff; bloquear mais é a direção segura (§4) |
| 4 | Falha do scanner vira `ok:false` no JSON, não exceção | Vira `action_required` (D16) em vez de container morto sem explicação |
| 5 | O S3 dispara a publicadora por notificação de evento, com filtro `saida/` | Sem filtro, a escrita em `entrada/` dispararia a publicadora — loop |
| 6 | A publicadora tem `dynamodb:PutItem` e nada mais | "Registro imutável" (D11) vira política de IAM, não promessa de prosa |
| 7 | Egress 443 aberto no SG do analisador | ECR e CloudWatch Logs não têm prefix list. Alternativa custa ~US$21/mês. **A promessa honesta passa a ser "não tem token", não "não tem rede"** — precisa estar no README |
| 8 | Retenção do bucket = 7 dias | O código não precisa durar; a auditoria (D11) é que dura, e vive no DynamoDB |
