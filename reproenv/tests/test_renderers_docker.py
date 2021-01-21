import pytest

from reproenv.exceptions import RendererError
from reproenv.renderers import DockerRenderer
from reproenv.template import Template


def test_docker_renderer_add_template():
    r = DockerRenderer("apt")

    d = {
        "name": "foobar",
        "binaries": {
            "urls": {"1.0.0": "foobar"},
            "env": {"foo": "bar"},
            "instructions": "{{self.install_dependencies()}}\necho hello\necho world",
            "arguments": {
                "required": [],
                "optional": {},
            },
            "dependencies": {"apt": ["curl"], "debs": [], "yum": ["python"]},
        },
    }

    # Not a Template type.
    with pytest.raises(
        RendererError, match="template must be an instance of 'Template' but got"
    ):
        r.add_template(d, method="binaries")

    # Invalid method
    with pytest.raises(
        RendererError, match="method must be 'binaries', 'source' but got 'fakemethod"
    ):
        r.add_template(Template(d), method="fakemethod")

    # Test apt.
    r.add_template(Template(d), method="binaries")
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
    r.add_template(Template(d), method="binaries")
    assert len(r._parts) == 2
    assert r._parts[0] == 'ENV foo="bar"'
    assert (
        r._parts[1]
        == """RUN yum install -y -q \\
           python \\
    && yum clean all \\
    && rm -rf /var/cache/yum/* \\
    && echo hello \\
    && echo world"""
    )

    # Test required arguments.
    d = {
        "name": "foobar",
        "binaries": {
            "urls": {"1.0.0": "foobar"},
            "env": {"foo": "bar"},
            "instructions": (
                "{{self.install_dependencies()}}\necho hello {{ self.name }}"
            ),
            "arguments": {
                "required": ["name"],
                "optional": {},
            },
            "dependencies": {"apt": ["curl"], "debs": [], "yum": ["python"]},
        },
    }
    r = DockerRenderer("apt")
    r.add_template(Template(d, binaries_kwds=dict(name="Bjork")), method="binaries")
    assert (
        str(r)
        == """ENV foo="bar"
RUN apt-get update -qq \\
    && apt-get install -y -q --no-install-recommends \\
           curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && echo hello Bjork"""
    )

    d = {
        "name": "foobar",
        "binaries": {
            "urls": {"1.0.0": "foobar"},
            "env": {"foo": "bar"},
            "instructions": (
                "{{self.install_dependencies()}}\necho hello {{ self.name }}"
            ),
            "arguments": {
                "required": [],
                "optional": {"name": "foo"},
            },
            "dependencies": {"apt": ["curl"], "debs": [], "yum": ["python"]},
        },
    }

    r = DockerRenderer("apt")
    r.add_template(Template(d), method="binaries")
    assert (
        str(r)
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
    assert str(d) == "FROM alpine"

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    assert str(d) == "FROM alpine AS builder"

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    assert str(d) == "FROM alpine AS builder\nARG FOO"

    d = DockerRenderer("apt")
    d.from_("alpine", as_="builder")
    d.arg("FOO")
    d.copy(
        ["foo/bar/baz.txt", "foo/baz/cat.txt"], "/opt/", from_="builder", chown="neuro"
    )
    assert (
        str(d)
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
        str(d)
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
        str(d)
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
        str(d)
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
        str(d)
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
        str(d)
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
    d.run_bash("source activate")
    assert (
        str(d)
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
WORKDIR /opt/foobar
RUN bash -c 'source activate'"""
    )
