"""Unit tests for the JSONProcessor class."""

from __future__ import annotations

import math
from collections import defaultdict
from copy import deepcopy
from json import dumps, loads
from typing import Any, Callable, Iterator
from unittest.mock import call, patch

import pytest
from pydantic import computed_field
from requests_mock import NoMockAddress

from tests.conftest import ApiStubNotFoundError
from tests.unit.functions import (
    random_nested_json,
    random_nested_json_with_arrays,
)
from wg_utilities.clients.spotify import SpotifyClient, User
from wg_utilities.helpers.mixin.instance_cache import (
    CacheIdNotFoundError,
    InstanceCacheDuplicateError,
)
from wg_utilities.helpers.processor import JProc
from wg_utilities.helpers.processor.json import (
    Callback,
    CallbackNotDecoratedError,
    InvalidCallbackError,
    InvalidItemFilterError,
    MissingArgError,
    MissingKwargError,
)


def test_initialisation(mock_cb: Callback[..., Any]) -> None:
    """Test that the JSONProcessor is initialised correctly."""
    jproc = JProc()

    assert jproc.callback_mapping == {}
    assert isinstance(jproc.callback_mapping, defaultdict)

    assert jproc.identifier == hash(jproc)
    assert jproc.config.process_subclasses is True

    assert JProc(identifier="not_hash").identifier == "not_hash"
    assert JProc(process_subclasses=False).config.process_subclasses is False

    assert JProc({int: mock_cb}).callback_mapping == {
        int: [JProc.cb(mock_cb)],
    }


def test_callbacks_are_registered(
    mock_cb: Callback[..., Any],
    mock_cb_two: Callback[..., Any],
) -> None:
    """Test that callbacks are registered when the JSONProcessor is initialised."""
    with patch(
        "wg_utilities.helpers.processor.json.JSONProcessor.register_callback",
    ) as mock_register_callback:
        JProc(
            {
                str: mock_cb,
                set: JProc.cb(mock_cb),
                int: [mock_cb, mock_cb_two],
                float: {mock_cb, mock_cb_two, mock_cb},
                bool: [(mock_cb,)],
                None: {(mock_cb, mock_cb_two), (mock_cb_two, mock_cb)},
                dict: ((mock_cb, mock_cb_two, False), (mock_cb_two, mock_cb, True)),
                list: [
                    JProc.cb(mock_cb),
                    JProc.cb(mock_cb, mock_cb_two),
                    JProc.cb(mock_cb, mock_cb_two, allow_callback_failures=True),
                ],
                tuple: [
                    mock_cb,
                    (mock_cb,),
                    (mock_cb, mock_cb_two),
                    (mock_cb, mock_cb_two, True),
                    JProc.cb(mock_cb),
                    JProc.cb(mock_cb, mock_cb_two),
                    JProc.cb(mock_cb, mock_cb_two, allow_callback_failures=True),
                ],
            },
        )

    t_cb = JProc.cb(mock_cb)
    t_cb2 = JProc.cb(mock_cb_two)
    t_cb_cb2 = JProc.cb(mock_cb, mock_cb_two)
    t_cb2_cb = JProc.cb(mock_cb_two, mock_cb)
    t_cb_cb2_t = JProc.cb(mock_cb, mock_cb_two, allow_callback_failures=True)
    t_cb2_cb_t = JProc.cb(mock_cb_two, mock_cb, allow_callback_failures=True)

    assert sorted(mock_register_callback.call_args_list, key=str) == sorted(
        [
            call(str, t_cb),
            call(set, t_cb),
            call(int, t_cb),
            call(int, t_cb2),
            call(float, t_cb),
            call(float, t_cb2),
            call(bool, t_cb),
            call(None, t_cb_cb2),
            call(None, t_cb2_cb),
            call(dict, t_cb_cb2),
            call(dict, t_cb2_cb_t),
            call(list, t_cb),
            call(list, t_cb_cb2),
            call(list, t_cb_cb2_t),
            call(tuple, t_cb),
            call(tuple, t_cb),
            call(tuple, t_cb_cb2),
            call(tuple, t_cb_cb2_t),
            call(tuple, t_cb),
            call(tuple, t_cb_cb2),
            call(tuple, t_cb_cb2_t),
        ],
        key=str,
    )


