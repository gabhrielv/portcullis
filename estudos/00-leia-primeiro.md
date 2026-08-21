# Estudos — PRA

Material de apoio pra construir o marco 1. **Não é documentação do projeto** — é o que você
precisa entender pra que o `docs/plano-marco-1.md` faça sentido em vez de virar
copiar-e-colar.

> Se um dia versionar isto junto com o repositório, tudo bem — não tem nada aqui que
> comprometa a apresentação. Se preferir manter privado, é só acrescentar `estudos/` ao
> `.gitignore`. **A escolha é sua e nenhum dos dois caminhos é errado.**

---

## Ordem de leitura

| Arquivo | Quando ler | Por quê |
|---|---|---|
| **[04-riscos-e-fixes.md](04-riscos-e-fixes.md)** | **antes de escrever qualquer código** | 8 furos que encontrei revisando o plano. Dois deles fazem o portão **falhar aberto** — deixar passar coisa que deveria bloquear. Ler isso primeiro é o que mais economiza retrabalho |
| [01-conceitos-aws.md](01-conceitos-aws.md) | antes da Tarefa 6 (Terraform) | IAM, VPC, Fargate, Lambda, SQS, S3, DynamoDB, Terraform. Cada conceito amarrado ao lugar exato onde ele aparece no PRA |
| [02-conceitos-seguranca.md](02-conceitos-seguranca.md) | antes da Tarefa 7 (webhook) | HMAC, ataque de temporização, zip-slip, fail-closed, separação de privilégio. É o vocabulário que sustenta a §4 do `ARQUITETURA.md` |
| [03-conceitos-engenharia.md](03-conceitos-engenharia.md) | antes da Tarefa 2 | TDD, função pura, idempotência, entrega ao-menos-uma-vez. Explica *por que* o plano começa pela regra e não pela infra |

---

## As cinco ideias que sustentam o projeto inteiro

Se você esquecer todo o resto, guarde estas. São elas que você defende numa entrevista, e são
elas que fazem o resto das decisões parecerem óbvias em vez de arbitrárias.

### 1. A assimetria dos dois erros

Dizer *"tem problema aqui"* e errar custa **seu tempo**.
Dizer *"não tem problema aqui"* e errar custa **uma vulnerabilidade em produção**.

Como os dois erros não custam igual, eles não podem ter o mesmo peso no sistema. É daí que
sai **tudo**: `nao_sei` bloqueia, o agente não emite veredito, o modo degradado bloqueia mais
e não menos. Não é paranoia — é assimetria de custo virando desenho.

### 2. Quem tem credencial não lê dado hostil

A Lambda buscadora tem o token do GitHub e nunca abre o código.
O container abre o código e não tem token nenhum.

Isso é **separação de privilégio**, e é o mesmo princípio por trás de `sudo`, de sandbox de
navegador e de processos separados em servidor de e-mail. A frase curta: *nenhum componente
acumula "poder de agir" e "exposição a entrada hostil" ao mesmo tempo*.

### 3. Quem bloqueia é o GitHub, não você

O robô só **reporta**. Quem impede o merge é a proteção de branch.

A consequência é a parte bonita: **se o robô cair, nada é liberado por engano**. Você ganha
fail-closed por construção, sem precisar lembrar de implementá-lo. Sistema que falha na
direção segura *por causa de como foi montado* é melhor que sistema que falha na direção
segura *porque alguém escreveu um `if`*.

### 4. A IA não decide nada

O agente preenche um formulário de três campos. Uma função em Python lê o formulário e decide.

Por que isso importa: o texto do PR é controlado por quem quer atravessar o portão. Se o
modelo julgasse, um comentário plantado (*"já revisado pelo time, é falso-positivo"*) viraria
argumento. Como o comentário **não é campo do formulário**, ele não tem por onde entrar.

### 5. Um portão que nasce vermelho é um portão que vai ser desligado

Todo repositório da sua frota tem código escrito antes deste portão existir. Se tudo
bloqueasse, o primeiro PR ficaria vermelho **sem caminho pra ficar verde** — e a única saída
seria desligar a checagem.

Por isso ele é sensível ao diff: bloqueia o que o PR **introduziu**, mostra o resto.
Isso é design de adoção, não de detecção — e é o que separa ferramenta usada de ferramenta
ignorada.

---

## Como estudar sem enrolar

O erro comum é ler tudo antes de escrever a primeira linha. Não faça isso.

```
1. Leia 04-riscos-e-fixes.md inteiro                  (~30 min)
2. Faça as Tarefas 1 e 2 do plano                     (~6 h, zero AWS)
3. Leia 03-conceitos-engenharia.md                    (~20 min)
4. Faça as Tarefas 3, 4 e 5                           (~12 h, ainda zero AWS)
5. AGORA leia 01-conceitos-aws.md inteiro             (~1 h)
6. Faça a Tarefa 6                                    (primeira que gasta dinheiro)
7. Leia 02-conceitos-seguranca.md
8. Tarefas 7 a 10
```

**Metade do marco 1 roda na sua máquina.** Você chega na AWS já com a lógica testada — e aí,
quando algo quebrar, você sabe que é infraestrutura, não código. Isso reduz o espaço de busca
pela metade, que é o motivo real de o plano estar nessa ordem.
