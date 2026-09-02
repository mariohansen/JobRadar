variable "project_name" {
  description = "Praefix fuer die Ressourcennamen"
  type        = string
}

variable "account_id" {
  description = "AWS-Account-ID, macht den Bucket-Namen weltweit eindeutig"
  type        = string
}
