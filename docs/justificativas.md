# Justificativas — decisões tomadas depois do ARQUITETURA.md

> Registro corrido do caminho: cada decisão com **as opções que existiam**, o que foi
> escolhido, o porquê e o que custa. Mesmo formato da §5 do `ARQUITETURA.md`.
>
> **`ARQUITETURA.md` é o documento consolidado** — a versão final de cada decisão mora lá.
> Este arquivo guarda o *raciocínio*, inclusive as opções descartadas e as recomendações
> que foram revertidas no meio da discussão. É o que responde "por que não fez do outro
> jeito?" numa entrevista.
>
> Iniciado em 11/08/2026. Cobre até 18/08/2026 — as decisões de mesa (P1 a P6, N1 a N4),
> as que a construção do marco 1 contrariou (P7 a P12) e a revisão do corpus do marco 2
> (P13 a P15).

---

## Estado

### Os 6 pontos abertos da §11

| # | Ponto | Estado |
|---|---|---|
| 1 | Nome do projeto | ✅ **fechado** — `pra` (era `aduana`; revisto em 13/08/2026) |
| 2 | Formato do Check Run / política de achado pré-existente | ✅ **fechado** (P2.1 política + P2.2 formato) |
| 3 | Como o container recebe o repositório | ✅ **fechado — 11/08/2026** |
| 4 | Retry quando o provedor devolve erro de cota | ✅ **fechado** — degrada pro modo marco 1 (o provedor virou Groq na P9) |
| 5 | Cronograma real | ✅ **fechado** — 20 h/semana, sem prazo; marco 1 em ~2–2,5 semanas |
| 6 | Se o marco 4 acontece | ✅ **fechado** — acontece; conteúdo decidido no fim do marco 3, de propósito |

### Decisões que não estavam na §11 e apareceram no caminho

| # | Ponto | Estado |
|---|---|---|
| D2′ | Escopo: uma cobaia → **frota de repos reais** | ✅ fechado — 11/08/2026 |
| N1 | Quanto de multi-repo entra no marco 1 | ✅ multi-repo, política única |
| N2 | Onde mora a config por repo | 🔸 adiada; armadilha (ler da base) já registrada |
| N3 | Cobaia do marco 1 | ✅ `hoppr` |
| N4 | Quem cobre Terraform | ✅ o próprio `pra` (dogfooding), no marco 4 |
| P3.4 | Webhook trata `pull_request` **e** `push` na main | ✅ obrigatório pro desenho da D10 funcionar |
| P3.6 | `historico_git` sai do harness | ✅ vira campo `linha_tocada_por_este_pr` |

### Decisões da execução — apareceram construindo, não planejando

| # | Ponto | Estado |
|---|---|---|
| P7 | Fargate → Lambda com imagem de container | ✅ 12/08 — custo; o isolamento ficou mais forte de brinde |
| P8 | Quais achados bloqueiam | ✅ 12/08 — `VERSAO_REGRA "2"`, resolvido medindo |
| P9 | Cerebras → Groq | ✅ 13/08 — **a aposta errada do projeto**; janela de contexto não estava na tabela |
| P10 | Onde o agente roda | ✅ 13/08 — vira a D20; a rede da T7 saiu mais estrita que o desenho |
| P11 | Teto de gasto sai do Terraform | ✅ 13/08 — sumiria no `destroy`, e a conta só dá dois orçamentos grátis |
| P12 | O que só apareceu rodando | ✅ 14/08 — cache do SSM eterno, segredo truncado, App assinando o evento errado |
| P13 | O corpus antes do prompt cobrou três vezes | ✅ 14–16/08 |
| P14 | Ler o corpus pronto derrubou 4 casos e 2 premissas | ✅ 18/08 — D25 a D28 |
| P15 | O aceite deixa de ser prosa | ✅ 18/08 — inclui um alarme falso meu, registrado |

---

## P3 — Como o container recebe o repositório

### O problema: o documento se contradizia

| Onde | O que dizia |
|---|---|
| §3 (harness) | container *"sem saída de rede, sem credencial da AWS, sem token do GitHub"* |
| §7 (fluxo) | `Fargate analisador → clona, roda Semgrep` |

Clonar do GitHub exige exatamente as duas coisas que o harness proíbe: rota pra internet e
um token. Uma das duas frases tinha que ceder — e é isso que o P3 decide.

Dois fatos que restringiram as opções:

- **No Fargate, todos os containers de uma task compartilham a mesma interface de rede.**
  Não existe sidecar "com rede" ao lado de outro "sem rede" na mesma task. Separação de
  privilégio aqui só acontece entre *processos/tasks diferentes*.
- **A API do GitHub serve o repositório como tarball** (`GET /repos/{owner}/{repo}/tarball/{ref}`):
  é um download HTTPS comum. Quem busca o código **não precisa ter `git` instalado** — o que
  torna viável uma Lambda fazer esse papel.

---

### P3.1 — Por onde o código chega no analisador

| | Como funciona | Ganha | Custa |
|---|---|---|---|
| A | Container clona sozinho: recebe o token de instalação, `git clone --depth 1` direto do github.com, roda Semgrep e publica o Check Run ele mesmo | É o desenho que já estava no §7. 3 Lambdas + 1 container, nada novo. Marco 1 mais curto | O processo que lê código de estranho carrega credencial e tem rota pra internet. A frase de defesa do §3 vira mentira — e é ela que sustenta o discurso de harness |
| **B ✅** | Lambda buscadora baixa `tarball/{sha}` por HTTPS com o token e põe no S3. Fargate lê do S3, descompacta em volume efêmero, roda Semgrep, grava o resultado no S3. Outra Lambda publica o Check Run | Separação de privilégio real: **quem tem token nunca lê código hostil; quem lê código hostil não tem token nem rota pra github.com.** O container vira função pura, testável offline | ~60% mais infra no marco 1: +1 bucket S3, +1 Lambda publicadora, + um caminho de volta que não existia no desenho. ~6–8 h a mais |
| C | Só o diff via `pulls/{n}/files`, sem clone | Nada pra isolar — o problema some por construção. Mais leve | **Mata o marco 2.** O agente não consegue seguir chamador fora do diff, e *"sanitização a distância"* (D12) é justamente o caso difícil que justifica o loop existir |
| D | A no marco 1, migra pra B no marco 2 | Defensável: no marco 1 quem lê o código é o Semgrep, que só parseia AST — sem prompt não existe prompt injection. Marco 1 sai antes | Retrabalho no meio do projeto: task definition, IAM, security group, caminho do código e quem publica o Check Run mudam de lugar justamente quando você está ocupado com o agente |

**✅ Escolhido: B.**

**Porquê:** o §3 é o *conteúdo* do projeto. O objetivo é ter uma frase de defesa pronta pra
cada negativa do harness; se o marco 1 sai com o token dentro do container, essa frase não
existe até o marco 2 — e o marco 1 é o que vai ser gravado primeiro. O custo (bucket +
Lambda + caminho de volta) é infra chata, não infra difícil.

**Consequência que só apareceu no detalhamento:** sem token do GitHub, **o container também
não pode publicar o Check Run**. A publicação migra pra uma Lambda e o container vira
**função pura** — código entra, achados saem. Isso é ganho: é exatamente o passo 3 da §8
(rodar no Docker local) e é o que permite o corpus da D12 rodar offline, sem mock.

**Custo em dinheiro: praticamente zero.** Delta A→B com 30 análises/mês:

| Peça nova | Cobrança | Custo/mês |
|---|---|---|
| S3 — armazenamento (lifecycle de 1 dia, ~5 MB médios) | US$0,023/GB-mês | ~US$0,0001 |
| S3 — requisições (30 PUT + 30 GET) | US$0,005 / 1000 PUT | ~US$0,0002 |
| Transferência S3 ↔ Fargate (mesma região) | grátis | US$0 |
| Lambda buscadora (30 × ~5 s) | franquia **permanente**: 1M req + 400 mil GB-s | US$0 |
| Lambda publicadora (30 × ~1 s) | mesma franquia | US$0 |
| VPC **Gateway** Endpoint pra S3 | gateway endpoint não tem cobrança horária nem por GB | US$0 |
| **Total adicional** | | **< US$0,01** |

O uso fica em ~150 GB-segundos de Lambda contra uma franquia de 400.000. É ruído.
**O custo real de B é tempo (~6–8 h), não fatura.**

#### Três armadilhas de custo que B abre e A não tinha

Todas custam mais que o projeto inteiro. Estão aqui pra não serem redescobertas na fatura.

| Armadilha | Preço do erro | A regra |
|---|---|---|
| Criar **Interface** Endpoint pra S3 em vez de **Gateway** | ~US$7,20/mês por AZ | S3 e DynamoDB são os **únicos dois** serviços com gateway endpoint (grátis). Todo o resto é interface e é pago |
| Pôr a Lambda buscadora **dentro da VPC** | NAT Gateway, ~US$32/mês | Ela precisa alcançar `github.com`. Lambda **fora** da VPC tem internet de graça. As Lambdas que falam com o GitHub ficam fora; só o Fargate entra na VPC |
| Mover o Fargate pra subnet privada "porque agora só fala com S3" | 3 interface endpoints (ECR API, ECR DKR, CloudWatch Logs) ≈ US$21/mês | Ele ainda puxa imagem do ECR e escreve log. Fica em subnet **pública** com SG de entrada fechado, como na D3 |

