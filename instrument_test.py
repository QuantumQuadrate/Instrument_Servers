import pytest
from instrument import XMLLoader


def test_str_to_bool():
    assert XMLLoader.str_to_bool("True")
    assert XMLLoader.str_to_bool("true")
    assert XMLLoader.str_to_bool("tRuE")
    assert not XMLLoader.str_to_bool("False")
    assert not XMLLoader.str_to_bool("false")
    assert not XMLLoader.str_to_bool("fAlSe")
    with pytest.raises(ValueError, match="Expected a string 'true' or 'false' but received"):
        XMLLoader.str_to_bool("Failure!")


def test_int_from_str():
    assert XMLLoader.str_to_int('-4.50A') == -4
    assert XMLLoader.str_to_int('31415q') == 31415
    with pytest.raises(ValueError, match="non-numeric"):
        XMLLoader.str_to_int('ph7cy')