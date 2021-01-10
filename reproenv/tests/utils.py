import subprocess
import pytest

try:
    import docker
except ImportError:
    docker = None

# See https://docs.pytest.org/en/stable/skipping.html#id1 for skipif.

skip_if_no_docker = pytest.mark.skipif(
    docker is None, reason="docker python package not found"
)

process = subprocess.run("sudo singularity help".split())
singularity_available = process.returncode == 0

skip_if_no_singularity = pytest.mark.skipif(
    not singularity_available, reason="singularity not found"
)
