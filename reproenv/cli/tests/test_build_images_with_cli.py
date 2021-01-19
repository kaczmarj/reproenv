from pathlib import Path

import click
from click.testing import CliRunner
import pytest

from reproenv import register_template
from reproenv.cli.cli import docker as generate_docker
from reproenv.cli.cli import singularity as generate_singularity
from reproenv.tests.utils import skip_if_no_docker
from reproenv.tests.utils import skip_if_no_singularity


@skip_if_no_docker
@skip_if_no_singularity
@pytest.mark.parametrize("cmd", [generate_docker, generate_singularity])
@pytest.mark.parametrize(
    ("pkg_manager", "base_image"), [("apt", "debian:buster-slim"), ("yum", "centos:7")]
)
def test_render_registered(cmd: click.Command, pkg_manager: str, base_image: str):
    path = Path(__file__).parent / "sample-template-jq.yaml"
    register_template(path)

    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "--base-image",
            base_image,
            "--pkg-manager",
            pkg_manager,
            "--jq",
            "version=1.5",
            "--jq",
            "version=1.6",
        ],
    )
    assert result.exit_code == 0
    assert "jq-1.5/jq-linux64" in result.output
    assert "jq-1.6/jq-linux64" in result.output

    # TODO: build the images.
    if "docker" in cmd.name:
        pass  # build docker image
    elif "singularity" in cmd.name:
        pass  # build singularity image
