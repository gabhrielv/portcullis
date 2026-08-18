# O bucket é criado FORA do Terraform, uma vez, na mão. Se este stack o
# gerenciasse, o `destroy` apagaria o próprio mapa junto com o território.
#
# `use_lockfile` faz o lock por escrita condicional no próprio S3 — a tabela
# DynamoDB que os tutoriais antigos mandam criar não é mais necessária.
#
# O nome ainda diz `portcullis`, e fica assim de propósito: nome de bucket é
# IMUTÁVEL, e este guarda o state de tudo que já foi aplicado. Renomear exige
# criar o bucket novo, migrar o state e apagar o velho — operação de conta, com
# a conta de pé. Trocar a string aqui antes disso faz `terraform init` apontar
# para um bucket que não existe, e o mapa some.
terraform {
  backend "s3" {
    bucket       = "portcullis-tfstate-523301712809"
    key          = "marco-1/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
