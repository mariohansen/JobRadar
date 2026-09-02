output "instance_id" {
  description = "Instanz-ID, etwa zum Stoppen per AWS CLI"
  value       = aws_instance.kafka.id
}

# Aendert sich bei jedem Stop/Start, weil bewusst keine Elastic IP
# reserviert ist. Nach jedem Start einmal terraform apply laufen lassen,
# damit die Lambda die neue Adresse bekommt.
output "public_ip" {
  description = "Aktuelle oeffentliche IP der Kafka-Instanz"
  value       = aws_instance.kafka.public_ip
}

output "public_dns" {
  description = "Oeffentlicher DNS-Name der Kafka-Instanz"
  value       = aws_instance.kafka.public_dns
}

output "security_group_id" {
  description = "Security Group des Brokers, ergaenzt um den Kafka-Port in Schritt 2"
  value       = aws_security_group.kafka.id
}

# Adresse, die Clients als bootstrap.servers eintragen. Enthaelt den
# oeffentlichen DNS-Namen, damit die Hostname-Pruefung gegen das
# Wildcard-Zertifikat aufgeht - mit der reinen IP wuerde sie scheitern.
output "bootstrap_servers" {
  description = "bootstrap.servers fuer Kafka-Clients"
  value       = "${aws_instance.kafka.public_dns}:9094"
}

output "sasl_username" {
  description = "SASL/SCRAM-Benutzername"
  value       = var.kafka_user
}

# Oeffentlicher Teil der CA. Clients brauchen ihn als Vertrauensanker,
# weil kein oeffentlich anerkannter Aussteller dahintersteht.
output "ca_certificate" {
  description = "CA-Zertifikat im PEM-Format"
  value       = tls_self_signed_cert.ca.cert_pem
}

output "password_ssm_parameter" {
  description = "SSM-Parameter, aus dem Clients das SASL-Passwort lesen"
  value       = aws_ssm_parameter.kafka_password.name
}

# ARNs fuer die Lambda-Policy: sie soll genau diese beiden Parameter
# lesen duerfen und sonst nichts.
output "password_ssm_parameter_arn" {
  description = "ARN des SASL-Passworts im Parameter Store"
  value       = aws_ssm_parameter.kafka_password.arn
}

output "ca_certificate_ssm_parameter" {
  description = "Name des CA-Zertifikat-Parameters"
  value       = aws_ssm_parameter.ca_certificate.name
}

output "ca_certificate_ssm_parameter_arn" {
  description = "ARN des CA-Zertifikat-Parameters"
  value       = aws_ssm_parameter.ca_certificate.arn
}