@pytest.mark.parametrize(
    ("callbacks", "exc_args"),
    [
        (123456789, (123456789, int)),
        ([987654321, 123456789], (987654321, int)),
    ],
)
def test_invalid_callback_parameters(
    callbacks: Callback[..., Any],
    exc_args: tuple[Any, ...],
) -> None:
    """Test that invalid callback parameters raise the correct error."""

    with pytest.raises(InvalidCallbackError) as exc_info:
        JProc({str: callbacks})

    assert exc_info.value.args == exc_args


def test_iterator() -> None:
    """Test the `_iterate` method returns the correct values."""

    assert isinstance(JProc()._iterate(["a", "b", "c"]), Iterator)
    assert list(JProc()._iterate(["a", "b", "c"])) == [0, 1, 2]

    assert isinstance(JProc()._iterate({"a": "b", "c": "d"}), Iterator)
    assert list(JProc()._iterate({"a": "b", "c": "d"})) == ["a", "c"]


def test_get_callbacks(
    mock_cb: Callback[..., Any],
    mock_cb_two: Callback[..., Any],
    mock_cb_three: Callback[..., Any],
    mock_cb_four: Callback[..., Any],
) -> None:
    """Test that the `_get_callbacks` method works correctly, including yielding subclasses."""

    jproc = JProc(
        {
            str: mock_cb,
            int: mock_cb_two,
            object: mock_cb_three,
            bool: [mock_cb_two, mock_cb_four],
        },
    )

    jp1 = JProc.cb(mock_cb)
    jp2 = JProc.cb(mock_cb_two)
    jp3 = JProc.cb(mock_cb_three)
    jp4 = JProc.cb(mock_cb_four)

    assert list(jproc._get_callbacks(str)) == [jp1, jp3]
    assert list(jproc._get_callbacks(int)) == [jp2, jp3]
    assert list(jproc._get_callbacks(object)) == [jp3]
    assert list(jproc._get_callbacks(bool)) == [
        jp2,  # Because it is a subclass of int
        jp3,  # Because it is a subclass of object
        jp2,  # (again); Because it is a bool (pt. 1)
        jp4,  # Because it is a bool (pt. 2)
    ]


def test_get_callbacks_no_subclasses(
    mock_cb: Callback[..., Any],
    mock_cb_two: Callback[..., Any],
    mock_cb_three: Callback[..., Any],
    mock_cb_four: Callback[..., Any],
) -> None:
    """Test that the `_get_callbacks` method works correctly, excluding yielding subclasses."""

    jproc = JProc(
        {
            str: mock_cb,
            int: mock_cb_two,
            object: mock_cb_three,
            bool: [mock_cb_two, mock_cb_four],
        },
        process_subclasses=False,
    )

    jp1 = JProc.cb(mock_cb)
    jp2 = JProc.cb(mock_cb_two)
    jp3 = JProc.cb(mock_cb_three)
    jp4 = JProc.cb(mock_cb_four)

    assert list(jproc._get_callbacks(str)) == [jp1]
    assert list(jproc._get_callbacks(int)) == [jp2]
    assert list(jproc._get_callbacks(object)) == [jp3]
    assert list(jproc._get_callbacks(bool)) == [jp2, jp4]


