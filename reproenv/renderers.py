"""Container specification renderers.

General overview of rendering:
1. Collect list of templates (either binaries or source installation method)
2. For each template,
    - Put together the raw string that will install that software. Do not
        render with jinja2 yet.
    - Change any references to `self` to some unique ID.
3. Collect the raw strings from each template and render with jinja2. Pass in
    keyword arguments of the unique IDs (that replaced `self`) so that instance
    methods and variables are used during rendering. This allows us to render
    everything just once.
"""

from __future__ import annotations

import os
import typing as ty

import jinja2

from reproenv.exceptions import RendererError
from reproenv.exceptions import TemplateError
from reproenv.state import _TemplateRegistry
from reproenv.template import BinariesTemplate
from reproenv.template import SourceTemplate
from reproenv.types import installation_methods_type
from reproenv.types import allowed_pkg_managers
from reproenv.types import pkg_managers_type
from reproenv.types import _SingularityHeaderType

# All jinja2 templates are instantiated from this environment object. It is
# configured to dislike undefined attributes. For example, if a template is
# created with the string '{{ foo.bar }}' and 'foo' does not have a 'bar'
# attribute, an error will be thrown when the jinja template is instantiated.
jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

# TODO: add a flag that avoids buggy behavior when basing a new container on
# one created with ReproEnv.


