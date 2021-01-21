# see https://click.palletsprojects.com/en/7.x/advanced/#forwarding-unknown-options

# TODO: consider using https://github.com/click-contrib/click-option-group to create
# groups of options in the cli. Could be helpful to separate the options.

# TODO: add a dedicated class for key=value in the eat-all class.

from pathlib import Path
import typing as ty

import click

from reproenv import __version__
from reproenv.renderers import DockerRenderer
from reproenv.renderers import SingularityRenderer
from reproenv.state import _TemplateRegistry
from reproenv.template import Template
from reproenv.types import allowed_pkg_managers


class GroupAddCommonParamsAndRegisteredTemplates(click.Group):
    """Subclass of `click.Group` that adds parameters common to `reproenv generate`
    commands, registers templates, and adds parameters to render templates.

    Note: Commands that are part of this group must be called using the group. This is
    because the `.get_command()` method of this group adds required parameters.
    """

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.params = [
            click.Option(
                ["--template-path"],
                multiple=True,
                envvar="REPROENV_TEMPLATE_PATH",
                show_envvar=True,
                help="Path to directories with templates to register",
                type=click.Path(exists=True, file_okay=False, dir_okay=True),
            )
        ]

    def get_command(self, ctx: click.Context, name: str) -> ty.Optional[click.Command]:
        command = self.commands.get(name)
        if command is None:
            return command  # return immediately to error can be logged

        # This is only set if a subcommand is called. Calling --help on the group
        # does not set --template-path.
        template_path: ty.Tuple[str] = ctx.params.get("template_path", tuple())
        yamls: ty.List[Path] = []
        for p in template_path:
            path = Path(p)
            for pattern in ("*.yaml", "*.yml"):
                yamls.extend(path.glob(pattern))
        # TODO: log warning if no yamls are found?
        for path in yamls:
            _TemplateRegistry.register(path)

        params: ty.List[click.Parameter] = [
            click.Option(
                ["-p", "--pkg-manager"],
                type=click.Choice(allowed_pkg_managers, case_sensitive=False),
                required=True,
                multiple=False,
                help="System package manager",
            ),
        ]
        params = _get_common_renderer_params()
        params += _get_params_for_registered_templates()
        command.params += params
        return command


# https://stackoverflow.com/a/65744803/5666087
class OrderedParamsCommand(click.Command):
    """Subclass of `click.Command` that maintains the order of user-provided
    parameters.
    """

    def parse_args(self, ctx: click.Context, args: ty.List[str]):
        self._options: ty.List[ty.Tuple[click.Parameter, ty.Any]] = []
        # run the parser for ourselves to preserve the passed order
        parser = self.make_parser(ctx)
        param_order: ty.List[click.Parameter]
        opts, _, param_order = parser.parse_args(args=list(args))
        for param in param_order:
            value = opts[param.name]
            # If we have multiple values, take the first one. We do this before type
            # casting, because type casting for some reason brings all of the given
            # values for a parameter into the container. Not sure why, but perhaps it
            # has to do with the click.Context object.
            if isinstance(value, list):
                value = value.pop(0)
            if param.multiple:
                # If the value is supposed to be in a tuple, put it back in a tuple.
                value = (value,)
            value = param.type_cast_value(ctx, value)
            if isinstance(value, tuple):
                value = value[0]
            self._options.append((param, value))

        # return "normal" parse results
        return super().parse_args(ctx, args)


