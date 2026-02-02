# Cerberus CTF - AD Service Challenge Template
# Active Directory style service with healthcheck sidecar

FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    samba \
    samba-common \
    smbclient \
    ldap-utils \
    slapd \
    ldapscripts \
    curl \
    netcat \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create service user
RUN groupadd -r ctf && useradd -r -g ctf -s /bin/false ctf

# Create directories
RUN mkdir -p /var/lib/samba /var/log/supervisor /etc/supervisor/conf.d

# Copy configuration files
COPY --chown=root:root smb.conf /etc/samba/
COPY --chown=root:root slapd.conf /etc/ldap/
COPY --chown=root:root supervisord.conf /etc/supervisor/
COPY --chown=root:root start.sh /start.sh

# Copy challenge files
COPY --chown=ctf:ctf challenge/ /opt/challenge/

# Set permissions
RUN chmod 755 /start.sh \
    && chmod -R 755 /opt/challenge

# Create flag files with proper permissions
RUN echo "CERBERUS{PLACEHOLDER_FLAG}" > /root/flag.txt \
    && chmod 400 /root/flag.txt

# Expose ports
# 389 - LDAP
# 445 - SMB
# 139 - NetBIOS
EXPOSE 389 445 139

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD (nc -z localhost 389 && nc -z localhost 445) || exit 1

# Start services via supervisor
CMD ["/start.sh"]