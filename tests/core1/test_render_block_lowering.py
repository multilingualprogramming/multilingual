"""Test semantic IR lowering for RenderBlock and UIElement."""

# pylint: disable=protected-access

from multilingualprogramming.core import ir_nodes as ir
from multilingualprogramming.core.semantic_lowering import SemanticLowering


def test_render_block_lowering_exists():
    """SemanticLowering has _lower_RenderBlock method."""
    lowering = SemanticLowering()
    assert hasattr(lowering, "_lower_RenderBlock")
    assert callable(lowering._lower_RenderBlock)


def test_ui_element_lowering_exists():
    """SemanticLowering has _lower_UIElement method."""
    lowering = SemanticLowering()
    assert hasattr(lowering, "_lower_UIElement")
    assert callable(lowering._lower_UIElement)


def test_ir_ui_element_node_exists():
    """IRUIElement node class exists in ir_nodes."""
    assert hasattr(ir, "IRUIElement")
    elem = ir.IRUIElement(tag="div")
    assert elem.tag == "div"
    assert not elem.children
    assert not elem.attributes


def test_ir_ui_attribute_node_exists():
    """IRUIAttribute node class exists in ir_nodes."""
    assert hasattr(ir, "IRUIAttribute")
    attr = ir.IRUIAttribute(name="class", value=ir.IRLiteral(value="active", kind="string"))
    assert attr.name == "class"
    assert not attr.is_class_binding
    assert not attr.is_event_handler


def test_ir_render_block_node_exists():
    """IRRenderBlock node class exists in ir_nodes."""
    assert hasattr(ir, "IRRenderBlock")
    block = ir.IRRenderBlock()
    assert block.root is None


def test_ir_ui_element_with_attributes():
    """IRUIElement can hold attributes."""
    attr1 = ir.IRUIAttribute(name="class", value=ir.IRLiteral(value="btn", kind="string"))
    attr2 = ir.IRUIAttribute(
        name="onclick",
        value=ir.IRIdentifier(name="handle_click"),
        is_event_handler=True,
    )
    elem = ir.IRUIElement(tag="button", attributes=[attr1, attr2])
    assert len(elem.attributes) == 2
    assert elem.attributes[0].name == "class"
    assert elem.attributes[1].is_event_handler


def test_ir_ui_element_with_children():
    """IRUIElement can hold children."""
    child1 = ir.IRUIElement(tag="span")
    child2 = ir.IRUIElement(tag="p")
    parent = ir.IRUIElement(tag="div", children=[child1, child2])
    assert len(parent.children) == 2
    assert parent.children[0].tag == "span"


def test_ir_ui_element_with_condition():
    """IRUIElement can have condition."""
    cond = ir.IRBinaryOp(
        left=ir.IRIdentifier(name="x"),
        op="==",
        right=ir.IRLiteral(value=1, kind="int"),
    )
    elem = ir.IRUIElement(tag="div", condition=cond)
    assert elem.condition is not None
    assert isinstance(elem.condition, ir.IRBinaryOp)


def test_ir_render_block_with_root():
    """IRRenderBlock can have root element."""
    root = ir.IRUIElement(tag="div")
    block = ir.IRRenderBlock(root=root)
    assert block.root is not None
    assert block.root.tag == "div"


def test_class_binding_attribute():
    """IRUIAttribute can mark class bindings."""
    attr = ir.IRUIAttribute(
        name="class:active",
        value=ir.IRIdentifier(name="is_active"),
        is_class_binding=True,
    )
    assert attr.is_class_binding
    assert not attr.is_event_handler


def test_event_handler_attribute():
    """IRUIAttribute can mark event handlers."""
    attr = ir.IRUIAttribute(
        name="onclick",
        value=ir.IRCallExpr(func=ir.IRIdentifier(name="handle_click")),
        is_event_handler=True,
    )
    assert attr.is_event_handler
    assert not attr.is_class_binding