@pytest.mark.parametrize(
    (
        "obj",
        "callback_mapping",
        "process_subclasses",
        "process_type_changes",
        "expected",
    ),
    [
        pytest.param(
            {
                "key": "value",
                "key2": "value2",
                "key3": 3,
            },
            {str: lambda _test_process__value: _test_process__value.upper()},
            True,
            True,
            {
                "key": "VALUE",
                "key2": "VALUE2",
                "key3": 3,
            },
            id="single_level_dict_str_to_upper",
        ),
        pytest.param(
            {
                "key": "value",
                "key2": b"value2",
                "key3": 3,
            },
            {bytes: lambda _test_process__value: _test_process__value.decode().upper()},
            True,
            True,
            {
                "key": "value",
                "key2": "VALUE2",
                "key3": 3,
            },
            id="single_level_dict_bytes_to_upper",
        ),
        pytest.param(
            {
                "key": "value",
                "key2": b"value2",
                "key3": {
                    "key": b"value",
                    "key2": b"value2",
                    "key3": 3,
                },
            },
            {
                str: lambda _test_process__value: _test_process__value.upper(),
                bytes: lambda _test_process__value: _test_process__value.decode(),
            },
            True,
            True,
            {
                "key": "VALUE",
                "key2": "VALUE2",
                "key3": {
                    "key": "VALUE",
                    "key2": "VALUE2",
                    "key3": 3,
                },
            },
            id="nested_dict_str_bytes_to_upper",
        ),
        pytest.param(
            {
                "key": "value",
                "key2": b"value2",
                "key3": {
                    "key": b"value",
                    "key2": b"value2",
                    "key3": 3,
                },
            },
            {
                str: lambda _test_process__value: _test_process__value.upper(),
                bytes: lambda _test_process__value: _test_process__value.decode(),
            },
            True,
            False,
            {
                "key": "VALUE",
                "key2": "value2",
                "key3": {
                    "key": "value",
                    "key2": "value2",
                    "key3": 3,
                },
            },
            id="nested_dict_str_bytes_to_upper_no_type_changes",
        ),
        pytest.param(
            {
                "key": "value",
                "key2": b"value2",
                "key3": [
                    {
                        "key": "value",
                        "key2": b"value2",
                        "key3": 56,
                    },
                    {
                        "key": b"value",
                        "key2": "value2",
                        "key3": {
                            "key": b"value",
                            "key2": "value2",
                            "key3": 3,
                        },
                    },
                ],
            },
            {
                str: lambda _test_process__value: _test_process__value.upper(),
                bytes: lambda _test_process__value: _test_process__value.decode(),
            },
            True,
            True,
            {
                "key": "VALUE",
                "key2": "VALUE2",
                "key3": [
                    {
                        "key": "VALUE",
                        "key2": "VALUE2",
                        "key3": 56,
                    },
                    {
                        "key": "VALUE",
                        "key2": "VALUE2",
                        "key3": {
                            "key": "VALUE",
                            "key2": "VALUE2",
                            "key3": 3,
                        },
                    },
                ],
            },
            id="nested_dict_with_list_str_bytes_to_upper",
        ),
        pytest.param(
            random_nested_json(),
            {
                bool: lambda _test_process__value: str(_test_process__value)[
                    ::-1
                ].upper(),
            },
            True,
            True,
            loads(
                dumps(random_nested_json())
                .replace("true", '"EURT"')
                .replace("false", '"ESLAF"'),
            ),
            id="random_nested_json_bool_to_reverse_upper",
        ),
        pytest.param(
            random_nested_json_with_arrays(),
            {
                bool: lambda _test_process__value: str(_test_process__value)[
                    ::-1
                ].upper(),
            },
            True,
            True,
            loads(
                dumps(random_nested_json_with_arrays())
                .replace("true", '"EURT"')
                .replace("false", '"ESLAF"'),
            ),
            id="random_nested_json_with_arrays_bool_to_reverse_upper",
        ),
    ],
)
def test_process(
    obj: dict[Any, Any],
    callback_mapping: dict[type[Any], Callable[..., Any]],
    process_subclasses: bool,
    process_type_changes: bool,
    expected: dict[Any, Any],
    wrap: Callable[[Callable[..., Any]], Callback[..., Any]],
) -> None:
    """Test that the `process` method works correctly."""

    jproc = JProc(
        {k: wrap(v) for k, v in callback_mapping.items()},
        process_subclasses=process_subclasses,
        process_type_changes=process_type_changes,
    )

    output = deepcopy(obj)

    jproc.process(output)

    assert output != obj
    assert output == expected