# https://stackoverflow.com/a/48394004/5666087
class OptionEatAll(click.Option):
    """Subclass of `click.Option` that allows for an arbitrary number of options.

    The behavior is similar to `nargs="*"` in argparse.
    """

    def __init__(self, *args, **kwargs):
        nargs = kwargs.pop("nargs", -1)
        assert nargs == -1, "nargs, if set, must be -1 not {}".format(nargs)
        super(OptionEatAll, self).__init__(*args, **kwargs)
        self._previous_parser_process = None
        self._eat_all_parser = None

    def add_to_parser(self, parser, ctx):
        def parser_process(value, state):
            # method to hook to the parser.process
            done = False
            value = [value]
            # grab everything up to the next option
            while state.rargs and not done:
                for prefix in self._eat_all_parser.prefixes:
                    if state.rargs[0].startswith(prefix):
                        done = True
                if not done:
                    value.append(state.rargs.pop(0))
            value = tuple(value)

            # call the actual process
            self._previous_parser_process(value, state)

        retval = super(OptionEatAll, self).add_to_parser(parser, ctx)
        for name in self.opts:
            our_parser = parser._long_opt.get(name) or parser._short_opt.get(name)
            if our_parser:
                self._eat_all_parser = our_parser
                self._previous_parser_process = our_parser.process
                our_parser.process = parser_process
                break
        return retval


class KeyValuePair(click.ParamType):
    """Type that accepts key=value pairs and converts to tuples of (key, value) if
    not multiple and ((key1, value1), (key2, value2)...) if multiple.
    """

    name = "key=value"

    def convert(self, value, param, ctx):
        def fn(v: str):
            strs = v.split("=")
            if len(strs) != 2:
                self.fail("expected string in format 'key=value'", param, ctx)
            k, v = strs
            return k, v

        # This might be a tuple or a list if using OptionEatAll.
        if isinstance(value, (list, tuple)):
            return tuple(map(fn, value))
        else:
            return fn(value)


def _get_common_renderer_params() -> ty.List[click.Parameter]:
    params: ty.List[click.Parameter] = [
        click.Option(
            ["-p", "--pkg-manager"],
            type=click.Choice(allowed_pkg_managers, case_sensitive=False),
            required=True,
            multiple=False,
            help="System package manager",
        ),
        click.Option(
            ["-b", "--base-image", "from_"],
            required=True,
            multiple=True,
            help="Base image",
        ),
        click.Option(
            ["--arg"],
            type=KeyValuePair(),
            multiple=True,
            help="Build-time variables (do not persist after container is built)",
        ),
        OptionEatAll(
            ["--copy"],
            multiple=True,
            help=(
                "Copy files into the container. Provide at least two paths."
                " The last path is always the destination path in the container."
            ),
        ),
        OptionEatAll(
            ["--env"],
            multiple=True,
            type=KeyValuePair(),
            help="Set persistent environment variables",
        ),
        OptionEatAll(
            ["--install"],
            multiple=True,
            help="Install packages with system package manager",
        ),
        OptionEatAll(
            ["--label"],
            multiple=True,
            type=KeyValuePair(),
            help="Set labels on the container",
        ),
        click.Option(
            ["--run"],
            multiple=True,
            help="Run commands in /bin/sh",
        ),
        click.Option(
            ["--run-bash"],
            multiple=True,
            help="Run commands in a bash shell",
        ),
        click.Option(
            ["--user"],
            multiple=True,
            help="Switch to a different user (create user if it does not exist)",
        ),
        click.Option(
            ["--workdir"],
            multiple=True,
            help="Set the working directory",
        ),
    ]
    return params


def _create_help_for_template(template):
    methods = []
    if template.binaries is not None:
        methods.append("binaries")
    if template.source is not None:
        methods.append("source")
    h = f"\b\nAdd {template.name}\n  method=[{'|'.join(methods)}]"
    for method in methods:
        h += f"\n  options for method={method}"
        for arg in getattr(template, method).required_arguments:
            h += f"\n    - {arg} [required]"
            # TODO: should we only include versions if using binaries?
            if arg == "version" and method == "binaries":
                h += f"""\n        version=[{'|'.join(
                    sorted(getattr(template, method).versions, reverse=True))}]"""
        for arg, default in getattr(template, method).optional_arguments.items():
            h += f"\n    - {arg} [default: {default}]"
    return h


def _get_params_for_registered_templates() -> ty.List[click.Parameter]:
    """Return list of click parameters for registered templates."""
    params: ty.List[click.Parameter] = []
    for name, tmpl in _TemplateRegistry.items():
        hlp = _create_help_for_template(Template(tmpl))
        param = OptionEatAll(
            [f"--{name.lower()}"],
            type=KeyValuePair(),
            multiple=True,
            help=hlp,
        )
        params.append(param)
    return params


