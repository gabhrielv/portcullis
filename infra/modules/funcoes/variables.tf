variable "prefixo" { type = string }
variable "caminho_zip" { type = string }

variable "url_fila" { type = string }
variable "arn_fila" { type = string }

# Consumidas pelas Lambdas das tarefas 8, 9 e 10. Declaradas agora para o
# wiring do main.tf não precisar mudar quando elas chegarem.
variable "arn_bucket_pacotes" { type = string }
variable "nome_bucket_pacotes" { type = string }
variable "arn_tabela" { type = string }
variable "nome_tabela" { type = string }
variable "github_app_id" { type = string }

# Teto de rajada. Conta nova da AWS às vezes vem com limite de concorrência de
# 10 em vez de 1000, e aí QUALQUER reserva é recusada — a AWS exige deixar 100
# sem reservar. Se o apply falhar com "below its minimum value of [100]",
# ponha -1 aqui: desliga a reserva e mantém o resto de pé.
variable "concorrencia_webhook" {
  type    = number
  default = 5
}

variable "nome_tabela_auditoria" {
  type    = string
  default = ""
}

# A Fatia 2 liga, quando a Lambda do analisador existir. Com o gatilho ligado
# antes disso, a buscadora monta o pacote, falha ao invocar o que não existe, e
# a mensagem roda o ciclo de retentativas até cair na fila de mortas.
variable "gatilho_buscadora_ligado" {
  type    = bool
  default = true
}

variable "concorrencia_buscadora" {
  type    = number
  default = -1
}

variable "arn_topico_alertas" {
  type    = string
  default = ""
}
