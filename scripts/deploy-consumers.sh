#!/usr/bin/env bash
# Rollt filter-dedup und notifier auf die Kafka-Instanz aus.
#
# Bewusst kein Terraform: Terraform verwaltet Infrastruktur, und
# Anwendungscode ueber user_data auszuliefern wuerde die Instanz bei
# jeder Codeaenderung ersetzen. Die systemd-Einheiten und die
# Konfiguration werden hier erzeugt, die Zugangsdaten holen sich die
# Dienste zur Laufzeit selbst aus SSM.
#
# Aufruf aus dem Projektverzeichnis: bash scripts/deploy-consumers.sh
set -euo pipefail

export AWS_EC2_METADATA_DISABLED=true

tf() { terraform -chdir=infra output -raw "$1" | tr -d '"'"'

'"'"'; }

HOST=$(tf kafka_public_dns)
BOOTSTRAP=$(tf kafka_bootstrap_servers)
TABELLE=$(tf dedup_table_name)
BUCKET=$(tf archive_bucket_name)
MAIL=$(tf notification_email)
PASSWORT_PARAM=$(tf kafka_password_ssm_parameter)
CA_PARAM=$(tf kafka_ca_certificate_ssm_parameter)
BENUTZER=$(tf kafka_sasl_username)

echo "Ziel: $HOST"

SSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new ec2-user@$HOST"

# Quellcode uebertragen. tar ueber die Pipe erspart es, scp fuer jede
# Datei einzeln aufzurufen, und uebernimmt die Verzeichnisstruktur.
echo "Uebertrage Quellcode..."
# gemeinsam/ enthaelt Faehigkeitsverzeichnis, Bewertung und Archiv-
# zugriff. Der filter-dedup braucht es zum Anreichern; ohne dieses
# Paket startet er nicht.
tar czf -   --exclude="__pycache__" --exclude="*.pyc" --exclude="build" --exclude="*.zip"   -C services filter-dedup notifier gemeinsam   | $SSH "sudo install -d -o ec2-user -g ec2-user /opt/jobradar && tar xzf - -C /opt/jobradar"

# Das Faehigkeitsprofil, falls vorhanden. Es enthaelt keine Unterlagen,
# nur die daraus erkannten Schlagwoerter - trotzdem verlaesst damit
# etwas Persoenliches den eigenen Rechner. Ohne die Datei laeuft die
# Pipeline wie zuvor, nur ohne Bewertung in der Mail.
PROFIL_LOKAL=bewerbung/profil.json
if [ -f "$PROFIL_LOKAL" ]; then
  echo "Uebertrage Faehigkeitsprofil (Schlagwoerter, keine Unterlagen)..."
  $SSH "cat > /opt/jobradar/profil.json" < "$PROFIL_LOKAL"
  PROFIL_ENTFERNT=/opt/jobradar/profil.json
else
  echo "Kein $PROFIL_LOKAL - Anzeigen werden ohne Bewertung gemeldet."
  echo "  Anlegen mit: (cd services/tracker && python -m tracker.main profil)"
  PROFIL_ENTFERNT=
fi

# Konfiguration. Enthaelt keine Geheimnisse - nur die Namen der
# SSM-Parameter, aus denen die Dienste Passwort und Zertifikat holen.
echo "Schreibe Konfiguration..."
# Die beiden MATCH_-Variablen bleiben leer. Ein leerer Wert heisst:
# nimm die Liste aus gemeinsam/ausschluss.py. Sie hier noch einmal
# auszuschreiben hiesse, dieselbe Liste an zwei Stellen zu pflegen - und
# genau das ist schon passiert: die Begriffe im Skript hingen dem Code
# hinterher, und der Consumer filterte nach der alten Fassung.
$SSH "cat > /opt/jobradar/env" <<ENV
KAFKA_BOOTSTRAP_SERVERS=$BOOTSTRAP
KAFKA_SASL_USERNAME=$BENUTZER
KAFKA_PASSWORD_SSM_PARAMETER=$PASSWORT_PARAM
KAFKA_CA_CERT_PATH=/opt/jobradar/ca.crt
KAFKA_TOPIC_RAW=jobs.raw
KAFKA_TOPIC_MATCHED=jobs.matched
DYNAMODB_TABLE_SEEN_JOBS=$TABELLE
MATCH_AUSSCHLUSS=
MATCH_ARBEITGEBER_AUSSCHLUSS=
S3_BUCKET_RAW_ARCHIVE=$BUCKET
JOBRADAR_PROFIL=$PROFIL_ENTFERNT
SES_SENDER_ADDRESS=$MAIL
SES_RECIPIENT_ADDRESS=$MAIL
AWS_DEFAULT_REGION=eu-central-1
ENV

echo "Richte Laufzeitumgebung ein..."
$SSH "bash -s" <<REMOTE
set -euo pipefail

# CA-Zertifikat aus SSM holen. Aendert es sich, genuegt ein erneuter
# Aufruf dieses Skripts.
aws ssm get-parameter --region eu-central-1 --name "$CA_PARAM"   --query 'Parameter.Value' --output text > /opt/jobradar/ca.crt

# Amazon Linux 2023 liefert python3.9 als Standard aus. boto3 warnt dort
# bereits vor dem Auslaufen des Supports, und die Lambda des Pollers
# laeuft auf 3.13 - eine einheitliche Version erspart Ueberraschungen,
# die nur auf einer der beiden Seiten auftreten.
sudo dnf install -q -y python3.13 >/dev/null

# Gemeinsame virtuelle Umgebung fuer beide Dienste. Sie haben dieselben
# Abhaengigkeiten; zwei getrennte Umgebungen waeren auf 1 GiB RAM nur
# unnoetiger Plattenverbrauch.
#
# Stammt eine vorhandene Umgebung aus einer aelteren Python-Version, wird
# sie verworfen - ein venv laesst sich nicht auf eine neue Version heben.
if [ -x /opt/jobradar/venv/bin/python ]; then
  VORHANDEN=\$(/opt/jobradar/venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  if [ "\$VORHANDEN" != "3.13" ]; then
    echo "Ersetze virtuelle Umgebung (war Python \$VORHANDEN)"
    rm -rf /opt/jobradar/venv
  fi
fi

if [ ! -d /opt/jobradar/venv ]; then
  python3.13 -m venv /opt/jobradar/venv
fi
/opt/jobradar/venv/bin/pip install --quiet --upgrade pip
/opt/jobradar/venv/bin/pip install --quiet -r /opt/jobradar/filter-dedup/requirements.txt

for DIENST in filter-dedup notifier; do
  MODUL=\$(echo "\$DIENST" | tr '-' '_')
  sudo tee /etc/systemd/system/jobradar-\$DIENST.service >/dev/null <<UNIT
[Unit]
Description=JobRadar \$DIENST
# Der Broker muss laufen, bevor ein Consumer sich verbinden kann.
Requires=kafka.service
After=kafka.service

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/jobradar/\$DIENST
EnvironmentFile=/opt/jobradar/env
# Das gemeinsame Paket liegt neben den Diensten. Die Pakete finden es
# zwar auch selbst ueber ihren Ablageort, aber ein gesetzter Pfad ist
# das, worauf man beim Suchen zuerst schaut.
Environment=PYTHONPATH=/opt/jobradar/gemeinsam
ExecStart=/opt/jobradar/venv/bin/python -m \$MODUL.main
# Bei einem Absturz neu starten. Dank bestaetigter Offsets setzt der
# Dienst dort fort, wo er aufgehoert hat.
Restart=always
RestartSec=10
# Speicherbremse: auf 1 GiB RAM darf kein Consumer den Broker verdraengen.
MemoryMax=200M

[Install]
WantedBy=multi-user.target
UNIT
done

sudo systemctl daemon-reload
sudo systemctl enable --now jobradar-filter-dedup.service jobradar-notifier.service
sudo systemctl restart jobradar-filter-dedup.service jobradar-notifier.service
REMOTE

echo "Status:"
$SSH "systemctl is-active jobradar-filter-dedup jobradar-notifier"
