import re

def format(format_string:str, data:dict):
    """
    Generates a string in the specified format using a format string and a data dictionary.

    This function extracts placeholder keys from the specified format string,
    applies the format by filtering only those keys that are present in the data dictionary.
    Even if a format specifier is included, it will be handled correctly.

    Arguments:: string
        format_string (str): The format specifier string. For example, “{key1}-{key2:08d}”.
        data (dict): A dictionary containing data to be used for formatting. Keys in the dictionary must correspond to
                     placeholders in the format string.

    Returns: str: the formatted string
        str: The formatted string.

    Example usage: str: formatted string.
        format_string = “{pc}-{note:08d}”
        data = {“pc”: 1, “note”: 123}
        result = format(format_string, data)
        print(result) # Output: '1-00000123'
    """

    # Extract only key names other than format specifiers
    keys_in_format  = re.findall(r'{(\w+)', format_string)

    # Make a dictionary with only the keys that are in the format string
    filtered = {key: data[key] for key in keys_in_format if key in data}

    return format_string.format(**filtered)
