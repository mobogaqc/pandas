import contextlib

import pytest

import pandas as pd
import pandas._testing as tm


@contextlib.contextmanager
def ensure_removed(obj, attr):
    """Ensure that an attribute added to 'obj' during the test is
    removed when we're done"""
    try:
        yield
    finally:
        try:
            delattr(obj, attr)
        except AttributeError:
            pass
        obj._accessors.discard(attr)


class MyAccessor:
    def __init__(self, obj):
        self.obj = obj
        self.item = "item"

    @property
    def prop(self):
        return self.item

    def method(self):
        return self.item


@pytest.mark.parametrize(
    "obj, registrar",
    [
        (pd.Series, pd.api.extensions.register_series_accessor),
        (pd.DataFrame, pd.api.extensions.register_dataframe_accessor),
        (pd.Index, pd.api.extensions.register_index_accessor),
    ],
)
def test_register(obj, registrar):
    with ensure_removed(obj, "mine"):
        before = set(dir(obj))
        registrar("mine")(MyAccessor)
        o = obj([]) if obj is not pd.Series else obj([], dtype=object)
        assert o.mine.prop == "item"
        after = set(dir(obj))
        assert (before ^ after) == {"mine"}
        assert "mine" in obj._accessors


def test_accessor_works():
    with ensure_removed(pd.Series, "mine"):
        pd.api.extensions.register_series_accessor("mine")(MyAccessor)

        s = pd.Series([1, 2])
        assert s.mine.obj is s

        assert s.mine.prop == "item"
        assert s.mine.method() == "item"


def test_overwrite_warns():
    # Need to restore mean
    mean = pd.Series.mean
    try:
        with tm.assert_produces_warning(UserWarning) as w:
            pd.api.extensions.register_series_accessor("mean")(MyAccessor)
            s = pd.Series([1, 2])
            assert s.mean.prop == "item"
        msg = str(w[0].message)
        assert "mean" in msg
        assert "MyAccessor" in msg
        assert "Series" in msg
    finally:
        pd.Series.mean = mean


def test_raises_attribute_error():

    with ensure_removed(pd.Series, "bad"):

        @pd.api.extensions.register_series_accessor("bad")
        class Bad:
            def __init__(self, data):
                raise AttributeError("whoops")

        with pytest.raises(AttributeError, match="whoops"):
            pd.Series([], dtype=object).bad
