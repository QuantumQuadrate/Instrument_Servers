from analogout import AnalogOutput
import pytest
import numpy as np


def test_wave_from_str():
    one_row = "1 2 3 4"
    assert np.allclose(np.array([1, 2, 3, 4]), AnalogOutput.wave_from_str(one_row))
    two_rows = "1 2 3 4\n5 6 7 8"
    assert np.allclose(np.array([[1, 2, 3, 4], [5, 6, 7, 8]]), AnalogOutput.wave_from_str(two_rows))

    empty_str = ""
    with pytest.raises(StopIteration):
        AnalogOutput.wave_from_str(empty_str)

    non_rectangular = "1 2 3 4\n5 6 7"
    with pytest.raises(ValueError, match="cannot copy sequence"):
        AnalogOutput.wave_from_str(non_rectangular)

    extra_space = "1 2 3 4\n 5 6 7 8"
    with pytest.raises(ValueError, match="cannot copy sequence"):
        AnalogOutput.wave_from_str(extra_space)

    non_numerics = "a e v 4\n1 2 3 b"
    with pytest.raises(ValueError, match="could not convert string to float"):
        AnalogOutput.wave_from_str(non_numerics)

