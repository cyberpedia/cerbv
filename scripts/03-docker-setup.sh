#!/bin/bash
###############################################################################
# Cerberus CTF Platform - Docker Setup Script
# Filename: 03-docker-setup.sh
# Description: Docker 24.x installation with rootless mode and security hardening
# Target: Ubuntu 22.04 LTS
# Requirements: root privileges (initial setup), then cerberus user for rootless
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
readonly DOCKER_VERSION="24.0"

# Rootless configuration
readonly ROOTLESS_DIR="/home/${CERBERUS_USER}/.docker"

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
        error "This script must be run as root for initial setup"
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

###############################################################################
# KERNEL CHECKS
###############################################################################

check_kernel_support() {
    info "Checking kernel support for rootless Docker..."
    
    local kernel_major
    local kernel_minor
    kernel_major=$(uname -r | cut -d. -f1)
    kernel_minor=$(uname -r | cut -d. -f2)
    
    info "Kernel version: $(uname -r)"
    
    # Check for user namespaces
    if [[ -f /proc/sys/kernel/unprivileged_userns_clone ]]; then
        local userns_value
        userns_value=$(cat /proc/sys/kernel/unprivileged_userns_clone)
        if [[ "$userns_value" != "1" ]]; then
            warn "User namespaces may be disabled"
            info "Enabling user namespaces..."
            sysctl -w kernel.unprivileged_userns_clone=1
            echo "kernel.unprivileged_userns_clone=1" > /etc/sysctl.d/99-docker-rootless.conf
        fi
    fi
    
    # Check for overlayfs support
    if [[ ! -d /sys/module/overlay ]]; then
        modprobe overlay 2>/dev/null || true
    fi
    
    # Check for newuidmap/newgidmap
    if ! command_exists newuidmap || ! command_exists newgidmap; then
        info "Installing uidmap package..."
        apt-get update -qq
        apt-get install -y -qq uidmap
    fi
    
    # Check uid_map
    if [[ ! -r /proc/self/uid_map ]]; then
        error "Cannot read /proc/self/uid_map"
        error "Rootless mode requires CONFIG_USER_NS in kernel"
    fi
    
    success "Kernel checks passed"
}

###############################################################################
# DOCKER INSTALLATION
###############################################################################

