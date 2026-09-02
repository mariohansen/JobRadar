variable "project_name" {
  description = "Praefix fuer die Ressourcennamen"
  type        = string
}

variable "vpc_cidr" {
  description = "Adressraum der VPC"
  type        = string
}

variable "public_subnet_cidr" {
  description = "Adressraum des oeffentlichen Subnetzes"
  type        = string
}
