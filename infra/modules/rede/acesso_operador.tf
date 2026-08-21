# Acesso de operador para depurar o analisador dentro da VPC.
resource "aws_security_group" "operador" {
  name        = "${var.prefixo}-operador"
  description = "Acesso de operador"
  vpc_id      = aws_vpc.principal.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
