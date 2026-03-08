"""
    Generic class parameter handling

    If a subclass has a class member `Parameters` declared as a `dataclass`,
    then it will be scanned for attributes and types.
    The class will have a member variable `self._parameters` added,
    and a method `update_parameters(**kwargs)`.

"""

from dataclasses import dataclass, fields, is_dataclass


class Parameterized:

    def __init__(self):
        P = type(self).Parameters
        assert is_dataclass(P)
        self._parameters = P()

    def update_parameters(self, **kwargs):
        """returns self so this method can be chained"""
        P = type(self).Parameters
        for (k, v) in kwargs.items():
            field_finder = (f for f in fields(P) if f.name == k)
            try:
                field = next(field_finder)
            except StopIteration:
                raise TypeError(f'{P} has no field {k!r}')
            value = field.type(v)
            setattr(self._parameters, k, value)
        return self


# Unit Test

class Test(Parameterized):
    @dataclass
    class Parameters:
        speed: float = 1.5
        is_happy: bool = True

t = Test()
assert t._parameters.speed == 1.5
assert t._parameters.is_happy is True

t.update_parameters(speed=7, is_happy=False)
assert type(t._parameters.speed) is float
assert t._parameters.speed == 7.0
assert t._parameters.is_happy is False

t.update_parameters(is_happy=Test)  # truthy enough
assert t._parameters.is_happy is True

try:
    t.update_parameters(is_grumpy=True)
    assert False, 'allowed nonexistent field'
except TypeError as x:
    import re
    assert re.match(
        r"<class .*Test\.Parameters'> has no field 'is_grumpy'",
        str(x),
    )

try:
    t.update_parameters(speed=Test)
    assert False, 'allowed bad type'
except TypeError as x:
    pass