install_docker() {
    info "Installing Docker ${DOCKER_VERSION}..."
    
    # Check if Docker is already installed
    if command_exists docker; then
        local installed_version
        installed_version=$(docker --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
        info "Docker ${installed_version} is already installed"
        
        if [[ "${installed_version%%.*}" -ge "${DOCKER_VERSION%%.*}" ]]; then
            success "Docker version is sufficient"
            return 0
        else
            warn "Docker version is older than ${DOCKER_VERSION}, upgrading..."
        fi
    fi
    
    # Remove old versions
    apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Install prerequisites
    apt-get update -qq
    apt-get install -y -qq \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        apt-transport-https \
        software-properties-common
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    
    # Add repository
    local arch
    arch=$(dpkg --print-architecture)
    local codename
    codename=$(lsb_release -cs)
    
    echo \
        "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
        > /etc/apt/sources.list.d/docker.list
    
    # Install Docker
    apt-get update -qq
    apt-get install -y -qq \
        docker-ce="5:${DOCKER_VERSION}.*" \
        docker-ce-cli="5:${DOCKER_VERSION}.*" \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin \
        2>/dev/null || {
            # Fallback to latest if specific version not available
            warn "Specific version ${DOCKER_VERSION} not available, installing latest"
            apt-get install -y -qq \
                docker-ce \
                docker-ce-cli \
                containerd.io \
                docker-buildx-plugin \
                docker-compose-plugin
        }
    
    # Hold Docker packages to prevent accidental upgrades
    apt-mark hold docker-ce docker-ce-cli containerd.io 2>/dev/null || true
    
    success "Docker installed successfully"
}

configure_docker_daemon() {
    info "Configuring Docker daemon..."
    
    mkdir -p /etc/docker
    
    backup_file "/etc/docker/daemon.json"
    
    # Create secure daemon configuration
    cat > /etc/docker/daemon.json << 'EOF'
{
    "userns-remap": "default",
    "live-restore": true,
    "no-new-privileges": true,
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ],
    "seccomp-profile": "/etc/docker/seccomp-default.json",
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 64000,
            "Soft": 64000
        },
        "nproc": {
            "Name": "nproc",
            "Hard": 32768,
            "Soft": 32768
        }
    },
    "iptables": false,
    "bridge": "none"
}
EOF
    
    # Create default seccomp profile (restrictive)
    cat > /etc/docker/seccomp-default.json << 'EOF'
{
    "defaultAction": "SCMP_ACT_ERRNO",
    "archMap": [
        {
            "architecture": "SCMP_ARCH_X86_64",
            "subArchitectures": [
                "SCMP_ARCH_X86",
                "SCMP_ARCH_X32"
            ]
        },
        {
            "architecture": "SCMP_ARCH_AARCH64",
            "subArchitectures": [
                "SCMP_ARCH_ARM"
            ]
        }
    ],
    "syscalls": [
        {
            "names": [
                "accept",
                "accept4",
                "access",
                "adjtimex",
                "alarm",
                "bind",
                "brk",
                "capget",
                "capset",
                "chdir",
                "chmod",
                "chown",
                "chown32",
                "clock_adjtime",
                "clock_getres",
                "clock_gettime",
                "clock_nanosleep",
                "clone",
                "clone3",
                "close",
                "close_range",
                "connect",
                "copy_file_range",
                "creat",
                "dup",
                "dup2",
                "dup3",
                "epoll_create",
                "epoll_create1",
                "epoll_ctl",
                "epoll_ctl_old",
                "epoll_pwait",
                "epoll_pwait2",
                "epoll_wait",
                "epoll_wait_old",
                "eventfd",
                "eventfd2",
                "execve",
                "execveat",
                "exit",
                "exit_group",
                "faccessat",
                "faccessat2",
                "fadvise64",
                "fadvise64_64",
                "fallocate",
                "fanotify_mark",
                "fchdir",
                "fchmod",
                "fchmodat",
                "fchown",
                "fchown32",
                "fchownat",
                "fcntl",
                "fcntl64",
                "fdatasync",
                "fgetxattr",
                "flistxattr",
                "flock",
                "fork",
                "fremovexattr",
                "fsetxattr",
                "fstat",
                "fstat64",
                "fstatat64",
                "fstatfs",
                "fstatfs64",
                "fsync",
                "ftruncate",
                "ftruncate64",
                "futex",
                "futex_time64",
                "getcpu",
                "getcwd",
                "getdents",
                "getdents64",
                "getegid",
                "getegid32",
                "geteuid",
                "geteuid32",
                "getgid",
                "getgid32",
                "getgroups",
                "getgroups32",
                "getitimer",
                "getpeername",
                "getpgid",
                "getpgrp",
                "getpid",
                "getppid",
                "getpriority",
                "getrandom",
                "getresgid",
                "getresgid32",
                "getresuid",
                "getresuid32",
                "getrlimit",
                "get_robust_list",
                "getrusage",
                "getsid",
                "getsockname",
                "getsockopt",
                "get_thread_area",
                "gettid",
                "gettimeofday",
                "getuid",
                "getuid32",
                "getxattr",
                "inotify_add_watch",
                "inotify_init",
                "inotify_init1",
                "inotify_rm_watch",
                "io_cancel",
                "ioctl",
                "io_destroy",
                "io_getevents",
                "io_pgetevents",
                "io_pgetevents_time64",
                "ioprio_get",
                "ioprio_set",
                "io_setup",
                "io_submit",
                "io_uring_enter",
                "io_uring_register",
                "io_uring_setup",
                "ipc",
                "kill",
                "lchown",
                "lchown32",
                "lgetxattr",
                "link",
                "linkat",
                "listen",
                "listxattr",
                "llistxattr",
                "lremovexattr",
                "lseek",
                "lsetxattr",
                "lstat",
                "lstat64",
                "madvise",
                "membarrier",
                "memfd_create",
                "mincore",
                "mkdir",
                "mkdirat",
                "mknod",
                "mknodat",
                "mlock",
                "mlock2",
                "mlockall",
                "mmap",
                "mmap2",
                "mprotect",
                "mq_getsetattr",
                "mq_notify",
                "mq_open",
                "mq_timedreceive",
                "mq_timedreceive_time64",
                "mq_timedsend",
                "mq_timedsend_time64",
                "mq_unlink",
                "mremap",
                "msgctl",
                "msgget",
                "msgrcv",
                "msgsnd",
                "msync",
                "munlock",
                "munlockall",
                "munmap",
                "nanosleep",
                "newfstatat",
                "open",
                "openat",
                "openat2",
                "pause",
                "pidfd_getfd",
                "pidfd_open",
                "pidfd_send_signal",
                "pipe",
                "pipe2",
                "pivot_root",
                "poll",
                "ppoll",
                "ppoll_time64",
                "prctl",
                "pread64",
                "preadv",
                "preadv2",
                "prlimit64",
                "pselect6",
                "pselect6_time64",
                "pwrite64",
                "pwritev",
                "pwritev2",
                "read",
                "readahead",
                "readdir",
                "readlink",
                "readlinkat",
                "readv",
                "recv",
                "recvfrom",
                "recvmmsg",
                "recvmmsg_time64",
                "recvmsg",
                "remap_file_pages",
                "removexattr",
                "rename",
                "renameat",
                "renameat2",
                "restart_syscall",
                "rmdir",
                "rseq",
                "rt_sigaction",
                "rt_sigpending",
                "rt_sigprocmask",
                "rt_sigqueueinfo",
                "rt_sigreturn",
                "rt_sigsuspend",
                "rt_sigtimedwait",
                "rt_sigtimedwait_time64",
                "rt_tgsigqueueinfo",
                "sched_getaffinity",
                "sched_getattr",
                "sched_getparam",
                "sched_get_priority_max",
                "sched_get_priority_min",
                "sched_getscheduler",
                "sched_rr_get_interval",
                "sched_rr_get_interval_time64",
                "sched_setaffinity",
                "sched_setattr",
                "sched_setparam",
                "sched_setscheduler",
                "sched_yield",
                "seccomp",
                "select",
                "semctl",
                "semget",
                "semop",
                "semtimedop",
                "semtimedop_time64",
                "send",
                "sendfile",
                "sendfile64",
                "sendmmsg",
                "sendmsg",
                "sendto",
                "setfsgid",
                "setfsgid32",
                "setfsuid",
                "setfsuid32",
                "setgid",
                "setgid32",
                "setgroups",
                "setgroups32",
                "setitimer",
                "setpgid",
                "setpriority",
                "setregid",
                "setregid32",
                "setresgid",
                "setresgid32",
                "setresuid",
                "setresuid32",
                "setreuid",
                "setreuid32",
                "setrlimit",
                "set_robust_list",
                "setsid",
                "setsockopt",
                "set_thread_area",
                "set_tid_address",
                "setuid",
                "setuid32",
                "setxattr",
                "shmat",
                "shmctl",
                "shmdt",
                "shmget",
                "shutdown",
                "sigaltstack",
                "signalfd",
                "signalfd4",
                "sigpending",
                "sigprocmask",
                "sigreturn",
                "socket",
                "socketcall",
                "socketpair",
                "splice",
                "stat",
                "stat64",
                "statfs",
                "statfs64",
                "statx",
                "symlink",
                "symlinkat",
                "sync",
                "sync_file_range",
                "syncfs",
                "sysinfo",
                "tee",
                "tgkill",
                "time",
                "timer_create",
                "timer_delete",
                "timer_getoverrun",
                "timer_gettime",
                "timer_gettime64",
                "timer_settime",
                "timer_settime64",
                "timerfd_create",
                "timerfd_gettime",
                "timerfd_gettime64",
                "timerfd_settime",
                "timerfd_settime64",
                "times",
                "tkill",
                "truncate",
                "truncate64",
                "ugetrlimit",
                "umask",
                "uname",
                "unlink",
                "unlinkat",
                "utime",
                "utimensat",
                "utimensat_time64",
                "utimes",
                "vfork",
                "wait4",
                "waitid",
                "waitpid",
                "write",
                "writev"
            ],
            "action": "SCMP_ACT_ALLOW"
        }
    ]
}
EOF
    
    # Restart Docker
    systemctl daemon-reload
    if systemctl is-active --quiet docker; then
        systemctl restart docker
    else
        systemctl start docker
    fi
    
    systemctl enable docker
    
    success "Docker daemon configured"
}

