import numpy as np
import struct
import pytest
from hamamatsu import u16_ar_to_bytes


def test_u16_ar_to_bytes():
    for trial in range(10):
        random_arr = np.random.randint(0, 65535, size=(100,), dtype=np.uint16)
        mess = u16_ar_to_bytes(random_arr)
        # Equivalent code is used to parse the message on the CsPy side
        parsed_arr = np.array(struct.unpack(f'!{int(len(mess)/2)}H', mess), dtype=np.uint16)
        assert np.allclose(random_arr, parsed_arr)

    with pytest.raises(TypeError, match="only integer scalar arrays can be converted"):
        bad_shape = random_arr.reshape((100, 1))
        u16_ar_to_bytes(bad_shape)
