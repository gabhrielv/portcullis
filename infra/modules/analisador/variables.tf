variable "prefixo" { type = string }
variable "arn_bucket_pacotes" { type = string }
variable "nome_bucket_pacotes" { type = string }
variable "ids_subnets" { type = list(string) }
variable "id_security_group" { type = string }

# A imagem precisa existir no ECR ANTES de a função ser criada. O primeiro
# apply sobe só o repositório (`make imagem-push` empurra), o segundo cria a
# função. Daí o interruptor.
variable "criar_funcao" {
  type    = bool
  default = false
}

variable "tag_imagem" {
  type    = string
  default = "local"
}

variable "concorrencia" {
  type    = number
  default = -1
}
