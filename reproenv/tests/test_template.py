import pytest

from reproenv import exceptions
from reproenv import template
from reproenv import types


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
    it = template.BinariesTemplate(d, name="didi", version="1.0.0", age=42)
    assert it.kwds_as_attrs.name == "didi"
    assert it.kwds_as_attrs.version == "1.0.0"
    # Values are all cast to string.
    assert it.kwds_as_attrs.age == "42"
    # invalid version - not found in urls
    with pytest.raises(exceptions.TemplateError):
        template.BinariesTemplate(d, version="2.0.0")

    #
    # Source template
    #
    d: types.SourceTemplateType = {
        "instructions": "hello {{ self.name }}",
        "arguments": {"required": ["name"], "optional": ["age"]},
    }
    it = template.SourceTemplate(d, name="foobar")
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
    it = template.SourceTemplate(d, name="foobar", age=42, height=100)
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
    assert it.kwds_as_attrs.name == "foobar"
    assert it.kwds_as_attrs.age == "42"
    assert it.kwds_as_attrs.height == "100"
