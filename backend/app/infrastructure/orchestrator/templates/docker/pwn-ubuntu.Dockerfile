# Cerberus CTF - Pwn Ubuntu Challenge Template
# Supports: Ubuntu 22.04 with glibc variants (2.31, 2.35, 2.37)

ARG GLIBC_VERSION=2.35
FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Install dependencies based on glibc version
RUN apt-get update && apt-get install -y --no-install-recommends \
    libc6 \
    libstdc++6 \
    socat \
    xinetd \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create CTF user (no shell access)
RUN groupadd -r ctf && useradd -r -g ctf -s /bin/false ctf

# Create challenge directory
WORKDIR /home/ctf

# Copy challenge binary and flag
COPY --chown=root:root challenge /home/ctf/
COPY --chown=root:root flag.txt /home/ctf/
COPY --chown=root:root start.sh /home/ctf/

# Set permissions
# Binary: readable/executable by ctf, not writable
# Flag: readable only by root
# start.sh: executable
RUN chmod 755 /home/ctf/challenge \
    && chmod 400 /home/ctf/flag.txt \
    && chmod 755 /home/ctf/start.sh

# Create tmp directory for challenge use
RUN mkdir -p /tmp/ctf && chmod 777 /tmp/ctf

# Remove unnecessary binaries that could be used for escapes
RUN rm -f /bin/mount /bin/umount /sbin/mount /sbin/umount \
    && rm -f /usr/bin/su /bin/su \
    && rm -f /usr/bin/sudo /usr/sbin/sudo \
    && rm -f /usr/bin/passwd /usr/sbin/passwd

# Switch to ctf user for running the challenge
USER ctf

# Expose the service port
EXPOSE 1337

# Health check - check if service is responding
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD echo "ping" | nc -q 1 localhost 1337 || exit 1

# Start the challenge using socat
CMD ["/home/ctf/start.sh"]

# Alternative start script for socat:
# socat TCP-LISTEN:1337,reuseaddr,fork EXEC:/home/ctf/challenge,stderr