#!/bin/bash
###############################################################################
# Cerberus CTF Platform - System Hardening Script
# Filename: 01-hard-system.sh
# Description: CIS Benchmarks Level 2 hardening, user management, sysctl tuning
# Target: Ubuntu 22.04 LTS
# Requirements: root privileges
###############################################################################

set -euo pipefail
IFS=$'\n\t'

# Configuration
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_DIR="/var/log"
readonly LOG_FILE="${LOG_DIR}/cerberus-setup.log"
readonly BACKUP_DIR="/opt/cerberus/backups/$(date +%Y%m%d_%H%M%S)"
readonly CERBERUS_USER="cerberus"
readonly CERBERUS_UID="1337"
readonly CERBERUS_HOME="/opt/cerberus"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

###############################################################################
# LOGGING FUNCTIONS
###############################################################################

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

info() { log "INFO" "$@"; }
warn() { log "WARN" "${YELLOW}$*${NC}"; }
error() { log "ERROR" "${RED}$*${NC}"; }
success() { log "SUCCESS" "${GREEN}$*${NC}"; }

###############################################################################
# UTILITY FUNCTIONS
###############################################################################

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
    success "Running with root privileges"
}

# Initialize logging
init_logging() {
    mkdir -p "${LOG_DIR}"
    mkdir -p "${BACKUP_DIR}"
    exec 1> >(tee -a "${LOG_FILE}")
    exec 2> >(tee -a "${LOG_FILE}" >&2)
    info "Starting ${SCRIPT_NAME}"
    info "Backup directory: ${BACKUP_DIR}"
}

