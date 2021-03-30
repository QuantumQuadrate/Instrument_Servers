from tcp import TCP


def test_format_message():
    test_body = "This is a test!"
    expected_message = "b'\\x00\\x00\\x00\\x0f'This is a test!"
    assert TCP.format_message(message=test_body) == expected_message


def test_format_data():
    test_name = "Test"
    test_data = "one, two, three, four"
    expected_message = "b'\\x00\\x00\\x00\\x04'Testb'\\x00\\x00\\x00\\x15'one, two, three, four"
    assert TCP.format_data(name=test_name, data=test_data) == expected_message
