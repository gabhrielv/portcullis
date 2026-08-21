# Riscos e correções — leia antes de escrever código

Oito coisas que encontrei revisando o `docs/plano-marco-1.md`. Estão em ordem de gravidade.

**Os dois primeiros fazem o portão falhar ABERTO** — deixar passar coisa que deveria bloquear.
Isso é pior que qualquer bug de custo, porque não aparece em lugar nenhum: o PR fica verde e
você acha que está tudo bem.

| # | Risco | Tipo | Custo do fix |
|---|---|---|---|
| 1 | Diff truncado pelo GitHub vira "pré-existente" | 🔴 falha aberta | ~20 min |
| 2 | Arquivo sem `patch` vira "pré-existente" | 🔴 falha aberta | ~10 min |
| 3 | Sem teto de concorrência: 20 PRs = 20 tasks | 💸 fatura | ~2 min |
| 4 | SQS entrega ao menos uma vez; análise pode duplicar | 💸 fatura | ~15 min |
| 5 | `--config=auto` precisa de rede e torna o corpus irreprodutível | 🟠 corretude | ~30 min |
| 6 | Tarball inteiro na memória da Lambda | 🟠 quebra em repo grande | ~15 min |
| 7 | Check Run só aparece no fim | 🟡 experiência | ~40 min |
| 8 | Falha da publicadora some em silêncio | 🟡 observabilidade | ~15 min |

---

## 🔴 1. Diff truncado vira "pré-existente" — e não bloqueia

### O problema

`GET /repos/{o}/{r}/pulls/{n}/files` **para em 3.000 arquivos**. É limite da API, não da sua
paginação — passou disso, o GitHub simplesmente não conta o resto.

Agora siga a lógica do plano:

```
arquivo não aparece no diff
   → não está em `linhas_tocadas`
      → `_e_novo()` devolve False
         → classificado como PRÉ-EXISTENTE
            → NÃO BLOQUEIA
```

Um PR gigante — um merge de branch longa, um `npm audit fix` que mexe em tudo, uma
formatação em massa — passa direto. **E é exatamente nesse PR que ninguém vai ler o diff.**

Repare que o erro é na direção errada. A §4 do `ARQUITETURA.md` diz que na dúvida se bloqueia;
aqui a dúvida virou liberação silenciosa.

### O fix

Quando a lista vem truncada, você não sabe quais arquivos ficaram de fora — então a única
resposta honesta é tratar tudo como novo. O campo `tudo_novo` já existe pra isso.

```python
# app/src/pra/buscador/github_api.py

LIMITE_ARQUIVOS_GITHUB = 3000


def linhas_tocadas_de_pr(
    token: str, owner: str, repo: str, numero: int
) -> tuple[dict[str, tuple[FaixaLinhas, ...]], bool]:
    """Devolve (mapa, tudo_novo). O segundo elemento é novo — ver risco 1."""
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
        if len(lote) < 100 or len(arquivos) >= LIMITE_ARQUIVOS_GITHUB:
            break
        pagina += 1

    # O GitHub para em 3000. Se batemos no teto, existem arquivos alterados
    # que não sabemos quais são — e classificá-los como pré-existentes seria
    # falhar ABERTO. Conservador: tudo conta como novo.
    truncado = len(arquivos) >= LIMITE_ARQUIVOS_GITHUB
    return _mapear_arquivos(arquivos), truncado
```

E no `buscador/handler.py`:

```python
    if trabalho["evento"] == "pull_request":
        tocadas, tudo_novo = linhas_tocadas_de_pr(...)
```

### O teste que prova

```python
def test_diff_truncado_marca_tudo_como_novo(monkeypatch):
    # 3000 arquivos = o GitHub parou de contar; não sabemos o que ficou de fora
    ...
    _, tudo_novo = linhas_tocadas_de_pr(token, "o", "r", 1)
    assert tudo_novo is True
```

> **A lição que vale além deste bug:** toda vez que uma API tem limite de paginação, pergunte
> *"o que meu código conclui quando bate no limite?"*. Se a resposta for "conclui a mesma
> coisa que concluiria se não houvesse nada", você tem uma falha aberta esperando escala.

---

## 🔴 2. Arquivo sem `patch` vira "pré-existente"

### O problema

O GitHub **omite o campo `patch`** quando o diff do arquivo é grande demais, ou quando o
arquivo é binário. O código do plano faz:

```python
patch = arquivo.get("patch")
if not patch:
    continue          # ← e aqui o arquivo some do mapa
```

Mesmo desfecho do risco 1: o arquivo **foi alterado**, mas some de `linhas_tocadas`, então
todo achado nele é "pré-existente" e não bloqueia.

Diferença importante em relação ao risco 1: aqui **você sabe o nome do arquivo**. Só não sabe
quais linhas mudaram. Então dá pra ser preciso em vez de conservador com tudo.

