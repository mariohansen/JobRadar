# Eingabewerte des Root-Moduls. Konkrete Werte kommen aus
# terraform.tfvars (gitignored) - Vorlage: terraform.tfvars.example

variable "project_name" {
  description = "Praefix fuer alle Ressourcennamen, damit im AWS-Account erkennbar bleibt, was zu diesem Projekt gehoert"
  type        = string
  default     = "jobradar"
}

variable "aws_region" {
  description = "Alle Ressourcen liegen in einer Region, um Cross-Region-Datenverkehr zu vermeiden"
  type        = string
  default     = "eu-central-1"
}

variable "vpc_cidr" {
  description = "Adressraum der VPC. /16 ist grosszuegig, kostet aber nichts und erspart spaeteres Umbauen"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Adressraum des einzigen Subnetzes. Bewusst nur eines: das Projekt braucht keine Hochverfuegbarkeit"
  type        = string
  default     = "10.0.1.0/24"
}

variable "admin_cidr" {
  description = "IP-Bereich, der per SSH auf die Kafka-Instanz darf, im CIDR-Format (eigene IP als x.x.x.x/32). Niemals 0.0.0.0/0"
  type        = string

  validation {
    # Faengt den haeufigsten Fehler ab: SSH versehentlich weltweit oeffnen.
    condition     = var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr darf nicht 0.0.0.0/0 sein - das oeffnet SSH fuer das gesamte Internet."
  }
}

variable "kafka_instance_type" {
  description = "Instanztyp des Kafka-Brokers. t3.micro ist Free-Tier-faehig, groesser kostet spuerbar"
  type        = string
  default     = "t3.micro"
}

variable "ssh_public_key_path" {
  description = "Pfad zum oeffentlichen SSH-Schluessel, der Zugang zur Kafka-Instanz bekommt"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "monthly_budget_usd" {
  description = "Monatliches Kostenlimit in USD fuer die Budget-Warnung"
  type        = string
  default     = "15"
}

variable "budget_alert_email" {
  description = "E-Mail-Adresse fuer Budget-Warnungen"
  type        = string
}

variable "suchbegriffe" {
  description = "Kommagetrennte Suchbegriffe fuer die Jobsuche"
  type        = string
  default     = "Data Engineer,Softwareentwickler,Software Engineer,Developer,Java"
}

variable "suchort" {
  description = "Ort, um den gesucht wird"
  type        = string
  default     = "Hamburg"
}

variable "such_umkreis_km" {
  description = "Suchradius in Kilometern"
  type        = number
  default     = 30
}

variable "veroeffentlicht_seit_tagen" {
  description = "Zeitfenster der Suche. Nur 0, 1, 7, 14 oder 28 - andere Werte ignoriert die API stillschweigend"
  type        = number
  default     = 7
}

variable "poller_schedule_expression" {
  description = "Zeitplan des Pollers in der Zeitzone Europe/Berlin"
  type        = string
  default     = "rate(10 hours)"
}


variable "notification_email" {
  description = "Adresse fuer die Job-Benachrichtigungen. Dient als Absender und Empfaenger; AWS schickt zur Verifizierung eine Bestaetigungsmail"
  type        = string
}

variable "remote_bundesweit" {
  description = "Zusaetzlich bundesweit nach vollstaendig remote zu erledigenden Stellen suchen"
  type        = bool
  default     = true
}

variable "remote_min_prozent" {
  description = "Mindestanteil Homeoffice fuer den bundesweiten Durchgang"
  type        = number
  default     = 100
}

variable "poller_quellen" {
  description = "Kommagetrennte Stellenboersen (siehe services/poller/poller/quellen/)"
  type        = string
  default     = "arbeitsagentur,arbeitnow"
}

variable "adzuna_app_id" {
  description = "Adzuna app_id aus der kostenlosen Registrierung, leer laesst die Quelle aus"
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