@pytest.mark.parametrize(
    ("obj", "loc"),
    [
        ({"a": "b", "c": "d"}, "e"),
        ([0, 1, 2], 3),
        ({"a": "b", "c": "d"}, 0),
        ([0, 1, 2], "a"),
    ],
)
def test_process_loc_invalid_loc(
    obj: dict[Any, Any] | list[Any],
    loc: Any | int,
) -> None:
    """Test that the `_process_loc` method doesn't raise an error when given an invalid location."""

    # Confirm it's an invalid location
    with pytest.raises((LookupError, TypeError)):
        obj[loc]

    jproc = JProc()

    # Shouldn't raise an error
    jproc._process_loc(obj=obj, loc=loc, kwargs={}, depth=0)


def test_allow_failures(
    wrap: Callable[[Callable[..., Any]], Callback[..., Any]],
) -> None:
    """Test that exceptions are only thrown when `allow_failures` is False for a given callback."""

    jproc_strict = JProc(
        {
            str: JProc.cb(
                wrap(lambda x: x.upper()),
                allow_callback_failures=False,
            ),
            int: JProc.cb(
                wrap(lambda x: x.upper()),
                allow_callback_failures=False,
            ),
        },
    )

    jproc_lax = JProc(
        {
            str: JProc.cb(wrap(lambda x: x.upper()), allow_callback_failures=True),
            int: JProc.cb(wrap(lambda x: x.upper()), allow_callback_failures=True),
        },
    )

    obj = {"a": "b", "c": "d", "e": 3, "f": "g", "h": 5}

    strict_obj = deepcopy(obj)
    lax_obj = deepcopy(obj)

    with pytest.raises(AttributeError):
        jproc_strict.process(strict_obj)

    assert strict_obj == {"a": "B", "c": "D", "e": 3, "f": "g", "h": 5}

    jproc_lax.process(lax_obj)

    assert lax_obj == {"a": "B", "c": "D", "e": 3, "f": "G", "h": 5}


def test_processing_type_changes(
    wrap: Callable[[Callable[..., Any]], Callback[..., Any]],
) -> None:
    """Test that values which change type can be re-processed."""

    orig_obj = {"a": "1", "b": 2, "c": "3"}

    type_changed_obj = deepcopy(orig_obj)
    no_type_changed_obj = deepcopy(orig_obj)

    jproc = JProc(
        {
            int: JProc.cb(wrap(lambda x: x * 2)),
            str: JProc.cb(wrap(lambda x: int(x))),
        },
        process_type_changes=True,
    )

    jproc.process(type_changed_obj)
    jproc.config.process_type_changes = False
    jproc.process(no_type_changed_obj)

    assert type_changed_obj == {"a": 2, "b": 4, "c": 6}
    assert no_type_changed_obj == {"a": 1, "b": 4, "c": 3}


def test_lambdas_get_wrapped() -> None:
    """Test that a lambda is automatically "decorated" (wrapped) when registered."""

    obj = {"a": "b", "c": "d"}

    JProc(
        {
            str: lambda _value_, arg, /, *, kwarg: _value_.upper() + arg + kwarg,  # type: ignore[misc]
        },
    ).process(
        obj,
        arg="arg",
        discarded_arg="discarded_arg",
        kwarg="kwarg",
        discarded_kwarg="discarded_kwarg",
    )

    assert obj == {"a": "Bargkwarg", "c": "Dargkwarg"}


def test_callback_with_no_args_or_kwargs() -> None:
    """Test that a callback with no args is perfectly fine."""

    @JProc.callback()
    def _my_callback() -> Any:
        """Null callback."""

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    JProc({str: _my_callback}).process(obj)

    assert obj == {"a": None, "c": {"d": None, "f": None}}


def test_undecorated_callbacks_throw_error() -> None:
    """Test that registering a non-decorated callback will throw an error."""

    def _my_callback() -> Any:
        """Null callback."""

    with pytest.raises(CallbackNotDecoratedError) as exc_info:
        JProc().register_callback(str, JProc.cb(_my_callback))

    assert exc_info.value.callback is _my_callback


def test_invalid_item_filter(mock_cb: Callback[..., Any]) -> None:
    """Test that item filters must be callable."""

    with pytest.raises(InvalidItemFilterError) as exc_info:
        JProc.cb(mock_cb, item_filter="not_callable")  # type: ignore[arg-type]

    assert exc_info.value.item_filter == "not_callable"


