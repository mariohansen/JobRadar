terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # ~> 6.0 erlaubt Updates innerhalb 6.x, aber keinen Sprung auf 7.0.
      # Major-Versionen des AWS-Providers aendern regelmaessig
      # Ressourcen-Argumente und brechen bestehenden Code.
      version = "~> 6.0"
    }

    # Erzeugt CA und Broker-Zertifikat lokal. Keine AWS-Ressourcen,
    # keine Kosten.
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }

    # Erzeugt das Broker-Passwort, damit es nirgends von Hand
    # eingetippt und versehentlich committet wird.
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Kein Remote-Backend: der State liegt lokal in infra/terraform.tfstate.
  # Fuer ein Solo-Projekt auf einem Rechner reicht das, und ein
  # S3-Backend haette ein Henne-Ei-Problem - der State-Bucket muesste
  # existieren, bevor Terraform ihn anlegen kann.
  #
  # Wichtig: der State enthaelt Werte im Klartext, auch Passwoerter.
  # Er steht deshalb in .gitignore und gehoert nie ins Repo.
}
