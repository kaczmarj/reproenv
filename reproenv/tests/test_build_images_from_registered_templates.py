# TODO: add more tests for `from_dict` method.

from pathlib import Path
import subprocess

import pytest

from reproenv.renderers import DockerRenderer
from reproenv.renderers import SingularityRenderer
from reproenv.state import _TemplateRegistry
from reproenv.tests.utils import singularity_build
from reproenv.tests.utils import skip_if_no_docker
from reproenv.tests.utils import skip_if_no_singularity

_template_filepath = Path(__file__).parent / "sample-template-jq.yaml"


@skip_if_no_docker
@pytest.mark.long
def test_build_docker_from_dict_apt(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    d = {
        "pkg_manager": "apt",
        "instructions": [
            {"name": "from_", "kwds": {"base_image": "debian:stretch"}},
            {"name": "run", "kwds": {"command": "echo hello there"}},
            {"name": "jq", "kwds": {"version": "1.6", "method": "binaries"}},
        ],
    }
    r = DockerRenderer.from_dict(d)
    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(str(r))
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")
    stdout = client.containers.run(image=image, command="jq --version")
    assert stdout.decode().strip() == "jq-1.6"
    # Test that deb was installed
    stdout = client.containers.run(image=image, command="fdfind --help")
    assert stdout.decode().strip().startswith("fd 7.2.0")


@skip_if_no_docker
@pytest.mark.long
def test_build_docker_from_dict_yum(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    d = {
        "pkg_manager": "yum",
        "instructions": [
            {"name": "from_", "kwds": {"base_image": "fedora:33"}},
            {"name": "run", "kwds": {"command": "echo hello there"}},
            {"name": "jq", "kwds": {"version": "1.6", "method": "binaries"}},
        ],
    }
    r = DockerRenderer.from_dict(d)
    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(str(r))
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")
    stdout = client.containers.run(image=image, command="jq --version")
    assert stdout.decode().strip() == "jq-1.6"
    stdout = client.containers.run(image=image, command="fd --help")
    assert stdout.decode().strip().startswith("fd")


@skip_if_no_singularity
@pytest.mark.long
def test_build_singularity_from_dict_apt(tmp_path):
    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    d = {
        "pkg_manager": "apt",
        "instructions": [
            {"name": "from_", "kwds": {"base_image": "debian:stretch"}},
            {"name": "run", "kwds": {"command": "echo hello there"}},
            {"name": "jq", "kwds": {"version": "1.6", "method": "binaries"}},
        ],
    }
    # Create a Singularity recipe.
    r = SingularityRenderer.from_dict(d)

    # Write Singularity recipe.
    sing_path = tmp_path / "Singularity"
    sif_path = tmp_path / "jq-test.sif"
    sing_path.write_text(str(r))

    _ = singularity_build(image_path=sif_path, build_spec=sing_path, cwd=tmp_path)
    completed = subprocess.run(
        f"singularity run {sif_path} jq --help".split(), capture_output=True, check=True
    )
    assert (
        completed.stdout.decode().strip().startswith("jq - commandline JSON processor")
    )
    completed = subprocess.run(
        f"singularity run {sif_path} jq --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip() == "jq-1.6"
    # Test that deb was installed
    completed = subprocess.run(
        f"singularity run {sif_path} fdfind --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip() == "fd 7.2.0"


@skip_if_no_singularity
@pytest.mark.long
def test_build_singularity_from_dict_yum(tmp_path):
    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    d = {
        "pkg_manager": "yum",
        "instructions": [
            {"name": "from_", "kwds": {"base_image": "fedora:33"}},
            {"name": "run", "kwds": {"command": "echo hello there"}},
            {"name": "jq", "kwds": {"version": "1.6", "method": "binaries"}},
        ],
    }
    # Create a Singularity recipe.
    r = SingularityRenderer.from_dict(d)

    # Write Singularity recipe.
    sing_path = tmp_path / "Singularity"
    sif_path = tmp_path / "jq-test.sif"
    sing_path.write_text(str(r))
    _ = singularity_build(image_path=sif_path, build_spec=sing_path, cwd=tmp_path)
    completed = subprocess.run(
        f"singularity run {sif_path} jq --help".split(), capture_output=True, check=True
    )
    assert (
        completed.stdout.decode().strip().startswith("jq - commandline JSON processor")
    )
    completed = subprocess.run(
        f"singularity run {sif_path} jq --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip() == "jq-1.6"
    completed = subprocess.run(
        f"singularity run {sif_path} fd --help".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip().startswith("fd")


@skip_if_no_docker
@pytest.mark.long
def test_build_docker_jq16_binaries(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="binaries", version="1.6")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(str(r))
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")
    stdout = client.containers.run(image=image, command="jq --version")
    assert stdout.decode().strip() == "jq-1.6"
    # Test that deb was installed
    stdout = client.containers.run(image=image, command="fdfind --help")
    assert stdout.decode().strip().startswith("fd 7.2.0")


@skip_if_no_docker
@pytest.mark.long
def test_build_docker_jq15_binaries(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="binaries", version="1.5")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(str(r))
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")
    stdout = client.containers.run(image=image, command="jq --version")
    assert stdout.decode().strip() == "jq-1.5"
    # Test that deb was installed
    stdout = client.containers.run(image=image, command="fdfind --help")
    assert stdout.decode().strip().startswith("fd 7.2.0")


@skip_if_no_docker
@pytest.mark.long
def test_build_docker_jq16_source(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="source", version="1.6")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(str(r))
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")
    stdout = client.containers.run(image=image, command="jq --version")
    assert stdout.decode().strip() == "jq-1.6"


@skip_if_no_docker
@pytest.mark.long
def test_build_docker_jq15_source(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="source", version="1.5")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(str(r))
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")
    stdout = client.containers.run(image=image, command="jq --version")
    assert stdout.decode().strip() == "jq-"  # this is what jq shows


@skip_if_no_singularity
@pytest.mark.long
def test_build_singularity_jq16_binaries(tmp_path):
    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    # Create a Singularity recipe.
    r = SingularityRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="binaries", version="1.6")

    # Write Singularity recipe.
    sing_path = tmp_path / "Singularity"
    sif_path = tmp_path / "jq-test.sif"
    sing_path.write_text(str(r))
    _ = singularity_build(image_path=sif_path, build_spec=sing_path, cwd=tmp_path)
    completed = subprocess.run(
        f"singularity run {sif_path} jq --help".split(), capture_output=True, check=True
    )
    assert (
        completed.stdout.decode().strip().startswith("jq - commandline JSON processor")
    )
    completed = subprocess.run(
        f"singularity run {sif_path} jq --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip() == "jq-1.6"
    # Test that deb was installed
    completed = subprocess.run(
        f"singularity run {sif_path} fdfind --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip() == "fd 7.2.0"


@skip_if_no_singularity
@pytest.mark.long
def test_build_singularity_jq15_binaries(tmp_path):
    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    # Create a Singularity recipe.
    r = SingularityRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="binaries", version="1.5")

    # Write Singularity recipe.
    sing_path = tmp_path / "Singularity"
    sif_path = tmp_path / "jq-test.sif"
    sing_path.write_text(str(r))
    _ = singularity_build(image_path=sif_path, build_spec=sing_path, cwd=tmp_path)
    completed = subprocess.run(
        f"singularity run {sif_path} jq --help".split(), capture_output=True, check=True
    )
    assert (
        completed.stdout.decode().strip().startswith("jq - commandline JSON processor")
    )
    completed = subprocess.run(
        f"singularity run {sif_path} jq --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip().startswith("jq-1.5")
    # Test that deb was installed
    completed = subprocess.run(
        f"singularity run {sif_path} fdfind --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip() == "fd 7.2.0"


@skip_if_no_singularity
@pytest.mark.long
def test_build_singularity_jq15_source(tmp_path):
    _TemplateRegistry._reset()
    _TemplateRegistry.register(_template_filepath)

    # Create a Singularity recipe.
    r = SingularityRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="source", version="1.5")

    # Write Singularity recipe.
    sing_path = tmp_path / "Singularity"
    sif_path = tmp_path / "jq-test.sif"
    sing_path.write_text(str(r))
    _ = singularity_build(image_path=sif_path, build_spec=sing_path, cwd=tmp_path)
    completed = subprocess.run(
        f"singularity run {sif_path} jq --help".split(), capture_output=True, check=True
    )
    assert (
        completed.stdout.decode().strip().startswith("jq - commandline JSON processor")
    )
    completed = subprocess.run(
        f"singularity run {sif_path} jq --version".split(),
        capture_output=True,
        check=True,
    )
    assert completed.stdout.decode().strip() == "jq-"
