# Chave composta porque o portão nasce multi-repo: PK = owner#repo, SK = sha.
# Trocar isso depois exigiria migrar dados.
resource "aws_dynamodb_table" "auditoria" {
  name         = "${var.prefixo}-auditoria"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "repo"
  range_key    = "sha"

  attribute {
    name = "repo"
    type = "S"
  }
  attribute {
    name = "sha"
    type = "S"
  }

  # Sem point-in-time recovery: é cobrado por GB e, se a tabela sumir, basta
  # reabrir os PRs.
  tags = { Name = "${var.prefixo}-auditoria" }
}
