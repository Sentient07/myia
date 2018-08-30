"""Definition of shape inference for primitives."""

import operator
from dataclasses import is_dataclass
from functools import partial, reduce

from ..infer import ANYTHING, GraphInferrer, register_inferrer, \
    PartialInferrer, Track, MyiaShapeError, Inferrer,  MetaGraphInferrer, \
    InferenceError
from ..ir import Graph, MetaGraph

from ..dtype import Array, Tuple, List, Class, TypeType, ismyiatype, \
    pytype_to_myiatype
from ..utils import Named

from . import ops as P
from .inferrer_utils import static_getter
from .ops import Primitive


def prod(iterable):
    """Return the product of the elements of the iterator."""
    return reduce(operator.mul, iterable, 1)


shape_inferrer_constructors = {}


NOSHAPE = Named('NOSHAPE')


class TupleShape:
    """Class to distinguish the shape of tuples items."""

    __slots__ = ['shape']

    def __init__(self, shape):
        """Create the shape."""
        self.shape = tuple(shape)

    def __repr__(self):
        return f"T{self.shape}"

    def __len__(self):
        return len(self.shape)

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.shape == other.shape)

    def __hash__(self):
        return hash((type(self), self.shape))


class ListShape:
    """Class to represent the shape of list elements."""

    __slots__ = ['shape']

    def __init__(self, shape):
        """Create the shape."""
        self.shape = shape

    def __repr__(self):
        return f"L{self.shape}"

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.shape == other.shape)

    def __hash__(self):
        return hash((type(self), self.shape))


class ClassShape:
    """Class to represent the shape of dataclass fields."""

    __slots__ = ['shape']

    def __init__(self, shape):
        """Create the shape."""
        self.shape = shape

    def __repr__(self):
        return f"C{self.shape}"

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.shape == other.shape)

    def __hash__(self):
        return hash((type(self), tuple(sorted(self.shape.items()))))


class ScalarShapeInferrer(Inferrer):
    """Shape inferrer for all primitives that don't take arrays."""

    def __init__(self, track):
        """Initialize the ScalarShapeInferrer."""
        super().__init__(track, 'scalar_shape_inferrer')

    async def __call__(self, *args):
        """Since no arrays are involved, there is no shape."""
        return NOSHAPE

    def provably_equivalent(self, other):
        """This is always equal to itself."""
        return type(self) == type(other)


def find_matching_shape(shps):
    """Returns a shape that matches all shapes in `shps`."""
    shp = shps[0]
    shps = shps[1:]

    if all(shp == s for s in shps):
        return shp

    if (not isinstance(shp, tuple) or
            any(not isinstance(s, tuple) for s in shps)):
        raise InferenceError("Mismatched element shapes in list")

    if not all(len(shp) == len(s) for s in shps):
        raise InferenceError("Arrays of differing ndim")

    shp = list(shp)
    for i, shp_i in enumerate(shp):
        if any(s[i] != shp_i for s in shps):
            shp[i] = ANYTHING

    return tuple(shp)


class ShapeTrack(Track):
    """Infer the shape of a constant."""

    def __init__(self, engine, name, *,
                 constructors=shape_inferrer_constructors):
        """Initialize a ShapeTrack."""
        super().__init__(engine, name)
        self.constructors = constructors

    def default(self, values):
        """Default value for ShapeTrack."""
        if ismyiatype(values['type'], Array):
            raise Exception(
                'There is no default value for Arrays on the shape track.'
            )  # pragma: no cover
        if ismyiatype(values['type'], Tuple):
            tup = values['type']
            return TupleShape(self.default({'type': e}) for e in tup.elements)
        elif ismyiatype(values['type'], List):
            lst = values['type']
            return ListShape(self.default({'type': lst.element_type}))
        elif ismyiatype(values['type'], Class):
            cls = values['type']
            return ClassShape(dict((attr, self.default({'type': tp}))
                                   for attr, tp in cls.attributes.items()))
        return NOSHAPE

    def from_value(self, v, context):
        """Infer the shape of a constant."""
        if isinstance(v, Primitive):
            if v in self.constructors:
                return self.constructors[v](self)
            else:
                return ScalarShapeInferrer(self)
        elif isinstance(v, Graph):
            return GraphInferrer(self, v, context)
        elif isinstance(v, MetaGraph):
            return MetaGraphInferrer(self, v)
        elif isinstance(v, tuple):
            return TupleShape(self.from_value(e, context) for e in v)
        elif isinstance(v, list):
            shps = [self.from_value(e, context) for e in v]
            if len(shps) == 0:
                return ListShape(NOSHAPE)  # pragma: no cover
            return ListShape(find_matching_shape(shps))
        elif is_dataclass(v):
            if isinstance(v, type):
                rec = self.constructors[P.make_record](self)
                typ = pytype_to_myiatype(v)
                vref = self.engine.vref({'value': typ, 'type': TypeType})
                return PartialInferrer(self, rec, [vref])
            else:
                return ClassShape(
                    dict((n, self.from_value(getattr(v, n), context))
                         for n in v.__dataclass_fields__.keys()))
        else:
            return getattr(v, 'shape', NOSHAPE)

    def to_element(self, sh):
        """Return the type of each element of shape sh."""
        if isinstance(sh, ListShape):
            return sh.shape
        elif isinstance(sh, tuple):
            # Array
            return NOSHAPE
        else:
            raise AssertionError()