def _params_to_renderer_dict(ctx: click.Context, pkg_manager) -> dict:
    """Return dictionary compatible with compatible with `_Renderer.from_dict()`."""
    renderer_dict = {
        "pkg_manager": pkg_manager,
        "instructions": [],
    }
    cmd = ctx.command
    cmd = ty.cast(OrderedParamsCommand, cmd)
    for param, value in cmd._options:
        d = _get_instruction_for_param(ctx=ctx, param=param, value=value)
        # TODO: what happens if `d is None`?
        if d is not None:
            renderer_dict["instructions"].append(d)
    if not renderer_dict["instructions"]:
        ctx.fail("not enough instructions to generate a container specification")
    return renderer_dict


def _get_instruction_for_param(
    ctx: click.Context, param: click.Parameter, value: ty.Any
):
    # TODO: clean this up.
    d = None
    if param.name == "from_":
        d = {"name": param.name, "kwds": {"base_image": value}}
    # arg
    elif param.name == "arg":
        assert len(value) == 2, "expected key=value pair for --arg"
        k, v = value
        d = {"name": param.name, "kwds": {"key": k, "value": v}}
    # copy
    elif param.name == "copy":
        assert len(value) > 1, "expected at least two values for --copy"
        source, destination = list(value[:-1]), value[-1]
        d = {"name": param.name, "kwds": {"source": source, "destination": destination}}
    # env
    elif param.name == "env":
        value = dict(value)
        d = {"name": param.name, "kwds": {**value}}
    # install
    elif param.name == "install":
        opts = None
        if isinstance(value, tuple):
            value = list(value)
        # Special case. Set `opts` if provided.
        for idx, val in enumerate(value):
            if val.startswith("opts="):
                opts = value.pop(idx)
                opts = opts[slice(len("opts="), None)]  # remove leading opts=
        if not value:
            ctx.fail("no packages provided to install")
        d = {
            "name": param.name,
            "kwds": {"pkgs": value, "opts": opts},
        }
    # label
    elif param.name == "label":
        value = dict(value)
        d = {"name": param.name, "kwds": {**value}}
    # run
    elif param.name == "run":
        d = {"name": param.name, "kwds": {"command": value}}
    # run_bash
    elif param.name == "run_bash":
        d = {"name": param.name, "kwds": {"command": value}}
    # user
    elif param.name == "user":
        d = {"name": param.name, "kwds": {"user": value}}
    # workdir
    elif param.name == "workdir":
        d = {"name": param.name, "kwds": {"path": value}}
    # probably a registered template?
    else:
        if param.name.lower() in _TemplateRegistry.keys():
            value = dict(value)
            d = {"name": param.name.lower(), "kwds": dict(value)}
        else:
            # TODO: should we do anything special with unknown options? Probably log it.
            pass
    return d


@click.group()
@click.version_option(__version__, message="%(prog)s version %(version)s")
def cli():
    pass


@cli.group(cls=GroupAddCommonParamsAndRegisteredTemplates)
def generate(*, template_path):
    """Generate container."""
    pass


@generate.command(cls=OrderedParamsCommand)
@click.pass_context
def docker(ctx: click.Context, pkg_manager, **kwds):
    """Generate a Dockerfile."""
    renderer_dict = _params_to_renderer_dict(ctx=ctx, pkg_manager=pkg_manager)
    renderer = DockerRenderer.from_dict(renderer_dict)
    output = str(renderer)
    click.echo(output)


@generate.command(cls=OrderedParamsCommand)
@click.pass_context
def singularity(ctx: click.Context, pkg_manager, **kwds):
    """Generate a Singularity recipe."""
    renderer_dict = _params_to_renderer_dict(ctx=ctx, pkg_manager=pkg_manager)
    renderer = SingularityRenderer.from_dict(renderer_dict)
    output = str(renderer)
    click.echo(output)
