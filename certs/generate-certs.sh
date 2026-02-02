#!/bin/bash
# Cerberus CTF Platform - TLS Certificate Generation
# Generates self-signed CA and service certificates for internal TLS

set -euo pipefail

CERT_DIR="${CERT_DIR:-/opt/cerberus/certs}"
VALIDITY_DAYS="${VALIDITY_DAYS:-365}"
CA_SUBJECT="/C=US/ST=State/L=City/O=Cerberus CTF/OU=Security/CN=Cerberus CA"

log() {
    echo "[$(date -Iseconds)] $*"
}

# Create certificate directory
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# Generate CA private key
if [[ ! -f ca.key ]]; then
    log "Generating CA private key..."
    openssl genrsa -out ca.key 4096
    chmod 600 ca.key
fi

# Generate CA certificate
if [[ ! -f ca.crt ]]; then
    log "Generating CA certificate..."
    openssl req -new -x509 -days $VALIDITY_DAYS -key ca.key -out ca.crt \
        -subj "$CA_SUBJECT"
fi

# Function to generate service certificate
generate_service_cert() {
    local service_name="$1"
    local san="${2:-DNS:localhost,DNS:$service_name,IP:127.0.0.1}"
    
    log "Generating certificate for $service_name..."
    
    # Generate private key
    openssl genrsa -out "${service_name}.key" 2048
    chmod 600 "${service_name}.key"
    
    # Generate CSR
    openssl req -new -key "${service_name}.key" -out "${service_name}.csr" \
        -subj "/C=US/ST=State/L=City/O=Cerberus CTF/OU=$service_name/CN=$service_name"
    
    # Create extension file for SAN
    cat > "${service_name}.ext" << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = $san
EOF
    
    # Sign certificate with CA
    openssl x509 -req -in "${service_name}.csr" -CA ca.crt -CAkey ca.key \
        -CAcreateserial -out "${service_name}.crt" -days $VALIDITY_DAYS \
        -extfile "${service_name}.ext"
    
    # Clean up
    rm -f "${service_name}.csr" "${service_name}.ext"
    
    log "Certificate generated: ${service_name}.crt"
}

# Generate certificates for each service
generate_service_cert "postgres" "DNS:localhost,DNS:postgres-primary,DNS:postgres,IP:127.0.0.1"
generate_service_cert "redis" "DNS:localhost,DNS:redis,IP:127.0.0.1"
generate_service_cert "minio" "DNS:localhost,DNS:minio,DNS:minio.cerberus.local,IP:127.0.0.1"
generate_service_cert "pgbouncer" "DNS:localhost,DNS:pgbouncer,IP:127.0.0.1"

# Set permissions
chmod 644 *.crt
chmod 600 *.key

log "All certificates generated successfully in $CERT_DIR"
ls -la "$CERT_DIR"