def test_invalid_allow_callback_failures(mock_cb: Callback[..., Any]) -> None:
    """Test that `allow_callback_failures` must be a bool."""

    with pytest.raises(InvalidCallbackError) as exc_info:
        JProc.cb(mock_cb, allow_callback_failures="not_bool")  # type: ignore[arg-type]

    assert exc_info.value.args == ("not_bool", str)


def test_none_as_target_type(
    wrap: Callable[[Callable[..., Any]], Callback[..., Any]],
) -> None:
    """Test that `None` is handled correctly when used as a target type."""

    cb_def = JProc.cb(wrap(lambda x: x))

    jproc = JProc()

    assert not jproc.callback_mapping

    jproc.register_callback(None, cb_def)

    assert len(jproc.callback_mapping) == 1
    assert None not in jproc.callback_mapping
    assert jproc.callback_mapping[type(None)] == [cb_def]

    # Confirm that if the user provides `type(None)` upfront no conversion is made

    jproc2 = JProc({type(None): cb_def})
    assert len(jproc2.callback_mapping) == 1
    assert None not in jproc2.callback_mapping
    assert jproc2.callback_mapping[type(None)] == [cb_def]


def test_callback_decorator_cache() -> None:
    """Test that the callback decorator stores the callback correctly."""

    assert not JProc._DECORATED_CALLBACKS

    @JProc.callback()
    def my_callback(my_custom_kwarg: float) -> float:  # pragma: no cover
        return my_custom_kwarg * 2

    assert {my_callback} == JProc._DECORATED_CALLBACKS

    @JProc.callback()
    def my_second_callback(my_custom_kwarg: float) -> float:  # pragma: no cover
        return my_custom_kwarg * 2

    assert {my_callback, my_second_callback} == JProc._DECORATED_CALLBACKS


def test_args_and_kwargs_passthrough() -> None:
    """Test that args and kwargs are passed through to the callback correctly."""

    @JProc.callback()
    def _my_callback(
        _value_: Any,
        _loc_: Any,
        _obj_type_: Any,
        arg1: Any,
        /,
        arg2: Any,
        kwarg1: Any = "kwarg1_default",
        *,
        kwarg2: Any = "kwarg2_default",
        calls: list[tuple[Any, Any, Any, Any, Any, Any, Any]],
    ) -> Any:
        calls.append((_value_, _loc_, _obj_type_, arg1, arg2, kwarg1, kwarg2))

        return _value_.upper()

    calls: list[tuple[str, str, type[Any], str, str, str, str]] = []

    jproc = JProc({str: _my_callback})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(obj, arg1="arg1", arg2="arg2", kwarg2="kwarg2", calls=calls)

    assert calls == [
        ("b", "a", dict, "arg1", "arg2", "kwarg1_default", "kwarg2"),
        ("e", "d", dict, "arg1", "arg2", "kwarg1_default", "kwarg2"),
        ("g", "f", dict, "arg1", "arg2", "kwarg1_default", "kwarg2"),
    ]
    assert obj == {"a": "B", "c": {"d": "E", "f": "G"}}


def test_invalid_classmethod_callbacks() -> None:
    """Test that invalid classmethod decoration throws the correct error."""

    with pytest.raises(InvalidCallbackError) as exc_info:

        class MyClass:
            @JProc.callback()
            @classmethod
            def _my_classmethod_callback(cls) -> None:
                """Incorrectly decorated callback."""

    assert (
        exc_info.value.callback.__qualname__
        == "test_invalid_classmethod_callbacks.<locals>.MyClass._my_classmethod_callback"
    )
    assert (
        str(exc_info.value) == "@JSONProcessor.callback must be used _after_ @classmethod"
    )


def test_classmethod_decoration() -> None:
    """Test that classmethod callbacks are processed correctly."""

    class MyClass:
        @classmethod
        @JProc.callback()
        def _my_classmethod_callback(
            cls,
            _value_: str,
            arg1: Any,
            *,
            kwarg1: Any = None,
            kwarg3: Any,
        ) -> Any:
            assert cls is MyClass
            return _value_ + arg1 + kwarg1 + kwarg3 + cls.__name__

    jproc = JProc({str: MyClass._my_classmethod_callback})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(obj, arg1="a", kwarg1="b", kwarg3="c")

    assert obj == {"a": "babcMyClass", "c": {"d": "eabcMyClass", "f": "gabcMyClass"}}


