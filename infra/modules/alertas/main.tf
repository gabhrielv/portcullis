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
