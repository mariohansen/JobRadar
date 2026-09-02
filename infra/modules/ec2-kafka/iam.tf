# Rolle der Kafka-Instanz.
#
# Ueber ein Instance Profile bekommt die Instanz temporaere, automatisch
# rotierende Credentials aus dem Metadatendienst. Die Alternative waere
# ein langlebiger Access Key auf der Platte - der laesst sich nicht
# rotieren, nicht widerrufen, ohne dass jemand es merkt, und liegt bei
# einem Snapshot der Platte gleich mit.

# Wer darf diese Rolle annehmen? Nur der EC2-Dienst. Ohne diese
# Vertrauensbeziehung koennte die Rolle niemand nutzen.
data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "kafka" {
  name               = "${var.project_name}-kafka"
  description        = "Erlaubt der Kafka-Instanz, ihre Zertifikate und ihr Passwort aus SSM zu lesen"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

# Was darf die Rolle? Ausschliesslich die vier Parameter dieses Projekts
# lesen - nicht den gesamten Parameter Store. Die Ressourcen-ARNs sind
# deshalb auf den Praefix eingegrenzt statt auf "*".
data "aws_iam_policy_document" "read_kafka_parameters" {
  statement {
    sid    = "ReadKafkaParameters"
    effect = "Allow"

    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]

    resources = [
      aws_ssm_parameter.broker_private_key.arn,
      aws_ssm_parameter.broker_certificate.arn,
      aws_ssm_parameter.ca_certificate.arn,
      aws_ssm_parameter.kafka_password.arn,
    ]
  }

  # SecureString-Werte sind mit dem AWS-verwalteten Schluessel
  # verschluesselt. Ohne dieses Recht bekaeme die Instanz den
  # Geheimtext, aber nicht den Klartext.
  statement {
    sid       = "DecryptSecureStrings"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["*"]

    # Eingrenzung auf den SSM-Dienst: der Schluessel darf nur
    # verwendet werden, wenn die Anfrage tatsaechlich ueber SSM laeuft.
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "read_kafka_parameters" {
  name   = "read-kafka-parameters"
  role   = aws_iam_role.kafka.id
  policy = data.aws_iam_policy_document.read_kafka_parameters.json
}

# Das Instance Profile ist die Huelle, ueber die eine Rolle ueberhaupt an
# eine EC2-Instanz gehaengt werden kann - eine Rolle allein genuegt dafuer
# nicht.
resource "aws_iam_instance_profile" "kafka" {
  name = "${var.project_name}-kafka"
  role = aws_iam_role.kafka.name
}

# --- Rechte der Consumer, die auf dieser Instanz laufen ---
#
# filter-dedup und notifier laufen als Prozesse neben dem Broker und
# nutzen dieselbe Instanzrolle. Sie brauchen Zugriff auf die
# Dedup-Tabelle, das Archiv und den Mailversand.
data "aws_iam_policy_document" "consumer" {
  statement {
    sid    = "DedupTabelle"
    effect = "Allow"

    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      # Der Tracker aktualisiert den Bewerbungsstatus einer bekannten
      # Anzeige.
      "dynamodb:UpdateItem",
      "dynamodb:Query",
    ]

    resources = [var.dedup_table_arn]
  }

  statement {
    sid    = "Rohdatenarchiv"
    effect = "Allow"
    # Nur schreiben und lesen, kein Loeschen: ein fehlerhafter Consumer
    # soll das Archiv nicht leeren koennen.
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${var.archive_bucket_arn}/*"]
  }

  statement {
    sid    = "Mailversand"
    effect = "Allow"

    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]

    resources = [var.ses_sender_arn]
  }
}

resource "aws_iam_role_policy" "consumer" {
  name   = "consumer-permissions"
  role   = aws_iam_role.kafka.id
  policy = data.aws_iam_policy_document.consumer.json
}
