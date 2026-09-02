# Verteilweg fuer Zertifikate und Passwort.
#
# Terraform erzeugt die Werte, legt sie hier ab, und die Instanz holt sie
# beim Boot mit ihrer IAM-Rolle. Das vermeidet den naheliegenden, aber
# falschen Weg, sie in user_data zu schreiben: user_data ist ueber den
# Metadatendienst fuer jeden Prozess auf der Instanz im Klartext lesbar.
#
# Kosten: Standard-Parameter sind kostenlos. Bei SecureString bewusst
# kein key_id gesetzt - dann verschluesselt SSM mit dem AWS-verwalteten
# Schluessel aws/ssm, der nichts kostet. Ein eigener KMS-Key waere
# 1 USD pro Monat.

locals {
  ssm_prefix = "/${var.project_name}/kafka"
}

resource "aws_ssm_parameter" "broker_private_key" {
  name        = "${local.ssm_prefix}/broker-private-key"
  description = "Privater Schluessel des Kafka-Brokers"
  type        = "SecureString"

  # PKCS#8, nicht das PKCS#1-Standardformat des tls-Providers. Java liest
  # "BEGIN RSA PRIVATE KEY" nicht und scheitert beim Broker-Start mit
  # "algid parse error, not a sequence".
  value = tls_private_key.broker.private_key_pem_pkcs8
}

resource "aws_ssm_parameter" "broker_certificate" {
  name        = "${local.ssm_prefix}/broker-certificate"
  description = "Von der internen CA signiertes Broker-Zertifikat"
  type        = "String" # oeffentlich, keine Verschluesselung noetig
  value       = tls_locally_signed_cert.broker.cert_pem
}

resource "aws_ssm_parameter" "ca_certificate" {
  name        = "${local.ssm_prefix}/ca-certificate"
  description = "CA-Zertifikat als Vertrauensanker fuer Broker und Clients"
  type        = "String"
  value       = tls_self_signed_cert.ca.cert_pem
}

resource "aws_ssm_parameter" "kafka_password" {
  name        = "${local.ssm_prefix}/user-password"
  description = "SASL/SCRAM-Passwort des Kafka-Benutzers"
  type        = "SecureString"
  value       = random_password.kafka_user.result
}