# Backup file before modification
backup_file() {
    local file="$1"
    if [[ -f "$file" ]]; then
        local backup_name
        backup_name="${BACKUP_DIR}/$(basename "$file").bak"
        cp "$file" "$backup_name"
        info "Backed up ${file} to ${backup_name}"
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Idempotent line addition to file
add_line_if_not_exists() {
    local line="$1"
    local file="$2"
    
    if [[ ! -f "$file" ]]; then
        mkdir -p "$(dirname "$file")"
        touch "$file"
    fi
    
    if ! grep -qF "${line}" "$file" 2>/dev/null; then
        echo "$line" >> "$file"
        info "Added to ${file}: ${line}"
    else
        info "Already exists in ${file}: ${line}"
    fi
}

###############################################################################
# SYSTEM HARDENING - CIS BENCHMARKS LEVEL 2
###############################################################################

harden_sysctl() {
    info "Applying sysctl hardening..."
    
    backup_file "/etc/sysctl.conf"
    
    # Network hardening
    add_line_if_not_exists "net.ipv4.ip_forward=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.all.send_redirects=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.default.send_redirects=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.all.accept_redirects=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.default.accept_redirects=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.all.secure_redirects=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.default.secure_redirects=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.all.log_martians=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.default.log_martians=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.icmp_echo_ignore_broadcasts=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.icmp_ignore_bogus_error_responses=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.all.rp_filter=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.conf.default.rp_filter=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "net.ipv4.tcp_syncookies=1" "/etc/sysctl.d/99-cerberus.conf"
    
    # Performance tuning (as specified)
    add_line_if_not_exists "net.core.somaxconn=65535" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "vm.swappiness=10" "/etc/sysctl.d/99-cerberus.conf"
    
    # Kernel hardening
    add_line_if_not_exists "kernel.randomize_va_space=2" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "fs.suid_dumpable=0" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "kernel.kptr_restrict=2" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "kernel.dmesg_restrict=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "fs.protected_hardlinks=1" "/etc/sysctl.d/99-cerberus.conf"
    add_line_if_not_exists "fs.protected_symlinks=1" "/etc/sysctl.d/99-cerberus.conf"
    
    # Apply sysctl settings
    sysctl --system > /dev/null 2>&1 || true
    success "Sysctl hardening applied"
}

harden_ssh() {
    info "Hardening SSH configuration..."
    
    backup_file "/etc/ssh/sshd_config"
    
    # Create hardening config
    cat > /etc/ssh/sshd_config.d/99-cerberus.conf << 'EOF'
# Cerberus SSH Hardening
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
LoginGraceTime 60
AllowUsers cerberus
Banner /etc/ssh/banner
EOF
    
    # Create SSH banner
    cat > /etc/ssh/banner << 'EOF'
***************************************************************************
*                         CERBERUS CTF PLATFORM                           *
*                         Authorized Access Only                          *
*        All activities are monitored and recorded.                       *
***************************************************************************
EOF
    
    chmod 644 /etc/ssh/banner
    chmod 644 /etc/ssh/sshd_config.d/99-cerberus.conf
    
    # Verify SSH config before restarting
    if sshd -t 2>/dev/null; then
        systemctl restart sshd || warn "SSH service restart failed"
        success "SSH hardening applied"
    else
        error "SSH configuration test failed"
        return 1
    fi
}

harden_pam() {
    info "Configuring PAM policies..."
    
    # Password policy
    backup_file "/etc/pam.d/common-password"
    
    # Install libpam-pwquality if not present
    if ! command_exists pwquality; then
        apt-get update -qq
        apt-get install -y -qq libpam-pwquality cracklib-runtime
    fi
    
    # Configure pwquality
    backup_file "/etc/security/pwquality.conf"
    cat > /etc/security/pwquality.conf << 'EOF'
minlen = 14
dcredit = -1
ucredit = -1
ocredit = -1
lcredit = -1
retry = 3
EOF
    
    success "PAM policies configured"
}

harden_login_defs() {
    info "Configuring login.defs..."
    
    backup_file "/etc/login.defs"
    
    # Update password aging policies
    sed -i 's/^PASS_MAX_DAYS.*/PASS_MAX_DAYS 90/' /etc/login.defs 2>/dev/null || true
    sed -i 's/^PASS_MIN_DAYS.*/PASS_MIN_DAYS 7/' /etc/login.defs 2>/dev/null || true
    sed -i 's/^PASS_WARN_AGE.*/PASS_WARN_AGE 7/' /etc/login.defs 2>/dev/null || true
    
    # Ensure UMASK is restrictive
    sed -i 's/^UMASK.*/UMASK 077/' /etc/login.defs 2>/dev/null || true
    
    success "Login.defs configured"
}

###############################################################################
# USER MANAGEMENT
###############################################################################

create_cerberus_user() {
    info "Creating cerberus service user..."
    
    if id "${CERBERUS_USER}" >/dev/null 2>&1; then
        # Check if UID matches
        local current_uid
        current_uid=$(id -u "${CERBERUS_USER}")
        if [[ "$current_uid" != "${CERBERUS_UID}" ]]; then
            warn "User ${CERBERUS_USER} exists with different UID (${current_uid}), fixing..."
            usermod -u "${CERBERUS_UID}" "${CERBERUS_USER}"
        else
            info "User ${CERBERUS_USER} already exists with correct UID"
        fi
    else
        # Create user with specific UID, no password, locked account
        useradd -m -u "${CERBERUS_UID}" \
                -d "${CERBERUS_HOME}" \
                -s /bin/bash \
                -c "Cerberus CTF Platform Service Account" \
                "${CERBERUS_USER}"
        
        # Lock password (no password login)
        passwd -l "${CERBERUS_USER}" >/dev/null 2>&1 || true
        
        success "Created user ${CERBERUS_USER} with UID ${CERBERUS_UID}"
    fi
    
    # Create .ssh directory
    local ssh_dir="${CERBERUS_HOME}/.ssh"
    mkdir -p "${ssh_dir}"
    chmod 700 "${ssh_dir}"
    chown "${CERBERUS_USER}:${CERBERUS_USER}" "${ssh_dir}"
    
    # Create authorized_keys file (admin must add keys)
    touch "${ssh_dir}/authorized_keys"
    chmod 600 "${ssh_dir}/authorized_keys"
    chown "${CERBERUS_USER}:${CERBERUS_USER}" "${ssh_dir}/authorized_keys"
    
    info "SSH key placeholder created at ${ssh_dir}/authorized_keys"
    info "Add SSH public keys before attempting SSH login"
}

###############################################################################
# PACKAGE MANAGEMENT & SECURITY UPDATES
###############################################################################

install_security_packages() {
    info "Installing security packages..."
    
    apt-get update -qq
    
    # Essential security packages
    local packages=(
        "ufw"
        "fail2ban"
        "auditd"
        "audispd-plugins"
        "chrony"
        "tpm2-tools"
        "tpm2-abrmd"
        "cryptsetup"
        "cryptsetup-initramfs"
        "vim"
        "curl"
        "wget"
        "gnupg"
        "software-properties-common"
        "apt-transport-https"
        "ca-certificates"
        "debsums"
        "rkhunter"
        "chkrootkit"
        "libpam-pwquality"
        "apparmor"
        "apparmor-utils"
    )
    
    for pkg in "${packages[@]}"; do
        if dpkg -l "$pkg" >/dev/null 2>&1; then
            info "Package ${pkg} already installed"
        else
            apt-get install -y -qq "$pkg" && info "Installed ${pkg}"
        fi
    done
    
    success "Security packages installed"
}

###############################################################################
# TIME SYNCHRONIZATION
###############################################################################

configure_ntp() {
    info "Configuring NTP time synchronization..."
    
    # Enable and configure chrony
    systemctl enable chrony >/dev/null 2>&1 || true
    
    backup_file "/etc/chrony/chrony.conf"
    
    cat > /etc/chrony/chrony.conf << 'EOF'
# Cerberus NTP Configuration
pool time.google.com iburst
pool ntp.ubuntu.com iburst

driftfile /var/lib/chrony/chrony.drift
makestep 1.0 3
maxupdateskew 100.0
rtcsync
logdir /var/log/chrony
log tracking measurements statistics
EOF
    
    systemctl restart chrony
    
    # Wait for sync
    info "Waiting for time synchronization..."
    sleep 2
    
    if chronyc tracking >/dev/null 2>&1; then
        success "NTP configured and synchronized"
    else
        warn "NTP may not be fully synchronized yet"
    fi
}

###############################################################################
# AUDIT CONFIGURATION
###############################################################################

configure_auditd() {
    info "Configuring auditd for security monitoring..."
    
    systemctl enable auditd >/dev/null 2>&1 || true
    
    # Create audit rules
    cat > /etc/audit/rules.d/cerberus.rules << 'EOF'
## Cerberus CTF Platform Audit Rules

# Monitor /etc/passwd and /etc/shadow
-w /etc/passwd -p wa -k identity_changes
-w /etc/shadow -p wa -k identity_changes
-w /etc/group -p wa -k identity_changes
-w /etc/gshadow -p wa -k identity_changes
-w /etc/security/opasswd -p wa -k identity_changes

# Monitor /opt/cerberus
-w /opt/cerberus -p wa -k cerberus_data_changes

# Monitor privileged commands
-a always,exit -F arch=b64 -S setuid -S setgid -S setreuid -S setregid -k privilege_escalation
-a always,exit -F arch=b64 -S setresuid -S setresgid -S setfsuid -S setfsgid -k privilege_escalation

# Monitor user/group modifications
-w /usr/sbin/useradd -p x -k user_management
-w /usr/sbin/userdel -p x -k user_management
-w /usr/sbin/usermod -p x -k user_management
-w /usr/sbin/groupadd -p x -k user_management
-w /usr/sbin/groupdel -p x -k user_management
-w /usr/sbin/groupmod -p x -k user_management

# Monitor sudoers
-w /etc/sudoers -p wa -k sudoers_changes
-w /etc/sudoers.d -p wa -k sudoers_changes

# Monitor SSH configuration
-w /etc/ssh/sshd_config -p wa -k ssh_config_changes
-w /etc/ssh/sshd_config.d -p wa -k ssh_config_changes

# Monitor Docker (if installed later)
-w /etc/docker -p wa -k docker_config_changes
-w /var/lib/docker -p wa -k docker_data_changes

# Log all commands run by root
-a always,exit -F arch=b64 -F euid=0 -S execve -k root_commands

# Make audit rules immutable (requires reboot to change)
-e 2
EOF
    
    chmod 640 /etc/audit/rules.d/cerberus.rules
    
    # Reload audit rules
    if systemctl is-active --quiet auditd; then
        auditctl -R /etc/audit/rules.d/cerberus.rules >/dev/null 2>&1 || true
    fi
    
    success "Auditd configured"
}

###############################################################################
# DISABLE ROOT LOGIN
###############################################################################

disable_root_login() {
    info "Disabling root login..."
    
    # Lock root password
    passwd -l root >/dev/null 2>&1 || true
    
    # Ensure root cannot login via SSH (redundant with sshd_config but safe)
    usermod -s /usr/sbin/nologin root 2>/dev/null || true
    
    success "Root login disabled"
}

###############################################################################
# VERIFICATION
###############################################################################

verify_setup() {
    info "Running verification checks..."
    
    local errors=0
    
    # Check user exists
    if id "${CERBERUS_USER}" >/dev/null 2>&1; then
        success "User ${CERBERUS_USER} exists"
    else
        error "User ${CERBERUS_USER} does not exist"
        ((errors++))
    fi
    
    # Check UID
    local current_uid
    current_uid=$(id -u "${CERBERUS_USER}" 2>/dev/null || echo "0")
    if [[ "$current_uid" == "${CERBERUS_UID}" ]]; then
        success "User ${CERBERUS_USER} has correct UID ${CERBERUS_UID}"
    else
        error "User ${CERBERUS_USER} has incorrect UID: ${current_uid}"
        ((errors++))
    fi
    
    # Check sysctl values
    if [[ "$(cat /proc/sys/net/core/somaxconn)" == "65535" ]]; then
        success "net.core.somaxconn is set correctly"
    else
        warn "net.core.somaxconn value check failed"
    fi
    
    if [[ "$(cat /proc/sys/vm/swappiness)" == "10" ]]; then
        success "vm.swappiness is set correctly"
    else
        warn "vm.swappiness value check failed"
    fi
    
    # Check SSH config
    if grep -q "PermitRootLogin no" /etc/ssh/sshd_config.d/99-cerberus.conf 2>/dev/null; then
        success "SSH root login disabled"
    else
        warn "SSH root login config check failed"
    fi
    
    # Check services
    if systemctl is-enabled chrony >/dev/null 2>&1; then
        success "chrony is enabled"
    else
        warn "chrony may not be enabled"
    fi
    
    if systemctl is-enabled auditd >/dev/null 2>&1 || systemctl is-enabled auditd.service >/dev/null 2>&1; then
        success "auditd is enabled"
    else
        warn "auditd may not be enabled"
    fi
    
    if [[ $errors -eq 0 ]]; then
        success "All verification checks passed"
        return 0
    else
        error "${errors} verification check(s) failed"
        return 1
    fi
}

###############################################################################
# MAIN
###############################################################################

main() {
    check_root
    init_logging
    
    info "=================================================="
    info "Cerberus System Hardening Script"
    info "=================================================="
    
    # Update package lists
    apt-get update -qq
    
    # Run hardening functions
    harden_sysctl
    harden_ssh
    harden_pam
    harden_login_defs
    create_cerberus_user
    install_security_packages
    configure_ntp
    configure_auditd
    disable_root_login
    
    # Verification
    verify_setup
    
    info "=================================================="
    success "System hardening complete!"
    info "=================================================="
    info "IMPORTANT NEXT STEPS:"
    info "1. Add SSH public key to ${CERBERUS_HOME}/.ssh/authorized_keys"
    info "2. Test SSH login as ${CERBERUS_USER} before disconnecting"
    info "3. Run disk encryption script: ./02-disk-encryption.sh"
    info "4. Run Docker setup script: ./03-docker-setup.sh"
    info "=================================================="
    
    exit 0
}

# Run main function
main "$@"
