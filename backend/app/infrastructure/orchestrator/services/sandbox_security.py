"""
Sandbox Security Profiles for Programming Judge

Provides security configurations for running untrusted code:
- Seccomp profiles for syscall filtering
- AppArmor profiles for container access control
- Resource limit configurations
- Network isolation rules
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


# ============================================================================
# Seccomp Profiles
# ============================================================================

# Default seccomp profile - allows common operations, blocks dangerous syscalls
DEFAULT_SECCOMP_PROFILE = {
    "defaultAction": "SCMP_ACT_KILL",
    "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_AARCH64"],
    "syscalls": [
        # Allowed syscalls for basic program execution
        {"name": "read", "action": "SCMP_ACT_ALLOW"},
        {"name": "write", "action": "SCMP_ACT_ALLOW"},
        {"name": "close", "action": "SCMP_ACT_ALLOW"},
        {"name": "brk", "action": "SCMP_ACT_ALLOW"},
        {"name": "mmap", "action": "SCMP_ACT_ALLOW"},
        {"name": "mprotect", "action": "SCMP_ACT_ALLOW"},
        {"name": "munmap", "action": "SCMP_ACT_ALLOW"},
        {"name": "prctl", "action": "SCMP_ACT_ALLOW"},
        {"name": "arch_prctl", "action": "SCMP_ACT_ALLOW"},
        {"name": "readlink", "action": "SCMP_ACT_ALLOW"},
        {"name": "sysinfo", "action": "SCMP_ACT_ALLOW"},
        {"name": "exit_group", "action": "SCMP_ACT_ALLOW"},
        
        # File operations (restricted)
        {"name": "openat", "action": "SCMP_ACT_ALLOW", "args": [
            {"index": 0, "value": -100, "op": "SCMP_CMP_EQ"},  # AT_FDCWD only
        ]},
        {"name": "newfstatat", "action": "SCMP_ACT_ALLOW", "args": [
            {"index": 0, "value": -100, "op": "SCMP_CMP_EQ"},  # AT_FDCWD only
        ]},
        
        # Clock and time (read-only)
        {"name": "clock_gettime", "action": "SCMP_ACT_ALLOW"},
        {"name": "gettimeofday", "action": "SCMP_ACT_ALLOW"},
        
        # Process management (limited)
        {"name": "getpid", "action": "SCMP_ACT_ALLOW"},
        {"name": "getppid", "action": "SCMP_ACT_ALLOW"},
        {"name": "getuid", "action": "SCMP_ACT_ALLOW"},
        {"name": "geteuid", "action": "SCMP_ACT_ALLOW"},
        {"name": "getgid", "action": "SCMP_ACT_ALLOW"},
        {"name": "getegid", "action": "SCMP_ACT_ALLOW"},
        
        # Memory operations
        {"name": "mlock", "action": "SCMP_ACT_ALLOW"},
        {"name": "madvise", "action": "SCMP_ACT_ALLOW"},
        
        # Signals (basic)
        {"name": "rt_sigaction", "action": "SCMP_ACT_ALLOW"},
        {"name": "rt_sigprocmask", "action": "SCMP_ACT_ALLOW"},
        
        # Blocked syscalls (explicit)
        {"name": "execve", "action": "SCMP_ACT_KILL"},
        {"name": "execveat", "action": "SCMP_ACT_KILL"},
        {"name": "fork", "action": "SCMP_ACT_KILL"},
        {"name": "vfork", "action": "SCMP_ACT_KILL"},
        {"name": "clone", "action": "SCMP_ACT_KILL"},
        {"name": "kill", "action": "SCMP_ACT_KILL"},
        {"name": "tkill", "action": "SCMP_ACT_KILL"},
        {"name": "tgkill", "action": "SCMP_ACT_KILL"},
        
        # Network (blocked)
        {"name": "socket", "action": "SCMP_ACT_KILL"},
        {"name": "connect", "action": "SCMP_ACT_KILL"},
        {"name": "accept", "action": "SCMP_ACT_KILL"},
        {"name": "bind", "action": "SCMP_ACT_KILL"},
        {"name": "listen", "action": "SCMP_ACT_KILL"},
        {"name": "sendto", "action": "SCMP_ACT_KILL"},
        {"name": "recvfrom", "action": "SCMP_ACT_KILL"},
        {"name": "sendmsg", "action": "SCMP_ACT_KILL"},
        {"name": "recvmsg", "action": "SCMP_ACT_KILL"},
        {"name": "shutdown", "action": "SCMP_ACT_KILL"},
        {"name": "getpeername", "action": "SCMP_ACT_KILL"},
        {"name": "getsockname", "action": "SCMP_ACT_KILL"},
        {"name": "socketpair", "action": "SCMP_ACT_KILL"},
        {"name": "setsockopt", "action": "SCMP_ACT_KILL"},
        {"name": "getsockopt", "action": "SCMP_ACT_KILL"},
        
        # File system modifications (blocked)
        {"name": "unlink", "action": "SCMP_ACT_KILL"},
        {"name": "unlinkat", "action": "SCMP_ACT_KILL"},
        {"name": "rename", "action": "SCMP_ACT_KILL"},
        {"name": "renameat", "action": "SCMP_ACT_KILL"},
        {"name": "mkdir", "action": "SCMP_ACT_KILL"},
        {"name": "mkdirat", "action": "SCMP_ACT_KILL"},
        {"name": "rmdir", "action": "SCMP_ACT_KILL"},
        {"name": "symlink", "action": "SCMP_ACT_KILL"},
        {"name": "symlinkat", "action": "SCMP_ACT_KILL"},
        {"name": "link", "action": "SCMP_ACT_KILL"},
        {"name": "linkat", "action": "SCMP_ACT_KILL"},
        {"name": "chmod", "action": "SCMP_ACT_KILL"},
        {"name": "fchmod", "action": "SCMP_ACT_KILL"},
        {"name": "chown", "action": "SCMP_ACT_KILL"},
        {"name": "fchown", "action": "SCMP_ACT_KILL"},
        {"name": "lchown", "action": "SCMP_ACT_KILL"},
        
        # Device operations (blocked)
        {"name": "mknod", "action": "SCMP_ACT_KILL"},
        {"name": "mknodat", "action": "SCMP_ACT_KILL"},
        {"name": "ioctl", "action": "SCMP_ACT_KILL"},
        
        # System configuration (blocked)
        {"name": "reboot", "action": "SCMP_ACT_KILL"},
        {"name": "settimeofday", "action": "SCMP_ACT_KILL"},
        {"name": "adjtimex", "action": "SCMP_ACT_KILL"},
        {"name": "setrlimit", "action": "SCMP_ACT_KILL"},
        {"name": "prlimit64", "action": "SCMP_ACT_KILL"},
        
        # Process injection (blocked)
        {"name": "ptrace", "action": "SCMP_ACT_KILL"},
        {"name": "personality", "action": "SCMP_ACT_KILL"},
        {"name": "seccomp", "action": "SCMP_ACT_KILL"},
    ],
}


# Python-specific seccomp profile - allows more syscalls for Python runtime
PYTHON_SECCOMP_PROFILE = {
    **DEFAULT_SECCOMP_PROFILE,
    "syscalls": DEFAULT_SECCOMP_PROFILE["syscalls"] + [
        # Python-specific syscalls
        {"name": "poll", "action": "SCMP_ACT_ALLOW"},
        {"name": "ppoll", "action": "SCMP_ACT_ALLOW"},
        {"name": "select", "action": "SCMP_ACT_ALLOW"},
        {"name": "epoll_create1", "action": "SCMP_ACT_ALLOW"},
        {"name": "epoll_ctl", "action": "SCMP_ACT_ALLOW"},
        {"name": "epoll_wait", "action": "SCMP_ACT_ALLOW"},
        {"name": "dup", "action": "SCMP_ACT_ALLOW"},
        {"name": "dup2", "action": "SCMP_ACT_ALLOW"},
        {"name": "pipe", "action": "SCMP_ACT_ALLOW"},
        {"name": "pipe2", "action": "SCMP_ACT_ALLOW"},
        {"name": "io_setup", "action": "SCMP_ACT_ALLOW"},
        {"name": "io_destroy", "action": "SCMP_ACT_ALLOW"},
        {"name": "io_getevents", "action": "SCMP_ACT_ALLOW"},
        {"name": "wait4", "action": "SCMP_ACT_ALLOW"},
        {"name": "sched_yield", "action": "SCMP_ACT_ALLOW"},
        {"name": "nanosleep", "action": "SCMP_ACT_ALLOW"},
        {"name": "getitimer", "action": "SCMP_ACT_ALLOW"},
        {"name": "setitimer", "action": "SCMP_ACT_ALLOW"},
    ],
}


# ============================================================================
# AppArmor Profiles
# ============================================================================

DEFAULT_APPARMOR_PROFILE = """
#include <tunables/global>

