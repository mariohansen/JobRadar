provider "aws" {
  region = var.aws_region

  # Diese Tags haengen automatisch an jeder Ressource, die der Provider
  # anlegt. In der Kostenuebersicht wird damit sofort sichtbar, was
  # JobRadar verursacht, und beim Aufraeumen ist erkennbar, was
  # dazugehoert.
  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}
