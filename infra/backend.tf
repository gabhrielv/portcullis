# No primeiro apply deixe COMENTADO: o bucket de state ainda não existe.
# Depois descomente e rode `terraform init -migrate-state`.
# terraform {
#   backend "s3" {
#     bucket       = "aduana-tfstate-SEU_ID_DE_CONTA"
#     key          = "marco-1/terraform.tfstate"
#     region       = "us-east-1"
#     use_lockfile = true
#   }
# }
