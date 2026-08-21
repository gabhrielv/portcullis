"""Achados que o portão não bloqueia.

Mora no repositório do pra, e não no repositório analisado: quem abre um PR
no alvo não alcança este arquivo. É a válvula de escape que substitui o
`# nosemgrep`, desligado de propósito em `analisador/semgrep.py`.

**Toda exceção diz por quê, e o porquê aponta para uma decisão.** Sem isso,
daqui a três meses ninguém distingue "dispensado por decisão" de "dispensado
por preguiça" — e a lista vira o `# nosemgrep` que ela substituiu.

**Só entra aqui o que é política deliberada.** Achado que expõe lacuna real
fica de fora, mesmo incomodando: assim uma ocorrência NOVA bloqueia. Usar a
válvula para o que ainda não foi decidido é esconder, não silenciar.

Escopo por repositório chega com o `.pra.yml` da D18, no marco 4.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Excecao:
    """`prefixo` vazio vale para o repositório inteiro — política de IaC não
    tem local, ao contrário de um segredo falso dentro de uma pasta de teste."""

    regra: str
    prefixo: str
    porque: str


EXCECOES: tuple[Excecao, ...] = (
    Excecao(
        "python.jwt.security.jwt-hardcode.jwt-python-hardcoded-secret",
        "backend/tests/",
        "Segredo falso dentro do teste que verifica a checagem de segredo.",
    ),
    # --- Checkov: retenção e observabilidade -------------------------------
    Excecao(
        "CKV_AWS_338",
        "infra/",
        "Exige log de 1 ano; a regra do projeto é `retention_in_days = 1`. "
        "O registro que precisa durar é a auditoria no DynamoDB, não o log.",
    ),
    Excecao(
        "CKV_AWS_76",
        "infra/",
        "Log de acesso no API Gateway foi decidido contra na T7: custa "
        "CloudWatch e não diz nada que o log da Lambda não diga.",
    ),
    Excecao(
        "CKV_AWS_50",
        "infra/",
        "X-Ray cobra por trace. O tempo de parede já é medido pelo REPORT de "
        "cada Lambda, que é grátis.",
    ),
    # --- Checkov: a arquitetura da D20 -------------------------------------
    Excecao(
        "CKV_AWS_117",
        "infra/",
        "Exige toda Lambda dentro da VPC. É o oposto da D20/G5: as que falam "
        "com a internet ficam FORA de propósito, porque colocá-las dentro "
        "exigiria NAT Gateway (~US$32/mês). O analisador, que não fala com "
        "ninguém, está dentro — e é a única que precisa estar.",
    ),
    Excecao(
        "CKV_AWS_290",
        "infra/modules/analisador/",
        "Acusa `Resource = \"*\"` nas ações de ENI. É exigência da AWS para "
        "Lambda em VPC: a função gerencia a própria interface de rede, e "
        "essas três ações não aceitam ARN específico.",
    ),
    Excecao(
        "CKV_AWS_355",
        "infra/modules/analisador/",
        "Mesma causa do CKV_AWS_290: as ações de ENI exigem `Resource = \"*\"`.",
    ),
    # --- Checkov: limites da conta, medidos --------------------------------
    Excecao(
        "CKV_AWS_115",
        "infra/",
        "Exige concorrência reservada. Medido em 13/08/2026: o limite da "
        "conta é 10, e a AWS recusa qualquer reserva que deixe menos de 100 "
        "livres — ou seja, recusa todas. O teto da conta já é o teto de rajada.",
    ),
    # --- Checkov: chave gerenciada pelo cliente ----------------------------
    # As sete abaixo pedem CMK onde a criptografia padrão da AWS já está
    # ligada. Cada chave custa ~US$1/mês, e são sete recursos distintos: o
    # custo zero morreria para trocar criptografia gerenciada pela AWS por
    # criptografia gerenciada por nós, sem mudança de modelo de ameaça.
    Excecao("CKV_AWS_26", "infra/", "CMK no SNS; a criptografia padrão já cobre."),
    Excecao("CKV_AWS_136", "infra/", "CMK no ECR; a criptografia padrão já cobre."),
    Excecao("CKV_AWS_158", "infra/", "CMK no CloudWatch; log tem retenção de 1 dia."),
    Excecao("CKV_AWS_119", "infra/", "CMK no DynamoDB; a criptografia padrão já cobre."),
    Excecao("CKV_AWS_145", "infra/", "CMK no S3; a criptografia padrão já cobre."),
    Excecao("CKV_AWS_27", "infra/", "CMK no SQS; a mensagem é um ponteiro, não dado."),
    Excecao(
        "CKV_AWS_173",
        "infra/",
        "CMK nas variáveis de ambiente da Lambda. Elas carregam NOMES de "
        "parâmetro do SSM, nunca valores — é a G2, e não há segredo ali.",
    ),
    # --- Checkov: o pacote é descartável -----------------------------------
    # O bucket guarda tarball e evidência com retenção de 1 dia. Versionar,
    # replicar entre regiões e auditar acesso a dado que morre em 24 h é
    # pagar por durabilidade que o desenho não quer.
    Excecao("CKV_AWS_21", "infra/", "Versionamento no bucket de pacotes descartáveis."),
    Excecao("CKV_AWS_144", "infra/", "Replicação entre regiões de dado que vive 1 dia."),
    Excecao("CKV_AWS_18", "infra/", "Log de acesso ao S3; custa mais que o dado vale."),
    Excecao(
        "CKV_AWS_51",
        "infra/",
        "Exige tag imutável no ECR. A política de ciclo de vida guarda 1 "
        "imagem e a tag `local` é reescrita a cada push, de propósito.",
    ),
)


def silenciado(regra: str, caminho: str) -> bool:
    return any(
        regra == excecao.regra and caminho.startswith(excecao.prefixo)
        for excecao in EXCECOES
    )
