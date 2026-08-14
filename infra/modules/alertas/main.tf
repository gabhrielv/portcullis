# Alarme sem destinatário não avisa nada. A assinatura por e-mail precisa ser
# confirmada uma vez, pelo link que a AWS manda.
resource "aws_sns_topic" "alertas" {
  name = "${var.prefixo}-alertas"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alertas.arn
  protocol  = "email"
  endpoint  = var.email_alertas
}

# O teto de gasto da conta NÃO mora aqui, de propósito. Ver a nota no README:
# orçamento gerenciado por este stack sumiria no `terraform destroy`, que é
# como toda sessão de trabalho termina — a rede de proteção ficaria ausente
# justamente enquanto ninguém está olhando. Ele vive fora, junto do bucket de
# state e dos segredos do SSM, na categoria "guarda-corpo permanente da conta".