A segunda é a mais provável: é o reflexo de "botar tudo na VPC" e é exatamente o NAT Gateway
que a D3 passa o documento inteiro tentando evitar.

**Ganho de brinde:** com o Gateway Endpoint, o egress do container passa a ser restringível
ao *managed prefix list* da S3 (`com.amazonaws.<região>.s3`). "Sem saída de rede" deixa de
ser promessa de prosa e vira **regra de security group que dá pra mostrar na tela** — sem
custo nenhum.

> Preços de `us-east-1`, de memória. Franquias permanentes de Lambda e SQS têm alta
> confiança; confirmar o resto na calculadora da AWS, como o §9 já pede.

---

### P3.2 — Como o resultado sai do container (e se ele tem credencial da AWS)

O §3 promete container **"sem credencial da AWS"**. Mas em B ele precisa ler o pacote no S3
e devolver os achados. Do jeito convencional isso são duas permissões IAM — ou seja,
credencial da AWS dentro do container. Segunda promessa do §3 em risco.

| | Como funciona | Ganha | Custa |
|---|---|---|---|
| **a ✅** | Task role com `s3:GetObject` num prefixo e `s3:PutObject` noutro. Container usa o SDK normalmente | O jeito convencional da AWS. "Least privilege via task role" é vocabulário que todo entrevistador reconhece. Rotação automática, credencial ligada à identidade da task, e o uso aparece no CloudTrail *como daquela task* — auditável. Fácil de debugar | O container **tem** credencial da AWS. A frase do §3 vira "credencial mínima", não "nenhuma" |
| b | URLs pré-assinadas (GET de entrada + PUT de saída) passadas via override de `ecs:RunTask`. Container faz dois HTTPS e mais nada. Evento do S3 no prefixo de saída acorda a publicadora | "Sem credencial da AWS" viraria literalmente verdade | **As URLs não somem, mudam de lugar:** overrides de `ecs:RunTask` entram nos parâmetros da requisição no **CloudTrail**, e overrides de ambiente de container não são redigidos. Você tira a credencial do container e põe uma URL com permissão de escrita no log de auditoria — justamente o lugar que a D11 quer confiável. Além disso, URL assinada é *bearer token*: uma vez copiada, é anônima e não rastreável |
| c | Container grava direto no DynamoDB; o stream da tabela de auditoria (que a D11 já exige) dispara a publicadora | Reusa tabela que já ia existir; zero peça nova. Gatilho semanticamente certo: "gravou o veredito → publica" | Mesma perda do §3 que (a), e acopla a publicação ao formato do registro de auditoria. Stream dispara em qualquer escrita, então exige filtro no evento |

**✅ Escolhido: (a) — task role com permissão mínima.**

> ⚠️ **Recomendação revertida no meio da discussão.** A primeira sugestão foi (b). Ela caiu
> por três motivos, e o registro fica porque *"por que não usou task role?"* é pergunta de
> entrevista.

**Por que (b) caiu:**

1. **CloudTrail.** As URLs pré-assinadas viajam como override de `ecs:RunTask` e acabam
   registradas. Trocar credencial-no-container por URL-de-escrita-no-log não é ganho líquido.
2. **Bearer token não é auditável.** Task role expira, rotaciona e é atribuível à task.
   URL copiada é anônima.
3. **Um argumento pró-(b) não sobrevivia ao escrutínio.** Foi dito que (b) daria "contrato
   idêntico local e na nuvem". Isso não é propriedade do mecanismo — é propriedade de
   escrever o analisador como **função pura sobre um diretório** (`recebe caminho → devolve
   JSON`) com o transporte num shim fino por fora. Com esse desenho, (a) roda igual no Docker
   local. Era organização de código disfarçada de decisão de infraestrutura.

**E o que o modelo de ameaça diz:** o §4 é explícito — *"o ataque não é roubar credencial, é
fazer o segurança mentir"*. Pra roubar qualquer credencial o atacante precisa de **execução
de código** dentro do container. O Semgrep não executa o código que analisa, só parseia AST;
as ferramentas do agente no marco 2 são só leitura. **Não há atacante lá dentro pra roubar
nada** — nem task role, nem URL assinada. A propriedade que (b) comprava defende uma ameaça
que o próprio documento diz não ser a principal.

**Onde (b) ainda ganharia:** contenção *se* algo dentro do container for explorado. Existe
uma superfície concreta — **descompactar tarball controlado pelo atacante** (path traversal,
o clássico *zip-slip*). Mitigação obrigatória, independente da escolha:

```python
tarfile.extractall(path=destino, filter='data')   # Python 3.12+
```

Com isso no lugar, a probabilidade cai o suficiente pra não justificar o preço do CloudTrail.

**A frase do §3 muda — e fica mais forte por ser verdade:**

> ~~sem credencial da AWS~~
> → **credencial da AWS que só lê um prefixo do S3 e escreve outro; nenhum token do GitHub
> e nenhuma rota pra `github.com`**

A segunda metade é a que defende a ameaça real: o container não consegue falar com o GitHub,
então não consegue agir sobre o repositório nem publicar veredito nenhum. *"Nenhuma
credencial"* era uma frase mais bonita defendendo o problema errado.

**Nota:** o log do container vai pro CloudWatch pela **execution role**, que pertence ao
agente do ECS e não ao processo dentro do container. Você tem log nas três opções, sem furar
promessa nenhuma.

---

### P3.3 — Qual árvore analisar

Um fato do GitHub elimina metade da decisão:

> **Proteção de branch confere as checagens no head SHA do PR.** Check Run publicado noutro
> commit simplesmente não trava o merge.

Publicação no head SHA, então, é forçada. Sobra o que **analisar**:

| | Analisa | Ganha | Custa |
|---|---|---|---|
| **head SHA ✅** | o código como o autor escreveu | Um SHA só, já disponível no payload do webhook. As anotações caem exatamente nas linhas que o revisor vê no diff | Não vê interação com o que entrou na `main` desde que o PR abriu |
| merge commit (`merge_commit_sha`) | o resultado da fusão — o que de fato vai pra `main` | Semanticamente o certo pra um portão. É o que o CodeQL faz | O GitHub calcula esse SHA de forma **assíncrona**: vem `null` logo depois do PR abrir e exige repetir a consulta. Se o PR tiver conflito, ele nem existe — precisa de caminho alternativo |

**✅ Escolhido: head SHA.**

**Porquê:** o buraco que ele deixa não é fechado pelo merge commit de qualquer jeito. O caso
é o **conflito semântico de merge** — dois PRs seguros que viram vulnerabilidade juntos:

```
main:  rota /user  →  middleware valida o id  →  UserRepo.buscar(id)

PR A:  remove a validação do middleware
       "nenhuma rota depende disso" — verdade na árvore de A   ✅ passa

PR B:  adiciona a rota /report, que chama UserRepo.buscar(id)
       "a validação existe"        — verdade na árvore de B    ✅ passa

merge de B, depois merge de A  →  /report sem validação        ❌ ninguém barrou
```

Analisar o merge commit mata o caso do *segundo* PR, mas não do primeiro — quando A abriu, B
ainda não existia. O merge commit só encurta a janela; não fecha. O que fecha é analisar a
`main` **depois** do merge, e isso vale a pena por outro motivo (abaixo).

---

### P3.4 — O webhook trata `pull_request` **e** `push` na `main`

**Não é preciosismo, é obrigatório pro desenho da D10 funcionar.**

A D10 diz que o deploy consulta `GET /veredito/{sha}`. Mas o SHA que vai pra produção
**nunca é o head do PR**:

| Estratégia de merge | SHA deployado |
|---|---|
| merge commit | SHA novo |
| squash | SHA novo |
| rebase | SHA novo |

Nas três, o commit deployado é um que ninguém analisou. Sem tratar `push`, a consulta não
acha veredito, o fail-closed dispara e **todo deploy trava pra sempre** — o sistema falha
fechado, mas por burrice, não por detecção.

Com `push` tratado:

| | Trava onde | Papel |
|---|---|---|
| Check Run no head SHA | no **merge** | mecanismo rápido e específico, anota a linha |
| Análise do push na `main` | antes do **deploy** | rede de segurança; é onde o conflito semântico aparece |

O §8 e o §10 já dizem *"push → webhook"*, então isso **alinha o documento consigo mesmo** em
vez de acrescentar coisa nova.

---

### P3.5 — Buscar o diff junto com o tarball

**✅ Escolhido: sim.** A buscadora já tem o token; uma chamada a mais em `pulls/{n}/files`
traz arquivos alterados e faixas de linha.

**Porquê:** sem isso não dá pra distinguir achado **novo** de achado **pré-existente**. O
`devops-portfolio` foi escrito sem esse portão existir e vai acusar achados no primeiro dia.
Se todo achado bloqueia, o primeiro PR nasce vermelho **sem caminho pra ficar verde**, e o
portão vira aquilo que todo mundo aprende a ignorar.

