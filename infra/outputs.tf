output "ids_subnets_privadas" { value = module.rede.ids_subnets_privadas }
output "id_sg_analisador" { value = module.rede.id_sg_analisador }
output "nome_bucket_pacotes" { value = module.pacotes.nome_bucket_pacotes }
output "url_fila" { value = module.fila.url_fila }
output "nome_tabela" { value = module.dados.nome_tabela }

output "url_webhook" { value = module.funcoes.url_webhook }
output "nome_funcao_webhook" { value = module.funcoes.nome_funcao_webhook }

# Lido pelo `make url-webhook`, para não repetir o App ID em dois lugares.
output "github_app_id" { value = var.github_app_id }
output "nome_funcao_buscadora" { value = module.funcoes.nome_funcao_buscadora }
output "url_repositorio_analisador" { value = module.analisador.url_repositorio }