def test_method_not_decorated() -> None:
    """Test that a method which isn't decorated throws the correct error."""

    class MyClass:
        @classmethod
        def _my_classmethod_callback(cls) -> None:
            """Not-decorated callback."""

        @staticmethod
        def _my_staticmethod_callback() -> None:
            """Not-decorated callback."""

        def _my_instance_method_callback(self) -> None:
            """Not-decorated callback."""

    with pytest.raises(CallbackNotDecoratedError):
        JProc({str: MyClass._my_classmethod_callback})

    with pytest.raises(CallbackNotDecoratedError):
        JProc({str: MyClass._my_staticmethod_callback})

    with pytest.raises(CallbackNotDecoratedError):
        JProc({str: MyClass()._my_instance_method_callback})


def test_staticmethod_callbacks() -> None:
    """Test that staticmethod callbacks are processed correctly."""

    class MyClass:
        @staticmethod
        @JProc.callback()
        def _my_staticmethod_callback(
            _value_: Any,
            arg1: Any,
            *,
            kwarg1: Any = None,
            kwarg3: Any,
        ) -> Any:
            return _value_ + arg1 + kwarg1 + kwarg3

    jproc = JProc({str: MyClass._my_staticmethod_callback})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(obj, arg1="a", kwarg1="b", kwarg3="c")

    assert obj == {"a": "babc", "c": {"d": "eabc", "f": "gabc"}}


def test_instance_method_callbacks() -> None:
    """Test that instance method callbacks are processed correctly."""

    class MyClass:
        @JProc.callback()
        def _my_instance_method_callback(
            self,
            _value_: Any,
            arg1: Any,
            *,
            kwarg1: Any = None,
            kwarg3: Any,
        ) -> Any:
            return _value_ + arg1 + kwarg1 + kwarg3 + str(self)

    my_instance = MyClass()

    jproc = JProc({str: my_instance._my_instance_method_callback})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(obj, arg1="a", kwarg1="b", kwarg3="c")

    assert obj == {
        "a": f"babc{my_instance}",
        "c": {"d": f"eabc{my_instance}", "f": f"gabc{my_instance}"},
    }


def test_name_unmangling_function() -> None:
    """Test name-mangled function kw/args are still processed correctly."""

    @JProc.callback()  # type: ignore[arg-type]
    def _my_callback_function(
        __mangled_pos_only: Any,
        /,
        __mangled_any: Any,
        *,
        __mangled_kwarg: Any,
    ) -> Any:
        return __mangled_pos_only + __mangled_any + __mangled_kwarg

    jproc = JProc({str: _my_callback_function})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(obj, __mangled_pos_only="a", __mangled_any="b", __mangled_kwarg="c")

    assert obj == {"a": "abc", "c": {"d": "abc", "f": "abc"}}


def test_name_unmangling_method() -> None:
    """Test name-mangled function kw/args are still processed correctly."""

    class MyClass:
        @JProc.callback()  # type: ignore[arg-type]
        def _my_instance_method_callback(
            self,
            __mangled_pos_only: Any,
            /,
            __mangled_any: Any,
            *,
            __mangled_kwarg: Any,
        ) -> Any:
            return __mangled_pos_only + __mangled_any + __mangled_kwarg

    jproc = JProc({str: MyClass()._my_instance_method_callback})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(
        obj,
        _MyClass__mangled_pos_only="a",
        _MyClass__mangled_any="b",
        _MyClass__mangled_kwarg="c",
    )

    assert obj == {"a": "abc", "c": {"d": "abc", "f": "abc"}}


def test_mangled_method() -> None:
    """Test that mangled methods are processed correctly."""

    class MyClass:
        @JProc.callback()
        def __my_mangled_method(
            self,
            _value_: Any,
            arg1: Any,
            *,
            kwarg1: Any = None,
            kwarg3: Any,
        ) -> Any:
            return _value_ + arg1 + kwarg1 + kwarg3

    my_instance = MyClass()

    jproc = JProc({str: my_instance._MyClass__my_mangled_method})  # type: ignore[attr-defined]

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(obj, arg1="a", kwarg1="b", kwarg3="c")

    assert obj == {"a": "babc", "c": {"d": "eabc", "f": "gabc"}}


