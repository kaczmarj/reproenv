"""ReproEnv is a generic generator of Dockerfiles and Singularity files."""

from reproenv.renderers import DockerRenderer  # noqa: F401
from reproenv.renderers import SingularityRenderer  # noqa: F401
from reproenv.state import _TemplateRegistry
from reproenv._version import get_versions

__version__ = get_versions()["version"]
del get_versions

register_template = _TemplateRegistry.register
registered_templates = _TemplateRegistry.keys
get_template = _TemplateRegistry.get

del _TemplateRegistry
