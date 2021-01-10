import pytest

from reproenv import exceptions
from reproenv import template
from reproenv import types

# TODO: move some of these tests to a `test_state.py` file.

from reproenv.state import _TemplateRegistry

register_template = _TemplateRegistry.register


def test_installation_template_base():
    d: types.BinariesTemplateType = {
        "urls": {"1.0.0": "foobar"},
        "env": {"foo": "bar"},
        "instructions": "foobar",
        "arguments": {
            "required": [],
            "optional": [],
        },
        "dependencies": {"apt": [], "dpkg": [], "yum": []},
    }

    it = template._BaseInstallationTemplate(d)
    assert it._template is d
    assert it.env is d["env"]
    assert it.instructions is d["instructions"]
    assert it.arguments is d["arguments"]
    assert it.required_arguments is d["arguments"]["required"]
    assert it.optional_arguments is d["arguments"]["optional"]
    assert it.dependencies("apt") is d["dependencies"]["apt"]
    with pytest.raises(ValueError):
        it.dependencies("foobar")

    with pytest.raises(exceptions.TemplateError):
        template._BaseInstallationTemplate(d, key="val")

    d["arguments"]["required"] = ["foo"]
    template._BaseInstallationTemplate(d, foo="bar")
    with pytest.raises(exceptions.TemplateError):
        template._BaseInstallationTemplate(d)

    d["arguments"]["required"] = ["version"]
    it = template.BinariesTemplate(d, version="1.0.0")
    with pytest.raises(exceptions.TemplateError):
        template.BinariesTemplate(d, version="fakeversion")

    assert it.urls is d["urls"]
    assert it.versions == d["urls"].keys()

    it = template.SourceTemplate(d, version="foobar")
    assert it.versions == {"ANY"}
