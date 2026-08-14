# portcullis

Portão de segurança para CI/CD. Um pull request abre, o código é analisado numa
conta da AWS, e o botão de merge fica cinza se **aquele PR** introduziu um
problema.

A ênfase está em *aquele PR*. Rodar um scanner é fácil; a parte difícil é não
transformar a dívida acumulada do repositório em ruído que todo mundo aprende a
ignorar.

---

## O que ele faz, em uma execução real

Medido no `hoppr`, um repositório Python/FastAPI + Next.js com 16 achados do
Semgrep acumulados:

| PR | achados novos | veredito | merge |
|---|---|---|---|
| altera um arquivo de texto | 0 | `success` — "nenhum achado novo bloqueia" | permitido |
| adiciona uma injeção de SQL | 1 | `failure` — "1 achado novo bloqueia" | **recusado pelo GitHub** |

Nos dois casos os 16 achados pré-existentes aparecem no resumo, recolhidos, e
**não** bloqueiam. Um portão que reprovasse os 16 seria desligado na primeira
semana — e um portão desligado protege menos que nenhum, porque dá a impressão
de que alguém está olhando.

---

## Desenho

```
PR ou push na main
   │
   ├─▶ API Gateway ─▶ Lambda webhook      valida HMAC, enfileira, responde <10s
   │                        │
   │                     SQS │  absorve rajada; é o ponto de backpressure
   │                        ▼
   │                  Lambda buscadora    TEM o token do GitHub
   │                        │             baixa o tarball, monta o pacote no S3
   │                        ▼
   │                  Lambda analisador   NÃO tem token, NÃO tem rota de saída
   │                        │             roda o Semgrep, escreve achados.json
   │                        ▼
   │                  Lambda publicadora  aplica a regra, publica o Check Run,
   │                        │             grava a auditoria no DynamoDB
   │                        ▼
   └─────────────────  Check Run + proteção de branch  ──▶ merge travado

deploy ─▶ GET /veredito/{owner}/{repo}/{sha} ─▶ Lambda consulta ─▶ 200 | 403 | 404
```

### Separação de privilégio

A peça que lê código de terceiros é a que tem menos poder no sistema:

| | buscadora | analisador |
|---|---|---|
| token do GitHub | tem | **não tem** |
| rota para a internet | tem (fora da VPC) | **nenhuma** |
| S3 | escreve em `entrada/` | lê `entrada/`, escreve `saida/` |
| lê o código baixado | **não** | sim |

O analisador vive numa subnet sem *internet gateway* — não existe rota para
lugar nenhum além do endpoint do S3, e a única regra de saída do security group
aponta para o prefix list da S3 na porta 443. Isso não é prosa: é `terraform
plan` que qualquer pessoa pode ler.

E é verificável antes de existir AWS. A imagem roda com
`docker run --network=none --read-only --tmpfs /tmp` na sua máquina.

---

## Por que Lambda e não Fargate

O documento de arquitetura deste projeto diz Fargate. O código diz Lambda com
imagem de container. A troca foi deliberada, e o motivo é custo.

O Fargate era o **único item pago** do desenho: ~US$0,01 por análise, cobrado
por segundo, sem franquia. A Lambda tem 400.000 GB-s por mês na franquia
**permanente** — não é o "grátis por 12 meses" que expira.

Medido: 247 s por análise a 1769 MB = **438 GB-s**. A franquia cobre ~900
análises por mês, contra as ~30 esperadas.

De brinde, o isolamento ficou **mais forte**. O Fargate precisava de subnet
pública com egress 443 aberto para alcançar o ECR e o CloudWatch — o container
teria rota para `github.com`, e a promessa de isolamento dependeria de ele não
ter credencial. A Lambda busca a imagem pela infraestrutura do serviço, fora da
VPC, então a função pode ficar numa subnet sem rota nenhuma.

### Por que 1769 MB

É onde a Lambda entrega uma vCPU inteira. Abaixo disso a CPU é estrangulada e o
trabalho demora proporcionalmente mais: o custo em GB-s dá no mesmo e só a
latência piora. Acima, paga-se por uma segunda vCPU que o Semgrep não usa,
porque é monotarefa. Pico de memória medido: 695 MB.

---

## A política do portão

Achado conta como **novo** quando cai numa linha que o diff adicionou. É o que
separa "você introduziu isto" de "isto já estava aqui".

```
VERSAO_REGRA = "2"
  ERROR                            → bloqueia
  WARNING com category=security    → bloqueia
  WARNING de outra categoria       → avisa
  achado fora do diff              → resumo, não bloqueia
```

