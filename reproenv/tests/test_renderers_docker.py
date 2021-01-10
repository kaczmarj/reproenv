import pytest

from reproenv.template import BinariesTemplate
from reproenv.renderers import DockerRenderer


def test_docker_renderer_add_template():
    r = DockerRenderer("apt")

    # Empty template.
    with pytest.raises(ValueError):
        r.add_template({})

    d = {
        "urls": {"1.0.0": "foobar"},
        "env": {"foo": "bar"},
        "instructions": "echo hello\necho world",
        "name": "foobar",
        "arguments": {
            "required": [],
            "optional": [],
        },
        "dependencies": {"apt": ["curl"], "dpkg": [], "yum": ["python"]},
    }

    # Not a BinariesTemplate type.
    with pytest.raises(ValueError):
        r.add_template(d)

    # Test apt.
    r.add_template(BinariesTemplate(d))
    assert len(r._parts) == 2
    assert r._parts[0] == 'ENV foo="bar"'
    assert (
        r._parts[1]
        == """RUN apt-get update -qq \\
    && apt-get install -y -q --no-install-recommends \\
           curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && echo hello \\
    && echo world"""
    )

    # Test yum.
    r = DockerRenderer("yum")
    r.add_template(BinariesTemplate(d))
    assert len(r._parts) == 2
    assert r._parts[0] == 'ENV foo="bar"'
    assert (
        r._parts[1]
        == """RUN yum install -y -q \\
           python \\
    && yum clean all \\
       rm -rf /var/cache/yum/* \\
    && echo hello \\
    && echo world"""
    )

    # Test required arguments.
    d = {
        "urls": {"1.0.0": "foobar"},
        "env": {"foo": "bar"},
        "instructions": "echo hello {{ self.myname }}",
        "name": "foobar",
        "arguments": {
            "required": ["myname"],
            "optional": [],
        },
        "dependencies": {"apt": ["curl"], "dpkg": [], "yum": ["python"]},
    }
    r = DockerRenderer("apt")
    r.add_template(BinariesTemplate(d, myname="Bjork"))
    assert (
        str(r)
        == """ENV foo="bar"
RUN apt-get update -qq \\
    && apt-get install -y -q --no-install-recommends \\
           curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && echo hello {{ template_0.myname }}"""
    )
    assert (
        r.render()
        == """ENV foo="bar"
RUN apt-get update -qq \\
    && apt-get install -y -q --no-install-recommends \\
           curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && echo hello Bjork"""
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
        "dependencies": {"apt": ["curl"], "dpkg": [], "yum": ["python"]},
    }

    r = DockerRenderer("apt")
    r.add_template(BinariesTemplate(d))
    assert (
        str(r)
        == """ENV foo="bar"
RUN apt-get update -qq \\
    && apt-get install -y -q --no-install-recommends \\
           curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && echo hello {{ template_0.myname | default('foo') }}"""
    )
    assert (
        r.render()
        == """ENV foo="bar"
RUN apt-get update -qq \\
    && apt-get install -y -q --no-install-recommends \\
           curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && echo hello foo"""
    )


def test_docker_render_from_instance_methods():
    d = DockerRenderer("apt")

    d.from_("alpine")
    assert d.render() == "FROM alpine"

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    assert d.render() == "FROM alpine AS builder"

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    assert d.render() == "FROM alpine AS builder\nARG FOO"

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    d.copy(
        ["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/", from_="builder", chown="neuro"
    )
    assert (
        d.render()
        == """\
FROM alpine AS builder
ARG FOO
COPY --from=builder --chown=neuro ["foo/bar/baz.txt", \\
      "foo/baz/cat.txt", \\
      "/opt/"]"""
    )

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    d.copy(
        ["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/", from_="builder", chown="neuro"
    )
    d.env(PATH="$PATH:/opt/foo/bin")
    assert (
        d.render()
        == """\
FROM alpine AS builder
ARG FOO
COPY --from=builder --chown=neuro ["foo/bar/baz.txt", \\
      "foo/baz/cat.txt", \\
      "/opt/"]
ENV PATH="$PATH:/opt/foo/bin\""""
    )

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    d.copy(
        ["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/", from_="builder", chown="neuro"
    )
    d.env(PATH="$PATH:/opt/foo/bin")
    d.label(ORG="myorg")
    assert (
        d.render()
        == """\
FROM alpine AS builder
ARG FOO
COPY --from=builder --chown=neuro ["foo/bar/baz.txt", \\
      "foo/baz/cat.txt", \\
      "/opt/"]
ENV PATH="$PATH:/opt/foo/bin"
LABEL ORG="myorg\""""
    )

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    d.copy(
        ["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/", from_="builder", chown="neuro"
    )
    d.env(PATH="$PATH:/opt/foo/bin")
    d.label(ORG="myorg")
    d.run("echo foobar")
    assert (
        d.render()
        == """\
FROM alpine AS builder
ARG FOO
COPY --from=builder --chown=neuro ["foo/bar/baz.txt", \\
      "foo/baz/cat.txt", \\
      "/opt/"]
ENV PATH="$PATH:/opt/foo/bin"
LABEL ORG="myorg"
RUN echo foobar"""
    )

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    d.copy(
        ["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/", from_="builder", chown="neuro"
    )
    d.env(PATH="$PATH:/opt/foo/bin")
    d.label(ORG="myorg")
    d.run("echo foobar")
    d.user("nonroot")
    assert (
        d.render()
        == """\
FROM alpine AS builder
ARG FOO
COPY --from=builder --chown=neuro ["foo/bar/baz.txt", \\
      "foo/baz/cat.txt", \\
      "/opt/"]
ENV PATH="$PATH:/opt/foo/bin"
LABEL ORG="myorg"
RUN echo foobar
RUN test "$(getent passwd nonroot)" \\
    || useradd --no-user-group --create-home --shell /bin/bash nonroot
USER nonroot"""
    )

    d = DockerRenderer("apt", users={"root", "nonroot"})
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    d.copy(
        ["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/", from_="builder", chown="neuro"
    )
    d.env(PATH="$PATH:/opt/foo/bin")
    d.label(ORG="myorg")
    d.run("echo foobar")
    d.user("nonroot")
    d.workdir("/opt/foobar")
    assert (
        d.render()
        == """\
FROM alpine AS builder
ARG FOO
COPY --from=builder --chown=neuro ["foo/bar/baz.txt", \\
      "foo/baz/cat.txt", \\
      "/opt/"]
ENV PATH="$PATH:/opt/foo/bin"
LABEL ORG="myorg"
RUN echo foobar
USER nonroot
WORKDIR /opt/foobar"""
    )
