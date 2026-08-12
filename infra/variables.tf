variable "prefixo" {
  type    = string
  default = "aduana"
}

variable "regiao" {
  type    = string
  default = "us-east-1"
}

variable "email_alertas" {
  type        = string
  description = "Recebe alarme de fila de mensagens mortas. Confirme a assinatura no e-mail."
}
