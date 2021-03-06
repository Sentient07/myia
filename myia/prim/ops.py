"""Primitive operations.

Primitive operations are handled as constants in the intermediate
representation, with the constant's value being an instance of a `Primitive`
subclass.

"""


from ..utils import Named


class Primitive(Named):
    """Base class for primitives."""


##############
# Arithmetic #
##############


scalar_add = Primitive('scalar_add')
scalar_sub = Primitive('scalar_sub')
scalar_mul = Primitive('scalar_mul')
scalar_div = Primitive('scalar_div')
scalar_mod = Primitive('scalar_mod')
scalar_pow = Primitive('scalar_pow')
scalar_uadd = Primitive('scalar_uadd')
scalar_usub = Primitive('scalar_usub')
scalar_exp = Primitive('scalar_exp')
scalar_log = Primitive('scalar_log')
scalar_sin = Primitive('scalar_sin')
scalar_cos = Primitive('scalar_cos')
scalar_tan = Primitive('scalar_tan')


###############
# Comparisons #
###############


scalar_eq = Primitive('scalar_eq')
scalar_lt = Primitive('scalar_lt')
scalar_gt = Primitive('scalar_gt')
scalar_ne = Primitive('scalar_ne')
scalar_le = Primitive('scalar_le')
scalar_ge = Primitive('scalar_ge')
bool_not = Primitive('bool_not')
bool_and = Primitive('bool_and')
bool_or = Primitive('bool_or')


######################
# Type introspection #
######################


typeof = Primitive('typeof')
hastype = Primitive('hastype')


###################
# Data structures #
###################


make_tuple = Primitive('make_tuple')
tail = Primitive('tail')
tuple_getitem = Primitive('tuple_getitem')
list_getitem = Primitive('list_getitem')
array_getitem = Primitive('array_getitem')
tuple_setitem = Primitive('tuple_setitem')
list_setitem = Primitive('list_setitem')
array_setitem = Primitive('array_setitem')
getattr = Primitive('getattr')
setattr = Primitive('setattr')
tuple_len = Primitive('tuple_len')
list_len = Primitive('list_len')
array_len = Primitive('array_len')


##########
# Arrays #
##########


scalar_to_array = Primitive('scalar_to_array')
broadcast_shape = Primitive('broadcast_shape')
shape = Primitive('shape')
array_map = Primitive('array_map')
array_scan = Primitive('array_scan')
array_reduce = Primitive('array_reduce')
distribute = Primitive('distribute')
reshape = Primitive('reshape')
dot = Primitive('dot')


##############
# Statements #
##############


if_ = Primitive('if')
switch = Primitive('switch')
return_ = Primitive('return')


#################
# Miscellaneous #
#################


scalar_cast = Primitive('scalar_cast')
list_map = Primitive('list_map')
identity = Primitive('identity')
resolve = Primitive('resolve')
partial = Primitive('partial')
make_record = Primitive('make_record')
