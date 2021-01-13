import subprocess

import pytest

try:
    import docker
except ImportError:
    docker = None


def _docker_available():
    """Return `True` if docker-py is installed and docker engine is available."""
    if docker is None:
        return False
    client = docker.from_env()
    try:
        return client.ping()  # bool, unless engine is unresponsive (eg not installed)
    except docker.errors.APIError:
        return False


def _singularity_available():
    process = subprocess.run("sudo singularity help".split())
    return process.returncode == 0


# See https://docs.pytest.org/en/stable/skipping.html#id1 for skipif.

skip_if_no_docker = pytest.mark.skipif(
    not _docker_available(), reason="docker not available"
)

skip_if_no_singularity = pytest.mark.skipif(
    not _singularity_available(), reason="singularity not available"
)
