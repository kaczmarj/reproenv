from pathlib import Path

import pytest
import yaml

from reproenv import exceptions
from reproenv.state import _TemplateRegistry, _validate_template
from reproenv import types


def test_validate_template_invalid_templates():
    with pytest.raises(exceptions.TemplateError, match="'name' is a required property"):
        _validate_template({})

    with pytest.raises(
        exceptions.TemplateError, match="'binaries' is a required property"
    ):
        _validate_template({"name": "bar"})

    # missing 'name' top-level key
    with pytest.raises(exceptions.TemplateError, match="'name' is a required property"):
        _validate_template(
            {
                # "name": "foobar",
                "binaries": {
                    "urls": {"1.0.0": "foobar.com"},
                    "instructions": "foobar",
                },
            }
        )

    # 'name' top-level value is not a string
    with pytest.raises(exceptions.TemplateError, match="1234 is not of type 'string'"):
        _validate_template(
            {
                "name": 1234,
                "binaries": {
                    "urls": {"1.0.0": "foobar.com"},
                    "instructions": "foobar",
                },
            }
        )

    #
    # test of 'binaries' templates
    #

    # no instructions
    with pytest.raises(
        exceptions.TemplateError, match="'instructions' is a required property"
    ):
        _validate_template(
            {
                "name": "foobar",
                "binaries": {
                    "urls": {"1.0.0": "foobar.com"},
                    # "instructions": "foobar",
                },
            }
        )

    # malformed env
    with pytest.raises(
        exceptions.TemplateError,
        match="Invalid template: \\['foo'\\] is not of type 'string'.",
    ):
        _validate_template(
            {
                "name": "foobar",
                "binaries": {
                    "urls": {"1.0.0": "foobar.com"},
                    "env": {"foo": ["foo"]},
                    "instructions": "foobar",
                },
            }
        )

    # binaries but no urls
    with pytest.raises(exceptions.TemplateError, match="'urls' is a required property"):
        _validate_template(
            {
                "name": "foobar",
                "binaries": {
                    # "urls": {"1.0.0": "foobar.com"},
                    "instructions": "foobar",
                },
            }
        )

    # extra keys
    with pytest.raises(
        exceptions.TemplateError,
        match=(
            "Invalid template: Additional properties are not allowed \\('extra' was"
            " unexpected\\)"
        ),
    ):
        _validate_template(
            {
                "name": "foobar",
                "binaries": {
                    "urls": {"1.0.0": "foobar.com"},
                    "instructions": "foobar",
                    "extra": "",
                },
            }
        )

    # extra keys in dependencies
    with pytest.raises(
        exceptions.TemplateError,
        match=(
            "Invalid template: Additional properties are not allowed \\('fakemngr'"
            " was unexpected\\)."
        ),
    ):
        _validate_template(
            {
                "name": "foobar",
                "binaries": {
                    "urls": {"1.0.0": "foobar.com"},
                    "instructions": "foobar",
                    "dependencies": {"apt": [], "fakemngr": []},
                },
            }
        )

    # has dependencies but never installs them.
    with pytest.raises(exceptions.TemplateError, match="defined but never installed"):
        _validate_template(
            {
                "name": "foobar",
                "binaries": {
                    "urls": {"1.0.0": "foobar.com"},
                    "env": {"foo": "bar"},
                    "instructions": "foobar",
                    "arguments": {
                        "required": [],
                        "optional": [],
                    },
                    "dependencies": {"apt": ["curl"], "dpkg": [], "yum": []},
                },
            }
        )

    # defines variable but does not indicate if optional or required
    # TODO

    #
    # test of 'source' templates
    #

    # urls should not be in source
    with pytest.raises(
        exceptions.TemplateError,
        match=(
            "Invalid template: Additional properties are not allowed \\('urls' was"
            " unexpected\\)."
        ),
    ):
        _validate_template(
            {
                "name": "foobar",
                "source": {
                    "urls": {"1.0.0": "foobar.com"},
                    "instructions": "foobar",
                },
            }
        )

    # no instructions
    with pytest.raises(
        exceptions.TemplateError, match="'instructions' is a required property"
    ):
        _validate_template(
            {
                "name": "foobar",
                "source": {
                    # "instructions": "foobar",
                },
            }
        )

    # malformed env
    with pytest.raises(
        exceptions.TemplateError,
        match="Invalid template: \\['foo'\\] is not of type 'string'.",
    ):
        _validate_template(
            {
                "name": "foobar",
                "source": {
                    "env": {"foo": ["foo"]},
                    "instructions": "foobar",
                },
            }
        )

    # extra keys
    with pytest.raises(
        exceptions.TemplateError,
        match=(
            "Invalid template: Additional properties are not allowed \\('extra' was"
            " unexpected\\)"
        ),
    ):
        _validate_template(
            {
                "name": "foobar",
                "source": {
                    "instructions": "foobar",
                    "extra": "",
                },
            }
        )

    # extra keys in dependencies
    with pytest.raises(
        exceptions.TemplateError,
        match=(
            "Invalid template: Additional properties are not allowed \\('fakemngr'"
            " was unexpected\\)."
        ),
    ):
        _validate_template(
            {
                "name": "foobar",
                "source": {
                    "instructions": "foobar",
                    "dependencies": {"apt": [], "fakemngr": []},
                },
            }
        )

    # has dependencies but never installs them.
    with pytest.raises(exceptions.TemplateError, match="defined but never installed"):
        _validate_template(
            {
                "name": "foobar",
                "source": {
                    "env": {"foo": "bar"},
                    "instructions": "foobar",
                    "arguments": {
                        "required": [],
                        "optional": [],
                    },
                    "dependencies": {"apt": ["curl"], "dpkg": [], "yum": []},
                },
            }
        )

    # defines variable but does not indicate if optional or required
    # TODO


