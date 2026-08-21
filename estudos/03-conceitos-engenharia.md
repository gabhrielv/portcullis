# Conceitos de engenharia por trás do plano

Por que o `docs/plano-marco-1.md` está na ordem em que está, e por que certas escolhas de
código não são estilo — são consequência.

---

## 1. Por que o plano começa pela regra, e não pela infraestrutura

A ordem óbvia seria "sobe a AWS, depois escreve o código". O plano faz o contrário: as
Tarefas 1 a 5 (**metade do marco**) não tocam em AWS nenhuma.

O motivo é **redução do espaço de busca**.

```
código não testado  +  infra não testada  =  quebrou. onde?
                                              → 2 suspeitos, e eles interagem

código testado      +  infra não testada  =  quebrou. é a infra.
                                              → 1 suspeito
```

Quando você chega na Tarefa 6 já sabendo que a regra está certa, todo erro dali pra frente é
de configuração. Isso não economiza 10% do tempo — economiza as tardes inteiras em que você
mexe no IAM porque desconfia dele, e o bug estava num `if`.

> **O padrão geral:** ordene o trabalho de forma que, quando algo quebrar, sobre **um**
> suspeito. Vale pra depuração, pra migração e pra deploy.

---

## 2. TDD — e por que aqui ele não é ideologia

O ciclo:

```
1. escreve o teste que falha
2. RODA e confirma que falha           ← o passo que todo mundo pula
3. escreve o mínimo pra passar
4. roda e confirma que passa
5. commita
```

### O passo 2 é o que dá valor

Teste que você nunca viu falhar **não é teste, é decoração**. O caso clássico:

```python
def test_bloqueia_achado_novo():
    v = decidir([achado(88)], contexto_com_linha_88_tocada())
    assert v.estado is EstadoVeredito.BLOQUEADO
```

Se você escreveu isso depois da implementação e ele passou de primeira, você não sabe se ele
passa **porque a lógica está certa** ou porque tem um erro de digitação no nome da fixture e
ele está testando o vazio. Vê-lo falhar primeiro prova que ele está olhando pra coisa certa.

### Por que o PRA é bom candidato

A regra de decisão é uma função pura com poucas entradas e saída discreta. TDD brilha
exatamente aí. Nem toda parte do projeto é assim — Terraform não tem esse ciclo, e forçá-lo
lá seria cerimônia. **Use TDD onde ele encaixa; nos outros lugares o critério de aceite é
outro** (o `terraform apply` sobe e o `destroy` derruba limpo).

---

## 3. Função pura — e por que ela resolveu dois problemas de uma vez

### O que é

Uma função é pura quando:

1. a saída depende **só** das entradas
2. ela não mexe em nada fora dela (arquivo, rede, variável global, relógio)

```python
def analisar(dir_entrada: Path, dir_saida: Path) -> Path:   # ~pura
def decidir(achados, contexto) -> Veredito:                 # pura
```

### Por que importa aqui

A decisão D14 tirou o token do GitHub de dentro do container **por segurança**. O efeito
colateral foi o container virar função pura — e isso comprou **testabilidade** de graça:

| Consequência | Ganho |
|---|---|
| Não tem token do GitHub | ✅ segurança |
| Não emite veredito | ✅ segurança (injeção não tem alvo) |
| Só lê pacote e escreve JSON | ✅ **testável offline, sem AWS e sem mock** |
| Mesmo comportamento local e na nuvem | ✅ **o corpus da D12 roda em segundos** |

> 🔑 Quando uma decisão de segurança melhora a testabilidade — ou o contrário — isso é sinal
> de que você achou uma boa fronteira. **Fronteira boa melhora várias coisas ao mesmo tempo;
> fronteira ruim obriga a escolher.**

### O invólucro de I/O

O container precisa falar com o S3 em algum momento. A solução é empurrar a impureza pra
casca fina:

```python
def analisar(entrada, saida):     # PURA — o corpus chama esta
    ...

def principal_s3():               # IMPURA — só o Fargate chama esta
    baixa_do_s3(...)
    analisar(entrada, saida)
    sobe_pro_s3(...)
```