### O fix

Se o arquivo mudou mas você não sabe onde, trate o **arquivo inteiro** como tocado. Um único
arquivo vira suspeito, em vez do repositório todo.

```python
# uma faixa que cobre qualquer arquivo real
ARQUIVO_INTEIRO = (FaixaLinhas(1, 1_000_000),)


def _mapear_arquivos(arquivos: list[dict]) -> dict[str, tuple[FaixaLinhas, ...]]:
    mapa: dict[str, tuple[FaixaLinhas, ...]] = {}
    for arquivo in arquivos:
        if arquivo.get("status") == "removed":
            continue  # não existe mais; não há o que anotar

        patch = arquivo.get("patch")
        if not patch:
            # O GitHub omitiu o diff (arquivo grande ou binário). O arquivo
            # MUDOU — só não sabemos onde. Tratar como não-tocado seria falhar
            # aberto, então o arquivo inteiro conta como novo.
            mapa[arquivo["filename"]] = ARQUIVO_INTEIRO
            continue

        faixas = faixas_de_patch(patch)
        if faixas:
            mapa[arquivo["filename"]] = faixas
    return mapa
```

Repare no `status == "removed"`: arquivo apagado não pode ter achado, e mapeá-lo como
"inteiro tocado" só geraria ruído.

---

## 💸 3. Sem teto de concorrência

### O problema

Nada no plano limita quantas análises rodam ao mesmo tempo. Um dia ruim:

```
você faz rebase de 4 branches e força push nas 4
   → 4 eventos
push de 8 commits numa branch com PR aberto
   → 8 eventos `synchronize`, um por push
alguém (você) roda um script que abre 10 PRs
   → 10 eventos
                                    = 22 tasks do Fargate simultâneas
```

O AWS Budgets avisa **depois** que o dinheiro saiu. Ele é alarme de incêndio, não extintor.

### O fix

Uma linha de Terraform. É o seguro mais barato do projeto inteiro:

```hcl
resource "aws_lambda_function" "buscadora" {
  # ...
  # Teto rígido: no máximo 2 análises sendo despachadas ao mesmo tempo.
  # O excedente espera na SQS em vez de virar Fargate — que é justamente
  # pra isso que a fila existe.
  reserved_concurrent_executions = 2
}
```

**Por que isso funciona:** a fila absorve o pico. As mensagens não somem, só esperam. Você
troca latência (um PR pode demorar mais pra ser analisado) por previsibilidade de custo — e
num projeto de portfólio essa troca é obviamente certa.

> **Conceito:** isso se chama *backpressure*. A fila entre o webhook e o trabalho pesado não
> serve só pra responder em 10s ao GitHub — serve pra **absorver rajada**. Um sistema sem
> ponto de backpressure converte todo pico de entrada em pico de custo.

---

## 💸 4. SQS entrega ao menos uma vez

### O problema

Fila SQS padrão é **at-least-once**: a mesma mensagem pode ser entregue duas vezes. Não é
bug, é o contrato do serviço — a garantia de "exatamente uma vez" custa caro e o SQS padrão
não a oferece.

Consequência aqui: duas tasks do Fargate para o mesmo commit, dois `achados.json`, dois
Check Runs. O resultado final é o mesmo (o segundo sobrescreve), mas você pagou duas vezes.

**Antes de consertar, separe dois casos que parecem iguais e não são:**

| Caso | É duplicata? |
|---|---|
| A mesma mensagem entregue 2× pelo SQS | **sim** — mesmo `sha`, trabalho repetido |
| 5 pushes rápidos na branch do PR | **não** — 5 SHAs diferentes, 5 análises legítimas (4 delas ficam obsoletas) |

O segundo caso **não** é problema de idempotência; é volume, e quem resolve é o risco 3.
Não tente consertar os dois com a mesma ferramenta.

### O fix barato (resolve ~90%)

Antes de chamar `RunTask`, veja se o resultado já existe:

```python
def _ja_analisado(bucket: str, prefixo: str) -> bool:
    chave = prefixo.replace("entrada/", "saida/", 1) + "/achados.json"
    try:
        s3.head_object(Bucket=bucket, Key=chave)
        return True
    except s3.exceptions.ClientError:
        return False
```

**Honestidade sobre o limite dele:** existe uma janela entre o `head_object` e o `RunTask` em
que uma segunda entrega passa. Isso se chama *TOCTOU* (*time of check to time of use*) e é a
mesma família de bug de quem escreve `if not os.path.exists(x): criar(x)`. Pra 30 análises por
mês, aceitável — mas saiba que é aceitação, não solução.

### O fix correto

Escrita condicional no DynamoDB. É atômica, então não tem janela:

