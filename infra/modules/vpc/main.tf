# Netzwerkfundament: eine VPC mit genau einem oeffentlichen Subnetz.
#
# Bewusst keine Default-VPC: die gibt AWS vor, sie ist nicht von Terraform
# verwaltet und in jedem Account anders geschnitten. Eine eigene VPC ist
# reproduzierbar und macht sichtbar, was das Netz tatsaechlich erlaubt.
#
# Kosten: VPC, Subnetz, Internet Gateway, Route Tables und Security Groups
# sind kostenlos. Geld kosten in einer VPC nur NAT Gateways, VPC Endpoints
# und oeffentliche IPv4-Adressen - das NAT Gateway vermeiden wir bewusst,
# siehe ADR 0002.

# AZ-Namen sind pro Account unterschiedlich auf die physische Hardware
# gemappt. Deshalb die Liste abfragen und die erste nehmen, statt
# "eu-central-1a" hart zu verdrahten.
data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr

  # Noetig, damit die EC2-Instanz einen internen DNS-Namen bekommt und
  # AWS-Endpunkte wie DynamoDB oder S3 ueberhaupt aufloesen kann.
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project_name}-vpc" }
}

# Ohne Internet Gateway gibt es keine Verbindung zwischen VPC und
# Internet - weder herein (Lambda erreicht den Broker) noch hinaus
# (Paketquellen, Docker Hub beim Provisionieren).
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]

  # Jede Instanz in diesem Subnetz bekommt automatisch eine oeffentliche
  # IP. Genau das braucht der Kafka-Broker, damit die Lambda ihn von
  # ausserhalb der VPC erreicht.
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public" }
}

# Ein Subnetz ist erst dann oeffentlich, wenn seine Route Table den
# Default-Verkehr zum Internet Gateway schickt. Die oeffentliche IP an der
# Instanz allein genuegt nicht - ohne diese Route laeuft der Verkehr ins
# Leere.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