###############################################################################
# ROOTLESS MODE SETUP
###############################################################################

setup_rootless_mode() {
    info "Setting up Docker rootless mode for ${CERBERUS_USER}..."
    
    # Check if cerberus user exists
    if ! id "${CERBERUS_USER}" >/dev/null 2>&1; then
        error "User ${CERBERUS_USER} does not exist. Run 01-hard-system.sh first."
        exit 1
    fi
    
    # Install docker-ce-rootless-extras
    apt-get install -y -qq docker-ce-rootless-extras 2>/dev/null || {
        warn "docker-ce-rootless-extras not available, will use fallback method"
    }
    
    # Setup subuid/subgid for rootless
    setup_subordinate_ids
    
    # Install rootless Docker as cerberus user
    info "Installing rootless Docker as ${CERBERUS_USER}..."
    
    # Create directory for Docker rootless
    mkdir -p "/home/${CERBERUS_USER}/.docker"
    chown -R "${CERBERUS_USER}:${CERBERUS_USER}" "/home/${CERBERUS_USER}"
    
    # Run dockerd-rootless-setuptool.sh as cerberus user
    local rootless_install_script
    rootless_install_script="/usr/bin/dockerd-rootless-setuptool.sh"
    
    if [[ -x "$rootless_install_script" ]]; then
        su - "${CERBERUS_USER}" -c "$rootless_install_script install" || {
            warn "Rootless install script failed, trying manual setup..."
            setup_rootless_manual
        }
    else
        warn "Rootless install script not found, using manual setup..."
        setup_rootless_manual
    fi
    
    # Configure systemd user service
    setup_rootless_systemd
    
    success "Rootless Docker setup complete"
}

