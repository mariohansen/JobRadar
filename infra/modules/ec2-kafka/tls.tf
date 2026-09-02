# Eigene Certificate Authority fuer den Broker.
#
# Let's Encrypt stellt fuer *.compute.amazonaws.com keine Zertifikate aus,
# und eine eigene Domain gibt es nicht. Also eine eigene CA: sie signiert
# das Broker-Zertifikat, und der Client bekommt das CA-Zertifikat als
# Vertrauensanker mit. Kosten: keine, der tls-Provider rechnet lokal.
#
# Zu beachten: die privaten Schluessel landen im Terraform-State. Der
# liegt lokal und ist gitignored - aber er ist damit eine Datei, die man
# behandeln muss wie einen Schluesselbund.

resource "tls_private_key" "ca" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "tls_self_signed_cert" "ca" {
  private_key_pem = tls_private_key.ca.private_key_pem

  subject {
    common_name  = "${var.project_name} internal CA"
    organization = var.project_name
  }

  validity_period_hours = 8760 # ein Jahr
  is_ca_certificate     = true

  # Eine CA darf ausschliesslich signieren, nicht selbst als Server
  # auftreten.
  allowed_uses = [
    "cert_signing",
    "crl_signing",
  ]
}

resource "tls_private_key" "broker" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_cert_request" "broker" {
  private_key_pem = tls_private_key.broker.private_key_pem

  subject {
    common_name  = "kafka.${var.project_name}"
    organization = var.project_name
  }

  # Kernpunkt: der oeffentliche DNS-Name der Instanz aendert sich bei
  # jedem Stop/Start, folgt aber immer dem Muster
  # ec2-<ip>.<region>.compute.amazonaws.com. Das Wildcard deckt damit
  # jede kuenftige Adresse ab - die Hostname-Pruefung im Client bleibt
  # aktiv, statt sie abschalten zu muessen.
  dns_names = [
    "*.${var.aws_region}.compute.amazonaws.com",
    "localhost",
  ]

  ip_addresses = ["127.0.0.1"]
}

resource "tls_locally_signed_cert" "broker" {
  cert_request_pem   = tls_cert_request.broker.cert_request_pem
  ca_private_key_pem = tls_private_key.ca.private_key_pem
  ca_cert_pem        = tls_self_signed_cert.ca.cert_pem

  validity_period_hours = 8760

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]
}

# Broker-Passwort fuer den SASL-Benutzer. Ohne Sonderzeichen, weil der
# Wert in einen JAAS-Konfigurationsstring eingesetzt wird und
# Anfuehrungszeichen oder Backslashes dort nur Aerger machen.
resource "random_password" "kafka_user" {
  length  = 32
  special = false
}
