# O bucket é criado FORA do Terraform, uma vez, na mão. Se este stack o
# gerenciasse, o `destroy` apagaria o próprio mapa junto com o território.
#
# `use_lockfile` faz o lock por escrita condicional no próprio S3 — a tabela
# DynamoDB que os tutoriais antigos mandam criar não é mais necessária.
terraform {
  backend "s3" {
    bucket       = "portcullis-tfstate-523301712809"
    key          = "marco-1/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