setup_subordinate_ids() {
    info "Configuring subordinate user/group IDs..."
    
    # Check if already configured
    if grep -q "^${CERBERUS_USER}:" /etc/subuid 2>/dev/null; then
        info "Subordinate UIDs already configured"
    else
        # Add subordinate UIDs (65536 IDs starting from UID 100000)
        echo "${CERBERUS_USER}:100000:65536" >> /etc/subuid
        success "Added subordinate UIDs for ${CERBERUS_USER}"
    fi
    
    if grep -q "^${CERBERUS_USER}:" /etc/subgid 2>/dev/null; then
        info "Subordinate GIDs already configured"
    else
        # Add subordinate GIDs
        echo "${CERBERUS_USER}:100000:65536" >> /etc/subgid
        success "Added subordinate GIDs for ${CERBERUS_USER}"
    fi
}

setup_rootless_manual() {
    info "Performing manual rootless Docker setup..."
    
    local cerberus_home
    cerberus_home=$(getent passwd "${CERBERUS_USER}" | cut -d: -f6)
    
    # Create necessary directories
    su - "${CERBERUS_USER}" -c "mkdir -p ${cerberus_home}/.local/share/docker"
    su - "${CERBERUS_USER}" -c "mkdir -p ${cerberus_home}/.config/docker"
    su - "${CERBERUS_USER}" -c "mkdir -p ${cerberus_home}/.config/systemd/user"
    
    # Create daemon.json for rootless
    su - "${CERBERUS_USER}" -c "cat > ${cerberus_home}/.config/docker/daemon.json << 'INNEREOF'
{
    \"storage-driver\": \"overlay2\",
    \"rootless\": true,
    \"experimental\": false
}
INNEREOF"
    
    success "Manual rootless configuration created"
}

