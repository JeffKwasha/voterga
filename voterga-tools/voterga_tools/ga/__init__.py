# this module handles data from the Georgia Secretary of State website(s)
# 1 - the official xml detailed election results
# 2 ...


def property_dict(**kwargs):
    """ returns the properties from an xml_to_dict 
        { "@property": value, "other": value }
    """
    rv = {}
    if not kwargs:
        return rv

    for k, v in kwargs.items():
        if k.startswith('@'):
            rv[k[1:]] = v
    return rv