```python
try:
    tabela.put_item(
        Item={"repo": f"{owner}#{repo}", "sha": f"lock#{sha}"},
        ConditionExpression="attribute_not_exists(sha)",
    )
except tabela.meta.client.exceptions.ConditionalCheckFailedException:
    return  # outro processo já pegou este commit
```

O `sha: lock#{sha}` usa a chave de ordenação pra guardar dois tipos de item na mesma tabela
(`lock#...` e o registro de auditoria). Isso se chama **single-table design** e é o padrão
normal em DynamoDB — parece esquisito vindo de SQL, mas é como se projeta lá.

> **Conceito — idempotência:** uma operação é idempotente quando executá-la duas vezes tem o
> mesmo efeito que executá-la uma. Em sistemas distribuídos você **não escolhe** se vai haver
> repetição; você escolhe se ela dói. Toda vez que você vir "at-least-once" numa
> documentação, a pergunta seguinte é sempre *"qual é a minha chave de deduplicação?"*.
> Aqui ela é óbvia e estável: o SHA do commit.

---

## 🟠 5. `--config=auto` precisa de rede — e destrói a reprodutibilidade do corpus

### O problema

Dois problemas na mesma linha, e o segundo é o pior.

**O operacional:** `--config=auto` faz o Semgrep buscar regras no registry da semgrep.dev em
tempo de execução. No container o egress é restrito, então isso trava ou falha. O plano tenta
contornar aquecendo cache na build (`--dryrun`), o que depende de comportamento não
documentado — vai quebrar numa atualização e você vai perder uma tarde.

**O de corretude, que importa mais:** `auto` significa *"o conjunto de regras que a semgrep.dev
achar melhor hoje"*. Ele muda sem aviso. Aí:

```
segunda:  recall 11/12 no corpus
quinta:   recall 9/12
```

Você mexeu em quê? Em nada. As regras mudaram. **O corpus da D12 deixa de medir o seu agente
e passa a medir o registry.** E o corpus é, segundo o próprio `ARQUITETURA.md`, o artefato
mais valioso do projeto.

### O fix

Congele as regras num arquivo, na build. Aí o container roda offline e o corpus vira
reprodutível.

```dockerfile
# baixa o conjunto de regras UMA vez, na build, e versiona junto com a imagem
RUN curl -sSL https://semgrep.dev/c/p/default -o /opt/pra/regras.yaml
ENV PRA_REGRAS=/opt/pra/regras.yaml
```

```python
comando = [
    "semgrep", "scan",
    f"--config={os.environ['PRA_REGRAS']}",
    "--json", "--quiet", "--metrics=off",
    str(raiz),
]
```

> ⚠️ Confirme a URL e o formato na documentação atual do Semgrep antes de fixar — o endpoint
> de ruleset já mudou de forma no passado. O **princípio** (vendorizar as regras na build) é
> que não muda.

**Ganho de brinde:** a versão das regras passa a fazer parte da imagem. Quando o número do
corpus mudar, você consegue responder *"foi porque atualizei as regras da v1.86 pra v1.90"* —
e isso é exatamente o tipo de rastreabilidade que a D11 quer no registro de auditoria.

---

## 🟠 6. Tarball inteiro na memória da Lambda

### O problema

```python
resposta = requests.get(...)
return resposta.content        # ← repositório inteiro na RAM
```

A Lambda tem 1024 MB. Um repositório que commitou `node_modules`, um `.zip` de assets ou
imagens grandes estoura — e o erro que você vê é a Lambda morrendo sem mensagem útil.

O `hoppr` não tem esse problema hoje. Mas a decisão D2 diz que o portão vai rodar em toda a
frota, e você não controla o que cada repositório commitou no passado.

### O fix

Faça o stream direto pro S3, sem passar pela memória, e recuse o que for absurdo:

```python
LIMITE_TARBALL_BYTES = 500 * 1024 * 1024


class RepositorioGrandeDemais(RuntimeError):
    pass


def tarball_para_s3(token, owner, repo, sha, bucket, chave) -> None:
    with requests.get(
        f"{API}/repos/{owner}/{repo}/tarball/{sha}",
        headers=_cabecalhos(token),
        timeout=TEMPO_LIMITE,
        stream=True,
    ) as resposta:
        resposta.raise_for_status()

        tamanho = int(resposta.headers.get("Content-Length", 0))
        if tamanho > LIMITE_TARBALL_BYTES:
            raise RepositorioGrandeDemais(f"{tamanho} bytes")

        resposta.raw.decode_content = True
        s3.upload_fileobj(resposta.raw, bucket, chave)
```

O `RepositorioGrandeDemais` vira `action_required` no Check Run (D16) — bloqueia, mas dizendo
por quê, em vez de a Lambda morrer em silêncio.

