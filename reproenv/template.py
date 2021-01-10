"""Template objects."""

from __future__ import annotations

import copy
import typing as ty

from reproenv.exceptions import TemplateError
from reproenv.types import allowed_pkg_managers
from reproenv.types import pkg_managers_type
from reproenv.types import BinariesTemplateType
from reproenv.types import SourceTemplateType


class _BaseInstallationTemplate:
    """Base class for installation template classes.

    This class and its subclasses make it more convenient to work with templates.
    It also allows one to set keyword arguments for instances of templates. For example,
    if a template calls for an argument `version`, this class can be used to hold both
    the template and the value for `version`.

    Parameters
    ----------
    template : BinariesTemplateType or SourceTemplateType
        Dictionary that defines how to install software from pre-compiled binaries or
        from source.
    kwds
        Keyword arguments to pass to the template. All values must be strings. Values
        that are not strings are cast to string.
    """

    def __init__(
        self,
        template: ty.Union[BinariesTemplateType, SourceTemplateType],
        **kwds: str,
    ) -> None:
        self._template = copy.deepcopy(template)
        # User-defined arguments that are passed to template at render time.
        for key in kwds.keys():
            if not isinstance(kwds[key], str):
                kwds[key] = str(kwds[key])
        self._kwds = kwds

        self._validate_kwds()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._template}, **{self._kwds})"

    def _validate_kwds(self):
        """Raise `TemplateError` if keyword arguments to template are invalid."""
        # Check that all required keywords were provided by user.
        req_keys_not_found = self.required_arguments.difference(self._kwds)
        if req_keys_not_found:
            raise TemplateError(
                "Missing required arguments: '{}'.".format(
                    "', '".join(req_keys_not_found)
                )
            )

        # TODO: should `pkg_manager` be provided if any requirements are defined?

        # Check that unknown kwargs weren't passed. We let 'pkg_manager' through so
        # that it can be passed to all templates without error.
        unknown_kwargs = set(self._kwds) - self.required_arguments.union(
            self.optional_arguments
        ).union({"pkg_manager"})
        if unknown_kwargs:
            raise TemplateError(
                "Keyword argument provided is not specified in template: '{}'.".format(
                    "', '".join(unknown_kwargs)
                )
            )
        # Check that version is valid.
        if "version" in self.required_arguments:
            # At this point, we are certain "version" has been provided.
            v = self._kwds["version"]
            # Templates for builds from source have versions `{"ANY"}` because they can
            # ideally build any version.
            if v not in self.versions and self.versions != {"ANY"}:
                raise TemplateError(
                    "Unknown version '{}'. Allowed versions are '{}'.".format(
                        v, "', '".join(self.versions)
                    )
                )

    @property
    def kwds_as_attrs(self):
        """Return object that can reference keyword arguments as attributes.

        These keywords are attributes of a separate object so that keyword names do not
        overwrite attributes defined by this class.
        """
        return _AttrDict(**self._kwds)

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
        args = self.arguments.get("required", None)
        return set(args) if args is not None else set()

    @property
    def optional_arguments(self) -> ty.Set[str]:
        args = self.arguments.get("optional", None)
        return set(args) if args is not None else set()

    @property
    def versions(self) -> ty.Set[str]:
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
    def __init__(self, template: BinariesTemplateType, **kwds: str):
        # TODO: how can we validate this better? Subset of JSON schema?
        if "instructions" not in template or "urls" not in template:
            raise TemplateError(
                "Invalid template. Expected keys 'instructions' and 'urls'"
            )
        super().__init__(template=template, **kwds)

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
    def __init__(self, template: SourceTemplateType, **kwds: str):
        if "instructions" not in template:
            raise TemplateError("Missing required key: 'instructions'")
        if "urls" in template:
            raise TemplateError("Forbidden key present: 'urls'")
        super().__init__(template=template, **kwds)

    @property
    def versions(self) -> ty.Set[str]:
        return {"ANY"}


class _AttrDict:
    def __init__(self, **kwds: ty.Dict[str, str]):
        self.__dict__.update(kwds)
