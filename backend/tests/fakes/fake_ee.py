"""A fake ``ee`` module for offline tests.

conftest injects this into ``sys.modules['ee']`` (unless ORBITER_GEE_LIVE=1),
so importing the app and exercising the fusion graph needs no live Earth
Engine, no network, and no credentials.

Design: every ee object is a chainable *recorder*. Each method call appends
``{"op", "args", "kwargs"}`` to a shared ``ops`` list threaded through the
chain, so tests assert on the *sequence* of operations (e.g. that Landsat
scale/offset is applied BEFORE ``normalizedDifference``, or that NDWI uses the
Green/NIR bands) without any numeric evaluation.
"""
from __future__ import annotations

from types import SimpleNamespace

# ── call log for ee.Initialize (auth-free-import assertions) ──────────────
initialize_calls: list[dict] = []

# ── tunable knobs ─────────────────────────────────────────────────────────
_state = {"collection_size": 5}


def reset() -> None:
    initialize_calls.clear()
    _state["collection_size"] = 5


def set_collection_size(n: int) -> None:
    """Control what ``ImageCollection(...).size().getInfo()`` returns."""
    _state["collection_size"] = n


class EEException(Exception):
    pass


class _Number:
    def __init__(self, value, ops):
        self._value = value
        self.ops = ops

    def getInfo(self):
        return self._value

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def _op(*a, **k):
            self.ops.append({"op": f"Number.{name}", "args": list(a), "kwargs": dict(k)})
            return self

        return _op


class _Obj:
    """Chainable operation recorder shared across a fusion pipeline."""

    def __init__(self, kind="image", ops=None, meta=None):
        self.kind = kind
        self.ops = ops if ops is not None else []
        self.meta = meta or {}

    # -- introspection helpers for tests --
    def op_names(self):
        return [o["op"] for o in self.ops]

    def find(self, name):
        return [o for o in self.ops if o["op"] == name]

    def index_of(self, name):
        for i, o in enumerate(self.ops):
            if o["op"] == name:
                return i
        return -1

    # -- internal --
    def _record(self, name, args, kwargs, kind=None):
        self.ops.append({"op": name, "args": list(args), "kwargs": dict(kwargs)})
        return _Obj(kind or self.kind, self.ops, self.meta)

    # -- terminals --
    def size(self):
        self.ops.append({"op": "size", "args": [], "kwargs": {}})
        return _Number(_state["collection_size"], self.ops)

    def getMapId(self, params=None):
        self.ops.append({"op": "getMapId", "args": [], "kwargs": {"params": params}})
        return {
            "mapid": "projects/test/maps/FAKEMAPID",
            "token": "",
            "tile_fetcher": SimpleNamespace(
                url_format=(
                    "https://earthengine.googleapis.com/v1/projects/test/maps/"
                    "FAKEMAPID/tiles/{z}/{x}/{y}"
                )
            ),
        }

    def getInfo(self):
        return self.meta.get("info", {})

    def map(self, fn, *a, **k):
        # Execute the mapped fn on a fake element sharing this ops list so the
        # per-scene ops (e.g. the cloud mask's updateMask) are recorded in the
        # graph — that's how tests prove mask-before-narrow ordering.
        self.ops.append({"op": "map", "args": [], "kwargs": {}})
        try:
            fn(_Obj("image", self.ops, self.meta))
        except Exception:
            pass
        return _Obj(self.kind, self.ops, self.meta)

    # -- generic op dispatcher --
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def _op(*args, **kwargs):
            return self._record(name, args, kwargs)

        return _op


class _FactoryNS:
    """Callable namespace: ``ee.Image(...)`` and ``ee.Image.constant(1)`` etc."""

    def __init__(self, kind):
        self._kind = kind

    def __call__(self, *a, **k):
        return _Obj(self._kind, [], {"init_args": a, "init_kwargs": k})

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def make(*a, **k):
            return _Obj(self._kind, [], {"factory": name, "args": a, "kwargs": k})

        return make


class _CallableNS:
    """``ee.Reducer.median()``, ``ee.Filter.date(...)`` — attr → factory."""

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def make(*a, **k):
            return _Obj("op", [], {"factory": name, "args": a, "kwargs": k})

        return make


# ── the public ee surface ──────────────────────────────────────────────────
Image = _FactoryNS("image")
ImageCollection = _FactoryNS("collection")
Geometry = _FactoryNS("geometry")
Feature = _FactoryNS("feature")
FeatureCollection = _FactoryNS("featurecollection")
Date = _FactoryNS("date")
String = _FactoryNS("string")
List = _FactoryNS("list")
Dictionary = _FactoryNS("dict")

Reducer = _CallableNS()
Filter = _CallableNS()
Algorithms = _CallableNS()
Terrain = _CallableNS()


def Number(x=0, *a, **k):
    return _Number(x if isinstance(x, (int, float)) else 0, [])


class ServiceAccountCredentials:
    def __init__(self, email=None, key_file=None, key_data=None):
        self.email = email
        self.key_file = key_file
        self.key_data = key_data


def Initialize(*args, **kwargs):
    initialize_calls.append({"args": list(args), "kwargs": dict(kwargs)})


def Authenticate(*args, **kwargs):
    pass
