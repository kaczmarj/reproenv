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


# https://stackoverflow.com/a/65744803/5666087
class OrderedParamsCommand(click.Command):
    _options: ty.List[ty.Tuple[click.Parameter, ty.Any]] = []

    def parse_args(self, ctx: click.Context, args: ty.List[str]):
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
            type(self)._options.append((param, value))

        # return "normal" parse results
        return super().parse_args(ctx, args)


# https://stackoverflow.com/a/48394004/5666087
class OptionEatAll(click.Option):
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


@click.group()
@click.version_option(__version__, message="%(prog)s version %(version)s")
def cli():
    pass


@cli.group()
def generate():
    """Generate instructions to build a container image."""
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


def _add_common_renderer_options(cmd: click.Command) -> click.Command:
    options = [
        click.option(
            "-p",
            "--pkg-manager",
            type=click.Choice(allowed_pkg_managers, case_sensitive=False),
            required=True,
            help="System package manager",
        ),
        click.option(
            "-b",
            "--base-image",
            "from_",
            required=True,
            multiple=True,
            help="Base image",
        ),
        click.option(
            "--arg",
            multiple=True,
            help="Build-time variables (do not persist after container is built)",
        ),
        # TODO: how to handle multiple files?
        click.option(
            "--copy",
            multiple=True,
            help="Copy files into the container",
        ),
        click.option(
            "--env",
            # multiple=True,
            type=KeyValuePair(),
            cls=OptionEatAll,
            help="Set persistent environment variables",
        ),
        click.option(
            "--install",
            multiple=True,
            help="Install packages with system package manager",
        ),
        click.option(
            "--label",
            type=KeyValuePair(),
            cls=OptionEatAll,
            help="Set labels on the container",
        ),
        click.option(
            "--run",
            multiple=True,
            help="Execute commands in /bin/sh",
        ),
        click.option(
            "--user",
            multiple=True,
            help="Switch to a different user (create user if it does not exist)",
        ),
        click.option(
            "--workdir",
            multiple=True,
            help="Set the working directory",
        ),
    ]

    for option in options:
        cmd = option(cmd)

    return cmd


# register templates
def _register_templates():
    # TODO: make this customizable.
    tmpl_path = Path(__file__).parent.parent.parent / "neurodocker-templates"
    assert tmpl_path.exists()
    template_paths = []
    template_paths.extend(tmpl_path.glob("*.yaml"))
    template_paths.extend(tmpl_path.glob("*.yml"))
    for path in template_paths:
        _TemplateRegistry.register(path)


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
        for arg in getattr(template, method).optional_arguments:
            h += f"\n    - {arg}"
    return h


def _add_registered_templates(cmd: click.Command) -> click.Command:
    """Add registered templates as options to the CLI."""

    _register_templates()

    for name, tmpl in _TemplateRegistry.items():
        hlp = _create_help_for_template(Template(tmpl))
        option = click.option(
            f"--{name.lower()}",
            type=KeyValuePair(),
            cls=OptionEatAll,
            multiple=True,
            help=hlp,
        )
        cmd = option(cmd)
    return cmd


def _params_to_renderer_dict(ctx: click.Context, pkg_manager):
    # Create a dictionary compatible with `_Renderer.from_dict()`.
    renderer_dict = {
        "pkg_manager": pkg_manager,
        "instructions": [],
    }
    # We could check if the instructions dict is empty, but it should never be
    # empty because `--base-image` is required.
    cmd = ctx.command
    cmd = ty.cast(OrderedParamsCommand, cmd)
    for param, value in cmd._options:
        d = _get_instruction_for_param(param=param, value=value)
        # TODO: what happens if `d is None`?
        if d is not None:
            renderer_dict["instructions"].append(d)
    return renderer_dict


def _get_instruction_for_param(param: click.Parameter, value: ty.Any):
    # TODO: clean this up.
    d = None
    if param.name == "from_":
        d = {"name": param.name, "kwds": {"base_image": value}}
    # arg
    elif param.name == "arg":
        d = {"name": param.name, "kwds": {"key": value, "value": value[0]}}
    # copy
    elif param.name == "copy":
        d = {"name": param.name, "kwds": {"source": value, "destination": value[0]}}
    # env
    elif param.name == "env":
        value = dict(value)
        d = {"name": param.name, "kwds": {**value}}
    # install
    elif param.name == "install":
        # TODO: add 'opts' kwd.
        d = {"name": param.name, "kwds": {"pkgs": value}}
    # label
    elif param.name == "label":
        value = dict(value)
        d = {"name": param.name, "kwds": {**value}}
    # run
    elif param.name == "run":
        d = {"name": param.name, "kwds": {"command": value[0]}}
    # user
    elif param.name == "user":
        d = {"name": param.name, "kwds": {"user": value[0]}}
    # workdir
    elif param.name == "workdir":
        d = {"name": param.name, "kwds": {"path": value[0]}}
    # probably a registered template?
    else:
        if param.name.lower() in _TemplateRegistry.keys():
            value = dict(value)
            d = {"name": param.name.lower(), "kwds": dict(value)}
        else:
            # TODO: should we do anything special with unknown options? Probably log it.
            pass
    return d


docker = _add_common_renderer_options(docker)
singularity = _add_common_renderer_options(singularity)

docker = _add_registered_templates(docker)
singularity = _add_registered_templates(singularity)
