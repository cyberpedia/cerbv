# Cerberus CTF - Crypto Static Challenge Template
# Supports: Python scripts for challenge generation and verification

FROM python:3.11-slim-bookworm

# Security: Run as non-root
RUN groupadd -r ctf && useradd -r -g ctf -s /bin/false ctf

# Install required packages for crypto challenges
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgmp-dev \
    libmpfr-dev \
    libmpc-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python crypto libraries
RUN pip install --no-cache-dir \
    pycryptodome \
    sympy \
    gmpy2 \
    numpy \
    sageconf 2>/dev/null || true

# Create challenge directory
WORKDIR /challenge

# Copy challenge files
COPY --chown=ctf:ctf . .

# Set permissions
RUN chmod -R 755 /challenge \
    && chmod -R 777 /challenge/tmp 2>/dev/null || true

# Switch to non-root user
USER ctf

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp

# Default command runs the challenge generator/verifier
CMD ["python3", "challenge.py"]