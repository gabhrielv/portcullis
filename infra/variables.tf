variable "prefixo" {
  type    = string
  default = "portcullis"
}

variable "regiao" {
  type    = string
  default = "us-east-1"
}

variable "email_alertas" {
  type        = string
  description = "Recebe o alarme da fila de mensagens mortas. Confirme a assinatura no e-mail."
}

# Não é segredo: identifica o App publicamente. Quem é segredo é a chave
# privada, e ela vive no SSM, nunca aqui nem no tfstate.
variable "github_app_id" {
  type        = string
  description = "App ID do GitHub App, visto na tela de configuração dele."
}

# `-1` = sem reserva. Medido em 13/08/2026: esta conta tem limite de
# concorrência de 10, e a AWS recusa qualquer reserva que deixe menos de 100
# execuções livres — ou seja, recusa todas. Não é perda de proteção: com teto
# de 10 na conta inteira, o limite da conta já é o teto de rajada que a reserva
# daria. Se o limite subir para 1000 (Service Quotas, aumento gratuito), volte
# para 5 e a reserva passa a valer por função.
variable "concorrencia_webhook" {
  type    = number
  default = -1
}