class _Renderer:
    def __init__(
        self, pkg_manager: pkg_managers_type, users: ty.Optional[ty.Set[str]] = None
    ) -> None:
        if pkg_manager not in allowed_pkg_managers:
            raise RendererError(
                "Unknown package manager '{}'. Allowed package managers are"
                " '{}'.".format(pkg_manager, "', '".join(allowed_pkg_managers))
            )

        self.pkg_manager = pkg_manager
        self._users = {"root"} if users is None else users
        self._templates: ty.Dict[str, ty.Union[BinariesTemplate, SourceTemplate]] = {}

    @property
    def jinja_template(self) -> jinja2.Template:
        return jinja_env.from_string(str(self))

    @property
    def users(self) -> ty.Set[str]:
        return self._users

    def add_template(
        self, template: ty.Union[BinariesTemplate, SourceTemplate]
    ) -> _Renderer:
        # First, replace all mentions of 'self' with some unique ID. (In
        # practice, we actually match 'self.' to avoid unwanted matches.)
        # Store a mapping of the unique IDs to the object that has the options
        # as attributes.
        # Then, add env (if it exists) and instructions.
        # The validation will have to happen at render time.

        if not isinstance(template, (BinariesTemplate, SourceTemplate)):
            raise ValueError(
                "Template must be an instance of `BinariesTemplate` or"
                f" `SourceTemplate`. Got {type(template)}"
            )

        t_id = f"template_{len(self._templates)}"
        t_id_dot = t_id + "."
        self._templates[t_id] = template

        # Add environment.
        if template.env:
            d: ty.Mapping[str, str] = {
                k.replace("self.", t_id_dot): v.replace("self.", t_id_dot)
                for k, v in template.env.items()
            }
            self.env(**d)

        # Add installation instructions.
        if template.instructions:
            run = ""
            dependencies = template.dependencies(self.pkg_manager)
            if dependencies:
                run = install(pkgs=dependencies, pkg_manager=self.pkg_manager)
                run += "\n"
            run += template.instructions.replace("self.", t_id_dot)
            self.run(run)

        return self

    def add_registered_template(
        self,
        name: str,
        installation_method: installation_methods_type = None,
        **kwargs,
    ) -> _Renderer:

        template_dict = _TemplateRegistry.get(name)

        # By default, prefer 'binaries', but use 'source' if 'binaries' is not defined.
        if installation_method is None:
            if "binaries" in template_dict:
                installation_method = "binaries"
            else:
                installation_method = "source"

        if installation_method not in template_dict:
            raise TemplateError(
                "Installation method '{}' not defined for template '{}'."
                " Options are '{}'.".format(
                    installation_method, name, "', '".join(template_dict.keys())
                )
            )

        # We ignore the type here because we've done enough checking ourselves.
        t = template_dict[installation_method]
        if installation_method == "binaries":
            self.add_template(BinariesTemplate(t, **kwargs))  # type: ignore
        elif installation_method == "source":
            self.add_template(SourceTemplate(t, **kwargs))
        else:
            raise RendererError("Unknown installation method.")

        return self

    def arg(self, key: str, value: str = None):
        raise NotImplementedError()

    def copy(
        self,
        source: ty.Union[ty.List[os.PathLike], os.PathLike],
        destination: os.PathLike,
    ) -> _Renderer:
        raise NotImplementedError()

    def env(self, **kwds: ty.Mapping[str, str]) -> _Renderer:
        raise NotImplementedError()

    def from_(self, base_image: str) -> _Renderer:
        raise NotImplementedError()

    def from_dict(
        self,
        d: ty.List[ty.Dict],
    ) -> _Renderer:
        if not isinstance(d, list) or not d:
            raise ValueError("Input must be a non-empty list.")

        for mapping in d:
            method_or_template = mapping["name"]
            kwds = mapping["kwds"]
            # for method_or_template, kwargs in d.items:
            this_instance_method = getattr(self, method_or_template, None)
            # Method exists and is something like 'copy', 'env', 'run', etc.
            if this_instance_method is not None:
                try:
                    this_instance_method(**kwds)
                except Exception as e:
                    raise RendererError(
                        f"Error on step '{method_or_template}'. Please see the"
                        " traceback above for details."
                    ) from e
            # This is actually a template.
            else:
                try:
                    self.add_registered_template(method_or_template, **kwds)
                except TemplateError as e:
                    raise RendererError(
                        f"Error on template '{method_or_template}'. Please see"
                        " the traceback above for details. Was the template registered?"
                    ) from e
        return self

    def label(self, **kwds: ty.Mapping[str, str]) -> _Renderer:
        raise NotImplementedError()

    def render(self) -> str:
        err = (
            "A template included in this renderer raised an error. Please"
            " check the template definition. A required argument might not"
            " be included in the required arguments part of the template."
            " Variables in the template should start with `self.`."
        )
        try:
            s = self.jinja_template.render(**self._templates)
        except jinja2.exceptions.UndefinedError:
            raise TemplateError(err)
        if (
            jinja_env.variable_start_string not in s
            and jinja_env.variable_end_string not in s
        ):
            return s

        # Render the string again. This is sometimes necessary because some
        # defaults in the template are rendered as {{ self.X }}. These defaults
        # need to be rendered again.
        try:
            return jinja_env.from_string(s).render(**self._templates)
        except jinja2.exceptions.UndefinedError:
            raise TemplateError(err)

    def run(self, command: str) -> _Renderer:
        raise NotImplementedError()

    def user(self, user: str) -> _Renderer:
        raise NotImplementedError()

    def workdir(self, path: os.PathLike) -> _Renderer:
        raise NotImplementedError()