shape_inferrer = partial(register_inferrer,
                         constructors=shape_inferrer_constructors)


@shape_inferrer(P.make_tuple, nargs=None)
async def infer_shape_make_tuple(track, *args):
    """Infer the shape for make_tuple."""
    sh = [await x['shape'] for x in args]
    return TupleShape(sh)


@shape_inferrer(P.tail, nargs=1)
async def infer_shape_tail(track, tup):
    """Infer the shape of tail."""
    return TupleShape((await tup['shape']).shape[1:])


@shape_inferrer(P.tuple_getitem, nargs=2)
async def infer_shape_tuple_getitem(track, seq, idx):
    """Infer the shape of tuple_getitem."""
    seq_sh = await seq['shape']
    idx_v = await idx['value']
    return seq_sh.shape[idx_v]


@shape_inferrer(P.make_record, nargs=None)
async def infer_type_make_record(track, cls, *elems):
    """Infer the shape of make_record."""
    elem_shapes = [await x['shape'] for x in elems]
    cls_v = await cls['value']
    return ClassShape(dict(zip(cls_v.attributes.keys(), elem_shapes)))


@shape_inferrer(P.return_, nargs=1)
async def infer_shape_return(track, v):
    """Infer the shape of return."""
    return await v['shape']


@shape_inferrer(P.if_, nargs=3)
async def infer_shape_if(track, cond, tb, fb):
    """Infer the shape of if."""
    tb_inf = await tb['shape']
    fb_inf = await fb['shape']
    v = await cond['value']
    if v is True:
        # We only visit the first branch if the condition is provably true
        return await tb_inf()
    elif v is False:
        # We only visit the second branch if the condition is provably false
        return await fb_inf()
    elif v is ANYTHING:
        # The first branch to finish will return immediately. When the other
        # branch finishes, its result will be checked against the other.
        return await track.assert_same(tb_inf(), fb_inf(), refs=[tb, fb])
    else:
        raise AssertionError("Invalid condition value for if.")


@shape_inferrer(P.switch, nargs=3)
async def infer_shape_switch(track, cond, tb, fb):
    """Infer the shape of switch."""
    v = await cond['value']
    if v is True:
        # We only visit the first branch if the condition is provably true
        return await tb['shape']
    elif v is False:
        # We only visit the second branch if the condition is provably false
        return await fb['shape']
    elif v is ANYTHING:
        # The first branch to finish will return immediately. When the other
        # branch finishes, its result will be checked against the other.
        return await track.assert_same(tb, fb, refs=[tb, fb])
    else:
        raise AssertionError("Invalid condition value for switch.")


@shape_inferrer(P.partial, nargs=None)
async def infer_shape_partial(engine, fn, *args):
    """Infer the return type of partial."""
    fn_t = await fn['shape']
    return PartialInferrer(engine, fn_t, args)


@shape_inferrer(P.array_map, nargs=None)
async def infer_shape_array_map(track, fn, *arrays):
    """Infer the shape of array_map."""
    shapes = [await a['shape'] for a in arrays]
    shape0, *rest = shapes
    if any(len(s) != len(shape0) for s in rest):
        raise MyiaShapeError("Expect same shapes for array_map")
    rshape = []
    for entries in zip(*shapes):
        entries = set(entries)
        entries.add(ANYTHING)
        if len(entries) == 1:
            rshape.append(ANYTHING)
        elif len(entries) == 2:
            entries.remove(ANYTHING)
            entry, = entries
            rshape.append(entry)
        else:
            raise MyiaShapeError("Expect same shapes for array_map")
    return tuple(rshape)


