# Kostenwaechter.
#
# AWS Budgets prueft taeglich die aufgelaufenen Kosten des Accounts und
# schickt eine E-Mail, wenn eine Schwelle gerissen wird. Das ist die
# einzige Ressource in diesem Projekt, die nichts zur Funktion beitraegt
# und trotzdem zuerst kommt: bei einem Guthaben-Account ist die teuerste
# Ueberraschung die, von der man erst auf der Rechnung erfaehrt.
#
# Alternative waere ein CloudWatch-Billing-Alarm. Der kann aber nur auf
# bereits angefallene Kosten reagieren, waehrend Budgets zusaetzlich eine
# Hochrechnung auf das Monatsende auswertet - man wird also gewarnt,
# bevor das Geld weg ist, nicht danach.
#
# Kosten: die ersten beiden Budgets pro Account sind kostenlos,
# Benachrichtigungen ohnehin. Wir legen genau eines an.

resource "aws_budgets_budget" "monthly" {
  name = "${var.project_name}-monthly"

  budget_type  = "COST"
  limit_amount = var.monthly_limit_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Schwelle 1: die Haelfte ist tatsaechlich ausgegeben. Frueh genug, um
  # nachzusehen, was laeuft, und die Instanz notfalls zu stoppen.
  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }

  # Schwelle 2: die Hochrechnung aufs Monatsende reisst das Limit. Das
  # schlaegt an, waehrend noch Zeit zum Gegensteuern ist - typisch fuer
  # eine Ressource, die versehentlich durchlaeuft.
  notification {
    notification_type          = "FORECASTED"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }
}
