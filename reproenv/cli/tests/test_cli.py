# TODO: add tests of individual CLI params.

from pathlib import Path

import click
from click.testing import CliRunner
import pytest

from reproenv import register_template
from reproenv.cli.cli import docker as generate_docker
from reproenv.cli.cli import singularity as generate_singularity


@pytest.mark.parametrize("cmd", [generate_docker, generate_singularity])
def test_fail_on_empty_args(cmd: click.Command):
    runner = CliRunner()
    result = runner.invoke(cmd)
    assert result.exit_code != 0


@pytest.mark.parametrize("cmd", [generate_docker, generate_singularity])
@pytest.mark.parametrize("pkg_manager", ["apt", "yum"])
def test_fail_on_no_base(cmd: click.Command, pkg_manager: str):
    runner = CliRunner()
    result = runner.invoke(cmd, ["--pkg-manager", pkg_manager])
    assert result.exit_code != 0


@pytest.mark.parametrize("cmd", [generate_docker, generate_singularity])
def test_fail_on_no_pkg_manager(cmd: click.Command):
    runner = CliRunner()
    result = runner.invoke(cmd, ["--base-image", "debian"])
    assert result.exit_code != 0


@pytest.mark.parametrize("cmd", [generate_docker, generate_singularity])
@pytest.mark.parametrize("pkg_manager", ["apt", "yum"])
def test_minimal_args(cmd: click.Command, pkg_manager: str):
    runner = CliRunner()
    result = runner.invoke(
        cmd, ["--pkg-manager", pkg_manager, "--base-image", "debian"]
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("cmd", [generate_docker, generate_singularity])
@pytest.mark.parametrize("pkg_manager", ["apt", "yum"])
def test_all_args(cmd: click.Command, pkg_manager: str):
    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "--pkg-manager",
            pkg_manager,
            "--base-image",
            "debian",
            # arg
            "--arg",
            "ARG=VAL",
            # copy
            "--copy",
            "file1",
            "file2",
            "file3",
            # env
            "--env",
            "VAR1=CAT",
            "VAR2=DOG",
            # install
            "--install",
            "python3",
            "curl",
            # run
            "--run",
            "echo foobar",
            # run bash
            "--run-bash",
            "source activate",
            # user
            "--user",
            "nonroot",
            # workdir
            "--workdir",
            "/data",
        ],
    )
    assert result.exit_code == 0, result.exception


# Test that a template can be rendered
@pytest.mark.parametrize("cmd", [generate_docker, generate_singularity])
@pytest.mark.parametrize("pkg_manager", ["apt", "yum"])
def test_render_registered(cmd: click.Command, pkg_manager: str):
    path = Path(__file__).parent / "sample-template-jq.yaml"
    register_template(path)

    runner = CliRunner()
    result = runner.invoke(
        cmd,
        [
            "--base-image",
            "debian:buster",
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
