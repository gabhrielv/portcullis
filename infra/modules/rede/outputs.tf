output "id_vpc" { value = aws_vpc.principal.id }
output "ids_subnets_privadas" { value = aws_subnet.privadas[*].id }
output "id_sg_analisador" { value = aws_security_group.analisador.id }
