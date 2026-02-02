#!/bin/bash
###############################################################################
# Cerberus CTF Platform - Disk Encryption Script
# Filename: 02-disk-encryption.sh
# Description: LUKS encryption for data partition with TPM2 auto-unlock
#              and passphrase fallback
# Target: Ubuntu 22.04 LTS
# Requirements: root privileges, TPM2 module, target disk
###############################################################################

set -euo pipefail
IFS=$'\n\t'

# Configuration
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_DIR="/var/log"
readonly LOG_FILE="${LOG_DIR}/cerberus-setup.log"
readonly BACKUP_DIR="/opt/cerberus/backups/$(date +%Y%m%d_%H%M%S)"

# Disk configuration
readonly TARGET_DISK="/dev/nvme1n1"
readonly LUKS_NAME="cerberus-data"
readonly LUKS_DEV="/dev/mapper/${LUKS_NAME}"
readonly MOUNT_POINT="/opt/cerberus/data"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

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
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

###############################################################################
# PREREQUISITE CHECKS
###############################################################################

check_prerequisites() {
    info "Checking prerequisites..."
    
    # Check for required tools
    local required_tools=("cryptsetup" "tpm2_getcap" "tpm2_nvread" "lsblk" "blkid")
    for tool in "${required_tools[@]}"; do
        if ! command_exists "$tool"; then
            error "Required tool not found: ${tool}"
            error "Install with: apt-get install cryptsetup tpm2-tools"
            exit 1
        fi
    done
    success "All required tools available"
    
    # Check if target disk exists
    if [[ ! -b "${TARGET_DISK}" ]]; then
        error "Target disk ${TARGET_DISK} does not exist"
        info "Available block devices:"
        lsblk -d -o NAME,SIZE,TYPE,MODEL 2>/dev/null || true
        exit 1
    fi
    success "Target disk ${TARGET_DISK} exists"
    
    # Check disk size
    local disk_size
    disk_size=$(lsblk -bnd -o SIZE "${TARGET_DISK}" 2>/dev/null || echo "0")
    local size_gb=$((disk_size / 1024 / 1024 / 1024))
    info "Target disk size: ${size_gb} GB"
    
    # Warn if disk is mounted
    if mount | grep -q "${TARGET_DISK}"; then
        error "Target disk ${TARGET_DISK} is currently mounted!"
        info "Unmount all partitions before proceeding:"
        mount | grep "${TARGET_DISK}"
        exit 1
    fi
    
    # Check TPM2 availability
    check_tpm2
}

check_tpm2() {
    info "Checking TPM2 availability..."
    
    # Check if TPM2 module is loaded
    if [[ -c /dev/tpm0 ]] || [[ -c /dev/tpmrm0 ]]; then
        success "TPM2 device found"
    else
        warn "TPM2 device not found. Checking for TPM module..."
        if lsmod | grep -q tpm; then
            warn "TPM module loaded but device not available"
        else
            warn "TPM module not loaded. Attempting to load..."
            modprobe tpm || true
            modprobe tpm_tis || true
            modprobe tpm_crb || true
        fi
    fi
    
    # Test TPM2 functionality
    if tpm2_getcap properties-fixed >/dev/null 2>&1; then
        success "TPM2 is functional"
        TPM2_AVAILABLE=true
    else
        warn "TPM2 is not functional - will use passphrase-only mode"
        TPM2_AVAILABLE=false
    fi
}

###############################################################################
# LUKS ENCRYPTION SETUP
###############################################################################