**O que trafega no S3 deixa de ser "um tarball" e vira um pacote de trabalho:**

```
s3://…/entrada/{head_sha}/
   codigo.tar.gz     árvore do head
   contexto.json     numero do PR, head_sha, base_sha,
                     arquivos alterados + faixas de linha
```

Duas obrigações que nascem daí:

- **O contrato do container passa a ser esse pacote**, não uma URL de repositório. É o que
  permite o corpus da D12 montar o mesmo pacote na mão e rodar offline.
- **Obriga a decidir a política de achado pré-existente** — que é o P2.

---

### P3.6 — Consequência: o tarball apaga uma ferramenta do agente

Tarball é foto da árvore, **sem histórico**. Isso atinge o §3:

| Ferramenta do harness | Sobrevive? |
|---|---|
| `ler_arquivo(caminho)` | ✅ |
| `buscar(regex)` | ✅ |
| `historico_git(caminho)` | ❌ não existe histórico pra ler |

Uma decisão de marco 1 apaga uma ferramenta de marco 2. Opções:

| | Consequência |
|---|---|
| Trocar tarball por `git clone --filter=blob:none` na buscadora | Lambda não vem com `git` → vira layer ou imagem de container; a peça deixa de ser trivial |
| Pré-computar: buscadora traz o histórico **só dos arquivos alterados** pela API e manda no pacote | Limitado e sem rede no container; mais uma chamada e mais um formato |
| **✅ Aposentar a ferramenta** | Harness cai de 3 pra 2 ferramentas |

**✅ Escolhido: aposentar.**

**Porquê: ela já ficou redundante.** O `historico_git` servia basicamente pra responder
*"essa linha entrou agora ou é antiga?"*. O diff (P3.5) responde isso de forma **exata e
determinística**, sem gastar passo do orçamento do agente nem depender de ele interpretar um
log. O que era ferramenta vira **campo no contexto**:

```yaml
linha_tocada_por_este_pr: sim | nao
```

Ganho duplo: harness menor é harness mais defensável, e os 8 passos de orçamento (§3) rendem
mais.

**Efeito colateral no marco 4:** o **gitleaks** é o único scanner que quer histórico — os
outros três (Semgrep, Checkov, Trivy) só olham a árvore. No modo diretório ele pega segredo
que está na árvore hoje, mas não o que foi commitado e removido depois. **Isso é aceitável e
até mais correto:** segredo em histórico já vazou, e o que ele exige é *rotação*, não bloqueio
de PR. Vira trabalho periódico separado, não portão.

---

### O que o P3 obriga a mudar no `ARQUITETURA.md`

Consolidar quando os 6 pontos fecharem.

| Seção | Mudança |
|---|---|
| §3 harness | Tabela de ferramentas cai de 3 pra 2 (`historico_git` sai, vira campo de contexto). Frase "sem credencial da AWS" → "task role que só lê um prefixo e escreve outro; sem token do GitHub e sem rota pra github.com" |
| §4 defesas | Linha nova: separação de privilégio — quem tem token não lê código, quem lê código não tem token |
| §7 fluxo | Redesenhar: buscadora → S3 → Fargate → S3 → publicadora. A regra determinística migra do container pra publicadora |
| §7 árvore | Entram `buscador/`, `publicador/` e um módulo de pacote (S3); `analisador/clone.py` sai |
| §8 ordem | Passo 3 vira "container consome pacote local"; passo novo pro caminho de volta |
| §9 conta | Linha do S3 (< US$0,01) e as três armadilhas de endpoint/VPC |
| §10 prompt | Refletir tudo acima — é o texto que carrega sessão nova |
| §11 | Item 3 sai |
| novo | Webhook trata `pull_request` **e** `push` na `main`; nota sobre `tarfile.extractall(filter='data')` |

---

## Revisão da D2 — de uma cobaia para uma frota

> **Decidido em 11/08/2026.** Substitui a D2 do `ARQUITETURA.md`, que assumia **uma** cobaia
> (`devops-portfolio`). O objetivo agora é que o portão sirva os projetos reais em
> `/projects` — hoppr e os demais — e não um repo dedicado.

### O que existe em `/projects`

| Projeto | Repo git | Remote | Superfícies | `.tf` |
|---|---|---|---|---|
| `hoppr` | ✅ | `gabhrielv/hoppr` | Python/FastAPI, Next.js/TS, Dockerfile, workflow | 0 |
| `notle` | ✅ | `gabhrielv/notle` | Node (pnpm workspace) + Python, 5 workflows | 0 |
| `wayfound` | ✅ | `gabhrielv/wayfound` | backend + frontend, Firebase | 0 |
| `pt1` | ✅ | `gabhrielv/GymTracker` | backend + frontend, Firestore rules, Dockerfile | 0 |
| `antilu` | ✅ | **sem remote** | TypeScript/Vite | 0 |
| `portfolio` | ✅ | `gabhrielv/portfolio` | HTML estático | 0 |
| `devops-portfolio` | ❌ nem é repo | — | Java/Spring, Nginx, Actions | **13** |
| `raio` | ❌ | — | só docs | 0 |

### Correção de fato no `ARQUITETURA.md`

A D2 afirma que usar todos os projetos *"triplica as ferramentas a integrar"*. **Isso está
errado.** O Semgrep é poliglota e os quatro scanners do marco 4 cobrem a frota inteira sem
nenhum scanner novo:

| Scanner | Cobre | Na frota |
|---|---|---|
| Semgrep | Java, Python, TS/JS, Go… | hoppr, notle, wayfound, pt1, antilu, devops-portfolio |
| Checkov | Terraform, Dockerfile, Actions, k8s | `pra` (ele mesmo), hoppr, pt1 |
| Trivy | imagem + dependências (`requirements.txt`, `package.json`) | todos |
| gitleaks | segredos | todos |

O que multiplica não são as ferramentas — é o **volume de achado** e a necessidade de
**política por repo**. Coisa diferente, e tratada abaixo.

---

### N1 — Quanto de multi-repo entra no marco 1

| | Escopo | Ganha | Custa |
|---|---|---|---|
| **✅ Multi-repo, política única** | Nada hardcoded: dono, repo e branch vêm do payload do webhook. Chave do DynamoDB `PK = owner#repo`, `SK = sha`; prefixo do S3 `entrada/{owner}/{repo}/{sha}/`. Política única no código da plataforma | Custo perto de zero — o payload **já traz** esses dados, hardcodar daria *mais* trabalho. Adicionar repo novo vira "instalar o App nele": zero código, zero deploy | Política igual pra todos; repo que precise de regra própria vai esperar |
| Um repo só, generaliza no marco 4 | `PK = sha`, prefixo `entrada/{sha}/` | Marco 1 com menos caso de borda | Retrabalho espalhado: chave do Dynamo (com migração de dado), prefixo do S3, token por instalação e todo lugar que assumiu "a cobaia" |
| Multi-repo com config por repo | `.pra.yml` lido da branch base | Mais completo e mais vendável como produto | Schema, parser, validação, defaults e o caminho de erro — trabalho real dentro do marco que deveria ser fino |

**✅ Escolhido: multi-repo com política única.**

**Porquê:** não hardcodar é literalmente o caminho de menor esforço — o dado já chega pronto
no webhook. Ignorá-lo agora custa reintroduzi-lo em cinco lugares depois, incluindo migração
de chave no DynamoDB.

---

### N2 — Config por repo: adiada, com a armadilha já registrada

Fica pro marco 4 ou depois. Mas a decisão de **onde** ela mora já tem resposta, e é de
segurança:

> Se a config morar no repo alvo (`.pra.yml`), **quem abre o PR pode editar o arquivo e
> desligar o portão no mesmo PR.** A config tem que ser lida sempre da branch **base**,
> nunca do head.

É exatamente o que o GitHub faz com workflows disparados por `pull_request`: usa a definição
da base, não a do PR. Registrar agora evita implementar errado depois.

---

### N3 — Qual repo é a cobaia do marco 1

| | Ganha | Custa |
|---|---|---|
| **✅ `hoppr`** | Já é repo, já tem remote e workflow — **as ~2 h do pré-requisito do §8 somem**, junto com o risco de workflow que nunca rodou. Backend em Python, mesma linguagem da plataforma (D13). Projeto real com histórico real | É aplicação, não infra: sem Terraform. E é projeto vivo — checagem obrigatória nele atrapalha o dia a dia |
| `devops-portfolio` | Superfície mais DevOps; único com Terraform | Nem é repo git e os workflows nunca rodaram: ~2 h de setup mais um desconhecido logo no começo. **E a Terraform só é analisada no marco 4**, quando o Checkov entra — no marco 1 é Semgrep, que roda igual nos dois |

**✅ Escolhido: `hoppr`.**

**Porquê:** sequenciamento. A única vantagem real do `devops-portfolio` é a Terraform, e nada
analisa Terraform até o marco 4. Pagar 2 h de setup agora por um ganho que só aparece três
marcos depois é adiantar trabalho pra ficar parado.

**Decisão do usuário (11/08/2026):** o `devops-portfolio` está inacabado e não é prioridade.
Sai do plano como cobaia. O pré-requisito de 2 h do §8 deixa de existir.

