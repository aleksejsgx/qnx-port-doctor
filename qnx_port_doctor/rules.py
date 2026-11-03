"""Rule database: Linux/glibc-specific constructs and their QNX equivalents."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str  # error | warning | info
    kind: str  # include | api | link | path | macro
    pattern: str  # regex
    title: str
    fix: str


RULES = [
    # Headers
    Rule("QPD001", "error", "include", r"#\s*include\s*<sys/epoll\.h>", "epoll is Linux-only",
         "Use poll()/select(), ionotify(), or libevent/libuv kqueue-less backends; QNX has no epoll."),
    Rule("QPD002", "error", "include", r"#\s*include\s*<sys/inotify\.h>", "inotify is Linux-only",
         "Use QNX inotify-like fsevmgr or poll with stat(); consider periodic polling."),
    Rule("QPD003", "error", "include", r"#\s*include\s*<sys/prctl\.h>", "prctl is Linux-only",
         "For thread names use pthread_setname_np(); drop PR_SET_PDEATHSIG or use procmgr_event_notify()."),
    Rule("QPD004", "error", "include", r"#\s*include\s*<sys/eventfd\.h>", "eventfd is Linux-only",
         "Use a pipe() pair or QNX pulses (MsgSendPulse) for wakeups."),
    Rule("QPD005", "error", "include", r"#\s*include\s*<sys/signalfd\.h>", "signalfd is Linux-only",
         "Use self-pipe trick with sigaction, or sigwaitinfo() in a dedicated thread."),
    Rule("QPD006", "error", "include", r"#\s*include\s*<sys/timerfd\.h>", "timerfd is Linux-only",
         "Use timer_create() with SIGEV_PULSE/SIGEV_THREAD, or poll() timeouts."),
    Rule("QPD007", "error", "include", r"#\s*include\s*<sys/sendfile\.h>", "sys/sendfile.h is Linux-only",
         "Fall back to read()/write() loop."),
    Rule("QPD008", "error", "include", r"#\s*include\s*<(linux|asm)/[^>]+>", "Linux kernel headers",
         "Remove or guard with #ifdef __linux__; find QNX devctl()/resource-manager equivalent."),
    Rule("QPD009", "warning", "include", r"#\s*include\s*<(sys/sysinfo|sys/vfs|mntent|sys/klog|sys/personality|sys/fsuid)\.h>",
         "Linux-specific system header", "Use sysconf(), statvfs(), or QNX-specific /proc-less APIs."),
    Rule("QPD010", "warning", "include", r"#\s*include\s*<(execinfo|malloc|features|gnu/libc-version|error)\.h>",
         "glibc-specific header", "Guard with __GLIBC__; QNX uses its own libc (backtrace via libbacktrace)."),
    Rule("QPD011", "info", "include", r"#\s*include\s*<sys/cdefs\.h>", "sys/cdefs.h is non-standard",
         "Usually available on QNX but verify macros used (__BEGIN_DECLS etc.)."),
    # APIs
    Rule("QPD020", "error", "api", r"\bepoll_(create1?|ctl|wait|pwait)\s*\(", "epoll API call",
         "Replace with poll() or an abstraction (libevent select/poll backend)."),
    Rule("QPD021", "error", "api", r"\bclone\s*\(", "clone() is Linux-only",
         "Use pthread_create() or posix_spawn()."),
    Rule("QPD022", "warning", "api", r"\b(accept4|pipe2|dup3)\s*\(", "Linux-only *4/*2/*3 syscall variant",
         "Check QNX libc version; else use accept()/pipe()/dup2() + fcntl(FD_CLOEXEC/O_NONBLOCK)."),
    Rule("QPD023", "error", "api", r"\b(splice|tee|vmsplice|sendfile)\s*\(", "Zero-copy Linux syscall",
         "Use read()/write() loop."),
    Rule("QPD024", "warning", "api", r"\bsched_(get|set)affinity\s*\(", "Linux CPU affinity API",
         "Use ThreadCtl(_NTO_TCTL_RUNMASK_GET_AND_SET_INHERIT, ...)."),
    Rule("QPD025", "warning", "api", r"\bmallinfo2?\s*\(|\bmalloc_usable_size\s*\(|\bmalloc_trim\s*\(", "glibc malloc extensions",
         "Guard with __GLIBC__; QNX offers mallinfo() in <malloc.h> with differences — verify."),
    Rule("QPD026", "warning", "api", r"\bgettid\s*\(|SYS_gettid", "gettid is Linux-specific",
         "Use gettid() from QNX <process.h> or pthread_self()."),
    Rule("QPD027", "warning", "api", r"\bsyscall\s*\(\s*SYS_", "raw Linux syscall()",
         "QNX has no Linux syscall numbers; call the libc wrapper or kernel call (ThreadCtl, etc.)."),
    Rule("QPD028", "warning", "api", r"\b(backtrace|backtrace_symbols(_fd)?)\s*\(", "glibc backtrace()",
         "Use QNX libbacktrace (bt_get_backtrace) or guard out."),
    Rule("QPD029", "warning", "api", r"\b(get_nprocs(_conf)?|sysinfo)\s*\(", "Linux sysinfo API",
         "Use sysconf(_SC_NPROCESSORS_ONLN) or _syspage_ptr->num_cpu."),
    Rule("QPD030", "info", "api", r"\bmemrchr\s*\(|\bstrchrnul\s*\(|\bmempcpy\s*\(|\bcanonicalize_file_name\s*\(",
         "GNU string extension", "Provide a fallback implementation or use realpath()."),
    Rule("QPD031", "warning", "api", r"\bprctl\s*\(", "prctl() call", "See QPD003."),
    Rule("QPD032", "warning", "api", r"\bMAP_(POPULATE|HUGETLB|LOCKED|NORESERVE)\b", "Linux-only mmap flag",
         "Drop flag or use QNX MAP_LAZY / shm_ctl()."),
    Rule("QPD033", "warning", "api", r"\bSO_REUSEPORT_LB\b|\bTCP_(CORK|QUICKACK|USER_TIMEOUT|DEFER_ACCEPT)\b|\bSOCK_(NONBLOCK|CLOEXEC)\b",
         "Linux-specific socket option/flag", "Guard with #ifdef; use fcntl() for NONBLOCK/CLOEXEC."),
    Rule("QPD034", "info", "api", r"\bO_(DIRECT|NOATIME|TMPFILE|PATH)\b", "Linux-specific open flag",
         "Guard with #ifdef; not supported on QNX."),
    Rule("QPD035", "error", "macro", r"^\s*#\s*define\s+_XOPEN_SOURCE\s*(//.*|/\*.*)?$", "_XOPEN_SOURCE defined without a value",
         "QNX <sys/platform.h> rejects it (#error ... XOPEN_SOURCE is not supported); use `#define _XOPEN_SOURCE 700`."),
    Rule("QPD036", "warning", "macro", r"^\s*#\s*define\s+_XOPEN_SOURCE\s+([1-4]\d\d|[1-9]\d?)\b", "old _XOPEN_SOURCE level",
         "QNX supports 500/600/700; older values may #error. Use 700."),
    Rule("QPD037", "warning", "api", r"\bstrptime\s*\(.*%[FTDRe]", "GNU strptime shorthand (%F/%T/%D/%R)",
         "QNX strptime() returns NULL for %F/%T; spell out %Y-%m-%d and %H:%M:%S."),
    Rule("QPD038", "info", "api", r"\bstrptime\s*\(", "strptime() with runtime format",
         "If formats come from users/scripts, expand %F/%T/%D/%R before calling (QNX lacks them)."),
    # Paths
    Rule("QPD040", "warning", "path", r"\"/proc/(self|\d+|%d)/(maps|status|stat|cmdline|exe|fd|task)",
         "Linux procfs layout", "QNX /proc/<pid>/as uses devctl(DCMD_PROC_*); /proc/self/exe -> _cmdname() / getexecname()."),
    Rule("QPD041", "warning", "path", r"\"/proc/(cpuinfo|meminfo|loadavg|mounts|net/)", "Linux /proc system file",
         "Use sysconf(), _syspage_ptr, or pidin-style devctl queries."),
    Rule("QPD042", "info", "path", r"\"/sys/(class|devices|fs|kernel)/", "Linux sysfs path",
         "No sysfs on QNX; query the resource manager via devctl()."),
    Rule("QPD043", "info", "path", r"\"/dev/shm/", "/dev/shm path", "Use shm_open(); QNX places it under /dev/shmem."),
    # Macros
    Rule("QPD050", "info", "macro", r"#\s*if(def)?\s*.*__linux__", "__linux__ conditional",
         "Check that the #else branch compiles on QNX; add `|| defined(__QNX__)` where POSIX code fits."),
    # Link flags
    Rule("QPD060", "warning", "link", r"(?<![\w-])-l(rt|dl|pthread|anl|crypt)\b", "glibc split library",
         "On QNX these live in libc: drop -lrt/-ldl/-lpthread; use -lsocket for sockets."),
    Rule("QPD061", "info", "link", r"\b(socket|connect|bind|getaddrinfo)\b", "socket usage in build file",
         "QNX needs -lsocket for BSD socket APIs."),
    Rule("QPD062", "warning", "link", r"-Wl,--as-needed|-static-libgcc|-rdynamic", "GNU ld-specific flag",
         "Usually fine with qcc (GNU ld), but verify -rdynamic/--as-needed behaviour."),
]

SOURCE_EXT = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}
BUILD_FILES = {"Makefile", "makefile", "GNUmakefile", "CMakeLists.txt", "configure.ac", "configure.in",
               "meson.build", "Makefile.am", "Makefile.in"}
