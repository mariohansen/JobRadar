variable "project_name" {
  description = "Praefix fuer die Ressourcennamen"
  type        = string
}

variable "aws_region" {
  description = "Region, geht in die KMS-Bedingung der Policy ein"
  type        = string
}

variable "package_path" {
  description = "Pfad zum Deployment-Paket. Erzeugt mit: python services/poller/build.py"
  type        = string
}

variable "kafka_bootstrap_servers" {
  description = "Broker-Adresse als DNS-Name mit Port"
  type        = string
}

variable "kafka_topic" {
  description = "Topic fuer die Rohdaten"
  type        = string
  default     = "jobs.raw"
}

variable "kafka_sasl_username" {
  description = "SASL-Benutzername"
  type        = string
}

variable "password_ssm_parameter" {
  description = "Name des SSM-Parameters mit dem SASL-Passwort"
  type        = string
}

variable "password_ssm_parameter_arn" {
  description = "ARN desselben Parameters, fuer die IAM-Policy"
  type        = string
}

variable "ca_certificate_ssm_parameter" {
  description = "Name des SSM-Parameters mit dem CA-Zertifikat"
  type        = string
}

variable "ca_certificate_ssm_parameter_arn" {
  description = "ARN desselben Parameters, fuer die IAM-Policy"
  type        = string
}

variable "suchbegriffe" {
  description = "Kommagetrennte Suchbegriffe fuer die Jobsuche"
  type        = string
  default     = "Data Engineer,Softwareentwickler"
}

variable "ort" {
  description = "Ort der Suche"
  type        = string
  default     = "Hamburg"
}

variable "umkreis_km" {
  description = "Suchradius in Kilometern"
  type        = number
  default     = 30
}

variable "veroeffentlicht_seit_tagen" {
  description = "Zeitfenster der Suche in Tagen"
  type        = number
  default     = 7

  validation {
    # Die API akzeptiert nur diese Werte und verwirft jeden anderen
    # kommentarlos - die Antwort enthaelt dann alle Treffer statt der
    # erwarteten Auswahl (siehe ADR 0001).
    condition     = contains([0, 1, 7, 14, 28], var.veroeffentlicht_seit_tagen)
    error_message = "Nur 0, 1, 7, 14 oder 28 zulaessig - andere Werte ignoriert die Jobsuche-API stillschweigend."
  }
}

variable "schedule_expression" {
  description = "Zeitplan des Pollers, in der Zeitzone Europe/Berlin"
  type        = string
  # Alle vier Stunden, also sechsmal taeglich. Fuer rund anderthalb neue
  # Anzeigen pro Tag ist das reichlich; ein 15-Minuten-Takt waere
  # gegenueber einer inoffiziellen API ohne Vertrag schwer zu begruenden.
  default = "rate(10 hours)"
}

variable "log_retention_days" {
  description = "Aufbewahrung der Lambda-Logs. Ohne Begrenzung wachsen sie unbegrenzt weiter"
  type        = number
  default     = 14
}

variable "remote_bundesweit" {
  description = "Zusaetzlich bundesweit nach vollstaendig remote zu erledigenden Stellen suchen"
  type        = bool
  default     = true
}

variable "remote_min_prozent" {
  description = "Mindestanteil Homeoffice fuer den bundesweiten Durchgang. 100 bedeutet vollstaendig remote"
  type        = number
  default     = 100

  validation {
    condition     = var.remote_min_prozent > 0 && var.remote_min_prozent <= 100
    error_message = "Der Anteil muss zwischen 1 und 100 liegen."
  }
}

variable "quellen" {
  description = "Kommagetrennte Stellenboersen, die der Poller abfragt"
  type        = string
  default     = "arbeitsagentur,arbeitnow"
}

# Adzuna ist die einzige Quelle mit Zugangsdaten. Sie stehen als
# Umgebungsvariable der Lambda, nicht in SSM: wer die Funktionskonfi-
# guration lesen darf, ist in diesem Projekt derselbe, dem die
# Registrierung gehoert. Leer bedeutet: Quelle bleibt still.
variable "adzuna_app_id" {
  description = "Adzuna app_id, leer laesst die Quelle aus"
  type        = string
  default     = ""
  sensitive   = true
}

variable "adzuna_app_key" {
  description = "Adzuna app_key, leer laesst die Quelle aus"
  type        = string
  default     = ""
  sensitive   = true
}
