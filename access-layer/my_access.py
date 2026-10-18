"""Solution to part B, Y2. unknown_properties with three things changed."""

from access_layer import ul_terms


def unknown_classes(query, classes, props):
    """Problems: food: classes the query uses that the graph does not have."""

    known = {c.split("#")[1] for c in classes}

    used = {t for t in ul_terms(query) if t[0].isupper()}

    listed = ", ".join(sorted("food:" + k for k in known))

    return [
        f"food:{t} is not a class of this graph. The classes are: {listed}"
        for t in sorted(used - known)
    ]
