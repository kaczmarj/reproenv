"""ReproEnv is a generic generator of Dockerfiles and Singularity files."""

from reproenv.renderers import DockerRenderer  # noqa: F401
from reproenv.renderers import SingularityRenderer  # noqa: F401
from reproenv.state import register_template  # noqa: F401
from reproenv.state import registered_templates  # noqa: F401
from reproenv.state import get_template  # noqa: F401
from reproenv.template import Template  # noqa: F401
from reproenv._version import get_versions

__version__ = get_versions()["version"]
del get_versions
