import pytest
import instrumentfuncs


def test_str_to_bool():
    assert instrumentfuncs.str_to_bool("True")
    assert instrumentfuncs.str_to_bool("true")
    assert instrumentfuncs.str_to_bool("tRuE")
    assert not instrumentfuncs.str_to_bool("False")
    assert not instrumentfuncs.str_to_bool("false")
    assert not instrumentfuncs.str_to_bool("fAlSe")
    with pytest.raises(ValueError, match="Expected a string 'true' or 'false' but received"):
        instrumentfuncs.str_to_bool("Failure!")


def test_int_from_str():
    assert instrumentfuncs.int_from_str('-4.50A') == -4
    assert instrumentfuncs.int_from_str('31415q') == 31415
    with pytest.raises(ValueError, match="non-numeric"):
        instrumentfuncs.int_from_str('ph7cy')