def test_missing_args_and_kwargs() -> None:
    """Test that the correct error is thrown when a required kwarg is missing."""

    @JProc.callback()
    def _my_callback(arg: Any, /, either: Any, *, kwarg: Any) -> None:
        """Callback which throws a "natural" TypeError."""
        _ = arg, either, kwarg

        _ = "hello" * "world"  # type: ignore[operator]

    jproc = JProc({str: _my_callback})

    obj = {"a": "b"}

    with pytest.raises(MissingArgError):
        jproc.process(obj, arg=1, kwarg=1)

    with pytest.raises(MissingArgError):
        jproc.process(obj, either=1, kwarg=1)

    with pytest.raises(MissingKwargError):
        jproc.process(obj, arg=1, either=1)

    with pytest.raises(
        TypeError,
        match="can't multiply sequence by non-int of type 'str'",
    ):
        # Extra kw/args will be filtered out
        jproc.process(obj, arg=1, arg2=2, either=1, kwarg=1, kwarg2=2)


def test_instance_caching() -> None:
    """Test that JProcs are cached correctly."""

    jproc1 = JProc(identifier="one")

    with pytest.raises(InstanceCacheDuplicateError):
        JProc(identifier="one")

    assert JProc.from_cache("one") is jproc1

    with pytest.raises(CacheIdNotFoundError):
        JProc.from_cache("two")


def test_non_mutating_callbacks() -> None:
    """Test that non-mutating callbacks do not edit the value in the object."""

    @JProc.callback(allow_mutation=False)
    def _my_callback(arg: Any, /, *, kwarg: Any, calls: list[Any]) -> Any:
        calls.append((arg, kwarg))
        return math.pi  # Shouldn't have any effect

    calls: list[tuple[str, str]] = []

    jproc = JProc({str: _my_callback})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    jproc.process(obj, arg="arg", kwarg="kwarg", calls=calls)

    assert calls == [
        ("arg", "kwarg"),
        ("arg", "kwarg"),
        ("arg", "kwarg"),
    ]

    assert obj == {"a": "b", "c": {"d": "e", "f": "g"}}


def test_non_mutating_lambda_callbacks() -> None:
    """Test that non-mutating lambdas do not edit the value in the object."""

    jproc = JProc(
        {
            str: JProc.cb(
                lambda a, *, k, calls: calls.append((a, k)),  # type: ignore[misc]
                allow_mutation=False,
            ),
        },
    )

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    calls: list[tuple[str, str]] = []
    jproc.process(obj, a="arg", k="kwarg", calls=calls)

    assert calls == [
        ("arg", "kwarg"),
        ("arg", "kwarg"),
        ("arg", "kwarg"),
    ]

    assert obj == {"a": "b", "c": {"d": "e", "f": "g"}}


def test_non_mutating_advanced() -> None:
    """Test that non-mutating callbacks can still edit objects in place."""

    @JProc.callback(allow_mutation=False)
    def _my_callback(_value_: dict[str, Any], calls: list[Any]) -> Any:
        _value_["newKey"] = "newValue"
        calls.append(_value_)

    jproc = JProc({dict: _my_callback})

    obj = {"a": "b", "c": {"d": "e", "f": "g"}}

    calls: list[Any] = []
    jproc.process(obj, arg="arg", kwarg=obj, calls=calls)

    assert calls == [{"d": "e", "f": "g", "newKey": "newValue"}]

    assert obj == {"a": "b", "c": {"d": "e", "f": "g", "newKey": "newValue"}}


class _UserWithComputedFields(User):
    @computed_field  # type: ignore[misc]
    @property
    def _my_computed_field(self) -> str:
        return self.name + "computed_field"