profile sandbox flags=(attach_disconnected) {
    #include <abstractions/base>
    
    # Deny network access
    deny network,
    deny network raw,
    deny network packet,
    
    # File system - read-only root, writable /tmp only
    / r,
    /etc/ r,
    /etc/passwd r,
    /etc/group r,
    /etc/hosts r,
    /etc/localtime r,
    /usr/ r,
    /lib/ r,
    /lib64/ r,
    /bin/ r,
    /sbin/ r,
    /usr/bin/ r,
    /usr/sbin/ r,
    
    # Writable areas
    /tmp/ w,
    /var/tmp/ w,
    
    # Deny all other file access
    deny /** w,
    deny /** rw,
    deny /** x,
    
    # Deny capabilities
    deny capability,
    deny capability net_admin,
    deny capability net_raw,
    deny capability sys_admin,
    deny capability sys_module,
    deny capability sys_time,
    deny capability sys_resource,
    
    # Deny mounting
    deny mount,
    deny umount,
    
    # Deny ptracing
    deny ptrace,
    
    # Deny signal to other processes
    signal send peer=unconfined,
    
    # Deny changing seccomp
    deny change_profile,
}
"""


PYTHON_APPARMOR_PROFILE = """
#include <tunables/global>

profile sandbox-python flags=(attach_disconnected) {
    #include <abstractions/base>
    
    # Allow basic network for Python runtime
    network inet stream,
    network inet6 stream,
    
    # Allow local connections
    network unix stream,
    
    # File system - read-only with limited write
    / r,
    /etc/ r,
    /etc/passwd r,
    /etc/group r,
    /etc/hosts r,
    /etc/localtime r,
    /etc/resolv.conf r,
    /usr/ r,
    /lib/ r,
    /lib64/ r,
    /bin/ r,
    /sbin/ r,
    /usr/bin/ r,
    /usr/sbin/ r,
    /usr/lib/ r,
    /usr/share/ r,
    
    # Python specific
    /usr/lib/python*/ r,
    /usr/lib/python*/** r,
    /usr/share/python*/ r,
    
    # Writable areas
    /tmp/ w,
    /var/tmp/ w,
    /dev/shm/ w,
    
    # Python bytecode cache
    owner /tmp/**/*.pyc w,
    owner /tmp/__pycache__/ w,
    
    # Deny other file access
    deny /** w,
    deny /** rw,
    
    # Allow executing Python interpreter
    /usr/bin/python* ixr,
    /usr/local/bin/python* ixr,
    
    # Allow reading stdin/stdout
    /dev/null rw,
    /dev/zero r,
    /dev/urandom r,
    
    # Deny capabilities
    deny capability net_admin,
    deny capability net_raw,
    deny capability sys_admin,
    deny capability sys_module,
    deny capability sys_time,
    deny capability sys_resource,
    
    # Allow basic signals
    signal send,
    
    # Deny ptracing
    deny ptrace,
    
    # Deny changing seccomp
    deny change_profile,
}
"""


# ============================================================================
# Resource Limit Configuration
# ============================================================================

@dataclass
class ResourceLimits:
    """Resource limits for sandbox execution."""
    cpu_quota: int = 200000  # 2 CPUs (200% = 2 full cores)
    memory_limit_mb: int = 256
    memory_swap_mb: int = 0
    pids_limit: int = 32
    storage_limit_mb: int = 100
    network_bandwidth_mbps: Optional[int] = None
    max_file_size_mb: int = 10
    max_open_files: int = 64
    max_processes: int = 8
    
    def to_dict(self) -> Dict[str, any]:
        return {
            "cpu_quota": self.cpu_quota,
            "memory_limit_mb": self.memory_limit_mb,
            "memory_swap_mb": self.memory_swap_mb,
            "pids_limit": self.pids_limit,
            "storage_limit_mb": self.storage_limit_mb,
            "network_bandwidth_mbps": self.network_bandwidth_mbps,
            "max_file_size_mb": self.max_file_size_mb,
            "max_open_files": self.max_open_files,
            "max_processes": self.max_processes,
        }


# Language-specific resource limits
PYTHON_LIMITS = ResourceLimits(
    cpu_quota=200000,  # 2 CPUs
    memory_limit_mb=256,
    pids_limit=32,
    max_file_size_mb=10,
    max_open_files=64,
    max_processes=8,
)

CPP_LIMITS = ResourceLimits(
    cpu_quota=200000,
    memory_limit_mb=256,
    pids_limit=32,
    max_file_size_mb=50,  # Larger for compiled binaries
    max_open_files=64,
    max_processes=4,
)

JAVA_LIMITS = ResourceLimits(
    cpu_quota=200000,
    memory_limit_mb=512,  # Java needs more memory
    pids_limit=32,
    max_file_size_mb=100,
    max_open_files=256,
    max_processes=8,
)

RUST_LIMITS = ResourceLimits(
    cpu_quota=200000,
    memory_limit_mb=256,
    pids_limit=32,
    max_file_size_mb=50,
    max_open_files=64,
    max_processes=4,
)


# ============================================================================
# Security Profile Factory
# ============================================================================

def get_seccomp_profile(language: str) -> Dict:
    """Get seccomp profile for a programming language."""
    profiles = {
        "python": PYTHON_SECCOMP_PROFILE,
        "cpp": DEFAULT_SECCOMP_PROFILE,
        "java": PYTHON_SECCOMP_PROFILE,  # JVM needs Python-like syscalls
        "rust": DEFAULT_SECCOMP_PROFILE,
        "go": DEFAULT_SECCOMP_PROFILE,
        "javascript": PYTHON_SECCOMP_PROFILE,
        "ruby": PYTHON_SECCOMP_PROFILE,
    }
    return profiles.get(language, DEFAULT_SECCOMP_PROFILE)


def get_apparmor_profile(language: str) -> str:
    """Get AppArmor profile for a programming language."""
    profiles = {
        "python": PYTHON_APPARMOR_PROFILE,
        "cpp": DEFAULT_APPARMOR_PROFILE,
        "java": PYTHON_APPARMOR_PROFILE,
        "rust": DEFAULT_APPARMOR_PROFILE,
        "go": DEFAULT_APPARMOR_PROFILE,
        "javascript": PYTHON_APPARMOR_PROFILE,
        "ruby": PYTHON_APPARMOR_PROFILE,
    }
    return profiles.get(language, DEFAULT_APPARMOR_PROFILE)


def get_resource_limits(language: str) -> ResourceLimits:
    """Get resource limits for a programming language."""
    limits = {
        "python": PYTHON_LIMITS,
        "cpp": CPP_LIMITS,
        "java": JAVA_LIMITS,
        "rust": RUST_LIMITS,
        "go": CPP_LIMITS,
        "javascript": PYTHON_LIMITS,
        "ruby": PYTHON_LIMITS,
    }
    return limits.get(language, ResourceLimits())


def export_seccomp_profile(language: str, filepath: str) -> None:
    """Export seccomp profile to JSON file."""
    profile = get_seccomp_profile(language)
    with open(filepath, "w") as f:
        json.dump(profile, f, indent=2)


def export_apparmor_profile(language: str, filepath: str) -> None:
    """Export AppArmor profile to file."""
    profile = get_apparmor_profile(language)
    with open(filepath, "w") as f:
        f.write(profile)