class DockerRenderer(_Renderer):
    def __init__(
        self, pkg_manager: pkg_managers_type, users: ty.Set[str] = None
    ) -> None:
        super().__init__(pkg_manager=pkg_manager, users=users)
        self._parts: ty.List[str] = []

    def __str__(self) -> str:
        """Return an un-rendered version of the Dockerfile.

        Use `.render()` to fill in Jinja template.
        """
        return "\n".join(self._parts)

    def arg(self, key: str, value: str = None) -> DockerRenderer:
        """Add a Dockerfile `ARG` instruction."""
        s = f"ARG {key}" if value is None else f"ARG {key}={value}"
        self._parts.append(s)
        return self

    def copy(
        self,
        source: ty.Union[ty.List[os.PathLike], os.PathLike],
        destination: os.PathLike,
        from_: str = None,
        chown: str = None,
    ) -> DockerRenderer:
        """Add a Dockerfile `COPY` instruction."""
        if not isinstance(source, (list, tuple)):
            source = [source]
        source.append(destination)
        files = '["{}"]'.format('", \\\n      "'.join(map(str, source)))
        s = "COPY "
        if from_ is not None:
            s += f"--from={from_} "
        if chown is not None:
            s += f"--chown={chown} "
        s += files
        self._parts.append(s)
        return self

    def env(self, **kwds: ty.Mapping[str, str]) -> DockerRenderer:
        """Add a Dockerfile `ENV` instruction."""
        s = "ENV " + " \\\n    ".join(f'{k}="{v}"' for k, v in kwds.items())
        self._parts.append(s)
        return self

    def from_(self, base_image: str, as_: str = None) -> DockerRenderer:
        """Add a Dockerfile `FROM` instruction."""
        if as_ is None:
            s = "FROM " + base_image
        else:
            s = f"FROM {base_image} AS {as_}"
        self._parts.append(s)
        return self

    def label(self, **kwds: ty.Mapping[str, str]) -> DockerRenderer:
        """Add a Dockerfile `LABEL` instruction."""
        s = "LABEL " + " \\\n      ".join(f'{k}="{v}"' for k, v in kwds.items())
        self._parts.append(s)
        return self

    def run(self, command: str) -> DockerRenderer:
        """Add a Dockerfile `RUN` instruction."""
        # TODO: should the command be quoted?
        # s = shlex.quote(command)
        # if s.startswith("'"):
        #     s = s[1:-1]  # Remove quotes on either end of the string.
        s = command
        s = indent("RUN " + s, add_list_op=True)
        self._parts.append(s)
        return self

    def user(self, user: str) -> DockerRenderer:
        """Add a Dockerfile `USER` instruction. If the user is not in
        `self.users`, then a `RUN` instruction that creates the user
        will also be added.
        """
        s = ""
        if user not in self._users:
            s = (
                f'RUN test "$(getent passwd {user})" \\\n    || useradd '
                f"--no-user-group --create-home --shell /bin/bash {user}"
            )
            self._parts.append(s)
            self._users.add(user)
        self._parts.append(f"USER {user}")
        return self

    def workdir(self, path: os.PathLike) -> DockerRenderer:
        """Add a Dockerfile `WORKDIR` instruction."""
        self._parts.append("WORKDIR " + str(path))
        return self


class SingularityRenderer(_Renderer):
    def __init__(
        self, pkg_manager: pkg_managers_type, users: ty.Optional[ty.Set[str]] = None
    ) -> None:
        super().__init__(pkg_manager=pkg_manager, users=users)

        self._header: _SingularityHeaderType = {}
        # The '%setup' section is intentionally ommitted.
        self._files: ty.List[str] = []
        self._environment: ty.List[ty.Tuple[str, str]] = []
        self._post: ty.List[str] = []
        self._runscript = ""
        # TODO: is it OK to use a dict here? Labels could be overwritten.
        self._labels: ty.Dict[str, str] = {}

    def __str__(self) -> str:
        s = ""
        # Create header.
        if self._header:
            s += (
                f"Bootstrap: {self._header['bootstrap']}\nFrom: {self._header['from_']}"
            )

        # Add files.
        if self._files:
            s += "\n\n%files\n"
            s += "\n".join(self._files)

        # Add environment.
        if self._environment:
            s += "\n\n%environment"
            for k, v in self._environment:
                s += f'\nexport {k}="{v}"'

        # Add post.
        if self._post:
            s += "\n\n%post\n"
            s += "\n\n".join(self._post)
            # for instruction in self._post:

        # Add runscript.
        if self._runscript:
            s += "\n\n%runscript\n"
            s += self._runscript

        # Add labels.
        if self._labels:
            s += "\n\n%labels\n"
            for kv in self._labels.items():
                s += " ".join(kv)

        return s

    def arg(self, *args, **kwargs):
        raise NotImplementedError("Singularity does not support `ARG`.")

    def copy(
        self,
        source: ty.Union[ty.List[os.PathLike], os.PathLike],
        destination: os.PathLike,
    ) -> SingularityRenderer:
        if not isinstance(source, (list, tuple)):
            source = [source]
        files = [f"{src} {destination}" for src in source]
        self._files.extend(files)
        return self

    def env(self, **kwds: ty.Mapping[str, str]) -> SingularityRenderer:
        # TODO: why does this raise a type error?
        self._environment.extend(kwds.items())  # type: ignore
        return self

    def from_(self, base_image: str) -> SingularityRenderer:
        if "://" not in base_image:
            bootstrap = "docker"
            image = base_image
        elif base_image.startswith("docker://"):
            bootstrap = "docker"
            image = base_image[9:]
        elif base_image.startswith("library://"):
            bootstrap = "library"
            image = base_image[10:]
        else:
            raise ValueError("Unknown singularity bootstrap agent.")

        self._header = {"bootstrap": bootstrap, "from_": image}
        return self

    def label(self, **kwds: ty.Mapping[str, str]) -> SingularityRenderer:
        # TODO: why are we getting this error?
        # Argument 1 to "update" of "dict" has incompatible type
        # "Dict[str, Mapping[str, str]]"; expected "Mapping[str, str]"
        self._labels.update(kwds)  # type: ignore
        return self

    def run(self, command: str):
        self._post.append(command)

    def user(self, user: str) -> SingularityRenderer:
        if user not in self._users:
            post = (
                f'test "$(getent passwd {user})" \\\n|| useradd '
                f"--no-user-group --create-home --shell /bin/bash {user}\n"
            )
            self._users.add(user)
            self._post.append(post)
        self._post.append(f"su - {user}")
        return self

    def workdir(self, path: os.PathLike) -> SingularityRenderer:
        self._post.append(f"mkdir -p {path}\ncd {path}")
        return self


