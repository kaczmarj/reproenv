import pytest

from reproenv.exceptions import RendererError
from reproenv.renderers import _Renderer


def test_renderer():
    with pytest.raises(RendererError):
        _Renderer(pkg_manager="foo")

    _Renderer("apt")
    assert _Renderer("yum").users == {"root"}
    assert _Renderer("apt", users={"root", "foo"}).users == {"root", "foo"}
    assert _Renderer("apt")._templates == {}


def test_not_implemented_methods():
    r = _Renderer("yum")
    with pytest.raises(NotImplementedError):
        r.arg(key="a", value="b")
    with pytest.raises(NotImplementedError):
        r.copy("", "")
    with pytest.raises(NotImplementedError):
        r.env(foo="bar")
    with pytest.raises(NotImplementedError):
        r.from_("baseimage")
    with pytest.raises(NotImplementedError):
        r.label(foo="bar")
    with pytest.raises(NotImplementedError):
        r.run("foo")
    with pytest.raises(NotImplementedError):
        r.user("nonroot")
    with pytest.raises(NotImplementedError):
        r.workdir("/opt/")
