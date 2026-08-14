# trimsuffix porque o invoke_url do estágio `$default` termina em barra em
# algumas versões do provider e não em outras.
output "url_webhook" {
  value = "${trimsuffix(aws_apigatewayv2_stage.padrao.invoke_url, "/")}/webhook"
}

output "id_api" { value = aws_apigatewayv2_api.principal.id }
output "arn_execucao_api" { value = aws_apigatewayv2_api.principal.execution_arn }
output "nome_funcao_webhook" { value = aws_lambda_function.webhook.function_name }

output "nome_funcao_buscadora" { value = aws_lambda_function.buscadora.function_name }
