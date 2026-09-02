variable "project_name" {
  description = "Praefix fuer die Ressourcennamen"
  type        = string
}

variable "vpc_id" {
  description = "VPC, in der die Security Group angelegt wird"
  type        = string
}

variable "subnet_id" {
  description = "Oeffentliches Subnetz fuer die Instanz"
  type        = string
}

variable "admin_cidr" {
  description = "IP-Bereich mit SSH-Zugang, als /32 der eigenen Adresse"
  type        = string
}

variable "instance_type" {
  description = "Instanztyp. t3.micro ist Free-Tier-faehig; groesser nur bewusst waehlen"
  type        = string
  default     = "t3.micro"
}

variable "ssh_public_key_path" {
  description = "Pfad zum oeffentlichen SSH-Schluessel auf dem eigenen Rechner"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "aws_region" {
  description = "Region der Instanz. Geht in das Wildcard-Zertifikat und in die SSM-Aufrufe ein"
  type        = string
}

variable "kafka_user" {
  description = "Name des SASL/SCRAM-Benutzers, mit dem sich die Services am Broker anmelden"
  type        = string
  default     = "jobradar"
}

variable "kafka_version" {
  description = "Tag des apache/kafka-Images"
  type        = string
  default     = "4.3.1"
}

variable "dedup_table_arn" {
  description = "ARN der DynamoDB-Tabelle fuer die Deduplizierung"
  type        = string
}

variable "archive_bucket_arn" {
  description = "ARN des S3-Buckets fuer das Rohdatenarchiv"
  type        = string
}

variable "ses_sender_arn" {
  description = "ARN der verifizierten SES-Absenderadresse"
  type        = string
}
