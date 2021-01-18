# see https://click.palletsprojects.com/en/7.x/advanced/#forwarding-unknown-options

from pathlib import Path
import typing as ty

import click

from reproenv import __version__
from reproenv.renderers import DockerRenderer
from reproenv.renderers import SingularityRenderer
from reproenv.state import _TemplateRegistry
from reproenv.template import Template
from reproenv.types import allowed_pkg_managers
from reproenv.types import TemplateType


# register templates
def _register_templates():
    tmpl_path = Path(__file__).parent.parent.parent / "neurodocker-templates"
    assert tmpl_path.exists()
    template_paths = []
    template_paths.extend(tmpl_path.glob("*.yaml"))
    template_paths.extend(tmpl_path.glob("*.yml"))
    for path in template_paths:
        _TemplateRegistry.register(path)


# We have to do this in global scope for now because options are added to the
# click cli functions at runtime and depend on the templates being registered.
_register_templates()


# https://stackoverflow.com/a/65744803/5666087
class OrderedParamsCommand(click.Command):
    """Subclass of `click.Command` that preserves order of user-provided params."""

    def parse_args(self, ctx, args):
        self._options: ty.List[ty.Tuple[click.Parameter, ty.Any]] = []
        parser = self.make_parser(ctx)
        opts, _, param_order = parser.parse_args(args=list(args))
        for param in param_order:
            value, args = param.handle_parse_result(ctx, opts, args)
            self._options.append((param, value))
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
    name = "key=value pair"

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
@click.option(
    "-p",
    "--pkg-manager",
    type=click.Choice(allowed_pkg_managers, case_sensitive=False),
    required=True,
    help="System package manager",
)
@click.option(
    "-b",
    "--base-image",
    "from_",
    required=True,
    multiple=True,
    help="Base image",
)
@click.option(
    "--arg",
    multiple=True,
    help="ARG instruction",
)
# TODO: how to handle multiple files?
@click.option(
    "--copy",
    multiple=True,
    help="COPY instruction",
)
@click.option(
    "--env",
    # multiple=True,
    type=KeyValuePair(),
    cls=OptionEatAll,
    help="ENV instruction",
)
@click.option(
    "--install",
    multiple=True,
    help="Install system packages with --pkg-manager.",
)
@click.option(
    "--label",
    type=KeyValuePair(),
    cls=OptionEatAll,
    help="LABEL instruction",
)
@click.option(
    "--run",
    multiple=True,
    help="RUN instruction",
)
@click.option(
    "--user",
    multiple=True,
    help="USER instruction (adds user if it does not exist)",
)
@click.option(
    "--workdir",
    multiple=True,
    help="WORKDIR instruction",
)
def docker(ctx: click.Context, pkg_manager, **kwds):
    """Generate a Dockerfile."""

    # Create a dictionary compatible with `_Renderer.from_dict()`.
    renderer_dict = {
        "pkg_manager": pkg_manager,
        "instructions": [],
    }

    cmd = ctx.command
    cmd = ty.cast(OrderedParamsCommand, cmd)
    for param, value in cmd._options:
        # print(param, value)
        d = get_instruction_for_param(param=param, value=value)
        # TODO: what happens if `d is None`?
        if d is not None:
            renderer_dict["instructions"].append(d)

    # We could check if the instructions dict is empty, but it should never be
    # empty because `--base-image` is required.

    renderer = DockerRenderer.from_dict(renderer_dict)
    output = str(renderer)
    click.echo(output)


@generate.command()
def singularity():
    """Generate a Singularity recipe."""
    click.echo("generating singularity")


def _make_help(template: TemplateType) -> str:
    t = Template(template)
    h = f"Add {t.name}."
    if t.binaries is not None:
        h += f"""
Install from pre-compiled binaries. Required arguments are \
'{"', '".join(t.binaries.required_arguments)}'. Optional arguments are \
'{"', '".join(t.binaries.optional_arguments)}'."""
    if t.source is not None:
        h += f"""
Install from source. Required arguments are \
'{"', '".join(t.source.required_arguments)}'. Optional arguments are \
'{"', '".join(t.source.optional_arguments)}'."""
    return h


def _add_registered_templates(fn: click.Command) -> click.Command:
    """Add registered templates as options to the CLI."""

    for name, tmpl in _TemplateRegistry.items():
        hlp = _make_help(tmpl)
        option = click.option(
            f"--{name.lower()}",
            type=KeyValuePair(),
            cls=OptionEatAll,
            # TODO make the help message niiiiice.
            help=hlp,
        )
        # This is what a decorator does.
        fn = option(fn)
    return fn


def get_instruction_for_param(param: click.Parameter, value: ty.Any):
    # TODO: clean this up.
    d = None
    if param.name == "from_":
        assert len(value) == 1
        d = {"name": param.name, "kwds": {"base_image": value[0]}}
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


docker = _add_registered_templates(docker)
singularity = _add_registered_templates(singularity)