**Ressalva operacional, vale pra qualquer alvo:** no marco 1 a checagem **não** entra como
obrigatória no `hoppr`. O Check Run reporta sem travar. A obrigatoriedade — o passo 7 do §8,
*"o botão de merge fica cinza"*, que é o que vai ser gravado — se liga quando for gravar.
Portão pouco confiável travando merge no seu projeto vivo é a receita pra você mesmo
desligar ele.

---

### N4 — Quem cobre Terraform, já que o `devops-portfolio` saiu

Sem ele, a frota tem **zero** arquivo `.tf`, e o Checkov do marco 4 ficaria só com Dockerfile
e workflows. Pra portfólio de DevOps, não ter IaC analisada é buraco visível.

**✅ Escolhido: o próprio `pra` é a cobaia de infraestrutura.** O §7 já prevê `infra/` com
cinco módulos — VPC, SQS, Lambdas, ECS, DynamoDB — e IAM espalhado por todos.

Isso ressuscita a opção *"robô analisa a si mesmo"* que a D2 tinha listado e descartado —
mas agora **como complemento**, não como substituta da cobaia:

| Alvo | Cobre | Entra em |
|---|---|---|
| `hoppr` | Python, TS/JS, Dockerfile, workflow | marco 1 |
| `pra` (ele mesmo) | Terraform, IAM, VPC, security group | marco 4, com o Checkov |
| demais repos da frota | mais linguagem, mais volume | quando quiser — instalar o App |

**Porquê:** *"o portão bloqueia PR na Terraform do próprio portão"* é história mais forte que
*"rodei num projeto de estudo abandonado"*. E é dogfooding de verdade, não demonstração
montada.

**A pegadinha, e ela vira ponto a favor quando contada:** se a checagem for obrigatória no
repo do `pra` e o `pra` quebrar, você não consegue mergear a correção — **fail-closed
aplicado a si mesmo tranca você do lado de fora.** Por isso a checagem fica
**não-obrigatória no repo do `pra`**. Não é concessão, é a resposta certa, e mostra que a
operação foi pensada junto com a arquitetura.

---

## P2 — Formato do Check Run e política de achado pré-existente

### P2.1 — Política de achado pré-existente

Os repos da frota foram escritos ao longo de meses, sem esse portão existir. Todos vão acusar
achados no primeiro dia — código que já está na `main`, que nenhum PR introduziu.

> Se todo achado bloqueia, o primeiro PR nasce vermelho **sem caminho pra ficar verde**. A
> única saída vira desligar a checagem obrigatória — e o portão vira enfeite. Esse é o modo
> de falha mais comum de ferramenta de segurança em CI, e não é técnico.

| | Política | Ganha | Custa |
|---|---|---|---|
| **✅ 1** | **Sensível ao diff** — só bloqueia achado em linha que o PR tocou | Todo PR nasce verde e fica verde fazendo o certo. É o *"clean as you code"* do Sonar e o comportamento do CodeQL em PR — vocabulário reconhecível. O dado já vem de graça (P3.5) | A dívida antiga nunca é cobrada. Escapa o PR que não toca a linha vulnerável mas a torna alcançável (liga flag, muda config) — o "caminho morto" da D12 ao contrário |
| 2 | **Baseline congelado** — snapshot dos achados de hoje; bloqueia o que não estiver na lista | Pega achado novo mesmo em arquivo não tocado, incluindo o caso do caminho morto. Baseline é artefato explícito, versionado, revisável em PR | Exige *fingerprint* estável: `arquivo + regra + hash do trecho`, **nunca o número da linha** — inserir código acima desloca tudo e invalida o baseline inteiro. Manter é trabalho recorrente |
| 3 | **Bloqueia tudo, paga a dívida antes de ligar o portão** | Portão mais simples que existe: crítico → bloqueia. Zero código de baseline, zero código de diff | Limpar as bases na mão antes do marco 1 |
| 4 | **Bloqueia tudo, sem faxina** | Nada pra escrever | Se houver dívida, o portão nasce inútil |

**✅ Escolhido: 1, na forma combinada — bloqueia o novo, mostra o antigo.**

```
achado em linha tocada pelo PR   →  BLOQUEIA  (annotation_level: failure)
achado pré-existente             →  mostra    (annotation_level: notice, não trava)
```

**Porquê:** você fica com portão utilizável desde o primeiro dia *e* com a dívida visível em
vez de escondida — que é o que a opção 1 pura perde.

**A escolha da frota decidiu essa por consequência.** A opção 3 era viável com **uma**
cobaia; com sete repos escritos ao longo de meses, virar faxineiro de sete bases antes de ter
sistema é inviável. Não foi preciso medir o volume de achados pra decidir.

**Frase de defesa:** *"o portão é sensível ao diff porque um portão que nasce vermelho é um
portão que vai ser desligado."*

### P2.2 — Formato da apresentação

**Um fato do GitHub descarta metade das opções antes de começar:**

> **Anotação só renderiza inline em linha que faz parte do diff do PR.** Anotar um achado
> pré-existente num arquivo que o PR não tocou não aparece na aba *Files changed* — fica só
> numa lista lateral que ninguém abre.

Ou seja, a divisão que a P2.1 fez entre *novo* e *pré-existente* mapeia exatamente na divisão
que a plataforma impõe entre *anotação* e *resumo*. Não é escolha, é encaixe:

```
seguranca/gate                                    ❌ Failing
───────────────────────────────────────────────────────────
3 achados novos bloqueiam · 11 pré-existentes

## Bloqueando (3)
| Sev.    | Achado             | Onde                            |
|---------|--------------------|---------------------------------|
| CRÍTICO | SQL injection      | backend/app/repo/user.py:88     |
| CRÍTICO | Segredo hardcoded  | backend/app/config.py:12        |
| ALTO    | Path traversal     | backend/app/files.py:203        |

## Pré-existente (11) — não bloqueia
▸ ver lista

regra v1 · a1b2c3 · 41s
```

As 3 de cima **também** viram anotação na linha; as 11 de baixo vivem só no resumo.

| Item | Decisão | Porquê |
|---|---|---|
| Ordem | severidade, depois `arquivo:linha` | Estável entre execuções — o mesmo PR reanalisado não embaralha a lista |
| Teto | trunca em 50 e o resumo diz `mostrando 50 de 73` | O limite da API é 50 anotações por requisição. Paginar com múltiplos updates é possível, mas ninguém lê 73 anotações — o número honesto no resumo entrega mais que a lista completa |
| `output.title` | veredito curto e contável | É o que aparece colado no nome da checagem |

#### Dois estados de falha, não um

O portão bloqueia por dois motivos diferentes, e confundi-los custa confiança:

| Situação | `conclusion` | `title` |
|---|---|---|
| Achou vulnerabilidade | `failure` | `3 achados novos bloqueiam` |
| **Não conseguiu concluir** (orçamento estourado, cota, scanner quebrou) | `action_required` | `não conclui: cota do LLM esgotada` |

| | Ganha | Custa |
|---|---|---|
| **✅ Dois estados** | O desenvolvedor vê de cara se o problema é o código dele ou o portão. Os dois travam o merge igual | Mais um caminho pra testar; e é preciso **verificar que `action_required` realmente bloqueia** na proteção de branch (só `success` passa) |
| Um estado só, motivo no título | Um caminho de código, um comportamento | "Vermelho" vira ambíguo — e portão que fica vermelho por motivo que o dev não controla é exatamente o que ensina todo mundo a ignorar o vermelho |
| Não concluir não bloqueia | Nunca atrapalha quem não tem culpa | **Quebra o fail-closed da D6/§4**, que é a espinha do projeto: quem quiser passar só precisa fazer o portão falhar |

**✅ Escolhido: dois estados.**

---

## P4 — Retry quando o provedor nega

> **O nome envelheceu, o conteúdo não** (13/08/2026). Esta seção foi escrita quando o
> provedor era Cerebras; ele virou Groq na **P9**. A decisão — degradar para o modo marco 1 —
> não depende de qual provedor é, e é por isso que ela sobreviveu à troca sem uma linha
> mudada. Onde o texto abaixo diz "Cerebras", leia "o provedor da D7".

Duas falhas diferentes que o `ARQUITETURA.md` trata como uma só:

| Falha | Retry adianta? | Resposta |
|---|---|---|
| 429 por requisições/minuto, 5xx, timeout | **sim** — some em segundos | backoff exponencial, 3 tentativas, dentro da própria execução |
| **cota diária esgotada** (1M tokens/dia) | **não** — só volta amanhã | ← a decisão está aqui |

A primeira linha não é escolha, é só estar certo.

**Restrição inegociável na segunda:** qualquer saída que faça o PR **passar** quebra a D6
(`nao_sei` bloqueia) e esvazia a §4 — bastaria estourar a cota pra atravessar o portão.