def indent(string, indent=4, add_list_op=False):
    """Return indented string for Dockerfile `RUN` command."""
    out = []
    lines = string.splitlines()

    for ii, line in enumerate(lines):
        line = line.rstrip()
        already_cont = line.startswith(("&&", "&", "||", "|", "fi"))
        previous_cont = lines[ii - 1].endswith("\\") or lines[ii - 1].startswith("if")
        if ii:
            if add_list_op and not already_cont and not previous_cont:
                line = "&& " + line
            if not already_cont and previous_cont:
                line = " " * (indent + 3) + line
            else:
                line = " " * indent + line
        if ii != len(lines) - 1:
            if not line.endswith("\\"):
                line += " \\"
        out.append(line)
    return "\n".join(out)


def install(pkgs: ty.List[str], pkg_manager: str, opts="") -> str:
    if pkg_manager == "apt":
        return apt_install(pkgs, opts)
    elif pkg_manager == "dpkg":
        return dpkg_install(pkgs, opts)
    elif pkg_manager == "yum":
        return yum_install(pkgs, opts)
    else:
        raise ValueError(
            f"Unknown package manager '{pkg_manager}'. Allowed package"
            " managers are 'apt', 'dpkg', and 'yum'."
        )


def apt_install(pkgs: ty.List[str], opts="", sort=True) -> str:
    if sort:
        pkgs = sorted(pkgs)
    if not opts:
        opts = "-q --no-install-recommends"
    s = """\
apt-get update -qq
apt-get install -y {opts} \\
    {pkgs}
rm -rf /var/lib/apt/lists/*
""".format(
        opts=opts, pkgs=" \\\n    ".join(pkgs)
    )
    return s.strip()


def dpkg_install(urls: ty.List[str], opts="") -> str:
    def install_one(url: str):
        return f"""\
curl -fsSL --retry 5 -o /tmp/toinstall.deb {url}
dpkg -i {opts} /tmp/toinstall.deb
rm /tmp/toinstall.deb"""

    s = "\n".join(install_one(u) for u in urls)
    s += """\
apt-get update -qq
apt-get install -y -q --fix-missing
rm -rf /var/lib/apt/lists/*"""
    return s


def yum_install(pkgs: ty.List[str], opts="", sort=True) -> str:
    if sort:
        pkgs = sorted(pkgs)
    if not opts:
        opts = "-q"
    s = """\
yum install -y {opts} \\
    {pkgs}
yum clean all \\
rm -rf /var/cache/yum/*
""".format(
        opts=opts, pkgs=" \\\n    ".join(pkgs)
    )
    return s.strip()