O `WARNING` de segurança bloquear veio de medição, não de opinião: há `WARNING`
com confiança e impacto altos, e `ERROR` com impacto baixo. **A severidade do
Semgrep não mede risco.**

### Onde ele erra para o lado de bloquear

Toda dúvida vira bloqueio, nunca liberação:

- listagem de arquivos do PR truncada no teto de 3.000 do GitHub → tudo conta
  como novo
- arquivo alterado sem campo `patch` (binário, diff grande demais) → o arquivo
  inteiro conta como tocado
- branch nova ou force push, sem base para comparar → tudo conta como novo
- Semgrep falhou → `action_required`, que trava o merge dizendo o motivo
- SHA sem veredito registrado → `404` e o deploy reprova

---

## Limitações conhecidas

Estão aqui porque um portão cujos furos você não sabe listar não é um portão.

**Achado introduzido apagando uma linha passa.** A política olha linhas
adicionadas. Um PR que remove uma validação e com isso torna vulnerável uma
linha que ele não tocou não é pego. O pacote nem carrega as linhas removidas
hoje — fechar isso é gravar o diff junto e comparar os dois lados.

**O endpoint de veredito é aberto.** A resposta é "liberado/bloqueado" para um
SHA que quem pergunta já conhece, e ela nunca lista o que foi encontrado. Vira
dívida quando o portão passar a cobrir repositório que não é meu.

**Um só scanner.** Não existe `scanners/base.py`, e isso é deliberado: inventar
uma taxonomia comum com um único scanner seria adivinhar o mapeamento certo
para scanners que ainda não existem.

**A análise leva ~4 minutos.** O Semgrep é ~2,2× mais lento numa vCPU da Lambda
que num núcleo de desktop. O Check Run abre como `in_progress` para o PR não
ficar mudo nesse tempo.

---

## Custo

O projeto foi construído para custar **US$ 0,00**, e custa.

| serviço | franquia | uso |
|---|---|---|
| Lambda | 400.000 GB-s/mês, permanente | ~13.000 GB-s |
| DynamoDB, S3, SQS, SNS, CloudWatch | permanentes | frações |
| API Gateway | expirada | ~US$0,0001 |
| **ECR** | expirada | **~US$0,04/mês se ficar de pé** |

O ECR é o único recurso que cobra por existir parado. `make destruir` ao fim de
cada sessão o zera — e como o ECR é cobrado por GB-mês rateado por hora, uma
sessão de trabalho custa ~US$0,0004.

Não há NAT Gateway (~US$32/mês), nem interface endpoint (~US$7,20/mês por AZ),
nem IP elástico. O endpoint do S3 é do tipo Gateway, que é grátis.

---

## Rodar

```bash
make instalar          # venv e dependências
make teste             # 163 testes, sem rede
make imagem            # imagem do analisador
```

Demonstração local do analisador, sem AWS e sem GitHub:

```bash
mkdir -p /tmp/pacote/{entrada,saida} && chmod 0777 /tmp/pacote/saida
# monte entrada/codigo.tar.gz e entrada/contexto.json, então:
docker run --rm --network=none --read-only --tmpfs /tmp \
  -v /tmp/pacote/entrada:/entrada:ro -v /tmp/pacote/saida:/saida \
  --entrypoint python portcullis-analisador:local -c \
  "from pathlib import Path; from portcullis.analisador.main import analisar; \
   analisar(Path('/entrada'), Path('/saida'))"
```

O `--network=none` é o ponto: o analisador funciona sem rede nenhuma.

### Na AWS

```bash
make subir       # dois applies (a imagem precisa existir antes da Lambda),
                 # empurra a imagem e aponta o GitHub App para a URL nova
make destruir    # derruba tudo
```

Sobrevivem ao destroy, de propósito: o bucket do state do Terraform, os dois
segredos no SSM e o orçamento de alerta. São guarda-corpos que precisam existir
justamente quando o stack não existe.

---

## Estrutura

```
app/src/portcullis/
├── modelos.py          contratos; não importa AWS nem GitHub
├── decisao/            a regra determinística e as exceções
├── analisador/         função pura: pacote entra, achados saem
├── buscador/           GitHub → pacote no S3
├── github/             JWT do App, token de instalação, Check Run
├── publicador/         regra → Check Run → auditoria
├── consulta/           GET /veredito
└── webhook/            HMAC e filtro de evento

infra/modules/          rede, pacotes, fila, dados, alertas, funcoes, analisador
```

`test_arquitetura.py` garante mecanicamente que o analisador não importe
`portcullis.github` nem `portcullis.decisao` — a separação de privilégio é
verificada por teste, não por disciplina.
