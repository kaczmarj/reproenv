"""Stateful objects in reproenv runtime."""

import copy
import json
import os
from pathlib import Path
import typing as ty
from typing_extensions import Literal


import jsonschema
import yaml

# The [C]SafeLoader will only load a subset of YAML, but that is fine for the
# purposes of this package.
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader  # type: ignore

from reproenv.exceptions import TemplateError
from reproenv.exceptions import TemplateNotFound
from reproenv.types import TemplateType

_schemas_path = Path(__file__).parent / "schemas"

with (_schemas_path / "template.json").open("r") as f:
    _TEMPLATE_SCHEMA: ty.Dict = json.load(f)

with (_schemas_path / "renderer.json").open("r") as f:
    _RENDERER_SCHEMA: ty.Dict = json.load(f)


def _validate_template(template: TemplateType):
    """Validate template against JSON schema. Raise exception if invalid."""
    # TODO: should reproenv have a custom exception for invalid templates? probably
    try:
        jsonschema.validate(template, schema=_TEMPLATE_SCHEMA)
    except jsonschema.exceptions.ValidationError as e:
        raise TemplateError(f"Invalid template: {e.message}.") from e

    # TODO: Check that all variables in the instructions are listed in arguments.
    # something like https://stackoverflow.com/a/8284419/5666087
    # but that solution does not get attributes like foo in `self.foo`.
    # For now, this is taken care of in Renderer classes, but it would be good to move
    # that behavior here, so we can catch errors early.
    pass

    # Check for `self.install_dependencies()` in instructions if dependencies are not
    # empty.
    # TODO: this mess happened while trying to enforce types... how can it be made
    # cleaner?
    method: Literal["binaries", "source"]
    methods: ty.Set[Literal["binaries", "source"]] = {"binaries", "source"}
    for method in methods:
        if method in template.keys():
            if "dependencies" in template[method]:
                has_deps = any(template[method]["dependencies"].values())
                if (
                    has_deps
                    and "self.install_dependencies()"
                    not in template[method]["instructions"]
                ):
                    raise TemplateError(
                        "Dependencies are defined but never installed in"
                        f" 'template.{method}.instructions'."
                        "\nAdd `{{ self.install_dependencies() }}` to instructions."
                    )


class _TemplateRegistry:
    """Object to hold templates in memory."""

    _templates: ty.Dict[str, TemplateType] = {}

    @classmethod
    def _reset(cls):
        """Clear all templates."""
        cls._templates = {}

    @classmethod
    def register(
        cls, name: str, path_or_template: ty.Union[str, os.PathLike, TemplateType]
    ):
        """Register a template. This will overwrite an existing template with the
        same name in the registry.

        The template is validated against reproenv's template JSON schema upon
        registration. An invalid template will raise an exception.

        Parameters
        ----------
        name : str
            Name of the template. This becomes the key to the template in the registry.
            The name is made lower-case.
        path_or_template : str, Path-like, or TemplateType
            Path to YAML file that defines the template, or the dictionary that
            represents the template.
        """
        name = str(name)
        if isinstance(path_or_template, dict):
            template = copy.deepcopy(path_or_template)
        else:
            path_or_template = Path(path_or_template)
            if not path_or_template.is_file():
                raise ValueError("template is not path to a file or a dictionary")
            with path_or_template.open() as f:
                template = yaml.load(f, Loader=SafeLoader)

        _validate_template(template)

        # TODO: Add the template name as an optional key to the renderer schema. This is
        # so that the dictionary passed to the `Renderer().from_dict()` method can
        # contain names of registered templates. These templates are not known when the
        # renderer schema is created.
        pass

        # Add template to registry.
        # TODO: should we log a message if overwriting a key-value pair?
        cls._templates[name.lower()] = template

    @classmethod
    def get(cls, name: str) -> TemplateType:
        """Return a Template object from the registry given a template name.

        Parameters
        ----------
        name : str
            The name of the registered template.

        If the template is not found, perhaps it was not added to the registry using
        `register`.
        """
        name = name.lower()
        try:
            return cls._templates[name]
        except KeyError:
            known = "', '".join(cls._templates.keys())
            raise TemplateNotFound(
                f"Unknown template '{name}'. Registered templates are '{known}'."
            )

    @classmethod
    def keys(cls) -> ty.KeysView[str]:
        """Return names of registered templates."""
        return cls._templates.keys()