create_luks_container() {
    info "Setting up LUKS encryption on ${TARGET_DISK}..."
    
    # Check if already LUKS encrypted
    if cryptsetup isLuks "${TARGET_DISK}" 2>/dev/null; then
        warn "Disk ${TARGET_DISK} is already LUKS encrypted"
        read -rp "Do you want to proceed with opening existing container? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            info "Skipping LUKS setup"
            return 0
        fi
        open_luks_container
        return 0
    fi
    
    # Get passphrase from user (secure input)
    info "WARNING: All data on ${TARGET_DISK} will be erased!"
    read -rp "Do you want to continue? Type 'YES' to proceed: " confirm
    if [[ "$confirm" != "YES" ]]; then
        info "Aborted by user"
        exit 0
    fi
    
    # Get passphrase
    local passphrase
    local passphrase_confirm
    
    while true; do
        read -rsp "Enter LUKS passphrase (min 8 characters): " passphrase
        echo
        
        if [[ ${#passphrase} -lt 8 ]]; then
            warn "Passphrase must be at least 8 characters"
            continue
        fi
        
        read -rsp "Confirm passphrase: " passphrase_confirm
        echo
        
        if [[ "$passphrase" != "$passphrase_confirm" ]]; then
            warn "Passphrases do not match"
            continue
        fi
        
        break
    done
    
    # Create LUKS container with strong parameters
    info "Creating LUKS2 container (this may take a while)..."
    
    # Use LUKS2 with Argon2id for key derivation
    echo -n "$passphrase" | cryptsetup luksFormat \
        --type luks2 \
        --cipher aes-xts-plain64 \
        --key-size 512 \
        --hash sha512 \
        --pbkdf argon2id \
        --pbkdf-memory 1048576 \
        --pbkdf-parallel 4 \
        --pbkdf-force-iterations 4 \
        --iter-time 2000 \
        --sector-size 4096 \
        --label "${LUKS_NAME}" \
        "${TARGET_DISK}" -
    
    if [[ $? -ne 0 ]]; then
        error "Failed to create LUKS container"
        exit 1
    fi
    
    success "LUKS container created successfully"
    
    # Open the container
    info "Opening LUKS container..."
    echo -n "$passphrase" | cryptsetup open "${TARGET_DISK}" "${LUKS_NAME}" -
    
    if [[ ! -b "${LUKS_DEV}" ]]; then
        error "Failed to open LUKS container"
        exit 1
    fi
    
    success "LUKS container opened at ${LUKS_DEV}"
    
    # Clear passphrase from memory
    passphrase=""
    passphrase_confirm=""
}

open_luks_container() {
    info "Opening existing LUKS container..."
    
    if [[ -b "${LUKS_DEV}" ]]; then
        success "LUKS container already open at ${LUKS_DEV}"
        return 0
    fi
    
    cryptsetup open "${TARGET_DISK}" "${LUKS_NAME}" || {
        error "Failed to open LUKS container"
        exit 1
    }
    
    success "LUKS container opened at ${LUKS_DEV}"
}

###############################################################################
# FILESYSTEM SETUP
###############################################################################

create_filesystem() {
    info "Setting up filesystem..."
    
    # Check if filesystem already exists
    if blkid "${LUKS_DEV}" -o value -s TYPE >/dev/null 2>&1; then
        local existing_fs
        existing_fs=$(blkid "${LUKS_DEV}" -o value -s TYPE)
        warn "Filesystem already exists: ${existing_fs}"
        
        read -rp "Format anyway? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            info "Skipping filesystem creation"
            return 0
        fi
    fi
    
    # Create ext4 filesystem
    info "Creating ext4 filesystem..."
    mkfs.ext4 -L "${LUKS_NAME}" -E discard "${LUKS_DEV}"
    
    if [[ $? -ne 0 ]]; then
        error "Failed to create filesystem"
        exit 1
    fi
    
    success "Filesystem created"
}

mount_filesystem() {
    info "Mounting encrypted filesystem..."
    
    # Create mount point
    mkdir -p "${MOUNT_POINT}"
    
    # Check if already mounted
    if mount | grep -q "${LUKS_DEV}"; then
        success "Filesystem already mounted at ${MOUNT_POINT}"
        return 0
    fi
    
    # Mount
    mount "${LUKS_DEV}" "${MOUNT_POINT}"
    
    if [[ $? -ne 0 ]]; then
        error "Failed to mount filesystem"
        exit 1
    fi
    
    # Set permissions
    chown cerberus:cerberus "${MOUNT_POINT}"
    chmod 750 "${MOUNT_POINT}"
    
    success "Filesystem mounted at ${MOUNT_POINT}"
}

configure_fstab() {
    info "Configuring /etc/fstab and /etc/crypttab..."
    
    # Get UUID of the LUKS container
    local luks_uuid
    luks_uuid=$(blkid "${TARGET_DISK}" -o value -s UUID)
    
    if [[ -z "$luks_uuid" ]]; then
        error "Could not determine UUID of ${TARGET_DISK}"
        exit 1
    fi
    
    # Configure crypttab for passphrase unlock
    local crypttab_entry="${LUKS_NAME} UUID=${luks_uuid} none luks,discard"
    
    if grep -q "^${LUKS_NAME}" /etc/crypttab 2>/dev/null; then
        warn "Entry for ${LUKS_NAME} already exists in /etc/crypttab"
    else
        echo "${crypttab_entry}" >> /etc/crypttab
        success "Added to /etc/crypttab"
    fi
    
    # Configure fstab
    local fstab_entry="${LUKS_DEV} ${MOUNT_POINT} ext4 defaults,noatime,discard 0 2"
    
    if grep -q "${LUKS_DEV}" /etc/fstab 2>/dev/null; then
        warn "Entry for ${LUKS_DEV} already exists in /etc/fstab"
    else
        echo "${fstab_entry}" >> /etc/fstab
        success "Added to /etc/fstab"
    fi
    
    # Update initramfs
    update-initramfs -u -k all >/dev/null 2>&1 || true
}

###############################################################################
# TPM2 AUTO-UNLOCK SETUP
###############################################################################

setup_tpm2_unlock() {
    if [[ "${TPM2_AVAILABLE:-false}" != "true" ]]; then
        warn "TPM2 not available - skipping auto-unlock setup"
        info "System will require passphrase on boot"
        return 0
    fi
    
    info "Setting up TPM2 auto-unlock..."
    
    # Check if TPM2 already enrolled
    if cryptsetup luksDump "${TARGET_DISK}" | grep -q "tpm2"; then
        warn "TPM2 key already enrolled for this disk"
        return 0
    fi
    
    # Generate a random key for TPM2
    local tpm_key_file
    tpm_key_file=$(mktemp)
    chmod 600 "$tpm_key_file"
    
    # Generate 512-bit key
    dd if=/dev/urandom bs=1 count=64 of="$tpm_key_file" 2>/dev/null
    
    # Add key to LUKS (requires existing passphrase)
    info "Adding TPM2 key to LUKS (enter existing passphrase when prompted)..."
    cryptsetup luksAddKey "${TARGET_DISK}" "$tpm_key_file"
    
    if [[ $? -ne 0 ]]; then
        error "Failed to add TPM2 key to LUKS"
        rm -f "$tpm_key_file"
        return 1
    fi
    
    # Seal key with TPM2
    local nv_index="0x1500016"
    
    # Define NV space for the key
    tpm2_nvundefine "$nv_index" 2>/dev/null || true
    tpm2_nvdefine -s 64 -a "ownerread|ownerwrite|policywrite|policyread" "$nv_index"
    
    # Write key to NV
    tpm2_nvwrite -i "$tpm_key_file" "$nv_index"
    
    # Create policy for unseal (PCR 0, 2, 7 - system state)
    local policy_file
    policy_file=$(mktemp)
    tpm2_createpolicy --policy-pcr -l "sha256:0,2,7" -L "$policy_file"
    
    # Create systemd-cryptsetup drop-in for TPM2
    mkdir -p /etc/cryptsetup-keys.d
    
    # Create key file that will be used by systemd-cryptenroll
    cp "$tpm_key_file" "/etc/cryptsetup-keys.d/${LUKS_NAME}.key"
    chmod 600 "/etc/cryptsetup-keys.d/${LUKS_NAME}.key"
    
    # Use systemd-cryptenroll if available
    if command_exists systemd-cryptenroll; then
        info "Using systemd-cryptenroll for TPM2 enrollment..."
        systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=0+2+7 "${TARGET_DISK}"
    else
        warn "systemd-cryptenroll not available"
        info "Manual TPM2 unlock configuration required"
    fi
    
    # Clean up
    rm -f "$tpm_key_file" "$policy_file"
    
    success "TPM2 auto-unlock configured"
    info "Note: TPM2 binding uses PCRs 0, 2, 7 (system firmware, kernel, secure boot policy)"
    info "If these change, you will need to use the passphrase"
}

###############################################################################
# VERIFICATION
###############################################################################

verify_encryption() {
    info "Running verification checks..."
    
    local errors=0
    
    # Check LUKS header
    if cryptsetup isLuks "${TARGET_DISK}"; then
        success "LUKS header verified on ${TARGET_DISK}"
    else
        error "LUKS header not found on ${TARGET_DISK}"
        ((errors++))
    fi
    
    # Check container is open
    if [[ -b "${LUKS_DEV}" ]]; then
        success "LUKS device open at ${LUKS_DEV}"
    else
        error "LUKS device not open"
        ((errors++))
    fi
    
    # Check mount
    if mount | grep -q "${MOUNT_POINT}"; then
        success "Filesystem mounted at ${MOUNT_POINT}"
        
        # Check writability
        if touch "${MOUNT_POINT}/.cerberus_test" 2>/dev/null; then
            rm -f "${MOUNT_POINT}/.cerberus_test"
            success "Filesystem is writable"
        else
            warn "Filesystem may not be writable"
        fi
    else
        error "Filesystem not mounted"
        ((errors++))
    fi
    
    # Check ownership
    if [[ "$(stat -c %U "${MOUNT_POINT}")" == "cerberus" ]]; then
        success "Mount point owned by cerberus user"
    else
        warn "Mount point ownership may be incorrect"
    fi
    
    # Display LUKS info
    info "LUKS container information:"
    cryptsetup luksDump "${TARGET_DISK}" | grep -E "(Version|Cipher|Key Length|PBKDF)" || true
    
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
    info "Cerberus Disk Encryption Script"
    info "Target: ${TARGET_DISK}"
    info "=================================================="
    
    # Run setup
    check_prerequisites
    create_luks_container
    create_filesystem
    mount_filesystem
    configure_fstab
    setup_tpm2_unlock
    
    # Verification
    verify_encryption
    
    info "=================================================="
    success "Disk encryption setup complete!"
    info "=================================================="
    info "Summary:"
    info "  - Encrypted device: ${TARGET_DISK}"
    info "  - Mapped device: ${LUKS_DEV}"
    info "  - Mount point: ${MOUNT_POINT}"
    info "  - TPM2 auto-unlock: ${TPM2_AVAILABLE:-false}"
    info ""
    info "IMPORTANT:"
    info "  - Store your passphrase securely!"
    info "  - TPM2 unlock will fail if system firmware/kernel changes"
    info "  - Use passphrase as fallback if TPM2 unlock fails"
    info "=================================================="
    
    exit 0
}

# Run main function
main "$@"