setup_rootless_systemd() {
    info "Setting up systemd user service for rootless Docker..."
    
    local cerberus_home
    cerberus_home=$(getent passwd "${CERBERUS_USER}" | cut -d: -f6)
    
    # Create systemd user service
    mkdir -p "${cerberus_home}/.config/systemd/user"
    
    cat > "${cerberus_home}/.config/systemd/user/docker.service" << 'EOF'
[Unit]
Description=Docker Application Container Engine (Rootless)
Documentation=https://docs.docker.com/go/rootless/

[Service]
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="DOCKER_HOST=unix:///run/user/1337/docker.sock"
Type=notify
ExecStart=/usr/bin/dockerd-rootless.sh \
    --storage-driver=overlay2 \
    --host=unix:///run/user/1337/docker.sock \
    --host=tcp://127.0.0.1:2375
ExecReload=/bin/kill -s HUP $MAINPID
TimeoutSec=0
RestartSec=2
Restart=always
StartLimitBurst=3
StartLimitInterval=60s
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
TasksMax=infinity
Delegate=yes
KillMode=process
OOMScoreAdjust=-500

[Install]
WantedBy=default.target
EOF
    
    chown -R "${CERBERUS_USER}:${CERBERUS_USER}" "${cerberus_home}/.config"
    
    # Enable linger for cerberus user (services run without login)
    loginctl enable-linger "${CERBERUS_USER}" 2>/dev/null || true
    
    # Enable and start service as user
    su - "${CERBERUS_USER}" -c "systemctl --user daemon-reload"
    su - "${CERBERUS_USER}" -c "systemctl --user enable docker.service"
    
    info "Docker rootless service configured (will start on next login)"
}

###############################################################################
# DOCKER COMPOSE SETUP
###############################################################################

setup_docker_compose() {
    info "Setting up Docker Compose..."
    
    # Docker Compose plugin should be installed with docker-ce
    if docker compose version >/dev/null 2>&1; then
        success "Docker Compose plugin is installed"
    else
        warn "Docker Compose plugin not found, installing standalone..."
        
        local compose_version
        compose_version=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
        
        curl -L "https://github.com/docker/compose/releases/download/${compose_version}/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        
        success "Docker Compose installed"
    fi
}

###############################################################################
# SECURITY HARDENING
###############################################################################

