# Kafka-Broker auf einer einzelnen EC2-Instanz.
#
# Der Broker ist oeffentlich erreichbar und ausschliesslich durch
# SASL_SSL geschuetzt (ADR 0002) - Zertifikate in tls.tf, Verteilung
# ueber SSM in ssm.tf, Leserecht der Instanz in iam.tf.
#
# Kosten: t3.micro liegt bei rund 8 USD/Monat im Dauerbetrieb, gedeckt
# vom Free-Tier-Kontingent. Das 8-GiB-Root-Volume liegt deutlich unter
# den 30 GiB EBS im Free Tier. Keine Elastic IP - die oeffentliche
# Adresse aendert sich damit bei jedem Stop/Start, dafuer faellt nichts
# an, waehrend die Instanz steht.

# Immer das aktuellste Amazon Linux 2023 nehmen, statt eine AMI-ID hart
# zu verdrahten: AMI-IDs sind regionsspezifisch und werden bei jedem
# Sicherheitsupdate durch eine neue ersetzt.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# Registriert den oeffentlichen Teil deines lokalen SSH-Schluessels bei
# AWS. Der private Schluessel verlaesst deinen Rechner nie und landet
# damit auch nicht im Terraform-State.
resource "aws_key_pair" "admin" {
  key_name   = "${var.project_name}-admin"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_security_group" "kafka" {
  name        = "${var.project_name}-kafka"
  description = "Kafka-Broker: SSH von der eigenen IP, Broker-Port oeffentlich mit SASL_SSL"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.project_name}-kafka-sg" }
}

# Regeln bewusst als eigene Ressourcen statt als inline-Bloecke: so
# aendert Terraform beim Hinzufuegen des Kafka-Ports gezielt eine Regel,
# statt das gesamte Regelwerk der Gruppe neu zu schreiben.
resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.kafka.id
  description       = "SSH nur von der eigenen IP"

  cidr_ipv4   = var.admin_cidr
  ip_protocol = "tcp"
  from_port   = 22
  to_port     = 22
}

# Ausgehend alles erlauben: die Instanz muss Systemupdates ziehen und das
# Kafka-Image von Docker Hub laden. Ausgehenden Verkehr einzuschraenken
# brachte hier keinen Sicherheitsgewinn, der den Aufwand rechtfertigt.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.kafka.id
  description       = "Paketquellen und Container-Registry erreichbar"

  cidr_ipv4   = "0.0.0.0/0"
  ip_protocol = "-1"
}

resource "aws_instance" "kafka" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  key_name               = aws_key_pair.admin.key_name
  vpc_security_group_ids = [aws_security_group.kafka.id]

  # Ueber das Instance Profile darf die Instanz ihre Zertifikate und ihr
  # Passwort aus SSM lesen, ohne dass ein Access Key auf der Platte liegt.
  iam_instance_profile = aws_iam_instance_profile.kafka.name

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    aws_region    = var.aws_region
    ssm_prefix    = local.ssm_prefix
    kafka_user    = var.kafka_user
    kafka_version = var.kafka_version
    cluster_id    = random_id.cluster.b64_url
  })

  # user_data laeuft nur beim allerersten Boot einer Instanz. Ohne dieses
  # Flag wuerde Terraform eine Aenderung am Script kommentarlos schlucken,
  # ohne dass sie je auf der Instanz ankommt.
  user_data_replace_on_change = true

  root_block_device {
    volume_size = 8     # GiB, weit unter den 30 GiB EBS im Free Tier
    volume_type = "gp3" # gp3 ist bei gleicher Groesse guenstiger als gp2
    encrypted   = true
  }

  metadata_options {
    http_endpoint = "enabled"
    # IMDSv2 erzwingen: verhindert, dass eine serverseitige Anfrage-
    # Faelschung die Instanz-Credentials ueber den Metadatendienst abholt.
    http_tokens = "required"
  }

  tags = { Name = "${var.project_name}-kafka" }

  lifecycle {
    # Der AMI-Lookup oben liefert immer das neueste Amazon Linux. Ohne
    # diese Ausnahme wuerde Terraform die Instanz jedes Mal ersetzen,
    # wenn AWS ein neues Image veroeffentlicht - also im Wochentakt, und
    # samt allem, was auf dem Root-Volume liegt.
    #
    # Ein Image-Wechsel ist damit eine bewusste Entscheidung:
    #   terraform apply -replace=module.ec2_kafka.aws_instance.kafka
    ignore_changes = [ami]
  }
}

# Der Broker-Port ist bewusst weltweit offen: die Lambda laeuft ausserhalb
# der VPC und kommt aus wechselnden AWS-IP-Bereichen, die sich nicht als
# feste Quelle eintragen lassen. Die Schranke ist deshalb SASL_SSL, nicht
# die Security Group (ADR 0002).
resource "aws_vpc_security_group_ingress_rule" "kafka_external" {
  security_group_id = aws_security_group.kafka.id
  description       = "Kafka SASL_SSL-Listener"

  cidr_ipv4   = "0.0.0.0/0"
  ip_protocol = "tcp"
  from_port   = 9094
  to_port     = 9094
}

# Kennung des KRaft-Clusters. 16 Byte ergeben base64-kodiert genau die
# 22 Zeichen, die Kafka als Cluster-ID erwartet. Ueber Terraform erzeugt,
# damit sie stabil bleibt - wechselt sie, haelt der Broker seine
# vorhandenen Daten fuer fremd.
resource "random_id" "cluster" {
  byte_length = 16
}
