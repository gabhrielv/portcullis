# Conceitos de AWS que o PRA usa

Cada seção tem três partes: **o modelo mental**, **onde aparece no PRA** e **a armadilha**.
A armadilha é a parte que economiza tempo — são os erros que todo mundo comete uma vez.

---

## 1. IAM — permissões

### O modelo mental

Toda decisão do IAM responde a uma frase:

> **Quem** pode fazer **o quê**, em **qual recurso**, sob **qual condição**?

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject"],          // o quê
  "Resource": "arn:aws:s3:::bucket/entrada/*",   // em qual recurso
  "Condition": { ... }                  // sob qual condição
}
```

O "quem" não está aí dentro — está em **onde a política foi anexada**.

Três regras que valem sempre:

1. **Tudo é negado por padrão.** Sem `Allow` explícito, não pode.
2. **`Deny` vence `Allow`.** Sempre, mesmo que o `Allow` seja mais específico.
3. **Permissão não é herdada por "estar dentro".** Uma Lambda dentro da sua conta não ganha
   acesso ao seu bucket por serem seus. Precisa estar escrito.

### Role vs usuário

| | Usuário IAM | Role |
|---|---|---|
| Credencial | fixa, dura pra sempre | temporária, expira em ~1 h |
| Como se obtém | você cria e guarda | o serviço **assume** automaticamente |
| Quando usar | pessoa, ou máquina fora da AWS | **tudo que roda dentro da AWS** |

No PRA, a única credencial fixa que existe é a sua, no `aws configure`. Todo o resto —
Lambdas, task do Fargate — usa role. É por isso que não existe chave de AWS em lugar nenhum
do código.

### As duas políticas de uma role (a confusão nº 1)

Toda role tem **duas** coisas que parecem a mesma e não são:

```hcl
resource "aws_iam_role" "webhook" {
  # POLÍTICA DE CONFIANÇA: QUEM pode virar esta role.
  # Sem isto, a role existe mas ninguém consegue usá-la.
  assume_role_policy = jsonencode({
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }   # <- o "quem"
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "webhook" {
  role = aws_iam_role.webhook.id
  # POLÍTICA DE PERMISSÃO: o que a role PODE FAZER depois de assumida.
  policy = jsonencode({ ... })
}
```

Regra pra decorar: **confiança = porta de entrada. Permissão = o que faz lá dentro.**
`AccessDenied` ao *invocar* costuma ser confiança; `AccessDenied` no meio da execução é
permissão.

### `iam:PassRole` — a permissão que ninguém adivinha

Quando a buscadora chama `ecs:RunTask`, ela está pedindo pra AWS criar uma task que vai rodar
**com outra role** (a task role). Isso exige uma permissão separada:

```hcl
{
  Effect   = "Allow"
  Action   = ["iam:PassRole"]
  Resource = [var.arn_role_task, var.arn_role_execucao]
  Condition = {
    StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
  }
}
```

**Por que existe:** sem `PassRole`, qualquer um que pudesse chamar `RunTask` poderia anexar a
role de administrador à task e escalar privilégio. `PassRole` é o freio contra isso — quem
lança um processo precisa de autorização explícita pra dar cada crachá.

O `Condition` aperta ainda mais: essa permissão só vale pra passar a role **ao ECS**. Mesmo
que a credencial da buscadora vaze, ela não passa role pra mais nada.

> **A armadilha:** `RunTask` sem `PassRole` devolve um `AccessDenied` que fala de `RunTask`, e
> você vai passar meia hora mexendo na permissão errada. Se der `AccessDenied` no `RunTask` e
> a permissão de `RunTask` estiver claramente lá, **a resposta é `PassRole`**.

### Onde aparece no PRA

| Componente | Pode | Não pode (de propósito) |
|---|---|---|
| Lambda webhook | escrever na fila, ler 1 parâmetro do SSM | tocar em S3, DynamoDB, ECS |
| Lambda buscadora | ler da fila, escrever em `entrada/*`, `RunTask`, ler SSM | ler `saida/*`, escrever no DynamoDB |
| **Task do Fargate** | ler `entrada/*`, escrever `saida/*` | **tudo o mais** — sem SSM, sem DynamoDB, sem SQS |
| Lambda publicadora | ler o bucket, `PutItem` no DynamoDB, ler SSM | **`UpdateItem` e `DeleteItem`** |
| Lambda consulta | `GetItem` no DynamoDB | escrever qualquer coisa |

A última linha da publicadora é a mais interessante: *"registro imutável de auditoria"* (D11)
não é uma promessa de prosa — é a **ausência** de `UpdateItem` na política. Ninguém consegue
reescrever a história nem querendo.

---

## 2. VPC — rede

### O modelo mental

Uma VPC é um pedaço de rede privada só sua. Dentro dela:

```
VPC  10.0.0.0/16
 ├── subnet 10.0.0.0/24   ─┐
 ├── subnet 10.0.1.0/24   ─┴─ pedaços da faixa, cada um numa AZ
 │
 ├── tabela de rotas       "pacote pra 0.0.0.0/0 vai por onde?"
 ├── internet gateway      a porta pra internet
 └── security groups       firewall por interface de rede
```

### A definição de "subnet pública" (que ninguém conta)

Não existe caixinha "pública" pra marcar. A regra é:

> **Uma subnet é pública se, e somente se, a tabela de rotas dela tem uma rota
> `0.0.0.0/0 → internet gateway`.** Só isso.

Se você tirar essa rota, a mesma subnet vira privada. Se puser, vira pública. É literalmente
uma linha de tabela de roteamento.

### NAT Gateway — o item de US$32

Uma máquina em subnet **privada** não alcança a internet. Se precisar (baixar pacote, chamar
API), a saída convencional é o NAT Gateway: ele fica na subnet pública e faz a tradução.

```
subnet privada → NAT Gateway (subnet pública) → IGW → internet
```

Custa **~US$32/mês só por existir**, mais US$0,045 por GB. Numa arquitetura pequena, ele é
maior que todo o resto somado — o `ARQUITETURA.md` inteiro é construído pra não precisar dele.

**A escolha do PRA:** Fargate em subnet pública, com security group sem nenhuma regra de
entrada. Ele tem rota pra internet, mas ninguém alcança ele.

### Security group vs NACL

| | Security group | Network ACL |
|---|---|---|
| Onde | na interface de rede | na subnet |
| Estado | **stateful** — resposta volta automática | stateless — precisa de regra nos dois sentidos |
| Regras | só `allow` | `allow` e `deny` |
| Uso normal | sempre | raro |

"Stateful" quer dizer: se você permite a **saída** pra 443, a resposta volta sozinha. Não
precisa de regra de entrada. Muita gente abre entrada sem necessidade por não saber disso.

### Endpoints de VPC — gateway vs interface

Endpoint deixa você alcançar um serviço da AWS sem passar pela internet.

| | Gateway endpoint | Interface endpoint |
|---|---|---|
| Serviços | **só S3 e DynamoDB** | quase todos os outros |
| Como funciona | entrada na tabela de rotas | uma ENI dentro da sua subnet |
| Preço | **grátis** | **~US$7,20/mês por AZ** + por GB |

> 🔴 **A armadilha mais cara do projeto.** No console, criar endpoint de S3 oferece os dois
> tipos. Escolher "Interface" por engano custa ~US$7,20/mês por AZ — mais de 30× a fatura
> inteira do pra. **Se o serviço não é S3 nem DynamoDB, é interface e é pago.**

### Prefix list gerenciada

É uma lista de faixas de IP que a AWS mantém atualizada pra um serviço. Serve pra escrever:

```hcl
resource "aws_vpc_security_group_egress_rule" "s3" {
  prefix_list_id = data.aws_prefix_list.s3.id   # "a S3, seja lá quais IPs forem hoje"
  ip_protocol    = "tcp"
  from_port      = 443
  to_port        = 443
}
```

em vez de listar IPs na mão e ver a regra apodrecer. É o que transforma *"o container só fala
com o S3"* de promessa em configuração conferível.

---

## 3. ECS e Fargate — containers

### O vocabulário

| Termo | O que é | Analogia |
|---|---|---|
| **cluster** | agrupamento lógico (não custa nada) | uma pasta |
| **task definition** | a receita: imagem, CPU, memória, roles | o `docker-compose.yml` |
| **task** | uma execução da receita | o `docker run` |
| **service** | mantém N tasks sempre no ar | o `restart: always` |

O PRA **não usa service** — ele chama `RunTask` sob demanda, a task roda uma vez e morre.
Isso é o certo pra trabalho em lote: você não paga nada entre análises.

### `awsvpc`: uma ENI por task

No Fargate, **cada task ganha uma interface de rede própria**, e todos os containers dentro
dela compartilham essa interface.

> 🔑 **Consequência que decidiu a D14:** não existe "um container com rede e outro sem" na
> mesma task. Isolamento de rede acontece entre *tasks*, nunca entre containers da mesma task.
> Foi esse fato que empurrou o desenho pra Lambda buscadora separada em vez de sidecar.

### As DUAS roles (a confusão nº 2, e é grande)

```
                       ┌──────────────────────────────┐
   execution role ───▶ │  agente do ECS               │
   (fora do container) │  puxa imagem do ECR          │
                       │  manda log pro CloudWatch    │
                       ├──────────────────────────────┤
   task role ────────▶ │  SEU processo                │
   (dentro)            │  o boto3 do analisador       │
                       └──────────────────────────────┘
```

| | Execution role | Task role |
|---|---|---|
| Quem usa | o agente do ECS | seu código |
| Pra quê | puxar imagem, escrever log | o que o app faz |
| No PRA | política gerenciada da AWS | `GetObject` em `entrada/*`, `PutObject` em `saida/*` |

**Por que isso importa aqui:** é o que permite ter log sem furar o privilégio mínimo. O
container tem log no CloudWatch, mas o processo lá dentro **não** tem permissão de escrever
log — quem escreve é o agente, do lado de fora. Detalhe fino e bom de saber explicar.

> **A armadilha:** imagem que não puxa é quase sempre execution role. Código que dá
> `AccessDenied` é quase sempre task role. Errar qual das duas mexer é o passatempo nacional
> de quem começa no ECS.

### Filesystem só-leitura

```json
"readonlyRootFilesystem": true,
"mountPoints": [{ "sourceVolume": "temporario", "containerPath": "/tmp" }]
```

A imagem fica imutável; só `/tmp` é gravável, e some quando a task morre. É onde o tarball
descompacta.

---

## 4. Lambda

### Três formas de invocar — e cada uma tem retry diferente

Esta tabela explica vários comportamentos do PRA que parecem arbitrários:

| Forma | Quem usa aqui | Se falhar |
|---|---|---|
| **Síncrona** | API Gateway → webhook, consulta | **não tenta de novo**; o erro volta pro cliente |
| **Assíncrona** | evento do S3 → publicadora | tenta mais 2× e **descarta em silêncio** |
| **Polling** | SQS → buscadora | volta pra fila até `maxReceiveCount`, depois vai pra DLQ |

> 🔑 É daqui que sai o risco 8 do `04-riscos-e-fixes.md`: a publicadora é assíncrona, então
> falha repetida **some**. Por isso ela precisa de destino de falha explícito.

### Concorrência

- **Reservada** — teto: "no máximo N ao mesmo tempo". Grátis. É o freio de custo do risco 3.
- **Provisionada** — mantém instâncias quentes pra matar cold start. **Custa dinheiro.** Não
  use aqui.

### Cold start

A primeira invocação depois de um tempo parado precisa criar o ambiente e importar o código:
centenas de ms a alguns segundos. Como o PRA roda dezenas de vezes por mês, **quase toda
invocação é fria** — e tudo bem, porque o gargalo é o Fargate, não a Lambda.

### Lambda dentro da VPC

Uma Lambda pode ser posta dentro da VPC. Aí ela alcança recursos privados, mas **perde
internet** a menos que você pague NAT.

> 🔴 A buscadora e a publicadora falam com `github.com`. Se alguém "organizar" a
> infraestrutura colocando tudo dentro da VPC, elas param de funcionar — e o conserto
> aparente (NAT Gateway) custa US$32/mês. **Lambda fora da VPC tem internet de graça.**

---

## 5. SQS — filas

### Para que serve aqui

O GitHub exige resposta em ~10 s. Baixar repositório e rodar scanner leva minutos. A fila
quebra isso em dois: o webhook responde na hora, o trabalho pesado acontece depois.

Mas ela faz uma segunda coisa, tão importante quanto: **absorve rajada**. 20 PRs de uma vez
viram 20 mensagens esperando, não 20 tasks simultâneas — desde que exista teto de
concorrência do outro lado.

### Visibility timeout

Quando um consumidor pega uma mensagem, ela fica **invisível** por um tempo em vez de sumir.
Se o consumidor terminar, ele apaga. Se morrer, a mensagem reaparece e outro pega.

```
visibility timeout (300s)  >  timeout da Lambda (120s)
```

> **A armadilha:** se o visibility timeout for **menor** que o timeout da função, o SQS
> reentrega enquanto a primeira execução ainda roda. Duas tasks do Fargate pro mesmo PR, conta
> dobrada. A AWS recomenda 6× o timeout da função.

### At-least-once

Fila padrão pode entregar a mesma mensagem duas vezes. Não é bug, é o contrato — ver o risco 4.

### Fila de mensagens mortas

```hcl
redrive_policy = jsonencode({
  deadLetterTargetArn = aws_sqs_queue.mortas.arn
  maxReceiveCount     = 3
})
```

Depois de 3 falhas, a mensagem vai pra fila de mortas em vez de ficar em loop eterno.
**Sem isso, uma mensagem venenosa dispara Fargate pra sempre** — é o único jeito de o marco 1
gerar fatura inesperada.

---

## 6. S3

### Prefixo não é pasta

O S3 é um mapa plano de chave → objeto. `entrada/gabhrielv/hoppr/a1b2c3/codigo.tar.gz` é uma
chave só, com barras dentro. As "pastas" que o console mostra são ilusão de interface.

Isso importa porque as políticas de IAM operam sobre o texto da chave:

```
"Resource": "arn:aws:s3:::bucket/entrada/*"
```

É comparação de prefixo, e é por isso que separar `entrada/` de `saida/` dá separação de
privilégio de graça.

### Notificação de evento

O S3 pode invocar uma Lambda quando um objeto é criado. É o que acorda a publicadora.

> 🔴 **A armadilha clássica: o loop.** Sem `filter_prefix`, a escrita da buscadora em
> `entrada/` também dispararia a publicadora. E se a publicadora escrevesse no mesmo bucket,
> seria recursão infinita — o caso mais famoso de conta cara acidental na AWS. **Sempre filtre
> por prefixo ou sufixo.**

### Lifecycle

Apaga objeto sozinho depois de N dias. No PRA o código expira em 7 dias: quem precisa durar
é a auditoria (D11), e ela mora no DynamoDB.

---

## 7. DynamoDB

### Chave

| Parte | Nome | O que faz |
|---|---|---|
| Partition key (PK) | `repo` | decide **em qual partição** o item mora |
| Sort key (SK) | `sha` | **ordena** dentro da partição |

No PRA: `PK = "gabhrielv#hoppr"`, `SK = "a1b2c3"`.

**Por que `owner#repo` e não só `repo`:** a D18 diz multi-repo desde o marco 1. Se a chave
fosse só o SHA, adicionar o segundo repositório exigiria **migrar dados** — e migração de
chave em DynamoDB significa reescrever a tabela inteira. Custo de acertar agora: zero.

### Query vs Scan

- `Query` precisa da PK. Rápido e barato.
- `Scan` lê a tabela inteira. **Nunca** em caminho quente.

O PRA só faz `GetItem` — PK e SK exatas. É o acesso mais barato que existe.

### Single-table design

Guardar tipos diferentes de item na mesma tabela, distinguidos por prefixo na SK:

```
PK = gabhrielv#hoppr   SK = a1b2c3           -> registro de auditoria
PK = gabhrielv#hoppr   SK = lock#a1b2c3      -> trava de deduplicação
```

Parece errado pra quem vem de SQL, mas é o padrão normal em DynamoDB. Aparece no fix do
risco 4.

### Escrita condicional

```python
ConditionExpression="attribute_not_exists(sha)"
```

Escreve **só se** ainda não existir, de forma atômica. É a primitiva que resolve deduplicação
sem race condition.

---

## 8. API Gateway

Duas versões, e você quer a mais nova:

| | HTTP API (v2) | REST API (v1) |
|---|---|---|
| Preço | ~US$1,00 por milhão | ~US$3,50 por milhão |
| Recursos | o essencial | validação de request, chaves de API, cache… |

O PRA usa **HTTP API**: mais barato e suficiente. Em Terraform são os recursos
`aws_apigatewayv2_*`.

`aws_lambda_permission` é obrigatório — ele diz à Lambda que aquele API Gateway pode invocá-la.
Sem isso, a rota existe e devolve 500. É a mesma ideia da política de confiança: a permissão
mora **no lado que recebe**.

---

## 9. Terraform

### Estado

O `terraform.tfstate` é o mapa entre o que você escreveu e o que existe de verdade na AWS.
Perder o estado é perder a capacidade de gerenciar aquilo — o Terraform passa a tentar criar
tudo de novo.

Por isso o estado vai pro S3 com trava assim que der. Enquanto for local, **faça backup**.

### Ciclo entre módulos

O erro que o plano já traz corrigido:

```
module.pacotes  precisa do ARN da Lambda    (que está em funcoes)
module.funcoes  precisa do ARN do bucket    (que está em pacotes)
                    → Cycle: recusa a aplicar
```

**A saída geral:** o recurso que liga os dois vai pro **módulo raiz**, onde os dois outputs já
existem. Vale pra qualquer ligação bidirecional entre módulos, não só esta.

### `depends_on`

O Terraform infere ordem pelas referências. Quando a dependência é real mas **invisível** —
"a permissão precisa existir antes de o S3 tentar invocar" — você declara na mão.

### Data source

`data "aws_prefix_list" "s3"` **lê** algo que já existe em vez de criar. É como você usa
informação da AWS sem chumbar valor no código.

### Drift

Mexeu no console, o mundo real e o estado divergem. `terraform plan` mostra a diferença.
**Regra:** depois que um recurso é do Terraform, não se mexe nele pelo console.

---

## Resumo de custo — o que dói e o que é ruído

| Item | Preço | Aparece quando |
|---|---|---|
| NAT Gateway | **~US$32/mês** | subnet privada precisando de internet |
| Interface endpoint | **~US$7,20/mês por AZ** | endpoint que não seja S3/DynamoDB |
| Secrets Manager | US$0,40 por segredo/mês | usar em vez do SSM Parameter Store |
| IPv4 público em EC2 | US$3,65/mês por IP | máquina ligada o mês inteiro |
| Fargate | US$0,004 por execução de 5 min | por análise |
| Lambda, SQS, gateway endpoint | **US$0** | franquia permanente |

> Os três primeiros, juntos, custam mais de 200× a fatura projetada do PRA inteiro
> (~US$0,22/mês). **Praticamente todo o desenho de rede do projeto existe pra evitar essas
> três linhas.** Se você entender só isso desta página, já entendeu a parte que importa.
