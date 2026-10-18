"""The class check: the twin of access_layer.unknown_properties.

A model can invent a class (food:Recipe, food:Allergen) as easily as a
property. `python evaluate.py --add-class-check` loads it from this file;
access_layer.py carries the same check in CHECKS.
"""

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
