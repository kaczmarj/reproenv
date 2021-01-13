"""Template objects."""

from __future__ import annotations

import copy
import typing as ty

from reproenv.exceptions import TemplateKeywordArgumentError
from reproenv.state import _validate_template
from reproenv.types import _BinariesTemplateType
from reproenv.types import _SourceTemplateType
from reproenv.types import TemplateType
from reproenv.types import allowed_pkg_managers
from reproenv.types import pkg_managers_type


class Template:
    """Template object.

    This class makes it more convenient to work with templates. It also allows one to
    set keyword arguments for instances of templates. For example, if a template calls
    for an argument `version`, this class can be used to hold both the template and the
    value for `version`.

    Parameters
    ----------
    template : TemplateType
        Dictionary that defines how to install software from pre-compiled binaries
        and/or from source.
    binaries_kwds : dict
        Keyword arguments to pass to the binaries section of the template. All keys and
        values must be strings.
    source_kwds : dict
        Keyword arguments passed to the source section of the template. All keys and
        values must be strings.
    """

    def __init__(
        self,
        template: TemplateType,
        binaries_kwds: ty.Mapping[str, str] = None,
        source_kwds: ty.Mapping[str, str] = None,
    ):
        # Validate against JSON schema. Registered templates were already validated at
        # registration time, but if we do not validate here, then in-memory templates
        # (ie python dictionaries) will never be validated.
        _validate_template(template)

        self._template = copy.deepcopy(template)
        self._binaries: ty.Optional[_BinariesTemplate] = None
        self._binaries_kwds = {} if binaries_kwds is None else binaries_kwds
        self._source: ty.Optional[_SourceTemplate] = None
        self._source_kwds = {} if source_kwds is None else source_kwds

        if "binaries" in self._template:
            self._binaries = _BinariesTemplate(
                self._template["binaries"], **self._binaries_kwds
            )
        if "source" in self._template:
            self._source = _SourceTemplate(
                self._template["source"], **self._source_kwds
            )

    @property
    def name(self) -> str:
        return self._template["name"]

    @property
    def binaries(self) -> ty.Union[None, _BinariesTemplate]:
        return self._binaries

    @property
    def source(self) -> ty.Union[None, _SourceTemplate]:
        return self._source


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
        template: ty.Union[_BinariesTemplateType, _SourceTemplateType],
        **kwds: str,
    ) -> None:
        self._template = copy.deepcopy(template)
        # User-defined arguments that are passed to template at render time.
        for key in kwds.keys():
            if not isinstance(kwds[key], str):
                kwds[key] = str(kwds[key])
        self._kwds = kwds

        self._validate_kwds()
        self._set_kwds_as_attrs()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._template}, **{self._kwds})"

    def _validate_kwds(self):
        """Raise `TemplateKeywordArgumentError` if keyword arguments to template are
        invalid.
        """
        # Check that keywords do not shadow attributes of this object.
        shadowed = set(self._kwds).intersection(dir(self))
        if shadowed:
            raise TemplateKeywordArgumentError(
                "Invalid keyword arguments: '{}'. If these keywords are used by the"
                " template, then the template must be modified to use different"
                " keywords.".format("', '".join(shadowed))
            )

        # Check that all required keywords were provided by user.
        req_keys_not_found = self.required_arguments.difference(self._kwds)
        if req_keys_not_found:
            raise TemplateKeywordArgumentError(
                "Missing required arguments: '{}'.".format(
                    "', '".join(req_keys_not_found)
                )
            )

        # Check that unknown kwargs weren't passed.
        unknown_kwargs = set(self._kwds).difference(
            self.required_arguments.union(self.optional_arguments)
        )
        if unknown_kwargs:
            raise TemplateKeywordArgumentError(
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
                raise TemplateKeywordArgumentError(
                    "Unknown version '{}'. Allowed versions are '{}'.".format(
                        v, "', '".join(self.versions)
                    )
                )

    def _set_kwds_as_attrs(self):
        # we check if keywords will shadow object's methods in `self._validate_kwds()`.
        for k, v in self._kwds.items():
            setattr(self, k, v)

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


class _BinariesTemplate(_BaseInstallationTemplate):
    def __init__(self, template: _BinariesTemplateType, **kwds: str):
        super().__init__(template=template, **kwds)

    @property
    def urls(self) -> ty.Mapping[str, str]:
        # TODO: how can the code be changed so this cast is not necessary?
        self._template = ty.cast(_BinariesTemplateType, self._template)
        return self._template.get("urls", {})

    @property
    def versions(self) -> ty.Set[str]:
        # TODO: how can the code be changed so this cast is not necessary?
        self._template = ty.cast(_BinariesTemplateType, self._template)
        return set(self.urls.keys())


class _SourceTemplate(_BaseInstallationTemplate):
    def __init__(self, template: _SourceTemplateType, **kwds: str):
        super().__init__(template=template, **kwds)

    @property
    def versions(self) -> ty.Set[str]:
        return {"ANY"}