Isso se chama **núcleo funcional, casca imperativa**. A lógica fica testável; a I/O fica num
lugar pequeno o suficiente pra você conferir a olho.

---

## 4. Pirâmide de testes

```
        ╱  3 casos como PR de verdade      lentos, frágeis, fiéis
       ╱────
      ╱  container local com pacote montado à mão
     ╱──────────
    ╱  20 casos do corpus, offline
   ╱────────────────
  ╱  testes unitários: regra, parser, HMAC, pacote
 ╱──────────────────────────  rápidos, estáveis, específicos
```

A regra: **quanto mais alto, menos casos.** Não porque os de cima sejam ruins, mas porque
custam caro (minutos, cota, rede instável) e falham por motivos que não são o seu código.

A D12 aplica exatamente isso: 20 casos rodam offline em segundos, e só **3** viram PR de
verdade. Você roda os 20 vinte vezes por dia; os 3, uma vez por marco.

> **O antipadrão** é a pirâmide invertida: quase tudo em teste ponta a ponta. Aí a suíte leva
> 40 minutos, falha aleatoriamente por rede, e todo mundo aprende a ignorar o vermelho — o
> mesmo modo de falha da D15, em outra roupa.

---

## 5. Idempotência e entrega ao menos uma vez

### O contrato que você não escolhe

Sistemas distribuídos entregam mensagem **ao menos uma vez**. "Exatamente uma vez" ou não
existe, ou custa caro, ou é mentira de marketing.

O motivo é simples: o consumidor processou e morreu antes de confirmar. O produtor não tem
como saber se foi antes ou depois. Só existem duas escolhas ruins — reenviar (pode duplicar)
ou não reenviar (pode perder). O SQS escolhe duplicar.

### A pergunta certa

Não é *"como evito duplicata?"* — é:

> **"Qual é a minha chave de deduplicação, e o que acontece se a operação rodar duas vezes?"**

No PRA a chave é óbvia e estável: **o SHA do commit**. Analisar o mesmo SHA duas vezes dá o
mesmo resultado; o desperdício é dinheiro, não corretude.

### Duas formas de lidar

```python
# barata, com janela de corrida (TOCTOU)
if ja_existe(saida): return

# correta, atômica
put_item(..., ConditionExpression="attribute_not_exists(sha)")
```

A primeira tem uma janela entre verificar e agir. É a mesma família de bug de
`if not os.path.exists(x): criar(x)` — entre o `if` e o `criar`, outro processo pode ter
criado. Aceitar essa janela é legítimo; **não perceber que ela existe, não.**

---

## 6. Fatia vertical vs construção em largura

```
LARGURA (o jeito que mata projeto)
  4 scanners integrados, nenhum rodando de ponta a ponta
  Terraform escrito, nunca aplicado
  4 semanas, nada demonstrável

VERTICAL (o jeito do plano)
  1 scanner, 1 repositório, atravessando TODAS as camadas
  2 semanas, o botão de merge fica cinza num PR de verdade
```

A fatia vertical é pior em cobertura e melhor em **informação**: ela força você a encontrar os
problemas de integração cedo, quando ainda são baratos. Os problemas que matam projeto quase
nunca estão dentro de um componente — estão entre dois.

E tem o efeito prático que a D19 explora: **cada marco é gravável**. Se aparecer uma vaga no
meio do marco 2, o marco 1 está pronto pra mostrar.

---

## 7. Teste de arquitetura

O `test_arquitetura.py` do plano não testa comportamento — testa **estrutura**:

```python
def test_analisador_nao_importa_github_nem_decisao():
    for arquivo in PASTA_ANALISADOR.rglob("*.py"):
        assert "pra.github" not in arquivo.read_text()
```

Ele existe porque a decisão D14 (o container não fala com o GitHub) é fácil de violar sem
querer: seis meses depois, alguém precisa de uma informação, escreve um `import`, e a
separação de privilégio some sem ninguém notar.