| | O que faz | Ganha | Custa |
|---|---|---|---|
| **✅ Degrada pro modo marco 1** | Pula o agente, aplica a regra sobre os achados crus, `failure` com `(modo degradado: sem triagem por IA)` no título | **Custo de implementação zero — o marco 1 já é esse caminho.** O portão continua utilizável, e erra pro lado de bloquear *mais*, então o fail-closed continua de pé | Volta o ruído que o marco 2 existia pra tirar. Achado que a triagem silenciaria passa a bloquear |
| Devolve pra fila, tenta depois | `ChangeMessageVisibility` com atraso de até 12 h — atravessa a virada da cota. Check fica `in_progress` | Check que nunca completa **já trava o merge**: fail-closed de graça. Resolve sozinho | PR pendurado por horas sem explicação útil. 10 PRs no dia = 10 esperando amanhã |
| Bloqueia e para | `action_required`, "não conclui: cota esgotada" | Honesto e simples: o portão diz que não sabe e não finge | **Os scanners já rodaram.** Joga fora informação que já estava pronta e deixa o dev sem nada até amanhã |
| Cai pro segundo provedor | Usa a segunda implementação de `ClienteLLM` | A interface da D7 existe justamente porque cota grátis pode sumir | O catálogo grátis não ajuda: Groq dá ~2 análises/dia. Os que servem são Bedrock (crédito) ou Anthropic (~US$0,07/análise). E dobra chave, teste e medição no corpus |

**✅ Escolhido: degrada pro modo marco 1.**

### Duas consequências que isso cria

**1. O marco 1 deixa de ser andaime e vira caminho permanente de código.**
Isso muda como ele é escrito: não é rascunho a ser substituído no marco 2, é o **modo
degradado definitivo** do sistema. O marco 2 *adiciona* uma etapa de triagem entre o scanner
e a regra; não reescreve o que existia.

```
marco 1 (e modo degradado):   scanners → regra → Check Run
marco 2 (caminho normal):     scanners → agente → regra → Check Run
```

**2. Modo degradado precisa ser observável.** Sem métrica no CloudWatch contando execuções
degradadas, você roda meses achando que a triagem está funcionando enquanto o portão só
repassa achado cru. Uma métrica e um alarme no Budgets-style: *"degradou mais de X vezes hoje"*.

---

## P5 — Cronograma

**Entrada do usuário (11/08/2026): ~20 h/semana, sem prazo, prioridade é fazer bem feito.**

### Tamanho do marco 1, já com as decisões de hoje

A opção B (P3.1) trouxe duas Lambdas a mais que o desenho original; em compensação, escolher
o `hoppr` (N3) eliminou o pré-requisito de ~2 h do `devops-portfolio`.

| | Passo | Horas |
|---|---|---|
| 1 | `regra.py` determinística, sensível ao diff + testes | 3–4 |
| 2 | `semgrep.py` — roda o CLI, parseia JSON, contra o `hoppr` local | 2–3 |
| 3 | `analisador/main.py` — função pura sobre o pacote, no Docker local | 4–5 |
| 4 | Terraform: rede, S3, SQS, DynamoDB, ECR | 6–9 |
| 5 | Lambda webhook + API Gateway + validação HMAC | 4–6 |
| 6 | Lambda buscadora (tarball + diff → S3) + dispatcher (`RunTask`) | 5–7 |
| 7 | Lambda publicadora + auth do GitHub App + Check Run | 5–7 |
| 8 | GitHub App instalado no `hoppr`, fim a fim, proteção de branch | 3–5 |
| | **subtotal** | **32–46** |

O §10 registra que o usuário é intermediário em AWS. Na prática o **imposto de IAM** (política
errada, `AccessDenied` sem mensagem útil) soma 20–30%. Conta realista: **35–50 h**.

### Projeção

| Marco | Escopo | Horas | Semanas a 20 h |
|---|---|---|---|
| 1 | encanamento, sem IA, fim a fim no `hoppr` | 35–50 | ~2–2,5 |
| 2 | corpus (D12) + agente + `ClienteLLM` | 21–30 | ~1,5 |
| 3 | Step Functions paralelizando | 8–12 | ~0,5 |
| | **até o "completo" da §8** | **64–92** | **~4–6 com folga** |

O corpus sozinho é 8–12 h dessas — a D12 avisa que o difícil não é a vulnerabilidade, é o
**falso-positivo convincente**, e isso é trabalho de escrita, não de código.

### Definição de pronto — a contramedida do "sem prazo"

Sem prazo, o risco deixa de ser ficar sem tempo e vira **nunca ter um pronto**: refinar o
marco 1 por seis semanas porque sempre dá pra melhorar. A D9 defende o projeto pelo lado da
largura; pelo lado da profundidade não havia defesa escrita.

> **Um marco só está fechado com as três coisas juntas:**
> 1. rodando de verdade (não em teste, não em rascunho)
> 2. um trecho de README com o número ou a evidência daquele marco
> 3. uma gravação de 60–90 s
>
> **Sem a gravação, o marco não está fechado.**

A terceira não é cerimônia: a D2b já obriga demo por vídeo (repos privados), e gravar força a
descobrir o que ainda depende de gambiarra manual.

---

## P6 — Marco 4: acontece, e o conteúdo fica deliberadamente em aberto

