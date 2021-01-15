import subprocess

from reproenv.renderers import SingularityRenderer
from reproenv.tests.utils import skip_if_no_singularity


@skip_if_no_singularity
def test_build_a(tmp_path):
    # Create a Singularity recipe.
    d = SingularityRenderer("apt")
    d.from_("debian:buster-slim")
    d.copy(["foo.txt", "tst/baz.txt"], "/opt/")
    d.env(PATH="$PATH:/opt/foo/bin")
    d.label(ORG="myorg")
    d.run("echo foobar")
    d.user("nonroot")
    d.workdir("/opt/foobar")

    # Create the paths that are copied in the Dockerfile.
    (tmp_path / "tst").mkdir(exist_ok=True)
    with (tmp_path / "foo.txt").open("w"):
        pass
    with (tmp_path / "tst" / "baz.txt").open("w"):
        pass
    # Write Singularity recipe.
    sing_path = tmp_path / "Singularity"
    sif_path = tmp_path / "test.sif"
    sing_path.write_text(str(d))
    subprocess.run(
        f"sudo singularity build {sif_path} {sing_path}".split(),
        check=True,
        cwd=tmp_path,
    )
    completed = subprocess.run(
        f"singularity run {sif_path} ls /opt".split(), capture_output=True, check=True
    )
    files_found = set(completed.stdout.decode().splitlines())
    assert files_found == {"baz.txt", "foo.txt", "foobar"}