> **Regra arquitetural que não é verificada vira comentário desatualizado.** Se a regra
> importa, transforme-a em teste — 8 linhas, e ela para de depender de disciplina.

Isso tem nome na literatura: *fitness function* (Building Evolutionary Architectures). Outros
exemplos: "nenhum módulo de domínio importa framework web", "nenhuma query fora da camada de
repositório".

---

## 8. Contrato explícito entre componentes

O `contexto.json` não é um detalhe de serialização. É **o contrato** entre a buscadora e o
analisador — e é ele que permite:

```
corpus (D12)  →  monta um contexto.json na mão  →  chama analisar()
                 sem GitHub, sem AWS, sem rede
```

Se o analisador recebesse "a URL do repositório", o corpus precisaria de um GitHub falso. Como
ele recebe **um pacote de arquivos**, o corpus só precisa de arquivos.

> **O teste de uma boa fronteira:** consigo exercitar o lado de cá sem levantar o lado de lá?
> Se a resposta for não, o contrato está vazando implementação.

---

## 9. Por que `frozen=True` nos dataclasses

```python
@dataclass(frozen=True)
class Achado: ...
```

Objeto imutável não muda depois de criado. Ganhos concretos aqui:

- Um `Achado` que atravessa `semgrep → regra → checks` **é o mesmo objeto o tempo todo**.
  Nenhuma função no meio do caminho pode "consertar" um campo em silêncio.
- Pode ser usado em `set` e como chave de `dict`.
- Comparação por valor de graça — é o que faz `test_contexto_sobrevive_a_ida_e_volta_em_json`
  ser um `assert lido == original` de uma linha.

O custo é ter que criar objeto novo pra "mudar" algo. Num sistema que só transforma dados de
uma forma em outra, isso não é custo — é como o trabalho já é.

---

## 10. Erro como valor vs erro como exceção

O analisador **não** lança exceção quando o Semgrep falha:

```python
resultado = {"ok": False, "erro": "semgrep saiu com 2", "achados": []}
```

O motivo é a fronteira de processo. Um container que morre com stack trace deixa a publicadora
sem informação nenhuma — ela só vê que o `achados.json` nunca apareceu, e não sabe dizer por
quê.

```
exceção        → morre dentro do processo, some na fronteira
erro em valor  → atravessa a fronteira, vira `action_required` com mensagem
```

> **A regra:** exceção é ótima **dentro** de um processo. Atravessando fronteira — container,
> fila, HTTP — o erro precisa virar dado. Isso é a mesma razão de HTTP ter código de status em
> vez de "a conexão simplesmente cai".

---

## 11. Backpressure

Uma fila entre o recebimento e o trabalho pesado faz **duas** coisas, e a segunda é a que
quase todo mundo esquece:

1. **Desacopla o tempo** — o webhook responde em 200 ms, o trabalho leva minutos
2. **Absorve rajada** — 20 eventos viram 20 mensagens esperando, não 20 tasks simultâneas

A segunda só funciona se existir **teto do outro lado** (`reserved_concurrent_executions`).
Sem teto, a fila só repassa o pico e você paga por ele.

> **Sistema sem ponto de backpressure converte todo pico de entrada em pico de custo.** Numa
> conta pessoal, essa frase vale dinheiro de verdade.

---

## 12. Como saber que terminou

A D19 define pronto como três coisas juntas: rodando, README com número, gravação de 60–90 s.

Sem prazo, o risco não é ficar sem tempo — é **nunca ter um pronto**. Sempre dá pra melhorar
mais um pouco, e "quase pronto" pode durar seis semanas.

A gravação é a parte esperta da definição, porque ela é **binária**: ou você consegue mostrar
o fluxo inteiro em 90 segundos, ou não consegue. E tentar gravar revela na hora tudo que ainda
depende de você abrir um terminal e rodar três comandos na mão.

> **Um critério de pronto que dá pra discutir não é critério.** "Está bom" é opinião;
> "o vídeo existe" é fato.