@pytest.mark.usefixtures("modify_base_model_config")
def test_pydantic_models_can_be_processed(
    spotify_client: SpotifyClient,
    spotify_user: User,
) -> None:
    """Test that Pydantic models can be parsed and traversed."""
    spotify_client.log_requests = False

    @JProc.callback(allow_mutation=False)
    def _my_callback(
        _value_: str,
        _loc_: Any,
        _obj_type_: type[Any],
        calls: list[Any],
    ) -> Any:
        calls.append((_value_, _loc_, _obj_type_))

    tt, tf, ft, ff = (1, 1), (1, 0), (0, 1), (0, 0)

    jprocs: dict[tuple[int, int], JProc] = {}
    calls: dict[Any, Any] = {}

    computed_user = _UserWithComputedFields.model_validate(
        {"spotify_client": spotify_client, **spotify_user.model_dump()},
    )

    for ppcf, ppmp in [tt, tf, ft, ff]:
        jprocs[(ppcf, ppmp)] = JProc(
            {str: JProc.cb(_my_callback, allow_callback_failures=True)},
            process_pydantic_computed_fields=ppcf,  # type: ignore[arg-type]
            process_pydantic_model_properties=ppmp,  # type: ignore[arg-type]
            ignored_loc_lookup_errors=(ApiStubNotFoundError, NoMockAddress),
        )

        calls[(ppcf, ppmp)] = []

    jprocs[ff].process_model(computed_user, calls=calls[ff])

    assert len(calls[ff]) == 18  # Control

    jprocs[tf].process_model(computed_user, calls=calls[tf])

    assert calls[tf] == calls[ff] + [
        ("Will Garsidecomputed_field", "_my_computed_field", _UserWithComputedFields),
    ]

    jprocs[ft].process_model(computed_user, calls=calls[ft])

    assert len(calls[ft]) == 213843

    jprocs[tt].process_model(computed_user, calls=calls[tt])

    assert calls[tt] == calls[ft] + [
        ("Will Garsidecomputed_field", "_my_computed_field", _UserWithComputedFields),
    ]


@pytest.mark.usefixtures("modify_base_model_config")
def test_pydantic_models_can_be_mutated(
    spotify_client: SpotifyClient,
    spotify_user: User,
) -> None:
    """Test that Pydantic models can be mutated."""
    spotify_client.log_requests = False

    jproc = JProc({str: JProc.cb(lambda _value_: _value_.upper())})  # type: ignore[misc]

    computed_user = _UserWithComputedFields.model_validate(
        {"spotify_client": spotify_client, **spotify_user.model_dump()},
    )

    jproc.process_model(computed_user)

    assert computed_user.spotify_client == spotify_client
    assert computed_user.name == "WILL GARSIDE"
    assert computed_user._my_computed_field == "WILL GARSIDEcomputed_field"


def test_set_item_setatrr_non_str() -> None:
    """Test that `setattr` isn't called for a non-str loc value."""

    jproc = JProc()

    assert jproc._set_item(int, 123, 456) is None  # type: ignore[arg-type]


def test_type_errors_still_get_raised() -> None:
    """Test that type errors still get raised when they should."""

    jproc = JProc()

    with pytest.raises(TypeError):
        jproc._get_item(int, 123)  # type: ignore[arg-type]


def test_depth_variable() -> None:
    """Test that the depth variable is set correctly."""

    obj = {
        "a": "b",
        "c": {
            "d": "e",
            "f": "g",
            "h": {
                "i": "j",
                "k": "l",
                "m": {
                    "n": "o",
                    "p": "q",
                },
            },
        },
    }

    expected_calls = [
        ("b", "a", dict, 0),
        ("e", "d", dict, 1),
        ("g", "f", dict, 1),
        ("j", "i", dict, 2),
        ("l", "k", dict, 2),
        ("o", "n", dict, 3),
        ("q", "p", dict, 3),
    ]

    @JProc.callback(allow_mutation=False)
    def _cb(
        _value_: str,
        _loc_: str,
        _obj_type_: type[Any],
        _depth_: int,
    ) -> None:
        nonlocal expected_calls
        assert expected_calls.pop(0) == (_value_, _loc_, _obj_type_, _depth_)

    jproc = JProc({str: _cb})

    jproc.process(obj)

    assert not expected_calls
