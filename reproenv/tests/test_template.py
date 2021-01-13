import pytest

from reproenv import exceptions
from reproenv import template
from reproenv import types


def test_template():
    d = {
        "name": "foobar",
        "binaries": {
            "urls": {"v1": "foo"},
            "env": {"baz": "cat", "boo": "123"},
            "instructions": "echo hi there\n{{ self.baz }}",
            "arguments": {"required": ["baz"], "optional": []},
            "dependencies": {"apt": ["curl"], "dpkg": ["foo"], "yum": ["curl"]},
        },
        "source": {
            "env": {"foo": "bar"},
            "instructions": "echo foo\n{{ self.boo | default('baz') }}",
            "arguments": {
                "required": [],
                "optional": ["boo"],
            },
            "dependencies": {"apt": ["curl"], "dpkg": [], "yum": []},
        },
    }
    # do not provide required kwds
    with pytest.raises(exceptions.TemplateKeywordArgumentError):
        template.Template(d)
    # only provide optional kwd to source
    with pytest.raises(exceptions.TemplateKeywordArgumentError):
        template.Template(d, source_kwds=dict(boo="cat"))
    # provide unknown kwd
    with pytest.raises(exceptions.TemplateKeywordArgumentError):
        template.Template(d, source_kwds=dict(boop="cat"))
    # provide empty dict
    with pytest.raises(exceptions.TemplateKeywordArgumentError):
        template.Template(d, binaries_kwds={}, source_kwds=dict(boop="cat"))

    # provide all kwds
    t = template.Template(d, binaries_kwds=dict(baz=1234), source_kwds=dict(boo="cat"))
    # do not provide optional kwds
    t = template.Template(d, binaries_kwds=dict(baz=1234))

    assert t.name == d["name"]
    assert t.binaries._template == d["binaries"]
    assert t.source._template == d["source"]
    assert t._template is not d  # check for deepcopy

    # only contains binaries
    t = template.Template(
        {
            "name": "foobar",
            "binaries": {
                "urls": {"v1": "foo"},
                "env": {"baz": "cat", "boo": "123"},
                "instructions": "echo hi there\n{{ self.baz }}",
                "arguments": {"required": ["baz"], "optional": []},
                "dependencies": {"apt": ["curl"], "dpkg": ["foo"], "yum": ["curl"]},
            },
        },
        binaries_kwds=dict(baz="1234"),
    )
    assert t.source is None

    t = template.Template(
        {
            "name": "foobar",
            "source": {
                "env": {"foo": "bar"},
                "instructions": "echo foo\n{{ self.boo | default('baz') }}",
                "arguments": {
                    "required": [],
                    "optional": ["boo"],
                },
                "dependencies": {"apt": ["curl"], "dpkg": [], "yum": []},
            },
        },
        source_kwds=dict(boo="baz"),
    )
    assert t.binaries is None

    # invalid template, but otherwise ok
    with pytest.raises(exceptions.TemplateError):
        template.Template(
            {
                "source": {
                    "env": {"foo": "bar"},
                    "instructions": "echo foo\n{{ self.boo | default('baz') }}",
                    "arguments": {
                        "required": [],
                        "optional": ["boo"],
                    },
                    "dependencies": {"apt": ["curl"], "dpkg": [], "yum": []},
                },
            },
            source_kwds=dict(boo="baz"),
        )


def test_installation_template_base():
    d: types.BinariesTemplateType = {
        "urls": {"1.0.0": "foobar"},
        "instructions": "foobar",
    }

    it = template._BaseInstallationTemplate(d)
    assert it._template == d
    assert it.env == {}
    assert it.instructions == d["instructions"]
    assert it.arguments == {}
    assert it.required_arguments == set()
    assert it.optional_arguments == set()
    assert it.dependencies("apt") == []
    with pytest.raises(ValueError):
        it.dependencies("foobar")

    d: types.BinariesTemplateType = {
        "urls": {"1.0.0": "foobar"},
        "instructions": "hello {{ self.name }}",
        "arguments": {"required": ["name"], "optional": ["age"]},
    }

    #
    # Test keyword arguments.
    #

    # missing required key
    with pytest.raises(exceptions.TemplateError, match="Missing required arguments"):
        template._BaseInstallationTemplate(d)

    # bad key
    with pytest.raises(
        exceptions.TemplateError,
        match="Keyword argument provided is not specified in template",
    ):
        template._BaseInstallationTemplate(d, name="foo", unknown="val")

    # optional key provided only
    with pytest.raises(exceptions.TemplateError, match="Missing required arguments"):
        template._BaseInstallationTemplate(d, age="42")

    # versions
    d["arguments"]["required"] += ["version"]
    it = template._BinariesTemplate(d, name="didi", version="1.0.0", age=42)
    assert it.name == "didi"
    assert it.version == "1.0.0"
    # Values are all cast to string.
    assert it.age == "42"
    # invalid version - not found in urls
    with pytest.raises(exceptions.TemplateError):
        template._BinariesTemplate(d, version="2.0.0")

    #
    # Source template
    #
    d: types.SourceTemplateType = {
        "instructions": "hello {{ self.name }}",
        "arguments": {"required": ["name"], "optional": ["age"]},
    }
    it = template._SourceTemplate(d, name="foobar")
    assert it.versions == {"ANY"}

    d: types.SourceTemplateType = {
        "env": {"foo": "bar", "cat": "dog"},
        "instructions": "echo {{ name }}\n{{ self.install_dependencies() }}",
        "arguments": {
            "required": ["name"],
            "optional": ["age", "height"],
        },
        "dependencies": {"apt": ["curl"], "dpkg": [], "yum": ["python"]},
    }
    it = template._SourceTemplate(d, name="foobar", age=42, height=100)
    assert it._template == d
    assert it.env == {"foo": "bar", "cat": "dog"}
    assert it.instructions == d["instructions"]
    assert it.arguments == d["arguments"]
    assert it.required_arguments == set(d["arguments"]["required"])
    assert it.optional_arguments == set(d["arguments"]["optional"])
    assert it.dependencies("apt") == d["dependencies"]["apt"]
    # TODO: add dpkg
    assert it.dependencies("yum") == d["dependencies"]["yum"]
    with pytest.raises(ValueError):
        it.dependencies("foobar")
    assert it._kwds == {"name": "foobar", "age": "42", "height": "100"}
    assert it.name == "foobar"
    assert it.age == "42"
    assert it.height == "100"