**✅ Acontece** — 20 h/semana sem prazo tornam a pergunta original da §11 ("se o marco 4
acontece") sem graça.

**✅ O conteúdo NÃO se decide agora.** O marco 4 fica a 4–6 semanas de distância. Escolher
hoje é decidir no escuro; no marco 3 o sistema estará rodando e a escolha será informada por
onde ele de fato dói. Os candidatos ficam registrados com custo e entrega:

| Candidato | Entrega | Custo | Nota |
|---|---|---|---|
| **Checkov no próprio `pra`** | Fecha o único buraco visível: hoje **zero IaC é analisada** (N4). Achado mais on-message pra vaga: security group aberto, IAM larga demais, bucket sem criptografia. E exercita multi-repo de verdade — o `pra` vira o segundo alvo | ~6–8 h | Era a recomendação, se fosse pra escolher hoje |
| Segundo provedor + comparação no corpus | A D7 chama isso de *"o artefato mais valioso do projeto"* e não está em marco nenhum. `ClienteLLM` e corpus já existem — é só mais uma implementação e rodar | ~4–6 h | Alto valor por hora, mas não acrescenta infraestrutura, que é o eixo da D1 |
| Expandir pra mais repos da frota | Instalar o App em `notle`, `wayfound`, `pt1`. Teste real de se o desenho generaliza | ~0 h se o multi-repo estiver certo | Provavelmente puxa a **N2** (`.pra.yml` lido da base) pra dentro, e aí deixa de ser de graça |
| Trivy + gitleaks | CVE em dependência (`requirements.txt`, `package.json`) e segredo. É o marco 4 como o documento escreveu | ~8–12 h | Largura pura — exatamente o risco que a D9 aponta. E o gitleaks ficou capenga sem histórico (P3.6) |

**Quando decidir:** ao fechar o marco 3.

---

## P1 — Nome do projeto

**✅ Escolhido em 11/08/2026: `aduana`.** `gate` era placeholder desde a primeira versão do
documento. **🔄 Revisto em 13/08/2026 para `portcullis`** — ver abaixo.

| Opção | Argumento |
|---|---|
| **✅ `aduana`** | A alfândega inspeciona o que atravessa uma fronteira e retém o que não passa. **São duas fronteiras e dois postos, que é literalmente a D10:** o PR atravessa pra `main` (Check Run) e a `main` atravessa pra produção (passo do deploy) |
| `crivo` | "Passar pelo crivo" = ser peneirado *e* ser examinado — as duas coisas que o sistema faz, na mesma palavra. A regra da D6 é literalmente uma peneira |
| `cancela` | A cancela não opina: fica baixada até alguém provar que pode subir. Fail-closed em uma imagem. Casa com o vocabulário do documento ("trava o merge") |
| manter `gate` | Zero trabalho de renomear, mas é o nome da **categoria**, não do projeto — some no meio de mil repositórios homônimos |

### 🔄 Revisão de 13/08/2026 — `aduana` → `portcullis`

O argumento de 11/08 continua inteiro; o que mudou foi a língua. O projeto é peça de
portfólio, e quem lê o README, o nome da checagem e a URL do repositório na maior parte
das vagas não fala português — `aduana` obriga a explicar o nome antes de explicar o
sistema. `portcullis` é a grade que fecha o portão do castelo, e paga por si em três
frentes:

| Critério | Como se sai |
|---|---|
| Duas fronteiras, dois postos (D10) | Mantém. Castelo tinha grades sucessivas — barbacã e portão interno — pelo mesmo motivo que este desenho tem dois portões: nada avança enquanto cada uma não sobe |
| Fail-closed da §4 | **Ganha sobre `aduana`.** A grade fica baixada por padrão; subir é o evento excepcional. A alfândega descreve a inspeção, a grade descreve o estado de repouso |
| Colisão de nome | Livre no espaço de CI/segurança. Descartados no caminho: `barbican` (OpenStack Barbican, gerenciador de segredos — colide na cara do público de infra), `bulwark` (framework de segurança web em Rust), `crucible` (code review da Atlassian) |

Descartados também `assay` (ensaio de pureza de metal — curto e exato, mas soa *essay* na
fala) e `touchstone` (a pedra de toque; bonito, mas abstrato demais, não diz "portão").

**Consequências:**

Todas executadas em 13–14/08/2026:

| Onde | Estado |
|---|---|
| Repositório | ✅ `portcullis` (ainda sem remote) |
| Pasta no disco | ✅ `/home/gabhriel/projects/portcullis` |
| Pacote Python | ✅ `app/src/portcullis/`; o git registrou como rename, não como apagar e recriar |
| Bucket do `tfstate` | ✅ `portcullis-tfstate-523301712809`; o antigo foi apagado vazio, porque nome de bucket é imutável |
| Parâmetros do SSM | ✅ `/portcullis/github/*` |
| GitHub App | ✅ criado direto como `portcullisapp`, App ID 4589712 |
| Nome da checagem | ✅ **fechado**: `seguranca/portcullis`, em `github/checks.py`. É o texto que a proteção de branch do `hoppr` referencia — trocar depois exigiria reconfigurar a proteção, e um PR aberto no meio da troca ficaria esperando uma checagem que nunca reporta |

> O prefixo `seguranca/` em português ficou. O nome da checagem é a única string
> do sistema que uma pessoa de fora lê no dia a dia, e ela aparece ao lado de
> `lint-and-test` e `Vercel` — a mistura é feia, mas trocar depois de a proteção
> de branch apontar para ela custa mais que o incômodo.

> Custou um *find-replace* em 32 arquivos mais os três itens de conta acima. Depois da T8 o
> nome também estaria no ECR e em print de tela — era a última janela barata.

### 🔄 Revisão de 16/08/2026 — `portcullis` → `PRA`

**Pedida pelo dono do projeto.** `PRA` = *Pull-Request Analyzer*.

O argumento de 13/08 — nome em inglês, para não gastar a primeira frase explicando o
nome — continua de pé, e esta troca vai mais longe no mesmo eixo: a sigla **diz o que o
sistema faz** sem exigir metáfora nenhuma. `portcullis` precisava de uma linha de
explicação ("a grade de ferro que fecha o portão do castelo"); `PRA` gasta três palavras.

| Critério | Como se sai contra `portcullis` |
|---|---|
| Diz o que faz | **Ganha.** Um leitor entende "analisador de pull request" sem nota de rodapé |
| Fail-closed da §4 | **Perde.** A grade baixada era uma imagem do estado de repouso; a sigla é neutra e não carrega postura de segurança nenhuma |
| Duas fronteiras, dois postos (D10) | **Perde.** `portcullis` justificava os dois portões pela grade sucessiva do castelo; a sigla fala só do PR, e o segundo posto é o deploy |
| Colisão de nome | **Perde.** Sigla de três letras colide com muita coisa; `portcullis` era livre no espaço de CI/segurança |
| Custo da troca | 409 ocorrências em 63 arquivos, mais os itens de conta abaixo |

**A escolha é do dono, e o trade-off fica registrado aqui em vez de virar discussão.** O que
se perde é imagem; o que se ganha é um nome que não precisa de glossário. Para um portfólio
lido em trinta segundos, dizer o que faz vale mais que a metáfora.

**Ortografia:** a sigla expande para *Pull-Request **Analyzer***, com `y`. `Analizer` não
existe em inglês, e um erro de grafia no nome do projeto é a primeira coisa que um leitor
técnico nota.

**Grafia no texto:** `PRA` maiúsculo em prosa, `pra` minúsculo só como identificador —
pacote Python, prefixo de recurso, caminho no SSM. O motivo é que "pra" é palavra corrente
em português e os documentos estão em português: sem a distinção, "o pra decide" fica
ilegível no meio de "pra vaga", "pra tudo".

**Consequências, e o que ainda não foi feito.** A parte de código está pronta; a parte de
conta depende da AWS de pé:

| Onde | Estado |
|---|---|
| Pacote Python, imports, testes | ✅ `app/src/pra/`; o git registrou como rename |
| Variáveis de ambiente `PORTCULLIS_*` | ✅ `PRA_*` |
| Prefixo do Terraform, nomes de recurso | ✅ `pra-webhook`, `pra-analisador`, … |
| Namespace da métrica do CloudWatch | ✅ `pra` |
| Imagem e caminho no container | ✅ `pra-analisador`, `/opt/pra/regras` |
| Nome da checagem | ✅ `seguranca/pra` no código |
| **Bucket do `tfstate`** | ❌ **continua `portcullis-tfstate-523301712809`**, de propósito. Nome de bucket é imutável e este guarda o state de tudo que já foi aplicado: renomear é criar o bucket novo, migrar o state e apagar o velho. Trocar a string antes disso faz `terraform init` apontar para um bucket que não existe |
| **Parâmetros do SSM** | ❌ os valores vivem em `/portcullis/*`; o código já procura em `/pra/*`. **Recriar antes do próximo apply**, senão toda leitura de segredo falha |
| **Proteção de branch do `hoppr`** | ❌ aponta para `seguranca/portcullis`. Enquanto não for reapontada, o PR espera para sempre uma checagem que ninguém reporta — e o código agora publica com outro nome |
| **GitHub App** | ❌ `portcullisapp`, App ID 4589712. O nome é cosmético; o App ID é o que o código usa, e ele não muda |
| **ECR** | ❌ repositório `portcullis-analisador` na conta. O `destroy` já o apagou; o próximo apply cria com o nome novo |
| **Pasta no disco** | ❌ ainda `/home/gabhriel/projects/portcullis` — renomear é `mv` mais reabrir o terminal |

> **A ordem importa no dia de subir:** recriar os parâmetros do SSM **antes** do `apply`, e
> reapontar a proteção de branch **depois** dele. Invertida, ou a Lambda sobe sem conseguir
> ler segredo, ou o `hoppr` fica com um PR travado esperando checagem inexistente.

---

# Execução do marco 1 — o que a construção mudou

> **12–14/08/2026.** Daqui em diante o projeto tem código rodando, e várias decisões de
> mesa não sobreviveram ao contato. O `ARQUITETURA.md` guarda o resultado consolidado
> (emendas na D3, D5, D6, D8, D14 e as decisões D20–D28); aqui fica o caminho, que é o que
> responde *"por que não fez do outro jeito?"*.

## P7 — Fargate vira Lambda com imagem de container

**Decidido em 12/08/2026.** Contraria a D3 e a D14 como estavam escritas.

O Fargate era o **único item pago** do desenho: ~US$0,01 por análise, cobrado por segundo,
sem franquia. Todo o resto cabia em franquia permanente.

| Opção | Ganha | Custa |
|---|---|---|
| **Lambda com imagem de container** | 400.000 GB-s/mês de franquia **permanente** — não é o "grátis por 12 meses" que expira. Custo zero de verdade | Teto de 15 min por execução e 512 MB em `/tmp`, que derruba o teto de extração de 2 GB para 300 MB |
| Manter Fargate | Sem limite de tempo nem de disco | O único gasto recorrente do projeto, e ele existe justamente para provar que dá para não ter |
| EC2 spot | Mais barato que Fargate | Máquina ligada para tratar ~30 eventos por mês, e some o argumento serverless da D3 |

**✅ Escolhido: Lambda de imagem.**

**O ganho que não estava previsto foi de segurança, não de custo.** O Fargate precisava de
subnet com egress 443 aberto para puxar a imagem do ECR e escrever log — o container teria
rota para `github.com`, e a promessa de isolamento dependeria de ele não ter credencial. A
Lambda busca a imagem pela infraestrutura do serviço, fora da VPC, então a função pôde ir
para uma subnet **sem rota nenhuma**. A promessa da §3 ficou mais forte por acidente.

**Custa:** o teto de extração cai de 2 GB para 300 MB, e a decisão de rede vira o motivo
pelo qual o agente do marco 2 não cabe dentro do analisador — ver P10.

---

## P8 — Quais achados bloqueiam, resolvido medindo em vez de opinando

**Decidido em 12/08/2026.** Fecha o que o plano do marco 1 deixava para "ajustar depois".

A premissa escrita era: *"o hoppr vai ter WARNING demais, então só ERROR bloqueia"*. Rodar
desmentiu. Linha de base medida no `hoppr`: **16 achados — 4 ERROR, 12 WARNING, 0 INFO**, e
4 dos avisos são de performance.

| Opção | Consequência |
|---|---|
| Só `ERROR` bloqueia | Deixa passar `WARNING` de segurança com confiança e impacto altos — e eles existem no conjunto |
| **`ERROR`, mais `WARNING` com `category == security`** | Pega os dois; categoria ausente nunca promove um aviso, e nunca rebaixa um `ERROR` |
| Tudo bloqueia | Os 4 avisos de performance travariam merge, e o portão seria desligado na primeira semana |

**✅ Escolhido: `VERSAO_REGRA = "2"`.**

**O que a medição ensinou, e vale mais que a regra:** há `WARNING` com confiança e impacto
altos, e `ERROR` com impacto baixo. **A severidade do semgrep não mede risco.** Escolher
por severidade sozinha teria sido escolher por um número que não significa o que parece.

Junto vieram duas descobertas que não eram sobre política:

- **Os dois conjuntos de regras não se contêm.** `p/default` e `p/security-audit`: cada um
  acha `ERROR` que o outro não acha, e rodar os dois custa o mesmo tempo (66 s no `hoppr`).
  Ficaram os dois.
- **`--disable-nosem` é obrigatório.** Sem ele, um `# nosemgrep` no fim da linha desliga o
  portão — verificado: 1 achado vira 0. Quem abre PR no repositório alvo escreveria essa
  linha. A lista de exceções mudou de lugar para `decisao/excecoes.py`, no repositório do
  portão, onde quem abre o PR não alcança.

---

## P9 — Cerebras vira Groq: o projeto apostou errado uma vez

**Decidido em 13/08/2026.** Revisa a D7. **É a reversão mais instrutiva do projeto**, e o
motivo de o `ARQUITETURA.md` terminar com um aviso sobre cotas que mudam sem avisar.

A D7 escolheu Cerebras comparando **tokens por dia** entre os provedores gratuitos. A tabela
estava correta e a conclusão estava errada, porque a coluna que decidia não estava na tabela:
**janela de contexto**. O nível grátis da Cerebras tem teto de **8.192 tokens**, e o loop de
8 passos da D5 estoura isso por volta do terceiro passo — cada passo carrega o histórico
inteiro mais a saída da ferramenta.

| Opção | Ganha | Custa |
|---|---|---|
| **Groq** | Janela folgada para o loop, rate limit sobrando para o volume, e a restrição da D2b de pé: não treina com o input, e a política vale igual no nível grátis | Mais um nome para confundir — ver o aviso abaixo |
| Manter Cerebras | Nada a mudar | O loop não cabe. Seria descobrir isso no meio do marco 2, com o corpus pronto |
| Ir direto para modelo pago | Sem teto nenhum | ~US$2/mês, e some o argumento de custo zero que sustenta o projeto |

**✅ Escolhido: Groq.**

> 🔴 **Groq não é Grok.** O da xAI treina com o input no nível grátis desde 15/01/2026;
> usar ele violaria a D2b. Os nomes diferem por uma letra e os dois aparecem em lista de
> "LLM grátis". Conferir o nome antes de configurar.

**A lição, que vale mais que a troca:** comparar provedores por uma métrica só é como
escolher por severidade do semgrep — o número existe, é verdadeiro, e não é o que decide.
Ficou por confirmar com medição, no marco 2: o rate limit do modelo específico e se ele faz
*tool calling* confiável. Existe uma sonda para isso (`scripts/sondar_modelo.py`) e ela
ainda não rodou.

> A **P4** deste documento se chama *"Retry quando o Cerebras nega"*. O nome do provedor
> envelheceu; o conteúdo não — a decisão lá é degradar para o modo marco 1, e ela vale para
> qualquer provedor.

---

## P10 — O agente sai de dentro do analisador

**Decidido em 13/08/2026.** Vira a **D20** no `ARQUITETURA.md`, e contraria duas linhas que
punham o agente dentro do container.

O que forçou não foi o desenho: foi a rede construída na T7, que saiu **mais estrita do que o
documento previa**. Não existe internet gateway, a route table só tem o gateway endpoint do
S3, e o security group do analisador só permite saída para o prefix list do S3. Ele não
alcança nada além do S3 — de propósito, e é a melhor propriedade de segurança do desenho.

Só que o agente precisa falar com a API de um modelo, que mora na internet. Dentro daquela
sala ele não alcança modelo nenhum — nem grátis, nem pago, nem a Bedrock.

As opções estão na D20. O que importa registrar aqui é **o que não foi escolhido e por quê**:
abrir egress no analisador custaria NAT Gateway (~US$32/mês) e mataria o custo zero sozinho —
exatamente a armadilha que a D3 passa o documento inteiro evitando. E tirar o analisador da
VPC jogaria fora o isolamento recém-construído, que é o que a §3 promete e a entrevista
pergunta.

**A promessa da D14 sobrevive**, e é o ponto fino: *"quem tem o token nunca lê código; quem
lê código não tem token"* continua verdadeira — a investigadora lê o pacote do S3 e não tem
credencial do GitHub. O que muda é que um processo que lê código passa a ter rota de saída.
Isso seria canal de exfiltração se o agente escolhesse o destino, e ele não escolhe: **as
duas ferramentas do harness não são de rede**, e quem chama o modelo é o código, num endpoint
fixo.

---

## P11 — O teto de gasto sai do Terraform

**Decidido em 13/08/2026.** Reverte a decisão anterior, que punha o orçamento no módulo
`alertas`.

Dois motivos, os dois descobertos **olhando a conta de verdade**, não pensando:

1. **Orçamento gerenciado pelo stack sumiria no `destroy`** — que é como toda sessão de
   trabalho termina. A rede de proteção ficaria ausente exatamente enquanto ninguém está
   olhando.
2. **A conta já tinha três orçamentos, e a AWS só dá dois grátis** (depois ~US$0,02/dia
   cada). O nosso seria o quarto, e a ferramenta de vigiar gasto viraria o maior gasto do
   projeto.

**✅ Escolhido: ficar com o `My Zero-Spend Budget` que a própria AWS cria** — US$1/mês com
aviso quando o gasto real passa de US$0,01, já apontando para o e-mail do dono. Os outros
dois foram apagados.

Ele entra na mesma categoria do bucket de state e dos segredos do SSM: **guarda-corpo
permanente da conta, que existe fora do stack porque precisa sobreviver a ele.**

---

## P12 — O que só apareceu rodando de verdade

**14/08/2026.** Nada aqui foi previsto em documento nenhum. Estão em ordem de gravidade.

### 🔴 Cache de parâmetro do SSM precisa expirar

A primeira versão usava `@cache`, eterno. Depois de rotacionar o segredo do webhook, os
containers quentes seguiram conferindo contra o valor velho e **toda entrega legítima virou
401** — sem sinal em lugar nenhum. O portão fica mudo e ninguém descobre.

Medido: de 8 requisições assinadas com o segredo novo, **1 passou** (container novo) e 7
falharam. Agora `VALIDADE_CACHE_S = 300`: rotação vale em no máximo 5 minutos, sozinha.

**A classe de falha é a que este projeto mais teme:** não é o portão recusando, é o portão
recusando *em silêncio, por um motivo errado*.

### 🔴 O segredo nunca passa por humano

A primeira tentativa de rotação foi copiar e colar entre duas telas, e o valor chegou ao SSM
com **51 caracteres em vez dos 64** do `openssl rand -hex 32` — colagem truncada, com sintoma
idêntico ao do cache eterno. `scripts/rotacionar_segredo.py` passou a sortear, gravar no SSM
e mandar para o GitHub na mesma execução: o valor não aparece na tela, no histórico do shell
nem em arquivo. **Ordem importa:** SSM primeiro, GitHub depois — se o GitHub falhar, ele
segue assinando com o antigo e basta rodar de novo.

### Verificar o App do GitHub pela API, não pela tela

O App tinha sido criado assinando `pull_request_review`, `pull_request_review_comment` e
`pull_request_review_thread` **em vez de** `pull_request` — os quatro ficam colados na lista.
O portão funcionaria em push na main e ficaria calado em todo PR. `GET /app` mostra `events`
e `permissions` em uma linha; a tela de configuração, não.

### O limite de concorrência da conta é 10, não 1000

A AWS recusa qualquer reserva que deixe menos de 100 execuções livres — ou seja, recusa
todas. `reserved_concurrent_executions` foi para `-1`. **Não é perda de proteção:** com teto
de 10 na conta inteira, o limite da conta já é o teto de rajada que a reserva daria.

### A duplicata é real, não teórica

Dois reenvios da mesma entrega puseram duas mensagens do mesmo SHA na fila. A chave de
deduplicação deixou de ser precaução.

### `depends_on` entre os módulos é obrigatório

Sem ele o Terraform cria `funcoes` e `analisador` em paralelo, o gatilho do SQS entrega
mensagem antes de a função existir, e a primeira análise falha com "Function not found" até
o SQS reentregar.

### O semgrep é ~7× mais lento em container, e ninguém sabe por quê

16 s no host, 113 s no container, **247 s na Lambda**. Causa não identificada: descartados
número de núcleos, `--jobs`, seccomp, `--privileged`, overlayfs contra tmpfs, cache em `$HOME`
e diferença de binário. Vale igual para Debian e Amazon Linux, então **não influenciou a
escolha entre Fargate e Lambda**. Consequência: o atributo de qualidade "análise < 5 minutos"
da §6 já estava furado antes de o agente existir, e foi revisto para 15 min.

---

# Execução do marco 2 — a revisão que o corpus provocou

> **14–18/08/2026.** As decisões consolidadas são D21–D28 no `ARQUITETURA.md`, com as opções
> de cada uma. Aqui fica o que elas têm em comum e o que só se entende em sequência.

## P13 — O corpus foi escrito antes do prompt, e cobrou por isso

A D12 manda escrever o corpus **antes** da primeira linha de prompt. A regra parece
cerimônia até você ver o que ela pega: escrever os dois na mesma sentada faz a pessoa
inventar sem perceber os casos que o próprio prompt dela já resolve.

Ela cobrou três vezes, e as três viraram decisão:

1. **Três padrões planejados não eram escrevíveis.** O semgrep não dispara neles, então não
   são casos difíceis — são casos ausentes, e passariam no placar como acerto. O
   `congelar.py` falha alto quando o alvo não casa, exatamente por isso (**D21**).
2. **O alvo precisou nomear a regra**, não só arquivo e linha: a linha 12 do `sqli-direto`
   acumula três achados de severidades diferentes, e sem a regra o corpus mediria o que o
   semgrep listasse primeiro.
3. **Apareceu um viés de medição no par difícil**: ele pedia 2 passos no vulnerável e 5 no
   falso-positivo, e estouro de orçamento bloqueia — o corpus acertaria um e erraria o outro
   **por construção**, medindo o teto de passos em vez do agente. A cadeia dos dois foi
   igualada.

## P14 — Ler o corpus pronto derrubou quatro casos e duas premissas

**18/08/2026.** A revisão caso a caso — feita depois de o corpus existir e antes de qualquer
medição — produziu **D25, D26, D27 e D28**. O que elas têm em comum vale registrar junto:

**Todas nasceram de olhar, não de rodar.** Nenhuma exigiu cota. O corpus se pagou antes de
a primeira chamada ao modelo acontecer, o que é o argumento mais forte a favor da D12 que o
projeto tem.

**Duas derrubaram coisas que pareciam prontas:**

- A **D26** removeu quatro casos e descobriu que o formulário do agente não serve para todo
  achado. Num segredo escrito no código, a resposta honesta a *"isso vem de fora?"* é `nao`,
  **que silencia** — um agente raciocinando corretamente soltaria uma credencial de produção.
  O corpus lia isso como *"sabe distinguir fixture de produção"*, que ele não sabe, porque
  ninguém perguntou.
- A **D27** virou o gabarito de um caso: o dado e a prosa se contradiziam, e a prosa estava
  errada. O argumento que fechou não é sobre o caso — é que "procurei o chamador e não achei"
  é **ausência de evidência**, e não sobrevive a import dinâmico, entry point ou decorador.

**Uma achou o buraco por onde o atacante entra.** A **D25**: a §4 tratava injeção como
problema de *texto*, e ela é também de **canal** — a saída de ferramenta entrava como
mensagem `user`, o mesmo papel do operador, sem moldura.

**E uma fez a conta que ninguém tinha feito.** A **D28**: *quanto tira um agente que não faz
nada?* A resposta — recall perfeito e zero falso-negativo — invalidou o critério de aceite
que estava escrito.

## P15 — O aceite deixa de ser prosa

**18/08/2026.** Fecha o marco 2 do lado da medição, e tem uma reversão minha no meio que
vale registrar.

**O alarme falso.** Eu avisei que o aceite deixava um agente regredir e passar: 14/22
aprovado, abaixo dos 15/22 do agente nulo. **Estava errado.** Para caso vulnerável,
`veredito_certo` é a mesma condição que `not falso_negativo` — então zero falso-negativo já
obriga 15 acertos, e o mínimo de ruído obriga mais 4. O piso de 19 já existia, derivado. O
buraco era real **antes** da mudança que fez o critério de falso-negativo valer para o corpus
todo, e eu não refiz a conta depois de fechá-lo.

**O que era problema de verdade:** o critério de aceite existia **só em prosa**. O `rodar.py`
saía com 0 mesmo reprovando, e somar as colunas era trabalho de quem lesse. O próprio
docstring do `placar.py` diz que *"critério de aceite sem teste reporta número bonito sem
avisar"* — e era o que acontecia com o critério em si.

Três mudanças saíram disso:

| Mudança | Por quê |
|---|---|
| `aceite()` em código, placar imprime `APROVADO`/`REPROVADO`, `rodar.py` sai com 3 | Critério que depende de alguém somar coluna a olho é intenção, não critério |
| **Ruído removido só conta pelo motivo certo** | Em `sqli-constante` o modelo pode calar apontando uma "sanitização" no arquivo do enum — existe, passa no `prova_valida`, não sanitiza nada. Contando só o veredito, esse acerto pagava igual ao de quem entendeu. **Não é limiar novo:** é exigir que duas colunas que já existiam concordem |
| Mínimo de ruído vira **fração** dos falso-positivos | `>= 4` é exigente com 7 e trivial com 20. Número fixo é o que envelheceu no `> 12/20` |

**O piso de veredito ficou, e é redundante de propósito.** Ele nunca reprova sozinho — cai
exatamente onde os outros dois critérios já colocavam o mínimo. A redundância é a rede: se
alguém afrouxar o critério de falso-negativo, o piso passa a ser o que segura, em tempo de
execução e sobre os dados reais. Há teste guardando a relação, e ele quebra no dia em que ela
mudar.

**Ancorado no agente nulo, não num número.** `base + mínimo de ruído`, e não `>= 19`: número
fixo apodrece na próxima mudança de tamanho do corpus, que foi literalmente o destino do
`> 12/20`.

---

## Regras de trabalho

### Nenhum indício de IA no repositório

**Pedido explicitamente em 11/08/2026.** Vale para commits, merges, PRs, issues e qualquer
arquivo versionado:

- **sem** trailer `Co-Authored-By:`
- **sem** linha de link de sessão
- **sem** `🤖 Generated with ...` em corpo de PR
- **sem** comentário, README ou doc atribuindo autoria a assistente

**Porquê:** os repositórios são portfólio para vaga de DevOps/Cloud e vão ser apresentados em
entrevista. As decisões de arquitetura são do usuário; a IA atua como consultora que apresenta
opções. Atribuição de co-autoria não representa como o trabalho foi feito.

### Arquivo feito para IA não entra no versionamento

A regra acima tem uma consequência estrutural: **o `ARQUITETURA.md` tinha uma §10 chamada
"Prompt para sessão nova"** — um prompt escrito para ser colado numa IA. Isso é exatamente o
tipo de arquivo que não pode aparecer num repositório apresentado em entrevista.

**Resolvido assim:**

| Arquivo | Onde vive | Versionado? |
|---|---|---|
| `ARQUITETURA.md` | raiz | ✅ sim — feito para humano |
| `docs/justificativas.md` | `docs/` | ✅ sim — feito para humano (e para entrevista) |
| **`.local/prompt-sessao.md`** | `.local/` | ❌ **não** — `.gitignore` |
| `CLAUDE.md`, `AGENTS.md`, `.claude/` | — | ❌ não — `.gitignore` |

O `.gitignore` nasce cobrindo `.local/`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` e `.claude/`,
junto com os segredos que a D11 exige.

---

## Estado da consolidação

**Feita em 11/08/2026.** O `ARQUITETURA.md` foi reescrito por inteiro:

| Mudança | Onde |
|---|---|
| `gate` → `aduana` em todo o documento (e `aduana` → `pra` em 13/08) | tudo |
| Fluxo redesenhado: buscadora → S3 → Fargate → S3 → publicadora | §1, §7 |
| Harness com 2 ferramentas e as negativas corrigidas | §3 |
| Separação de privilégio e nota "qual NÃO é a ameaça" | §4 |
| **D2 revisada** (frota) + correção do "triplica as ferramentas" | §5 |
| **D10b** — webhook trata `push` | §5 |
| **D14–D19** — as seis decisões novas | §5 |
| 3 atributos de qualidade novos | §6 |
| Árvore com `buscador/`, `publicador/`, `pacotes/`; sem `clone.py` | §7 |
| Ordem de construção com horas, 8 passos, sem pré-requisito | §8 |
| Conta com S3 e as armadilhas de VPC/endpoint | §9 |
| §10 "Prompt para sessão nova" **removida** → `.local/prompt-sessao.md` | — |
| §11 virou §10, só com o que sobrou aberto | §10 |

**Pendência conhecida em 11/08:** a pasta no disco ainda era `/home/gabhriel/projects/gate`.
Resolvida na renomeação de 13/08; hoje a pendência equivalente é a pasta ainda dizer
`portcullis` depois da troca para `PRA` — ver P1.

---

## Segunda consolidação — 18/08/2026

O `ARQUITETURA.md` foi emendado, não reescrito: decisão contrariada pela realidade ganha
emenda datada em vez de sumir. Um documento que se reescreve para sempre parecer certo perde
a única coisa que ele tem de valioso.

| Mudança | Onde |
|---|---|
| Emendas datadas na D3, D5, D6, D8 e D14 — o que a construção contrariou | §5 |
| **D20–D28** — o agente fora da VPC, o marco 2 e a revisão do corpus | §5 |
| Alvo de "análise < 5 min" **desmentido por medição** e revisto para 15 min | §6 |
| Diagrama refeito: mostrava Fargate e quatro Lambdas; são seis Lambdas | §7 |
| Ordem de construção do marco 2, com a armadilha do viés de medição | §8 |
| GB-s corrigidos — a estimativa errava por duas ordens de grandeza | §9 |
| Custo do ECR medido (270 MB compactados) em vez de estimado três vezes diferente | §9 |
| Pendências 1 e 2 fechadas; entra o que falta medir | §10 |

**O que este documento tem e o `ARQUITETURA.md` não:** as reversões. A aposta errada no
provedor (P9), o orçamento que voltou para fora do Terraform (P11), o gabarito que virou
(P14) e o alarme falso sobre o piso (P15). O consolidado guarda a decisão; aqui fica o
caminho torto que levou até ela.
