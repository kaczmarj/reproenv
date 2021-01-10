"""Template objects."""

from __future__ import annotations

import typing as ty

from reproenv.exceptions import TemplateError
from reproenv.types import allowed_pkg_managers
from reproenv.types import pkg_managers_type
from reproenv.types import BinariesTemplateType
from reproenv.types import SourceTemplateType


class _BaseInstallationTemplate:
    """Base class for installation template classes.

    Parameters
    ----------
    template : BinariesTemplateType or SourceTemplateType
        Dictionary that defines how to install software from pre-compiled binaries or
        from source.
    kwargs : dict
        Dictionary of keyword arguments to pass to the template.
    """

    def __init__(
        self, template: ty.Union[BinariesTemplateType, SourceTemplateType], **kwargs
    ) -> None:
        self._template = template
        self._kwargs = kwargs
        req_keys_not_found = set(self.required_arguments).difference(kwargs)
        if req_keys_not_found:
            raise TemplateError(
                "Missing required arguments: '{}'.".format(
                    "', '".join(req_keys_not_found)
                )
            )

        # Check that unknown kwargs weren't passed. We let 'pkg_manager'
        # through so that it can be passed to all templates without error.
        unknown_kwargs = set(kwargs) - set(self.required_arguments).union(
            self.optional_arguments
        ).union({"pkg_manager"})
        if unknown_kwargs:
            raise TemplateError(
                "Unknown keyword arguments: '{}'.".format("', '".join(unknown_kwargs))
            )

        # TODO: keep user kwargs in a separate dictionary, so names don't clash?
        # Set kwargs as attributes.
        existing_attrs = set(kwargs).intersection(self.__dict__)
        if existing_attrs:
            raise AttributeError(
                "Attribute already exists: '{}'.".format("', '".join(existing_attrs))
            )
        self.__dict__.update(kwargs)

        if "version" in self.required_arguments:
            v = kwargs["version"]
            if v not in self.versions and self.versions != {"ANY"}:
                raise TemplateError(
                    "Unknown version '{}'. Allowed versions are '{}'.".format(
                        v, "', '".join(self.versions)
                    )
                )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._template}, **{self._kwargs})"

    @property
    def template(self):
        return self._template

    @property
    def env(self) -> ty.Mapping[str, str]:
        return self._template.get("env", {})

    @property
    def instructions(self) -> str:
        return self._template.get("instructions", "")

    @property
    def arguments(self) -> ty.Mapping:
        return self._template.get("arguments", {})

    @property
    def required_arguments(self) -> ty.Set[str]:
        args = self.arguments.get("required", set())
        return set(args) if args else args

    @property
    def optional_arguments(self) -> ty.Set[str]:
        args = self.arguments.get("optional", set())
        return set(args) if args else args

    @property
    def versions(self):
        raise NotImplementedError()

    def dependencies(self, pkg_manager: pkg_managers_type) -> ty.List[str]:
        if pkg_manager not in allowed_pkg_managers:
            raise ValueError(
                f"invalid package manager: '{pkg_manager}'. valid options are"
                f" {', '.join(allowed_pkg_managers)}."
            )
        deps = self._template.get("dependencies", {})
        # TODO: not sure why the following line raises a type error in mypy.
        return deps.get(pkg_manager, [])  # type: ignore


class BinariesTemplate(_BaseInstallationTemplate):
    def __init__(self, template: BinariesTemplateType, **kwargs):
        super().__init__(template=template, **kwargs)

    @property
    def urls(self) -> ty.Mapping[str, str]:
        # TODO: how can the code be changed so this cast is not necessary?
        self._template = ty.cast(BinariesTemplateType, self._template)
        return self._template["urls"]

    @property
    def versions(self) -> ty.Set[str]:
        # TODO: how can the code be changed so this cast is not necessary?
        self._template = ty.cast(BinariesTemplateType, self._template)
        return set(self._template["urls"].keys())


class SourceTemplate(_BaseInstallationTemplate):
    def __init__(self, template: SourceTemplateType, **kwargs):
        super().__init__(template=template, **kwargs)

    @property
    def versions(self) -> ty.Set[str]:
        return {"ANY"}
