# Ablagen der Pipeline: DynamoDB fuer die Deduplizierung, S3 fuer das
# Rohdatenarchiv.

# --- DynamoDB: welche Anzeige wurde schon gesehen? ---
#
# Der Dedup-Schritt fragt fuer jede Anzeige, ob ihre Referenznummer schon
# bekannt ist. Das ist ein reiner Schluesselzugriff ohne Abfragen ueber
# mehrere Felder - genau das, wofuer eine Key-Value-Tabelle gemacht ist.
# Eine relationale Datenbank waere hier teurer (RDS laeuft durch) und
# koennte nichts, was wir brauchen.
resource "aws_dynamodb_table" "seen_jobs" {
  name = "${var.project_name}-seen-jobs"

  # On-Demand statt fester Kapazitaet: es gibt nichts zu dimensionieren
  # und nichts, was bei Leerlauf weiterlaeuft. Bei rund 300 Schreib-
  # vorgaengen am Tag kostet das im Cent-Bereich pro Monat; der Free
  # Tier deckt ohnehin 25 GB Speicher ab.
  billing_mode = "PAY_PER_REQUEST"

  # Die Referenznummer der Bundesagentur ist bereits eindeutig - ein
  # eigener Schluessel waere nur eine zusaetzliche Indirektion.
  hash_key = "referenznummer"

  attribute {
    name = "referenznummer"
    type = "S"
  }

  # Eintraege raeumen sich selbst ab. Ohne TTL waechst die Tabelle
  # unbegrenzt, obwohl eine Anzeige von vor einem Jahr fuer die
  # Deduplizierung bedeutungslos ist.
  ttl {
    attribute_name = "ablauf_zeitpunkt"
    enabled        = true
  }

  # Bei einem Lernprojekt ist der Wiederherstellungspunkt jeder Anzeige
  # der naechste Lauf des Pollers - Backups waeren hier reine Kosten.
  point_in_time_recovery {
    enabled = false
  }

  tags = { Name = "${var.project_name}-seen-jobs" }
}

# --- S3: Rohdatenarchiv ---
#
# Jede Anzeige wird so abgelegt, wie die API sie geliefert hat. Das ist
# die Grundlage fuer spaetere Auswertungen (Skill-Trends) und die einzige
# Moeglichkeit, einen Filterfehler rueckwirkend zu korrigieren - Kafka
# haelt die Rohdaten nur begrenzt vor.
resource "aws_s3_bucket" "archive" {
  # Bucket-Namen sind weltweit eindeutig. Das Suffix aus der Account-ID
  # verhindert eine Kollision mit einem fremden Bucket.
  bucket = "${var.project_name}-archive-${var.account_id}"

  tags = { Name = "${var.project_name}-archive" }
}

# Standardmaessig blockiert AWS oeffentlichen Zugriff bereits; hier
# explizit, damit es nicht von einer spaeteren Aenderung abhaengt.
resource "aws_s3_bucket_public_access_block" "archive" {
  bucket = aws_s3_bucket.archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    apply_server_side_encryption_by_default {
      # SSE-S3 mit von AWS verwalteten Schluesseln: kostenlos. SSE-KMS
      # mit eigenem Schluessel waere 1 USD im Monat plus Anfragekosten.
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    id     = "archiv-aufraeumen"
    status = "Enabled"

    filter {}

    # Nach einem Jahr loeschen. Der Free Tier umfasst 5 GB; eine Anzeige
    # ist wenige Kilobyte gross, damit ist das Limit auf Jahre hinaus
    # kein Thema - die Regel verhindert nur unbegrenztes Wachstum.
    expiration {
      days = 365
    }

    # Abgebrochene mehrteilige Uploads belegen sonst dauerhaft Platz,
    # ohne irgendwo sichtbar zu sein.
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
