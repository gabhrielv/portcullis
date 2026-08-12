# Sem fila de mensagens mortas, uma mensagem que sempre falha é reprocessada
# para sempre — e cada tentativa dispara uma análise.
resource "aws_sqs_queue" "mortas" {
  name                      = "${var.prefixo}-mortas"
  message_retention_seconds = 1209600 # 14 dias, o máximo
}

resource "aws_sqs_queue" "analises" {
  name = "${var.prefixo}-analises"

  # Precisa ser MAIOR que o timeout da buscadora, senão o SQS reentrega a
  # mensagem enquanto a primeira execução ainda está rodando.
  visibility_timeout_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.mortas.arn
    maxReceiveCount     = 3
  })
}

resource "aws_cloudwatch_metric_alarm" "mortas" {
  alarm_name          = "${var.prefixo}-mortas"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.mortas.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_description   = "Analise que falhou 3 vezes e foi descartada"
  alarm_actions       = [var.arn_topico_alertas]
}
