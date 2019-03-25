"""Small class to convert a JSON object/dictionary into an object

This module is for "formalising" JSON object into Python objects for referencing attributes with dot notation, rather
than index-lookups
"""

from pprint import pprint


class DictToObject:
    """Simple class to convert a dictionary to an object for more formal constants"""

    def __init__(self, d):
        self.json_obj: dict = d

        for k, v in d.items():
            if isinstance(v, (list, tuple)):
                setattr(self, k, [DictToObject(x) if isinstance(x, dict) else x for x in v])
            else:
                setattr(self, k, DictToObject(v) if isinstance(v, dict) else v)

    def __str__(self):
        pprint(self.json_obj)

    def json(self):
        """Get object as JSON

        Returns:
             JSON dictionary
        """
        return self.json_obj

    def keys(self):
        """Return list of object's keys

        Returns:
            list of keys
        """
        return list(self.json_obj.keys())

    def values(self):
        """Return list of object's values

        Returns:
            list of values
        """
        return list(self.json_obj.values())