> **Conceito — streaming:** a diferença entre `resposta.content` e `resposta.raw` é a
> diferença entre "carregar tudo e depois processar" e "processar enquanto chega". A segunda
> forma usa memória constante independente do tamanho. Em ambiente com memória limitada e
> entrada de tamanho desconhecido, streaming não é otimização — é requisito.

---

## 🟡 7. O Check Run só aparece no fim

### O problema

O plano cria a checagem **já concluída**, na publicadora. Enquanto a análise roda — o que
pode levar minutos — não existe checagem nenhuma no PR.

Duas consequências:

- **A boa:** proteção de branch com checagem obrigatória que nunca reportou **já bloqueia o
  merge** (aparece como *"Expected — Waiting for status to be reported"*). O fail-closed
  continua de pé.
- **A ruim:** o desenvolvedor não vê nada acontecendo. Sem sinal, ele assume que quebrou.
  E o `ARQUITETURA.md` (D16) promete `in_progress` — então o documento e o código discordam.

### O fix

Quem cria o `in_progress` é a **buscadora**, não o webhook. Motivo: o webhook precisa
responder em 10s (§6) e a buscadora já tem o token do GitHub em mãos.

```python
# no buscador/handler.py, logo depois de obter o token
id_checagem = criar_em_progresso(token, owner, repo, head_sha)
```

Guarde o `id_checagem` no `contexto.json`, e a publicadora faz `PATCH` em vez de `POST`:

```python
requests.patch(
    f"{API}/repos/{owner}/{repo}/check-runs/{id_checagem}",
    headers=..., json=corpo, timeout=TEMPO_LIMITE,
)
```

**Faça isso na Tarefa 9**, não antes — é polimento, e polimento antes de a fatia vertical
fechar é exatamente o que a D9 manda evitar.

---

## 🟡 8. Falha da publicadora some em silêncio

### O problema

S3 → Lambda é invocação **assíncrona**. Se a função falha, a AWS tenta mais 2 vezes e depois
**descarta o evento**. Sem barulho nenhum.

Cenário real: o token expira, a API do GitHub muda, um `KeyError` num campo. Resultado: nenhum
Check Run é publicado. O merge continua travado (fail-closed funcionando), mas você não faz
ideia do motivo, e vai debugar achando que o problema é no Fargate.

### O fix

Fila de mensagens mortas na própria Lambda:

```hcl
resource "aws_sqs_queue" "publicadora_mortas" {
  name = "${var.prefixo}-publicadora-mortas"
}

resource "aws_lambda_function_event_invoke_config" "publicadora" {
  function_name          = aws_lambda_function.publicadora.function_name
  maximum_retry_attempts = 2

  destination_config {
    on_failure {
      destination = aws_sqs_queue.publicadora_mortas.arn
    }
  }
}
```

E um alarme que te avisa quando ela deixa de estar vazia:

```hcl
resource "aws_cloudwatch_metric_alarm" "publicadora_mortas" {
  alarm_name          = "${var.prefixo}-publicadora-mortas"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.publicadora_mortas.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
}
```

> **Conceito — o silêncio é o pior estado.** Um sistema que falha ruidosamente você conserta;
> um que falha em silêncio te ensina a não confiar nele. É a mesma ideia por trás da decisão
> D17 de fazer o modo degradado ser observável: **degradar sem avisar é pior que falhar.**

---

## O que NÃO consertar agora

Tão importante quanto a lista acima. Estas coisas parecem problema e não são — pelo menos não
no marco 1:

| Parece problema | Por que não é agora |
|---|---|
| Task do Fargate sem timeout próprio | O `subprocess.run(timeout=600)` cobre o caso real (Semgrep travado). Timeout de task exige EventBridge + Lambda — cerimônia pra um risco que não se manifestou |
| Endpoint `GET /veredito` sem autenticação | A resposta é "liberado/bloqueado" pra um SHA que quem pergunta já conhece. Vira dívida registrada, não bloqueio |
| Egress 443 aberto no security group | Conhecido, documentado, com as três saídas escritas no plano. Fechar custa ~US$21/mês. **Decisão sua, não bug** |
| Sem cache de camada Docker / imagem grande | Você constrói a imagem umas 10 vezes no marco inteiro |
| Sem retry no `token_de_instalacao` | A SQS já reentrega a mensagem inteira em caso de falha. Retry dentro de retry costuma piorar |
| Sem métricas customizadas no CloudWatch | Entra no marco 2, junto com a contagem de execuções degradadas que a D17 exige |

> **O padrão a reconhecer:** quase todo item dessa segunda tabela é "poderia dar errado". Os
> oito da primeira são "vai dar errado, e do jeito errado". A diferença entre engenharia e
> paranoia é saber em qual das duas listas cada coisa está — e a resposta muda com a escala,
> não com a sua ansiedade.
