terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.regiao
  default_tags {
    tags = {
      Projeto   = "portcullis"
      Terraform = "true"
    }
  }
}

module "alertas" {
  source        = "./modules/alertas"
  prefixo       = var.prefixo
  email_alertas = var.email_alertas
}

module "rede" {
  source  = "./modules/rede"
  prefixo = var.prefixo
}

module "pacotes" {
  source  = "./modules/pacotes"
  prefixo = var.prefixo
}

module "fila" {
  source             = "./modules/fila"
  prefixo            = var.prefixo
  arn_topico_alertas = module.alertas.arn_topico
}

module "dados" {
  source  = "./modules/dados"
  prefixo = var.prefixo
}

module "funcoes" {
  source              = "./modules/funcoes"
  prefixo             = var.prefixo
  caminho_zip         = "${path.module}/../build/lambda.zip"
  url_fila            = module.fila.url_fila
  arn_fila            = module.fila.arn_fila
  arn_bucket_pacotes  = module.pacotes.arn_bucket_pacotes
  nome_bucket_pacotes = module.pacotes.nome_bucket_pacotes
  arn_tabela          = module.dados.arn_tabela
  nome_tabela         = module.dados.nome_tabela
  github_app_id       = var.github_app_id

  concorrencia_webhook = var.concorrencia_webhook
}