def test_validate_template_valid_templates():
    # minimal templates
    _validate_template(
        {
            "name": "foobar",
            "binaries": {
                "urls": {"v1": "foo"},
                "instructions": "foobar",
            },
        }
    )
    _validate_template(
        {
            "name": "foobar",
            "source": {
                "instructions": "foobar",
            },
        }
    )

    # bigger templates
    _validate_template(
        {
            "name": "foobar",
            "binaries": {
                "urls": {"v1": "foo"},
                "env": {"baz": "cat", "boo": "123"},
                "instructions": "echo hi there\n{{ self.install_dependencies() }}",
                "arguments": {"required": [], "optional": []},
                "dependencies": {"apt": ["curl"], "dpkg": ["foo"], "yum": ["curl"]},
            },
            "source": {
                "env": {"foo": "bar"},
                "instructions": "echo foo\n{{ self.install_dependencies() }}",
                "arguments": {
                    "required": [],
                    "optional": [],
                },
                "dependencies": {"apt": ["curl"], "dpkg": [], "yum": []},
            },
        }
    )


def test_register(tmp_path: Path):
    _TemplateRegistry._reset()

    _one_test_template: types.TemplateType = {
        "name": "foobar",
        "binaries": {
            "urls": {"1.0.0": "foobar.com"},
            "env": {"foo": "bar"},
            "instructions": "foobar",
            "arguments": {
                "required": [],
                "optional": [],
            },
            "dependencies": {"apt": [], "dpkg": [], "yum": []},
        },
        "source": {
            "env": {"foo": "bar"},
            "instructions": "foobar",
            "arguments": {
                "required": [],
                "optional": [],
            },
            "dependencies": {"apt": [], "dpkg": [], "yum": []},
        },
    }

    with pytest.raises(ValueError):
        _TemplateRegistry.register("foobar", path_or_template="")

    _TemplateRegistry.register("foobar", _one_test_template)
    assert _TemplateRegistry._templates["foobar"] == _one_test_template
    assert not _TemplateRegistry._templates["foobar"] is _one_test_template
    assert _TemplateRegistry.get("foobar") == _one_test_template
    assert _TemplateRegistry.get("FOOBAR") == _one_test_template
    with pytest.raises(exceptions.TemplateNotFound):
        _TemplateRegistry.get("baz")

    yaml_path = tmp_path / "foo.yaml"
    with yaml_path.open("w") as f:
        yaml.dump(_one_test_template, f)

    _TemplateRegistry.register("foobar_yaml", path_or_template=yaml_path)
    assert _TemplateRegistry.get("foobar_yaml") == _one_test_template


def test_get():
    _TemplateRegistry._reset()

    with pytest.raises(exceptions.TemplateNotFound):
        _TemplateRegistry.get("foobar")

    d = {"name": "foo"}
    _TemplateRegistry._templates["foobar"] = d
    assert _TemplateRegistry.get("foobar") == d

    with pytest.raises(exceptions.TemplateNotFound):
        _TemplateRegistry.get("baz")


def test_keys():
    _TemplateRegistry._reset()
    assert _TemplateRegistry.keys() == set()

    name = "foo"
    _TemplateRegistry._templates[name] = {}
    assert _TemplateRegistry.keys() == {"foo"}
