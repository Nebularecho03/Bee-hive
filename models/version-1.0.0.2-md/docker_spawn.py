import shutil
import subprocess


def docker_available():
    return shutil.which("docker") is not None


def spawn_bees(count, workdir):
    if not docker_available():
        raise RuntimeError("docker not installed or not in PATH")
    cmd = ["docker", "compose", "up", "--build", "--scale", f"bee={count}"]
    subprocess.run(cmd, cwd=workdir, check=True)
