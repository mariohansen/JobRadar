# Diese Werte braucht das ec2-kafka-Modul, um Instanz und Security Group
# im richtigen Netz zu platzieren.

output "vpc_id" {
  description = "ID der VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "ID des oeffentlichen Subnetzes fuer die Kafka-Instanz"
  value       = aws_subnet.public.id
}
