"""Container specification renderers."""

from __future__ import annotations

import os
import typing as ty

import jinja2

from reproenv.exceptions import RendererError
from reproenv.exceptions import TemplateError
from reproenv.state import _TemplateRegistry
from reproenv.state import _validate_renderer
from reproenv.template import _BaseInstallationTemplate
from reproenv.template import Template
from reproenv.types import _SingularityHeaderType
from reproenv.types import allowed_pkg_managers
from reproenv.types import allowed_installation_methods
from reproenv.types import installation_methods_type
from reproenv.types import pkg_managers_type

# All jinja2 templates are instantiated from this environment object. It is
# configured to dislike undefined attributes. For example, if a template is
# created with the string '{{ foo.bar }}' and 'foo' does not have a 'bar'
# attribute, an error will be thrown when the jinja template is instantiated.
_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

# TODO: add a flag that avoids buggy behavior when basing a new container on
# one created with ReproEnv.

# TODO: add `install` instance method to `_Renderer`.


def _render_string_from_template(
    source: str, template: _BaseInstallationTemplate
) -> str:
    """Take a string from a template and render """
    source = source.replace("self.", "template.")
    tmpl = _jinja_env.from_string(source)
    err = (
        "A template included in this renderer raised an error. Please check the"
        " template definition. A required argument might not be included in the"
        " required arguments part of the template. Variables in the template should"
        " start with `self.`."
    )
    try:
        return tmpl.render(template=template)
    except jinja2.exceptions.UndefinedError as e:
        raise RendererError(err) from e


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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (_Renderer, str)):
            raise NotImplementedError()

        def rm_empty_lines(s):
            return "\n".join(
                j
                for j in str(s).splitlines()
                if j.strip() and not j.strip().startswith("#")
            )

        # Empty lines and commented lines do not affect container definitions.
        return rm_empty_lines(self) == rm_empty_lines(other)

    @property
    def users(self) -> ty.Set[str]:
        return self._users

    @classmethod
    def from_dict(cls, d: ty.Mapping) -> _Renderer:
        """Instantiate a new renderer from a dictionary of instructions."""
        # raise error if invalid
        _validate_renderer(d)

        pkg_manager = d["pkg_manager"]
        users = d.get("existing_users", None)

        # create new renderer object
        renderer = cls(pkg_manager=pkg_manager, users=users)

        for mapping in d["instructions"]:
            method_or_template = mapping["name"]
            kwds = mapping["kwds"]
            this_instance_method = getattr(renderer, method_or_template, None)
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
                    renderer.add_registered_template(method_or_template, **kwds)
                except TemplateError as e:
                    raise RendererError(
                        f"Error on template '{method_or_template}'. Please see"
                        " the traceback above for details. Was the template registered?"
                    ) from e
        return renderer

    def add_template(
        self, template: Template, method: installation_methods_type
    ) -> _Renderer:
        """Add a template to the renderer.

        Parameters
        ----------
        template : Template
            The template to add. To reference templates by name, use
            `.add_registered_template`.
        method : str
            The method to use to install the software described in the template.
        """

        if not isinstance(template, Template):
            raise RendererError(
                "template must be an instance of 'Template' but got"
                f" '{type(template)}'."
            )
        if method not in allowed_installation_methods:
            raise RendererError(
                "method must be '{}' but got '{}'.".format(
                    "', '".join(sorted(allowed_installation_methods)), method
                )
            )

        template_method: _BaseInstallationTemplate = getattr(template, method)
        if template_method is None:
            raise RendererError(f"template does not have entry for: '{method}'")
        # Validate kwds passed by user to template, and raise an exception if any are
        # invalid.
        template_method.validate_kwds()

        # If we keep the `self.VAR` syntax of the template, then we need to pass
        # `self=template_method` to the renderer function. But that function is an
        # instance method, so passing `self` will override the `self` argument.
        # To get around this, we replace `self.` with something that is not an
        # argument to the renderer function.

        # Add environment (render any jinja templates).
        if template_method.env:
            d: ty.Mapping[str, str] = {
                _render_string_from_template(
                    k, template_method
                ): _render_string_from_template(v, template_method)
                for k, v in template_method.env.items()
            }
            self.env(**d)

        # Add installation instructions (render any jinja templates).
        if template_method.instructions:
            command = ""
            dependencies = template_method.dependencies(self.pkg_manager)
            if dependencies:
                # TODO: how can we pass in arguments here?
                command += _install(pkgs=dependencies, pkg_manager=self.pkg_manager)
                # Install debs if we are using apt and debs are requested.
                if self.pkg_manager == "apt":
                    debs = template_method.dependencies("debs")
                    if debs:
                        command += "\n" + _apt_install_debs(debs)
                command += "\n"
            command += _render_string_from_template(
                template_method.instructions, template_method
            )
            self.run(command)

        return self

    def add_registered_template(
        self,
        name: str,
        method: installation_methods_type = None,
        **kwds,
    ) -> _Renderer:

        # Template was validated at registration time.
        template_dict = _TemplateRegistry.get(name)

        # By default, prefer 'binaries', but use 'source' if 'binaries' is not defined.
        # TODO: should we require user to provide method?
        if method is None:
            method = "binaries" if "binaries" in template_dict else "source"
        if method not in template_dict:
            raise RendererError(
                f"Installation method '{method}' not defined for template '{name}'."
                " Options are '{}'.".format("', '".join(template_dict.keys()))
            )

        binaries_kwds = source_kwds = None
        if method == "binaries":
            binaries_kwds = kwds
        elif method == "source":
            source_kwds = kwds

        template = Template(
            template=template_dict,
            binaries_kwds=binaries_kwds,
            source_kwds=source_kwds,
        )

        self.add_template(template=template, method=method)
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

    def install(self, pkgs: ty.List[str], opts=None) -> _Renderer:
        raise NotImplementedError()

    def label(self, **kwds: ty.Mapping[str, str]) -> _Renderer:
        raise NotImplementedError()

    def run(self, command: str) -> _Renderer:
        raise NotImplementedError()

    def run_bash(self, command: str) -> _Renderer:
        command = f"bash -c '{command}'"
        return self.run(command)

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

    def install(self, pkgs: ty.List[str], opts=None) -> DockerRenderer:
        """Install system packages."""
        command = _install(pkgs, pkg_manager=self.pkg_manager, opts=opts)
        command = _indent_run_instruction(command)
        self.run(command)
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
        s = _indent_run_instruction(f"RUN {s}")
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

    def arg(self, key: str, value: str = None) -> SingularityRenderer:
        # TODO: look into whether singularity has something like ARG, like passing in
        # environment variables.
        s = f"{key}" if value is None else f"{key}={value}"
        self._post.append(s)
        return self

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
            raise RendererError("Unknown singularity bootstrap agent.")

        self._header = {"bootstrap": bootstrap, "from_": image}
        return self

    def install(self, pkgs: ty.List[str], opts=None) -> SingularityRenderer:
        """Install system packages."""
        command = _install(pkgs, pkg_manager=self.pkg_manager, opts=opts)
        self.run(command)
        return self

    def label(self, **kwds: ty.Mapping[str, str]) -> SingularityRenderer:
        # TODO: why are we getting this error?
        # Argument 1 to "update" of "dict" has incompatible type
        # "Dict[str, Mapping[str, str]]"; expected "Mapping[str, str]"
        self._labels.update(kwds)  # type: ignore
        return self

    def run(self, command: str) -> SingularityRenderer:
        self._post.append(command)
        return self

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