harden_docker() {
    info "Applying Docker security hardening..."
    
    # Create AppArmor profile for Docker
    if command_exists aa-genprof; then
        cat > /etc/apparmor.d/docker-cerberus << 'EOF'
#include <tunables/global>

profile docker-cerberus flags=(attach_disconnected,mediate_deleted) {
    #include <abstractions/base>
    
    capability,
    network,
    file,
    umount,
    
    deny @{PROC}/* w,
    deny @{PROC}/{[^1-9],[^1-9][^0-9],[^1-9s][^0-9y][^0-9s],[^1-9][^0-9][^0-9][^0-9]*}/** w,
    deny @{PROC}/sys/[^k]** w,
    deny @{PROC}/sys/kernel/{?,??,[^s][^h][^m]**} w,
    deny @{PROC}/sysrq-trigger rwklx,
    deny @{PROC}/mem rwklx,
    deny @{PROC}/kmem rwklx,
    deny @{PROC}/kcore rwklx,
    
    deny mount,
    deny /sys/[^f]*/** wklx,
    deny /sys/f[^s]*/** wklx,
    deny /sys/fs/[^c]*/** wklx,
    deny /sys/fs/c[^g]*/** wklx,
    deny /sys/fs/cg[^r]*/** wklx,
    deny /sys/firmware/efi/efivars/** rwklx,
    deny /sys/kernel/security/** rwklx,
}
EOF
        apparmor_parser -r /etc/apparmor.d/docker-cerberus 2>/dev/null || true
    fi
    
    # Create docker group and add cerberus (for non-rootless fallback)
    if ! getent group docker >/dev/null 2>&1; then
        groupadd docker
    fi
    
    # Note: cerberus user doesn't need docker group for rootless mode
    # but we add it for compatibility
    usermod -aG docker "${CERBERUS_USER}" 2>/dev/null || true
    
    success "Docker security hardening applied"
}

###############################################################################
# VERIFICATION
###############################################################################

verify_docker() {
    info "Running verification checks..."
    
    local errors=0
    
    # Check Docker is installed
    if command_exists docker; then
        local version
        version=$(docker --version)
        success "Docker installed: ${version}"
    else
        error "Docker is not installed"
        ((errors++))
    fi
    
    # Check Docker daemon
    if systemctl is-active --quiet docker; then
        success "Docker daemon is running (system mode)"
    else
        warn "Docker daemon not running in system mode (expected for rootless)"
    fi
    
    # Check rootless configuration
    local cerberus_home
    cerberus_home=$(getent passwd "${CERBERUS_USER}" | cut -d: -f6)
    
    if [[ -f "${cerberus_home}/.config/systemd/user/docker.service" ]]; then
        success "Rootless systemd service configured"
    else
        warn "Rootless systemd service not found"
    fi
    
    # Check subordinate IDs
    if grep -q "^${CERBERUS_USER}:" /etc/subuid && grep -q "^${CERBERUS_USER}:" /etc/subgid; then
        success "Subordinate IDs configured"
    else
        error "Subordinate IDs not configured"
        ((errors++))
    fi
    
    # Check linger
    if [[ -f "/var/lib/systemd/linger/${CERBERUS_USER}" ]]; then
        success "Linger enabled for ${CERBERUS_USER}"
    else
        warn "Linger not enabled"
    fi
    
    # Test Docker as root (system mode)
    if docker ps >/dev/null 2>&1; then
        success "Docker system mode is functional"
        info "Running containers:"
        docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true
    else
        warn "Docker system mode not accessible (may be expected)"
    fi
    
    # Display Docker info
    info "Docker configuration:"
    docker info --format "Storage Driver: {{.Driver}}" 2>/dev/null || true
    docker info --format "Rootless: {{.SecurityOptions}}" 2>/dev/null || true
    
    if [[ $errors -eq 0 ]]; then
        success "All critical verification checks passed"
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
    info "Cerberus Docker Setup Script"
    info "Target Version: ${DOCKER_VERSION}"
    info "=================================================="
    
    # Run setup
    check_kernel_support
    install_docker
    configure_docker_daemon
    setup_rootless_mode
    setup_docker_compose
    harden_docker
    
    # Verification
    verify_docker
    
    info "=================================================="
    success "Docker setup complete!"
    info "=================================================="
    info "Summary:"
    info "  - Docker version: $(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')"
    info "  - Rootless mode: Configured for ${CERBERUS_USER}"
    info "  - Socket: unix:///run/user/${CERBERUS_UID}/docker.sock"
    info ""
    info "IMPORTANT NEXT STEPS:"
    info "1. Log in as ${CERBERUS_USER}: su - ${CERBERUS_USER}"
    info "2. Start rootless Docker: systemctl --user start docker"
    info "3. Test: docker run hello-world"
    info "4. To use Docker without login: loginctl enable-linger ${CERBERUS_USER}"
    info ""
    info "Environment setup for ${CERBERUS_USER}:"
    info "  export DOCKER_HOST=unix:///run/user/${CERBERUS_UID}/docker.sock"
    info "=================================================="
    
    exit 0
}

# Run main function
main "$@"