@shape_inferrer(P.list_map, nargs=None)
async def infer_shape_list_map(track, fn, *lsts):
    """Infer the shape of list_map."""
    argrefs = [lst.transform(lambda track, x: track.to_element(x))
               for lst in lsts]
    return ListShape(await (await fn['shape'])(*argrefs))


@shape_inferrer(P.array_scan, nargs=4)
async def infer_shape_array_scan(track, fn, init, ary, ax):
    """Infer the shape of array_scan."""
    return await ary['shape']


@shape_inferrer(P.array_reduce, nargs=3)
async def infer_shape_array_reduce(track, fn, ary, shp):
    """Infer the shape of array_reduce."""
    shp_i = await ary['shape']
    shp_v = await shp['value']
    if shp_v == ANYTHING:
        raise AssertionError(
            'We currently require knowing the shape for reduce.'
        )
        # return (ANYTHING,) * (len(shp_i) - 1)
    else:
        delta = len(shp_i) - len(shp_v)
        if delta < 0 \
                or any(1 != s1 != ANYTHING and 1 != s2 != ANYTHING and s1 != s2
                       for s1, s2 in zip(shp_i[delta:], shp_v)):
            raise MyiaShapeError(
                f'Incompatible dims for reduce: {shp_i}, {shp_v}'
            )
        return shp_v


@shape_inferrer(P.distribute, nargs=2)
async def infer_shape_distribute(track, v, shape):
    """Infer the shape of distribute."""
    shp = await shape['value']
    if shp == ANYTHING:
        shp_t = await shape['type']
        shp = (ANYTHING,) * len(shp_t.elements)
    v_t = await v['type']
    if ismyiatype(v_t, Array):
        v_shp = await v['shape']
        delta = len(shp) - len(v_shp)
        if delta < 0:
            raise MyiaShapeError("Cannot distribute to smaller shape")
        elif delta > 0:
            v_shp = (1,) * delta + v_shp
        for vs, s in zip(v_shp, shp):
            if vs != s and vs not in (1, ANYTHING) and s not in (1, ANYTHING):
                raise MyiaShapeError("Cannot change shape when distributing")
    return shp


@shape_inferrer(P.reshape, nargs=2)
async def infer_shape_reshape(track, v, shape):
    """Infer the shape of reshape."""
    shp = await shape['value']
    if shp == ANYTHING:
        shp_t = await shape['type']
        shp = (ANYTHING,) * len(shp_t.elements)
    v_shp = await v['shape']
    if (all(s is not ANYTHING for s in shp) and
        all(s is not ANYTHING for s in v_shp) and
            prod(shp) != prod(v_shp)):
        raise MyiaShapeError("Cannot change the total number of elements "
                             "in reshape")
    return shp


@shape_inferrer(P.dot, nargs=2)
async def infer_shape_dot(track, a, b):
    """Infer the shape of dot."""
    a_shp = await a['shape']
    b_shp = await b['shape']
    if len(a_shp) != 2 or len(b_shp) != 2:
        raise MyiaShapeError("dot needs matrix inputs")
    if (a_shp[1] != b_shp[0] and
            a_shp[1] is not ANYTHING and b_shp[0] is not ANYTHING):
        raise MyiaShapeError(
            f"Incompatible shapes in dot: {a_shp} and {b_shp}"
        )
    return (a_shp[0], b_shp[1])


@shape_inferrer(P.resolve, nargs=2)
async def infer_shape_resolve(track, data, item):
    """Infer the shape of resolve."""
    return await static_getter(track, data, item, lambda x, y: x[y])


@shape_inferrer(P.getattr, nargs=2)
async def infer_shape_getattr(track, data, item):
    """Infer the shape of getattr."""
    data_typ = await data['type']
    if ismyiatype(data_typ, Class):
        item_v = await item['value']
        if item_v is ANYTHING:
            raise InferenceError(
                "getattr with non-constant item")  # pragma: no cover
        if item_v in data_typ.attributes:
            data_sh = await data['shape']
            return data_sh.shape[item_v]
    return await static_getter(track, data, item, getattr)


@shape_inferrer(P.identity, nargs=1)
async def infer_shape_identity(track, x):
    """Infer the shape of identity."""
    return await x['shape']


@shape_inferrer(P.scalar_to_array, nargs=1)
async def infer_shape_scalar_to_array(track, x):
    """Infer the shape of scalar_to_array."""
    return ()
