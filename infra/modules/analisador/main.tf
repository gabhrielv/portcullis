data "aws_region" "atual" {}
data "aws_caller_identity" "atual" {}

resource "aws_ecr_repository" "analisador" {
  name         = "${var.prefixo}-analisador"
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Guarda 1 imagem. Sem isto cada build deixa uma camada de ~400 MB para trás, e
# o ECR é o único recurso do projeto que cobra por existir parado.
resource "aws_ecr_lifecycle_policy" "uma_imagem" {
  repository = aws_ecr_repository.analisador.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "guarda apenas a imagem mais recente"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 1
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_iam_role" "analisador" {
  count = var.criar_funcao ? 1 : 0
  name  = "${var.prefixo}-analisador"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_cloudwatch_log_group" "analisador" {
  count             = var.criar_funcao ? 1 : 0
  name              = "/aws/lambda/${var.prefixo}-analisador"
  retention_in_days = 1
}

resource "aws_iam_role_policy" "analisador" {
  count = var.criar_funcao ? 1 : 0
  name  = "${var.prefixo}-analisador"
  role  = aws_iam_role.analisador[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # LÊ de entrada/, ESCREVE em saida/. Nada além disso, e nunca o
        # inverso: se o analisador for comprometido pelo código que examina,
        # ele não consegue reescrever o pacote de outra análise.
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${var.arn_bucket_pacotes}/entrada/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${var.arn_bucket_pacotes}/saida/*"
      },
      {
        # Exigido para a função viver dentro da VPC: a Lambda cria e destrói a
        # interface de rede dela. Não dá acesso a nada.
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.analisador[0].arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "analisador" {
  count         = var.criar_funcao ? 1 : 0
  function_name = "${var.prefixo}-analisador"
  role          = aws_iam_role.analisador[0].arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.analisador.repository_url}:${var.tag_imagem}"

  # 1769 MB é onde a Lambda entrega uma vCPU inteira. Abaixo disso a CPU é
  # estrangulada e o trabalho demora proporcionalmente mais — o GB-s dá no
  # mesmo e só a latência piora. Acima, paga-se por uma segunda vCPU que o
  # semgrep não usa, porque é monotarefa.
  memory_size = 1769

  # Maior que o timeout do subprocesso do semgrep (600 s). Se fosse menor, um
  # semgrep travado mataria a Lambda antes de ela escrever `ok: false`, e a
  # publicadora não saberia o que houve.
  timeout = 700

  reserved_concurrent_executions = var.concorrencia

  # Dentro da VPC, em subnet sem rota para a internet. A única saída é o
  # gateway endpoint do S3. A imagem do ECR não vem por aqui — quem a busca é a
  # infraestrutura da Lambda, fora da VPC.
  vpc_config {
    subnet_ids         = var.ids_subnets
    security_group_ids = [var.id_security_group]
  }

  depends_on = [aws_cloudwatch_log_group.analisador]
}
