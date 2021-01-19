from pathlib import Path

from click.testing import CliRunner
import pytest

from reproenv.cli.cli import generate
from reproenv.tests.utils import skip_if_no_docker
from reproenv.tests.utils import skip_if_no_singularity

# Test that a template can be rendered
# We need to use `reproenv generate` as the entrypoint here because the generate command
# is what registers the templates. Using the `docker` function
# (`reproenv generate docker`) directly does not fire `generate`.


@skip_if_no_docker
@skip_if_no_singularity
@pytest.mark.parametrize("cmd", ["docker", "singularity"])
@pytest.mark.parametrize(
    ["pkg_manager", "base_image"], [("apt", "debian:buster-slim"), ("yum", "centos:7")]
)
def test_build_image_from_registered(cmd: str, pkg_manager: str, base_image: str):
    # Templates are in this directory.
    template_path = Path(__file__).parent
    runner = CliRunner(env={"REPROENV_TEMPLATE_PATH": str(template_path)})
    result = runner.invoke(
        generate,
        [
            "--template-path",
            str(template_path),
            cmd,
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
    assert result.exit_code == 0, result.output
    assert "jq-1.5/jq-linux64" in result.output
    assert "jq-1.6/jq-linux64" in result.output
