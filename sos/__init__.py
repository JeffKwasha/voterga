
def property_dict(**kwargs):
    """ returns the properties from an xml_to_dict """
    rv = {}
    if not kwargs:
        return rv

    for k, v in kwargs.items():
        if k.startswith('@'):
            rv[k[1:]] = v
    return rv