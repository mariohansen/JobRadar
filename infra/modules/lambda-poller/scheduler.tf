# Zeitplan fuer den Poller.
#
# EventBridge Scheduler statt der aelteren EventBridge Rule: er kennt
# Zeitzonen, wodurch "morgens um sieben" auch nach der Zeitumstellung
# stimmt. Eine Rule koennte nur UTC und muesste zweimal im Jahr
# nachgezogen werden.
#
# Kosten: 14 Millionen Aufrufe pro Monat sind kostenlos. Wir liegen bei
# rund 90.

# Anders als eine EventBridge Rule ruft der Scheduler die Funktion nicht
# ueber eine Berechtigung an der Lambda auf, sondern mit einer eigenen
# Rolle. Deshalb braucht er hier ein eigenes Gegenstueck.
data "aws_iam_policy_document" "assume_scheduler" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.project_name}-poller-scheduler"
  description        = "Erlaubt dem Zeitplan, die Poller-Lambda aufzurufen"
  assume_role_policy = data.aws_iam_policy_document.assume_scheduler.json
}

data "aws_iam_policy_document" "invoke_poller" {
  statement {
    sid       = "InvokePoller"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.poller.arn]
  }
}

resource "aws_iam_role_policy" "invoke_poller" {
  name   = "invoke-poller"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.invoke_poller.json
}

resource "aws_scheduler_schedule" "poller" {
  name        = "${var.project_name}-poller"
  description = "Ruft den Poller nach Zeitplan auf"

  # OFF bedeutet: exakt zur angegebenen Zeit. Die Alternative FLEXIBLE
  # laesst AWS den Aufruf innerhalb eines Fensters verteilen, was bei
  # vielen Zeitplaenen die Last glaettet - hier ohne Nutzen.
  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "Europe/Berlin"

  target {
    arn      = aws_lambda_function.poller.arn
    role_arn = aws_iam_role.scheduler.arn
  }
}
