# Account-ID der aktuellen Anmeldung. Geht in den Bucket-Namen ein, der
# weltweit eindeutig sein muss.
data "aws_caller_identity" "current" {}

# Netzwerkfundament. Kafka-Instanz und alles Weitere setzen darauf auf.
module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  vpc_cidr           = var.vpc_cidr
  public_subnet_cidr = var.public_subnet_cidr
}

# Dedup-Tabelle und Rohdatenarchiv.
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  account_id   = data.aws_caller_identity.current.account_id
}

# Verifizierte Adressen fuer den Mailversand.
module "ses" {
  source = "./modules/ses"

  sender_email    = var.notification_email
  recipient_email = var.notification_email
}

# Kafka-Broker. Netz-IDs kommen aus dem VPC-Modul, damit Instanz und
# Security Group garantiert im selben Netz landen. Auf derselben Instanz
# laufen die Consumer, daher bekommt ihre Rolle auch Zugriff auf Tabelle,
# Archiv und Mailversand.
module "ec2_kafka" {
  source = "./modules/ec2-kafka"

  project_name        = var.project_name
  aws_region          = var.aws_region
  vpc_id              = module.vpc.vpc_id
  subnet_id           = module.vpc.public_subnet_id
  admin_cidr          = var.admin_cidr
  instance_type       = var.kafka_instance_type
  ssh_public_key_path = var.ssh_public_key_path

  dedup_table_arn    = module.storage.table_arn
  archive_bucket_arn = module.storage.bucket_arn
  ses_sender_arn     = module.ses.sender_arn
}

# Kostenwaechter. Steht bewusst vor allem, was Geld kostet.
module "budget" {
  source = "./modules/budget"

  project_name      = var.project_name
  monthly_limit_usd = var.monthly_budget_usd
  alert_email       = var.budget_alert_email
}

# Poller als Lambda. Laeuft ausserhalb der VPC und erreicht den Broker
# ueber dessen oeffentliche Adresse.
module "lambda_poller" {
  source = "./modules/lambda-poller"

  project_name = var.project_name
  aws_region   = var.aws_region

  # Muss vor dem apply gebaut sein: python services/poller/build.py
  package_path = "${path.root}/../services/poller/poller.zip"

  kafka_bootstrap_servers = module.ec2_kafka.bootstrap_servers
  kafka_sasl_username     = module.ec2_kafka.sasl_username

  password_ssm_parameter           = module.ec2_kafka.password_ssm_parameter
  password_ssm_parameter_arn       = module.ec2_kafka.password_ssm_parameter_arn
  ca_certificate_ssm_parameter     = module.ec2_kafka.ca_certificate_ssm_parameter
  ca_certificate_ssm_parameter_arn = module.ec2_kafka.ca_certificate_ssm_parameter_arn

  suchbegriffe               = var.suchbegriffe
  ort                        = var.suchort
  umkreis_km                 = var.such_umkreis_km
  veroeffentlicht_seit_tagen = var.veroeffentlicht_seit_tagen
  schedule_expression        = var.poller_schedule_expression
  remote_bundesweit          = var.remote_bundesweit
  remote_min_prozent         = var.remote_min_prozent
}
