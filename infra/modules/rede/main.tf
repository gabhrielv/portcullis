data "aws_availability_zones" "disponiveis" {
  state = "available"
}

data "aws_region" "atual" {}

data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${data.aws_region.atual.region}.s3"
}

resource "aws_vpc" "principal" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.prefixo}-vpc" }
}

# NÃO existe internet gateway. O analisador é a única coisa dentro da VPC e ele
# só precisa do S3, que é alcançado pelo gateway endpoint abaixo. As Lambdas que
# falam com o GitHub ficam fora da VPC.
resource "aws_subnet" "privadas" {
  count             = 2
  vpc_id            = aws_vpc.principal.id
  cidr_block        = cidrsubnet(var.cidr_vpc, 8, count.index)
  availability_zone = data.aws_availability_zones.disponiveis.names[count.index]
  tags              = { Name = "${var.prefixo}-privada-${count.index}" }
}

resource "aws_route_table" "privada" {
  vpc_id = aws_vpc.principal.id
  tags   = { Name = "${var.prefixo}-rt-privada" }
}

resource "aws_route_table_association" "privadas" {
  count          = length(aws_subnet.privadas)
  subnet_id      = aws_subnet.privadas[count.index].id
  route_table_id = aws_route_table.privada.id
}

# GATEWAY endpoint, não interface: gateway é grátis, interface custa ~US$7,20
# por mês por AZ. S3 e DynamoDB são os dois únicos com gateway.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.principal.id
  service_name      = "com.amazonaws.${data.aws_region.atual.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.privada.id]
  tags              = { Name = "${var.prefixo}-endpoint-s3" }
}

# Este security group É a promessa de isolamento virando configuração
# verificável: nenhuma entrada, e saída apenas para o S3.
resource "aws_security_group" "analisador" {
  name        = "${var.prefixo}-analisador"
  description = "Analisador: sem entrada, saida apenas para S3"
  vpc_id      = aws_vpc.principal.id
  tags        = { Name = "${var.prefixo}-analisador" }
}

resource "aws_vpc_security_group_egress_rule" "s3" {
  security_group_id = aws_security_group.analisador.id
  prefix_list_id    = data.aws_prefix_list.s3.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "S3 via gateway endpoint"
}
