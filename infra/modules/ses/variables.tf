variable "sender_email" {
  description = "Absenderadresse. Bleibt konstant, damit sich beim Mailanbieter eine Reputation aufbaut"
  type        = string
}

variable "recipient_email" {
  description = "Empfaengeradresse der Benachrichtigungen"
  type        = string
}
