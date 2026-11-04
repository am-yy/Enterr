from types import SimpleNamespace

from execution.login.dom_interaction.dom_interaction_driver import _find_node_by_class


def _node(attributes=None, children=None, shadow_roots=None):
    return SimpleNamespace(attributes=attributes, children=children, shadow_roots=shadow_roots)


def test_find_node_by_class_searches_closed_shadow_roots():
    # Shape of the XewdyCaptcha widget as returned by DOM.getDocument(pierce=True).
    checkbox = _node(["class", "checkbox-box", "style", "border-color: red"])
    shadow_root = _node(children=[_node(["class", "checkbox-widget"], children=[checkbox])])
    widget = _node(["id", "challenge-widget"], shadow_roots=[shadow_root])
    document = _node(children=[_node(children=[_node(["class", "auth-form"]), widget])])

    assert _find_node_by_class(document, "checkbox-box") is checkbox
    assert _find_node_by_class(document, "checkbox") is None
