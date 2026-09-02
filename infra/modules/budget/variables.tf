variable "project_name" {
  description = "Praefix fuer die Ressourcennamen"
  type        = string
}

variable "monthly_limit_usd" {
  description = "Monatliches Kostenlimit in USD, ab dem gewarnt wird"
  type        = string
}

variable "alert_email" {
  description = "Empfaenger der Budget-Warnungen. AWS schickt einmalig eine Bestaetigungsmail, die zu quittieren ist"
  type        = string
}