def _indent_run_instruction(string: str, indent=4) -> str:
    """Return indented string for Dockerfile `RUN` command."""
    out = []
    lines = string.splitlines()
    for ii, line in enumerate(lines):
        line = line.rstrip()
        is_last_line = ii == len(lines) - 1
        already_cont = line.startswith(("&&", "&", "||", "|", "fi"))
        is_comment = line.startswith("#")
        previous_cont = lines[ii - 1].endswith("\\") or lines[ii - 1].startswith("if")
        if ii:  # do not apply to first line
            if not already_cont and not previous_cont and not is_comment:
                line = "&& " + line
            if not already_cont and previous_cont:
                line = " " * (indent + 3) + line  # indent + len("&& ")
            else:
                line = " " * indent + line
        if not is_last_line and not line.endswith("\\") and not is_comment:
            line += " \\"
        out.append(line)
    return "\n".join(out)


def _install(pkgs: ty.List[str], pkg_manager: str, opts: str = None) -> str:
    if pkg_manager == "apt":
        return _apt_install(pkgs, opts)
    elif pkg_manager == "yum":
        return _yum_install(pkgs, opts)
    # TODO: add debs here?
    else:
        raise RendererError(f"Unknown package manager '{pkg_manager}'.")


def _apt_install(pkgs: ty.List[str], opts: str = None, sort=True) -> str:
    """Return command to install deb packages with `apt-get` (Debian-based distros).

    `opts` are options passed to `yum install`. Default is "-q --no-install-recommends".
    """
    pkgs = sorted(pkgs) if sort else pkgs
    opts = "-q --no-install-recommends" if opts is None else opts
    s = """\
apt-get update -qq
apt-get install -y {opts} \\
    {pkgs}
rm -rf /var/lib/apt/lists/*
""".format(
        opts=opts, pkgs=" \\\n    ".join(pkgs)
    )
    return s.strip()


def _apt_install_debs(urls: ty.List[str], opts: str = None, sort=True) -> str:
    """Return command to install deb packages with `apt-get` (Debian-based distros).

    `opts` are options passed to `yum install`. Default is "-q".
    """

    def install_one(url: str):
        return f"""\
_reproenv_tmppath="$(mktemp -t tmp.XXXXXXXXXX.deb)"
curl -fsSL --retry 5 -o "${{_reproenv_tmppath}}" {url}
apt-get install --yes {opts} "${{_reproenv_tmppath}}"
rm "${{_reproenv_tmppath}}\""""

    urls = sorted(urls) if sort else urls
    opts = "-q" if opts is None else opts

    s = "\n".join(map(install_one, urls))
    s += """
apt-get update -qq
apt-get install --yes --quiet --fix-missing
rm -rf /var/lib/apt/lists/*"""
    return s


def _yum_install(pkgs: ty.List[str], opts: str = None, sort=True) -> str:
    """Return command to install packages with `yum` (CentOS, Fedora).

    `opts` are options passed to `yum install`. Default is "-q".
    """
    pkgs = sorted(pkgs) if sort else pkgs
    opts = "-q" if opts is None else opts

    s = """\
yum install -y {opts} \\
    {pkgs}
yum clean all
rm -rf /var/cache/yum/*
""".format(
        opts=opts, pkgs=" \\\n    ".join(pkgs)
    )
    return s.strip()
