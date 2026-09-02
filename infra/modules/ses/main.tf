# E-Mail-Versand ueber SES.
#
# SES arbeitet fuer neue Accounts in einer Sandbox: es darf nur an
# verifizierte Adressen gesendet werden, und das Kontingent ist begrenzt.
# Fuer den Eigenbedarf mit einer festen Empfaengeradresse genuegt das
# vollstaendig - der Antrag auf Produktionszugang waere nur noetig, um an
# beliebige Dritte zu senden.
#
# Ohne eigene Domain bleibt nur die Verifizierung einzelner Adressen.
# SPF, DKIM und DMARC setzen eine Domain voraus und entfallen damit.
#
# Kosten: keine. Das Kontingent deckt deutlich mehr, als dieses Projekt
# je versenden wird.

resource "aws_ses_email_identity" "absender" {
  email = var.sender_email
}

# Nur anlegen, wenn Absender und Empfaenger sich unterscheiden - sonst
# wuerde dieselbe Adresse zweimal verifiziert.
resource "aws_ses_email_identity" "empfaenger" {
  count = var.recipient_email == var.sender_email ? 0 : 1

  email = var.recipient_email
}
