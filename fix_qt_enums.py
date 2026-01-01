"""
Script to fix all Qt enum access to use fully qualified paths.
This aligns with PySide6 6.4+ type stub requirements.
"""

from pathlib import Path

# Mapping of shorthand to fully qualified enum paths
ENUM_REPLACEMENTS = {
    # Qt.DockWidgetArea
    "Qt.AllDockWidgetAreas": "Qt.DockWidgetArea.AllDockWidgetAreas",
    "Qt.LeftDockWidgetArea": "Qt.DockWidgetArea.LeftDockWidgetArea",
    "Qt.RightDockWidgetArea": "Qt.DockWidgetArea.RightDockWidgetArea",
    "Qt.TopDockWidgetArea": "Qt.DockWidgetArea.TopDockWidgetArea",
    "Qt.BottomDockWidgetArea": "Qt.DockWidgetArea.BottomDockWidgetArea",
    "Qt.NoDockWidgetArea": "Qt.DockWidgetArea.NoDockWidgetArea",
    # Qt.Corner
    "Qt.TopLeftCorner": "Qt.Corner.TopLeftCorner",
    "Qt.TopRightCorner": "Qt.Corner.TopRightCorner",
    "Qt.BottomLeftCorner": "Qt.Corner.BottomLeftCorner",
    "Qt.BottomRightCorner": "Qt.Corner.BottomRightCorner",
    # Qt.ConnectionType
    "Qt.QueuedConnection": "Qt.ConnectionType.QueuedConnection",
    "Qt.DirectConnection": "Qt.ConnectionType.DirectConnection",
    "Qt.AutoConnection": "Qt.ConnectionType.AutoConnection",
    # Qt.CursorShape
    "Qt.WaitCursor": "Qt.CursorShape.WaitCursor",
    "Qt.ArrowCursor": "Qt.CursorShape.ArrowCursor",
    "Qt.PointingHandCursor": "Qt.CursorShape.PointingHandCursor",
    # Qt.KeyboardModifier
    "Qt.ControlModifier": "Qt.KeyboardModifier.ControlModifier",
    "Qt.ShiftModifier": "Qt.KeyboardModifier.ShiftModifier",
    "Qt.AltModifier": "Qt.KeyboardModifier.AltModifier",
    "Qt.NoModifier": "Qt.KeyboardModifier.NoModifier",
    # Qt.MouseButton
    "Qt.LeftButton": "Qt.MouseButton.LeftButton",
    "Qt.RightButton": "Qt.MouseButton.RightButton",
    "Qt.MiddleButton": "Qt.MouseButton.MiddleButton",
    "Qt.NoButton": "Qt.MouseButton.NoButton",
    # Qt.Orientation
    "Qt.Horizontal": "Qt.Orientation.Horizontal",
    "Qt.Vertical": "Qt.Orientation.Vertical",
    # Qt.AlignmentFlag
    "Qt.AlignLeft": "Qt.AlignmentFlag.AlignLeft",
    "Qt.AlignRight": "Qt.AlignmentFlag.AlignRight",
    "Qt.AlignCenter": "Qt.AlignmentFlag.AlignCenter",
    "Qt.AlignHCenter": "Qt.AlignmentFlag.AlignHCenter",
    "Qt.AlignVCenter": "Qt.AlignmentFlag.AlignVCenter",
    "Qt.AlignTop": "Qt.AlignmentFlag.AlignTop",
    "Qt.AlignBottom": "Qt.AlignmentFlag.AlignBottom",
    # Qt.Key (common keys)
    "Qt.Key_Enter": "Qt.Key.Key_Enter",
    "Qt.Key_Return": "Qt.Key.Key_Return",
    "Qt.Key_Escape": "Qt.Key.Key_Escape",
    "Qt.Key_Tab": "Qt.Key.Key_Tab",
    "Qt.Key_Backtab": "Qt.Key.Key_Backtab",
    "Qt.Key_BracketLeft": "Qt.Key.Key_BracketLeft",
    "Qt.Key_BracketRight": "Qt.Key.Key_BracketRight",
    # QMainWindow.DockOption
    "QMainWindow.AnimatedDocks": "QMainWindow.DockOption.AnimatedDocks",
    "QMainWindow.AllowNestedDocks": "QMainWindow.DockOption.AllowNestedDocks",
    "QMainWindow.AllowTabbedDocks": "QMainWindow.DockOption.AllowTabbedDocks",
    # QTabWidget.TabPosition
    "QTabWidget.North": "QTabWidget.TabPosition.North",
    "QTabWidget.South": "QTabWidget.TabPosition.South",
    "QTabWidget.West": "QTabWidget.TabPosition.West",
    "QTabWidget.East": "QTabWidget.TabPosition.East",
    # QDockWidget.DockWidgetFeature
    "QDockWidget.DockWidgetMovable": "QDockWidget.DockWidgetFeature.DockWidgetMovable",
    "QDockWidget.DockWidgetFloatable": "QDockWidget.DockWidgetFeature.DockWidgetFloatable",
    "QDockWidget.DockWidgetClosable": "QDockWidget.DockWidgetFeature.DockWidgetClosable",
    # QMessageBox.StandardButton
    "QMessageBox.Yes": "QMessageBox.StandardButton.Yes",
    "QMessageBox.No": "QMessageBox.StandardButton.No",
    "QMessageBox.Ok": "QMessageBox.StandardButton.Ok",
    "QMessageBox.Cancel": "QMessageBox.StandardButton.Cancel",
    "QMessageBox.Save": "QMessageBox.StandardButton.Save",
    "QMessageBox.Discard": "QMessageBox.StandardButton.Discard",
    "QMessageBox.Close": "QMessageBox.StandardButton.Close",
    "QMessageBox.Apply": "QMessageBox.StandardButton.Apply",
    "QMessageBox.Reset": "QMessageBox.StandardButton.Reset",
    "QMessageBox.Help": "QMessageBox.StandardButton.Help",
    "QMessageBox.Abort": "QMessageBox.StandardButton.Abort",
    "QMessageBox.Retry": "QMessageBox.StandardButton.Retry",
    "QMessageBox.Ignore": "QMessageBox.StandardButton.Ignore",
    # QDialog.DialogCode
    "QDialog.Accepted": "QDialog.DialogCode.Accepted",
    "QDialog.Rejected": "QDialog.DialogCode.Rejected",
    # QMessageBox.ButtonRole
    "QMessageBox.AcceptRole": "QMessageBox.ButtonRole.AcceptRole",
    "QMessageBox.RejectRole": "QMessageBox.ButtonRole.RejectRole",
    "QMessageBox.DestructiveRole": "QMessageBox.ButtonRole.DestructiveRole",
    "QMessageBox.ActionRole": "QMessageBox.ButtonRole.ActionRole",
    "QMessageBox.HelpRole": "QMessageBox.ButtonRole.HelpRole",
    "QMessageBox.YesRole": "QMessageBox.ButtonRole.YesRole",
    "QMessageBox.NoRole": "QMessageBox.ButtonRole.NoRole",
    "QMessageBox.ApplyRole": "QMessageBox.ButtonRole.ApplyRole",
    "QMessageBox.ResetRole": "QMessageBox.ButtonRole.ResetRole",
    # NEW MAPPINGS
    # Qt.WidgetAttribute
    "Qt.WA_StyledBackground": "Qt.WidgetAttribute.WA_StyledBackground",
    "Qt.WA_DeleteOnClose": "Qt.WidgetAttribute.WA_DeleteOnClose",
    "Qt.WA_TranslucentBackground": "Qt.WidgetAttribute.WA_TranslucentBackground",
    # Qt.ItemDataRole
    "Qt.UserRole": "Qt.ItemDataRole.UserRole",
    "Qt.DisplayRole": "Qt.ItemDataRole.DisplayRole",
    "Qt.EditRole": "Qt.ItemDataRole.EditRole",
    "Qt.ToolTipRole": "Qt.ItemDataRole.ToolTipRole",
    "Qt.CheckStateRole": "Qt.ItemDataRole.CheckStateRole",
    "Qt.DecorationRole": "Qt.ItemDataRole.DecorationRole",
    "Qt.FontRole": "Qt.ItemDataRole.FontRole",
    "Qt.BackgroundRole": "Qt.ItemDataRole.BackgroundRole",
    "Qt.ForegroundRole": "Qt.ItemDataRole.ForegroundRole",
    # Qt.AspectRatioMode
    "Qt.KeepAspectRatio": "Qt.AspectRatioMode.KeepAspectRatio",
    "Qt.KeepAspectRatioByExpanding": "Qt.AspectRatioMode.KeepAspectRatioByExpanding",
    "Qt.IgnoreAspectRatio": "Qt.AspectRatioMode.IgnoreAspectRatio",
    # Qt.PenStyle
    "Qt.NoPen": "Qt.PenStyle.NoPen",
    "Qt.SolidLine": "Qt.PenStyle.SolidLine",
    "Qt.DashLine": "Qt.PenStyle.DashLine",
    "Qt.DotLine": "Qt.PenStyle.DotLine",
    # QAbstractItemView.SelectionMode
    "QAbstractItemView.SingleSelection": "QAbstractItemView.SelectionMode.SingleSelection",
    "QAbstractItemView.MultiSelection": "QAbstractItemView.SelectionMode.MultiSelection",
    "QAbstractItemView.ExtendedSelection": "QAbstractItemView.SelectionMode.ExtendedSelection",
    "QAbstractItemView.NoSelection": "QAbstractItemView.SelectionMode.NoSelection",
    # QAbstractItemView.SelectionBehavior
    "QAbstractItemView.SelectRows": "QAbstractItemView.SelectionBehavior.SelectRows",
    "QAbstractItemView.SelectColumns": "QAbstractItemView.SelectionBehavior.SelectColumns",
    "QAbstractItemView.SelectItems": "QAbstractItemView.SelectionBehavior.SelectItems",
    # Qt.ContextMenuPolicy
    "Qt.CustomContextMenu": "Qt.ContextMenuPolicy.CustomContextMenu",
    "Qt.Exposed": "Qt.WindowState.WindowNoState",
    # QGraphicsView.DragMode
    "QGraphicsView.ScrollHandDrag": "QGraphicsView.DragMode.ScrollHandDrag",
    "QGraphicsView.RubberBandDrag": "QGraphicsView.DragMode.RubberBandDrag",
    "QGraphicsView.NoDrag": "QGraphicsView.DragMode.NoDrag",
    # QGraphicsItem.GraphicsItemFlag
    "QGraphicsItem.ItemIsMovable": "QGraphicsItem.GraphicsItemFlag.ItemIsMovable",
    "QGraphicsItem.ItemIsSelectable": "QGraphicsItem.GraphicsItemFlag.ItemIsSelectable",
    "QGraphicsItem.ItemIsFocusable": "QGraphicsItem.GraphicsItemFlag.ItemIsFocusable",
    "QGraphicsItem.ItemSendsGeometryChanges": "QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges",
    # Qt.GlobalColor
    "Qt.white": "Qt.GlobalColor.white",
    "Qt.black": "Qt.GlobalColor.black",
    "Qt.red": "Qt.GlobalColor.red",
    "Qt.darkRed": "Qt.GlobalColor.darkRed",
    "Qt.green": "Qt.GlobalColor.green",
    "Qt.darkGreen": "Qt.GlobalColor.darkGreen",
    "Qt.blue": "Qt.GlobalColor.blue",
    "Qt.darkBlue": "Qt.GlobalColor.darkBlue",
    "Qt.cyan": "Qt.GlobalColor.cyan",
    "Qt.magenta": "Qt.GlobalColor.magenta",
    "Qt.yellow": "Qt.GlobalColor.yellow",
    "Qt.darkYellow": "Qt.GlobalColor.darkYellow",
    "Qt.gray": "Qt.GlobalColor.gray",
    "Qt.darkGray": "Qt.GlobalColor.darkGray",
    "Qt.lightGray": "Qt.GlobalColor.lightGray",
    "Qt.transparent": "Qt.GlobalColor.transparent",
    # QLineEdit.EchoMode
    "QLineEdit.Password": "QLineEdit.EchoMode.Password",
    "QLineEdit.Normal": "QLineEdit.EchoMode.Normal",
    # QHeaderView.ResizeMode
    "QHeaderView.Stretch": "QHeaderView.ResizeMode.Stretch",
    "QHeaderView.ResizeToContents": "QHeaderView.ResizeMode.ResizeToContents",
    "QHeaderView.Interactive": "QHeaderView.ResizeMode.Interactive",
    "QHeaderView.Fixed": "QHeaderView.ResizeMode.Fixed",
    # QFrame.Shape
    "QFrame.NoFrame": "QFrame.Shape.NoFrame",
    "QFrame.Box": "QFrame.Shape.Box",
    "QFrame.Panel": "QFrame.Shape.Panel",
    "QFrame.StyledPanel": "QFrame.Shape.StyledPanel",
    "QFrame.HLine": "QFrame.Shape.HLine",
    "QFrame.VLine": "QFrame.Shape.VLine",
    # Qt.CheckState
    "Qt.Checked": "Qt.CheckState.Checked",
    "Qt.Unchecked": "Qt.CheckState.Unchecked",
    "Qt.PartiallyChecked": "Qt.CheckState.PartiallyChecked",
    # QSizePolicy.Policy
    "QSizePolicy.Expanding": "QSizePolicy.Policy.Expanding",
    "QSizePolicy.Fixed": "QSizePolicy.Policy.Fixed",
    "QSizePolicy.Preferred": "QSizePolicy.Policy.Preferred",
    "QSizePolicy.Minimum": "QSizePolicy.Policy.Minimum",
    "QSizePolicy.Maximum": "QSizePolicy.Policy.Maximum",
    "QSizePolicy.MinimumExpanding": "QSizePolicy.Policy.MinimumExpanding",
    "QSizePolicy.Ignored": "QSizePolicy.Policy.Ignored",
    # Qt.TextInteractionFlag
    "Qt.TextBrowserInteraction": "Qt.TextInteractionFlag.TextBrowserInteraction",
    "Qt.TextEditorInteraction": "Qt.TextInteractionFlag.TextEditorInteraction",
    "Qt.TextSelectableByMouse": "Qt.TextInteractionFlag.TextSelectableByMouse",
    "Qt.TextSelectableByKeyboard": "Qt.TextInteractionFlag.TextSelectableByKeyboard",
    # Qt.WindowType
    "Qt.Window": "Qt.WindowType.Window",
    "Qt.Dialog": "Qt.WindowType.Dialog",
    "Qt.Popup": "Qt.WindowType.Popup",
    "Qt.Tool": "Qt.WindowType.Tool",
    "Qt.ToolTip": "Qt.WindowType.ToolTip",
    "Qt.SplashScreen": "Qt.WindowType.SplashScreen",
    "Qt.Widget": "Qt.WindowType.Widget",
    "Qt.SubWindow": "Qt.WindowType.SubWindow",
    "Qt.FramelessWindowHint": "Qt.WindowType.FramelessWindowHint",
    "Qt.WindowStaysOnTopHint": "Qt.WindowType.WindowStaysOnTopHint",
    # ViewportAnchor
    "QGraphicsView.AnchorUnderMouse": "QGraphicsView.ViewportAnchor.AnchorUnderMouse",
    "QGraphicsView.NoAnchor": "QGraphicsView.ViewportAnchor.NoAnchor",
    # QDialogButtonBox.StandardButton
    "QDialogButtonBox.Save": "QDialogButtonBox.StandardButton.Save",
    "QDialogButtonBox.Cancel": "QDialogButtonBox.StandardButton.Cancel",
    "QDialogButtonBox.Ok": "QDialogButtonBox.StandardButton.Ok",
    "QDialogButtonBox.Apply": "QDialogButtonBox.StandardButton.Apply",
    "QDialogButtonBox.Reset": "QDialogButtonBox.StandardButton.Reset",
    "QDialogButtonBox.Close": "QDialogButtonBox.StandardButton.Close",
    "QDialogButtonBox.Help": "QDialogButtonBox.StandardButton.Help",
    "QDialogButtonBox.Yes": "QDialogButtonBox.StandardButton.Yes",
    "QDialogButtonBox.No": "QDialogButtonBox.StandardButton.No",
    # Qt.ScrollBarPolicy
    "Qt.ScrollBarAlwaysOff": "Qt.ScrollBarPolicy.ScrollBarAlwaysOff",
    "Qt.ScrollBarAlwaysOn": "Qt.ScrollBarPolicy.ScrollBarAlwaysOn",
    "Qt.ScrollBarAsNeeded": "Qt.ScrollBarPolicy.ScrollBarAsNeeded",
    # Qt.CaseSensitivity
    "Qt.CaseInsensitive": "Qt.CaseSensitivity.CaseInsensitive",
    "Qt.CaseSensitive": "Qt.CaseSensitivity.CaseSensitive",
    # Qt.TransformationMode
    "Qt.SmoothTransformation": "Qt.TransformationMode.SmoothTransformation",
    "Qt.FastTransformation": "Qt.TransformationMode.FastTransformation",
    # QFrame.Shadow
    "QFrame.Plain": "QFrame.Shadow.Plain",
    "QFrame.Raised": "QFrame.Shadow.Raised",
    "QFrame.Sunken": "QFrame.Shadow.Sunken",
    # QGraphicsScene.ItemIndexMethod
    "QGraphicsScene.NoIndex": "QGraphicsScene.ItemIndexMethod.NoIndex",
    "QGraphicsScene.BspTreeIndex": "QGraphicsScene.ItemIndexMethod.BspTreeIndex",
}


def fix_file(filepath):
    """Fix Qt enum usage in a single file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Apply all replacements
        for old, new in ENUM_REPLACEMENTS.items():
            content = content.replace(old, new)

        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main():
    """Fix all Python files in src/app and src/gui."""
    base_dirs = ["src/app", "src/gui"]
    fixed_count = 0

    for base_dir in base_dirs:
        for filepath in Path(base_dir).rglob("*.py"):
            if fix_file(filepath):
                print(f"Fixed: {filepath}")
                fixed_count += 1

    print(f"\nTotal files fixed: {fixed_count}")


if __name__ == "__main__":
    main()
