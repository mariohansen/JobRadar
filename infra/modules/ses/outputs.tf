output "sender_email" {
  description = "Verifizierte Absenderadresse"
  value       = aws_ses_email_identity.absender.email
}

output "sender_arn" {
  description = "ARN der Absender-Identitaet, fuer die IAM-Policy"
  value       = aws_ses_email_identity.absender.arn
}

output "recipient_email" {
  description = "Empfaengeradresse"
  value       = var.recipient_email
}
