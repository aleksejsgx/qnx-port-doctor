"""Boot a QNX QEMU quickstart image, copy a binary in over ssh and run it."""
import os
import shlex
import socket
import stat
import subprocess
import tempfile
import time

DEFAULT_IMAGE = os.path.expanduser("~/qnx800/images/qemu/qemu")
# aarch64le image built with:
#   mkqnximage --type=qemu --arch=aarch64le --ssh-ident=none --data-size=200 --build
DEFAULT_IMAGES = {
    "x86_64": DEFAULT_IMAGE,
    "aarch64le": os.path.expanduser("~/qnx800/images/qemu-aarch64"),
}
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10"]


def detect_arch(path):
    """Return 'x86_64' or 'aarch64le' from an ELF header, None if unknown/not ELF."""
    try:
        with open(path, "rb") as f:
            h = f.read(20)
    except OSError:
        return None
    if h[:4] != b"\x7fELF":
        return None
    return {62: "x86_64", 183: "aarch64le"}.get(int.from_bytes(h[18:20], "little"))


def qemu_cmd(image, port, kvm=False, smp=2, mem="2G", serial_log="/tmp/qnx-serial.log", arch="x86_64"):
    out = os.path.join(image, "output")
    if arch == "aarch64le":
        # Mirrors mkqnximage's qemu/runimage for OPT_AARCH64_VERSION=8 (virt-4.2, cortex-a57).
        return ["qemu-system-aarch64", "-machine", "virt-4.2", "-cpu", "cortex-a57", "-smp", str(smp),
                "-m", mem, "-snapshot",
                "-drive", f"file={out}/disk-qemu.vmdk,if=none,id=drv0",
                "-device", "virtio-blk-device,drive=drv0",
                "-netdev", f"user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22",
                "-device", "virtio-net-device,netdev=net0",
                "-kernel", f"{out}/ifs.bin", "-display", "none", "-monitor", "none",
                "-serial", f"file:{serial_log}",
                "-object", "rng-random,filename=/dev/urandom,id=rng0",
                "-device", "virtio-rng-device,rng=rng0"]
    cpu = ["-enable-kvm", "-cpu", "host"] if kvm else ["-cpu", "max"]
    return ["qemu-system-x86_64", *cpu, "-smp", str(smp), "-m", mem, "-snapshot",
            "-drive", f"file={out}/disk-qemu.vmdk,if=ide,id=drv0",
            "-netdev", f"user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22",
            "-device", "virtio-net-pci,netdev=net0",
            "-kernel", f"{out}/ifs.bin", "-display", "none", "-monitor", "none",
            "-serial", f"file:{serial_log}",
            "-object", "rng-random,filename=/dev/urandom,id=rng0",
            "-device", "virtio-rng-pci,rng=rng0"]


class Session:
    """ssh/scp helper using password auth through SSH_ASKPASS (no extra deps)."""

    def __init__(self, port, user, password):
        self.port, self.user = port, user
        fd, self.askpass = tempfile.mkstemp(prefix="qpd-askpass-")
        with os.fdopen(fd, "w") as f:
            f.write("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(password) + "\n")
        os.chmod(self.askpass, stat.S_IRWXU)
        self.env = dict(os.environ, SSH_ASKPASS=self.askpass, SSH_ASKPASS_REQUIRE="force",
                        DISPLAY=os.environ.get("DISPLAY", ":0"))

    def close(self):
        try:
            os.unlink(self.askpass)
        except OSError:
            pass

    def ssh(self, command, timeout=120):
        cmd = ["ssh", "-p", str(self.port), *SSH_OPTS, f"{self.user}@127.0.0.1", command]
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout)

    def scp(self, src, dst, timeout=300):
        cmd = ["scp", "-P", str(self.port), *SSH_OPTS, src, f"{self.user}@127.0.0.1:{dst}"]
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout)


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_ready(sess, deadline):
    while time.time() < deadline:
        if port_open(sess.port):
            try:
                if sess.ssh("true", timeout=20).returncode == 0:
                    return True
            except subprocess.TimeoutExpired:
                pass
        time.sleep(3)
    return False


def run(binary, args=(), image=None, port=None, user="qnxuser", password="qnxuser",
        boot_timeout=300, keep=False, kvm=False, extra_files=(), stdin_file=None, log=print, arch=None):
    """Returns (exit_code, stdout, stderr). Reuses a VM already listening on `port`."""
    if arch is None:
        arch = detect_arch(binary) or next(
            (a for a in map(detect_arch, extra_files) if a), "x86_64")
    image = image or DEFAULT_IMAGES[arch]
    port = port or (2222 if arch == "x86_64" else 2223)
    sess = Session(port, user, password)
    proc = None
    try:
        if not port_open(port):
            if not os.path.exists(os.path.join(image, "output", "ifs.bin")):
                raise SystemExit(f"QNX QEMU image not found in {image}")
            cmd = qemu_cmd(image, port, kvm=kvm, arch=arch, serial_log=f"/tmp/qnx-serial-{arch}.log")
            log("+ " + " ".join(cmd))
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"[{arch}] waiting for ssh on :{port} ...")
        t0 = time.time()
        if not wait_ready(sess, t0 + boot_timeout):
            raise SystemExit("VM did not become reachable over ssh")
        log(f"VM ready after {time.time() - t0:.0f}s")
        remote_dir = "/tmp/qpd"
        sess.ssh(f"mkdir -p {remote_dir}")
        for f in [binary, *extra_files] + ([stdin_file] if stdin_file else []):
            r = sess.scp(f, f"{remote_dir}/")
            if r.returncode:
                raise SystemExit(f"scp failed for {f}: {r.stderr.strip()}")
        exe = f"{remote_dir}/{os.path.basename(binary)}"
        line = f"cd {remote_dir} && chmod +x {shlex.quote(exe)} && {shlex.quote(exe)} " + \
            " ".join(shlex.quote(a) for a in args)
        if stdin_file:
            line += f" < {remote_dir}/{shlex.quote(os.path.basename(stdin_file))}"
        r = sess.ssh(line, timeout=600)
        return r.returncode, r.stdout, r.stderr
    finally:
        sess.close()
        if proc and not keep:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
