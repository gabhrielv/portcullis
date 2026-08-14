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

# ---------------------------------------------------------------------------
# Buscadora: consome a fila, monta o pacote no S3, dispara a análise.
# Fica FORA da VPC porque fala com o github.com. Ela TEM o token do GitHub e
# NÃO lê o código que baixa — o analisador lê o código e não tem token. Separar
# as duas coisas é a defesa; juntá-las numa função só a desfaz.
# ---------------------------------------------------------------------------

locals {
  arn_analisador = "arn:aws:lambda:${data.aws_region.atual.region}:${data.aws_caller_identity.atual.account_id}:function:${var.prefixo}-analisador"
}

resource "aws_iam_role" "buscadora" {
  name = "${var.prefixo}-buscadora"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "buscadora" {
  name = "${var.prefixo}-buscadora"
  role = aws_iam_role.buscadora.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.arn_fila
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = local.arn_parametros
      },
      {
        # Escreve só no prefixo de entrada. O resultado da análise mora em
        # `saida/`, e quem escreve lá é o analisador.
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${var.arn_bucket_pacotes}/entrada/*"
      },
      {
        # Só o lock da deduplicação. O registro de auditoria é da publicadora.
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = var.arn_tabela
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = local.arn_analisador
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.buscadora.arn}:*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "buscadora" {
  name              = "/aws/lambda/${var.prefixo}-buscadora"
  retention_in_days = 1
}

resource "aws_lambda_function" "buscadora" {
  function_name    = "${var.prefixo}-buscadora"
  role             = aws_iam_role.buscadora.arn
  handler          = "portcullis.buscador.handler.lambda_handler"
  runtime          = "python3.12"
  filename         = var.caminho_zip
  source_code_hash = filebase64sha256(var.caminho_zip)

  # Precisa ser MENOR que o visibility timeout da fila (300 s), senão o SQS
  # reentrega a mensagem enquanto esta execução ainda está rodando.
  timeout     = 120
  memory_size = 512

  reserved_concurrent_executions = var.concorrencia_buscadora

  environment {
    variables = {
      PORTCULLIS_BUCKET_PACOTES    = var.nome_bucket_pacotes
      PORTCULLIS_TABELA            = var.nome_tabela_auditoria
      PORTCULLIS_FUNCAO_ANALISADOR = "${var.prefixo}-analisador"
      PORTCULLIS_GITHUB_APP_ID     = var.github_app_id
      PORTCULLIS_PARAM_CHAVE_APP   = "/portcullis/github/chave-privada"
    }
  }

  depends_on = [aws_cloudwatch_log_group.buscadora]
}

resource "aws_lambda_event_source_mapping" "fila_para_buscadora" {
  event_source_arn = var.arn_fila
  function_name    = aws_lambda_function.buscadora.arn
  enabled          = var.gatilho_buscadora_ligado
  # Uma mensagem por invocação: uma falha no meio de um lote reentregaria o
  # lote inteiro, e as mensagens que já deram certo seriam refeitas.
  batch_size = 1
}
