output "function_name" {
  description = "Name der Lambda, etwa fuer: aws lambda invoke"
  value       = aws_lambda_function.poller.function_name
}

output "log_group_name" {
  description = "Log-Gruppe der Funktion"
  value       = aws_cloudwatch_log_group.poller.name
}

output "schedule_expression" {
  description = "Aktiver Zeitplan"
  value       = aws_scheduler_schedule.poller.schedule_expression
}
