data "aws_region" "atual" {}
data "aws_caller_identity" "atual" {}

locals {
  # Só os parâmetros do projeto, não o Parameter Store inteiro.
  arn_parametros = "arn:aws:ssm:${data.aws_region.atual.region}:${data.aws_caller_identity.atual.account_id}:parameter/portcullis/github/*"
}

# Esta Lambda fica FORA da VPC. Dentro, alcançar o SSM exigiria NAT Gateway
# (~US$32/mês) ou interface endpoint (~US$7,20/mês por AZ). Quem mora dentro da
# VPC é só o analisador, que não fala com serviço nenhum além do S3.
resource "aws_iam_role" "webhook" {
  name = "${var.prefixo}-webhook"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Escrita na mão em vez de política gerenciada: ela pode escrever NESTA fila,
# ler ESTES parâmetros e gravar NESTE grupo de log. Mais nada. A gerenciada
# AWSLambdaBasicExecutionRole daria log em qualquer grupo da conta.
resource "aws_iam_role_policy" "webhook" {
  name = "${var.prefixo}-webhook"
  role = aws_iam_role.webhook.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = var.arn_fila
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = local.arn_parametros
      },
      {
        # Sem `logs:CreateLogGroup`: o grupo é criado pelo Terraform abaixo, com
        # retenção definida. Se a Lambda pudesse criá-lo, criaria com retenção
        # infinita no dia em que alguém apagasse o grupo.
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.webhook.arn}:*"
      },
    ]
  })
}

# Declarado antes da função: se a Lambda for invocada primeiro, ela cria o
# grupo sozinha com retenção infinita, e o apply seguinte falha com
# "already exists". `1` porque log de webhook só serve para depurar hoje;
# nunca `0`, que no Terraform significa "para sempre".
resource "aws_cloudwatch_log_group" "webhook" {
  name              = "/aws/lambda/${var.prefixo}-webhook"
  retention_in_days = 1
}

resource "aws_lambda_function" "webhook" {
  function_name = "${var.prefixo}-webhook"
  role          = aws_iam_role.webhook.arn
  handler       = "portcullis.webhook.handler.lambda_handler"
  runtime       = "python3.12"
  filename      = var.caminho_zip
  # Sem isto o Terraform não percebe que o código mudou e não redeploya.
  source_code_hash = filebase64sha256(var.caminho_zip)

  # O GitHub desiste da entrega em ~10 s. A memória não é por CPU — é para o
  # cold start (importar boto3 e ler o SSM) caber nesse orçamento.
  timeout     = 10
  memory_size = 256

  # Teto de rajada: o excedente é recusado em vez de virar fatura. O GitHub não
  # reenvia webhook recusado, então a análise não acontece — mas o Check Run
  # nunca reporta e o merge segue travado. Falha fechada.
  reserved_concurrent_executions = var.concorrencia_webhook

  environment {
    variables = {
      PORTCULLIS_FILA_URL              = var.url_fila
      PORTCULLIS_PARAM_SEGREDO_WEBHOOK = "/portcullis/github/segredo-webhook"
    }
  }

  depends_on = [aws_cloudwatch_log_group.webhook]
}

resource "aws_apigatewayv2_api" "principal" {
  name          = "${var.prefixo}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "webhook" {
  api_id           = aws_apigatewayv2_api.principal.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.webhook.invoke_arn
  # A 2.0 é a que entrega `isBase64Encoded` e cabeçalhos em minúsculo — o
  # handler depende dos dois.
  payload_format_version = "2.0"
}

# Rota única e explícita: não existe `$default`, então qualquer outro caminho
# devolve 404 sem acordar a Lambda.
resource "aws_apigatewayv2_route" "webhook" {
  api_id    = aws_apigatewayv2_api.principal.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.webhook.id}"
}

resource "aws_apigatewayv2_stage" "padrao" {
  api_id      = aws_apigatewayv2_api.principal.id
  name        = "$default"
  auto_deploy = true

  # Recusa na porta, antes de a Lambda existir. O padrão da conta é 10.000/s;
  # o tráfego real é um punhado de eventos por dia.
  default_route_settings {
    throttling_rate_limit  = 10
    throttling_burst_limit = 20
  }
}

# Sem isto o API Gateway recebe 403 da Lambda: a permissão de invocar mora na
# função, não na API.
resource "aws_lambda_permission" "api" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.principal.execution_arn}/*/*"
}
