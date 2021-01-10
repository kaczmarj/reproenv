import pytest

from reproenv.template import BinariesTemplate
from reproenv.renderers import SingularityRenderer


def test_singularity_renderer_add_template():
    s = SingularityRenderer("apt")

    # Empty template.
    with pytest.raises(ValueError):
        s.add_template({})

    d = {
        "urls": {"1.0.0": "foobar"},
        "env": {"foo": "bar"},
        "instructions": "echo hello {{ self.myname }}",
        "name": "foobar",
        "arguments": {
            "required": ["myname"],
            "optional": [],
        },
        "dependencies": {"apt": ["curl wget"], "dpkg": [], "yum": ["python wget"]},
    }

    # Not a BinariesTemplate type.
    with pytest.raises(ValueError):
        s.add_template(d)

    # Test apt.
    s = SingularityRenderer("apt")
    s.add_template(BinariesTemplate(d, myname="Bjork"))
    assert (
        str(s)
        == """\


%environment
export foo="bar"

%post
apt-get update -qq
apt-get install -y -q --no-install-recommends \\
    curl wget
rm -rf /var/lib/apt/lists/*
echo hello {{ template_0.myname }}"""
    )

    assert (
        s.render()
        == """\


%environment
export foo="bar"

%post
apt-get update -qq
apt-get install -y -q --no-install-recommends \\
    curl wget
rm -rf /var/lib/apt/lists/*
echo hello Bjork"""
    )

    d = {
        "urls": {"1.0.0": "foobar"},
        "env": {"foo": "bar"},
        "instructions": "echo hello {{ self.myname | default('foo') }}",
        "name": "foobar",
        "arguments": {
            "required": [],
            "optional": ["myname"],
        },
        "dependencies": {"apt": ["curl wget"], "dpkg": [], "yum": ["python wget"]},
    }

    s = SingularityRenderer("apt")
    s.add_template(BinariesTemplate(d))
    assert (
        str(s)
        == """\


%environment
export foo="bar"

%post
apt-get update -qq
apt-get install -y -q --no-install-recommends \\
    curl wget
rm -rf /var/lib/apt/lists/*
echo hello {{ template_0.myname | default('foo') }}"""
    )

    assert (
        s.render()
        == """\


%environment
export foo="bar"

%post
apt-get update -qq
apt-get install -y -q --no-install-recommends \\
    curl wget
rm -rf /var/lib/apt/lists/*
echo hello foo"""
    )


def test_singularity_render_from_instance_methods():
    s = SingularityRenderer("apt")
    s.from_("alpine")
    s.copy(["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/")
    assert (
        s.render()
        == """\
Bootstrap: docker
From: alpine

%files
foo/bar/baz.txt /opt/
foo/baz/cat.txt /opt/"""
    )

    s = SingularityRenderer("apt")
    s.from_("alpine")
    s.copy(["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/")
    s.env(FOO="BAR")
    assert (
        s.render()
        == """\
Bootstrap: docker
From: alpine

%files
foo/bar/baz.txt /opt/
foo/baz/cat.txt /opt/

%environment
export FOO="BAR\""""
    )

    # Label
    s = SingularityRenderer("apt")
    s.from_("alpine")
    s.copy(["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/")
    s.env(FOO="BAR")
    s.label(ORG="BAZ")
    assert (
        s.render()
        == """\
Bootstrap: docker
From: alpine

%files
foo/bar/baz.txt /opt/
foo/baz/cat.txt /opt/

%environment
export FOO="BAR"

%labels
ORG BAZ"""
    )

    # Run
    s = SingularityRenderer("apt")
    s.from_("alpine")
    s.copy(["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/")
    s.env(FOO="BAR")
    s.label(ORG="BAZ")
    s.run("echo foobar")
    assert (
        s.render()
        == """\
Bootstrap: docker
From: alpine

%files
foo/bar/baz.txt /opt/
foo/baz/cat.txt /opt/

%environment
export FOO="BAR"

%post
echo foobar

%labels
ORG BAZ"""
    )

    # User
    s = SingularityRenderer("apt")
    s.from_("alpine")
    s.copy(["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/")
    s.env(FOO="BAR")
    s.label(ORG="BAZ")
    s.run("echo foobar")
    s.user("nonroot")
    assert (
        s.render()
        == """\
Bootstrap: docker
From: alpine

%files
foo/bar/baz.txt /opt/
foo/baz/cat.txt /opt/

%environment
export FOO="BAR"

%post
echo foobar

test "$(getent passwd nonroot)" \\
|| useradd --no-user-group --create-home --shell /bin/bash nonroot


su - nonroot

%labels
ORG BAZ"""
    )

    # Workdir
    s = SingularityRenderer("apt")
    s.from_("alpine")
    s.copy(["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/")
    s.env(FOO="BAR")
    s.label(ORG="BAZ")
    s.run("echo foobar")
    s.user("nonroot")
    s.workdir("/opt/foo")
    s.user("root")
    s.user("nonroot")
    assert (
        s.render()
        == """\
Bootstrap: docker
From: alpine

%files
foo/bar/baz.txt /opt/
foo/baz/cat.txt /opt/

%environment
export FOO="BAR"

%post
echo foobar

test "$(getent passwd nonroot)" \\
|| useradd --no-user-group --create-home --shell /bin/bash nonroot


su - nonroot

mkdir -p /opt/foo
cd /opt/foo

su - root

su - nonroot

%labels
ORG BAZ"""
    )
