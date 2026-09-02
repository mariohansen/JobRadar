output "table_name" {
  description = "Name der Dedup-Tabelle"
  value       = aws_dynamodb_table.seen_jobs.name
}

output "table_arn" {
  description = "ARN der Dedup-Tabelle, fuer IAM-Policies"
  value       = aws_dynamodb_table.seen_jobs.arn
}

output "bucket_name" {
  description = "Name des Archiv-Buckets"
  value       = aws_s3_bucket.archive.id
}

output "bucket_arn" {
  description = "ARN des Archiv-Buckets, fuer IAM-Policies"
  value       = aws_s3_bucket.archive.arn
}
