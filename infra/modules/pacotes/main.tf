data "aws_caller_identity" "atual" {}

resource "aws_s3_bucket" "pacotes" {
  bucket        = "${var.prefixo}-pacotes-${data.aws_caller_identity.atual.account_id}"
  force_destroy = true
  tags          = { Name = "${var.prefixo}-pacotes" }
}

resource "aws_s3_bucket_public_access_block" "pacotes" {
  bucket                  = aws_s3_bucket.pacotes.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "pacotes" {
  bucket = aws_s3_bucket.pacotes.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# O código-fonte não precisa durar. Quem dura é a auditoria, e ela vive no
# DynamoDB.
resource "aws_s3_bucket_lifecycle_configuration" "pacotes" {
  bucket = aws_s3_bucket.pacotes.id
  rule {
    id     = "expirar-pacotes"
    status = "Enabled"
    filter {}
    expiration { days = var.dias_retencao }
  }
}
