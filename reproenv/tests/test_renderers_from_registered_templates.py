# TODO: test `from_dict` methods too.

import subprocess

from reproenv.renderers import DockerRenderer
from reproenv.renderers import SingularityRenderer
from reproenv.state import _TemplateRegistry
from reproenv.tests.utils import skip_if_no_docker
from reproenv.tests.utils import skip_if_no_singularity

d = {
    "name": "testing",
    "binaries": {
        "arguments": {"required": ["version"]},
        "instructions": """\
curl -fsSL --output /usr/local/bin/jq {{ self.urls[self.version]}}
chmod +x /usr/local/bin/jq
""",
        "urls": {
            "1.6": "https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64",
            "1.5": "https://github.com/stedolan/jq/releases/download/jq-1.5/jq-linux64",
        },
        "env": {"ND_FOO": "BAR", "ND_BAZ": "1234"},
        "dependencies": {
            "apt": ["ca-certificates", "curl"],
            # To test that dpkg installations work
            "dpkg": [
                "http://ftp.us.debian.org/debian/pool/main/r/rust-fd-find/fd-find_7.2.0-2_amd64.deb"  # noqa: E501
            ],
            "yum": ["curl", "fd-find"],
        },
    },
    "source": {
        "arguments": {"required": ["version"]},
        "instructions": """\
mkdir jq
cd jq
curl -fsSL https://github.com/stedolan/jq/releases/download/jq-{{self.version}}/jq-{{self.version}}.tar.gz \\
| tar xz --strip-components 1
autoreconf -fi
./configure --disable-maintainer-mode
make
make install
""",
        "env": {"ND_FOO": "BAR", "ND_BAZ": "1234"},
        "dependencies": {
            "apt": [
                "ca-certificates",
                "curl",
                "automake",
                "gcc",
                "git",
                "libtool",
                "make",
            ],
            "yum": [
                "ca-certificates",
                "curl",
                "automake",
                "gcc",
                "git",
                "libtool",
                "make",
            ],
        },
    },
}


@skip_if_no_docker
def test_build_docker_jq16_binaries(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register("jq", d)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="binaries", version="1.6")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(r.render())
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")


@skip_if_no_docker
def test_build_docker_jq15_binaries(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register("jq", d)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="binaries", version="1.5")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(r.render())
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")


@skip_if_no_docker
def test_build_docker_jq16_source(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register("jq", d)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="source", version="1.6")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(r.render())
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")


@skip_if_no_docker
def test_build_docker_jq15_source(tmp_path):
    import docker

    client = docker.from_env()

    _TemplateRegistry._reset()
    _TemplateRegistry.register("jq", d)

    r = DockerRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="source", version="1.5")

    # Write Dockerfile.
    (tmp_path / "Dockerfile").write_text(r.render())
    image = client.images.build(path=str(tmp_path), tag="jq", rm=True)
    # This is a tuple...
    image = image[0]
    stdout = client.containers.run(image=image, command="jq --help")
    assert stdout.decode().strip().startswith("jq - commandline JSON processor")


@skip_if_no_singularity
def test_build_singularity_jq16_binaries(tmp_path):
    _TemplateRegistry._reset()
    _TemplateRegistry.register("jq", d)

    # Create a Singularity recipe.
    r = SingularityRenderer(pkg_manager="apt")
    r.from_("debian:buster-slim")
    r.add_registered_template("jq", method="binaries", version="1.6")

    # Write Singularity recipe.
    sing_path = tmp_path / "Singularity"
    sif_path = tmp_path / "jq-test.sif"
    sing_path.write_text(r.render())
    subprocess.run(
        f"sudo singularity build {sif_path} {sing_path}".split(),
        check=True,
        cwd=tmp_path,
    )
    completed = subprocess.run(
        f"singularity run {sif_path} jq --help".split(), capture_output=True, check=True
    )
    assert (
        completed.stdout.decode().strip().startswith("jq - commandline JSON processor")
    )
