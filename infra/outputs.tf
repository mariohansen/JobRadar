output "vpc_id" {
  description = "ID der VPC"
  value       = module.vpc.vpc_id
}

output "public_subnet_id" {
  description = "ID des oeffentlichen Subnetzes"
  value       = module.vpc.public_subnet_id
}

output "kafka_public_ip" {
  description = "Oeffentliche IP des Brokers. Aendert sich nach jedem Stop/Start"
  value       = module.ec2_kafka.public_ip
}

output "kafka_public_dns" {
  description = "Oeffentlicher DNS-Name des Brokers"
  value       = module.ec2_kafka.public_dns
}

output "kafka_ssh_command" {
  description = "Fertiger SSH-Befehl fuer den Zugang zur Instanz"
  value       = "ssh ec2-user@${module.ec2_kafka.public_ip}"
}

output "kafka_bootstrap_servers" {
  description = "bootstrap.servers fuer Kafka-Clients"
  value       = module.ec2_kafka.bootstrap_servers
}

output "kafka_sasl_username" {
  description = "SASL/SCRAM-Benutzername"
  value       = module.ec2_kafka.sasl_username
}

output "kafka_password_ssm_parameter" {
  description = "SSM-Parameter mit dem SASL-Passwort. Auslesen mit: aws ssm get-parameter --name <wert> --with-decryption"
  value       = module.ec2_kafka.password_ssm_parameter
}

output "kafka_ca_certificate" {
  description = "CA-Zertifikat, das Clients als Vertrauensanker brauchen"
  value       = module.ec2_kafka.ca_certificate
}

output "kafka_instance_id" {
  description = "Instanz-ID, etwa zum Stoppen: aws ec2 stop-instances --instance-ids <wert>"
  value       = module.ec2_kafka.instance_id
}

output "poller_function_name" {
  description = "Lambda des Pollers. Testaufruf: aws lambda invoke --function-name <wert> antwort.json"
  value       = module.lambda_poller.function_name
}

output "poller_log_group" {
  description = "Log-Gruppe des Pollers"
  value       = module.lambda_poller.log_group_name
}

output "poller_schedule" {
  description = "Aktiver Zeitplan des Pollers"
  value       = module.lambda_poller.schedule_expression
}

output "dedup_table_name" {
  description = "DynamoDB-Tabelle der bereits gesehenen Anzeigen"
  value       = module.storage.table_name
}

output "archive_bucket_name" {
  description = "S3-Bucket des Rohdatenarchivs"
  value       = module.storage.bucket_name
}

output "notification_email" {
  description = "Adresse der Benachrichtigungen. Muss in SES bestaetigt werden"
  value       = module.ses.sender_email
}

output "kafka_ca_certificate_ssm_parameter" {
  description = "SSM-Parameter mit dem CA-Zertifikat"
  value       = module.ec2_kafka.ca_certificate_ssm_parameter
}
