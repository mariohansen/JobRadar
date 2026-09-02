# Poller als Lambda mit Zeitplan.
#
# Die Funktion laeuft ausserhalb der VPC (ADR 0002): sie braucht Zugang
# zum Internet fuer die Jobsuche-API und erreicht den Broker ueber dessen
# oeffentliche Adresse. In der VPC waere fuer den Internetzugang ein NAT
# Gateway noetig - rund 35 USD im Monat.
#
# Kosten: Das Free Tier von Lambda umfasst 1 Million Aufrufe und 400.000
# GB-Sekunden pro Monat. Bei dreimal taeglich rund zwei Sekunden mit
# 256 MB sind das etwa 90 Aufrufe und 45 GB-Sekunden - drei
# Groessenordnungen darunter.

data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "poller" {
  name               = "${var.project_name}-poller"
  description        = "Rolle der Poller-Lambda"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}

data "aws_iam_policy_document" "poller" {
  # Ohne Schreibrecht auf die eigene Log-Gruppe laeuft die Funktion zwar,
  # aber jede Fehlersuche wird blind.
  statement {
    sid    = "WriteOwnLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["${aws_cloudwatch_log_group.poller.arn}:*"]
  }

  # Genau die beiden Parameter, die der Poller braucht - nicht der
  # gesamte Parameter Store.
  statement {
    sid       = "ReadKafkaCredentials"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [var.password_ssm_parameter_arn, var.ca_certificate_ssm_parameter_arn]
  }

  # Das Passwort liegt als SecureString vor. Ohne Entschluesselungsrecht
  # bekaeme die Funktion nur den Geheimtext.
  statement {
    sid       = "DecryptSecureString"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "poller" {
  name   = "poller-permissions"
  role   = aws_iam_role.poller.id
  policy = data.aws_iam_policy_document.poller.json
}

# Bewusst vor der Funktion angelegt. Legt Lambda die Gruppe selbst an,
# steht die Aufbewahrung auf unbegrenzt und die Logs wachsen fuer immer.
resource "aws_cloudwatch_log_group" "poller" {
  name              = "/aws/lambda/${var.project_name}-poller"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "poller" {
  function_name = "${var.project_name}-poller"
  description   = "Fragt die Jobsuche-API der Bundesagentur ab und schreibt nach Kafka"

  role    = aws_iam_role.poller.arn
  runtime = "python3.13"
  # Paketstruktur: poller/main.py, darin die Funktion lambda_handler.
  handler       = "poller.main.lambda_handler"
  architectures = ["x86_64"]

  filename = var.package_path
  # Ohne diesen Hash bemerkt Terraform eine Aenderung am Paket nicht und
  # laesst die alte Fassung stehen.
  source_code_hash = filebase64sha256(var.package_path)

  # Der Poller braucht im Normalfall wenige Sekunden. 60 Sekunden lassen
  # Luft fuer eine langsame API, ohne dass ein Haenger lange kostet.
  timeout = 60
  # 256 MB reichen; mehr Speicher bedeutet bei Lambda auch mehr CPU,
  # lohnt sich hier aber nicht.
  memory_size = 256

  environment {
    variables = {
      # Aendert sich, sobald die Kafka-Instanz gestoppt und neu gestartet
      # wird - dann muss terraform apply erneut laufen.
      KAFKA_BOOTSTRAP_SERVERS = var.kafka_bootstrap_servers
      KAFKA_TOPIC_RAW         = var.kafka_topic
      KAFKA_SASL_USERNAME     = var.kafka_sasl_username

      # Nur die Namen der Parameter, nicht die Werte: die Konfiguration
      # einer Lambda ist fuer jeden lesbar, der die Funktion einsehen darf.
      KAFKA_PASSWORD_SSM_PARAMETER = var.password_ssm_parameter
      KAFKA_CA_CERT_SSM_PARAMETER  = var.ca_certificate_ssm_parameter

      JOBSUCHE_WAS                        = var.suchbegriffe
      JOBSUCHE_WO                         = var.ort
      JOBSUCHE_UMKREIS_KM                 = tostring(var.umkreis_km)
      JOBSUCHE_VEROEFFENTLICHT_SEIT_TAGEN = tostring(var.veroeffentlicht_seit_tagen)

      # Zweiter Suchdurchgang ohne Ortsbindung, der nur vollstaendig
      # remote zu erledigende Stellen mitnimmt.
      JOBSUCHE_REMOTE_BUNDESWEIT  = tostring(var.remote_bundesweit)
      JOBSUCHE_REMOTE_MIN_PROZENT = tostring(var.remote_min_prozent)
    }
  }

  depends_on = [aws_cloudwatch_log_group.poller]
}
