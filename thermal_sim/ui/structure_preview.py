"""Structure preview dialog for stack and layout visualization."""

from __future__ import annotations

from matplotlib import colormaps
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Patch, Rectangle
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from thermal_sim.models.project import DisplayProject


# Fixed recognizable colors for common display-module materials (matches assembly_3d.py)
_FIXED_COLORS: dict[str, tuple[float, float, float, float]] = {
    "Steel": (0.60, 0.60, 0.65, 1.0),
    "Aluminum": (0.75, 0.78, 0.82, 1.0),
    "FR4": (0.00, 0.50, 0.00, 1.0),
    "PMMA": (0.85, 0.92, 0.95, 1.0),
    "Glass": (0.70, 0.85, 0.95, 1.0),
    "PC": (0.90, 0.90, 0.85, 1.0),
    "Air Gap": (1.00, 1.00, 1.00, 1.0),
    "Air": (0.95, 0.95, 1.00, 1.0),
    "Copper": (0.85, 0.53, 0.10, 1.0),
    "OCA": (0.95, 0.92, 0.80, 1.0),
}


def _material_color_map(names: list[str]) -> dict[str, tuple]:
    """Build a color map for material names. Known materials get fixed colors."""
    cmap = colormaps["tab20"]
    result: dict[str, tuple] = {}
    tab_idx = 0
    for name in names:
        if name in _FIXED_COLORS:
            result[name] = _FIXED_COLORS[name]
        elif name not in result:
            result[name] = cmap(tab_idx % 20)
            tab_idx += 1
    return result


class _Canvas(FigureCanvasQTAgg):
    """Simple matplotlib canvas that expands to fill available space."""

    def __init__(self, width: float = 4.0, height: float = 4.0, dpi: int = 100) -> None:
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class StructurePreviewDialog(QDialog):
    """Preview stack cross-sections (X and Y) and plan-view geometry."""

    def __init__(self, project: DisplayProject, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self._expanded_sources = project.expanded_heat_sources()
        self.setWindowTitle(f"Structure Preview - {project.name}")
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = min(int(avail.width() * 0.85), 1400)
            h = min(int(avail.height() * 0.85), 860)
            self.resize(w, h)
        else:
            self.resize(1400, 860)
        self.setMinimumSize(600, 450)

        # Collect all material names for consistent color mapping
        all_mats: list[str] = []
        for layer in project.layers:
            if layer.material not in all_mats:
                all_mats.append(layer.material)
            for zone in layer.zones:
                if zone.material not in all_mats:
                    all_mats.append(zone.material)
            for edge_list in getattr(layer, "edge_layers", {}).values():
                for el in edge_list:
                    if el.material not in all_mats:
                        all_mats.append(el.material)
        self._mat_color = _material_color_map(all_mats)

        self._build_ui()
        self._draw_cross_section(self.xsec_canvas.axes, direction="x")
        self.xsec_canvas.figure.tight_layout()
        self.xsec_canvas.draw()
        self._draw_cross_section(self.ysec_canvas.axes, direction="y")
        self.ysec_canvas.figure.tight_layout()
        self.ysec_canvas.draw()
        self._draw_plan()

    def closeEvent(self, event) -> None:
        self.xsec_canvas.figure.clear()
        self.ysec_canvas.figure.clear()
        self.plan_canvas.figure.clear()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                f"Panel: {self.project.width * 1000:.1f} mm x {self.project.height * 1000:.1f} mm, "
                f"Layers: {len(self.project.layers)}, "
                f"Sources: {len(self.project.heat_sources)} + LED arrays: {len(self.project.led_arrays)} "
                f"(expanded: {len(self._expanded_sources)}), "
                f"Probes: {len(self.project.probes)}"
            )
        )

        # Vertical splitter: cross-sections on top, plan view on bottom
        vsplitter = QSplitter(Qt.Orientation.Vertical)

        # Top row: two cross-sections side by side
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("X Cross-Section (Width direction)"))
        self.xsec_canvas = _Canvas(width=4.0, height=3.5, dpi=100)
        left_layout.addWidget(self.xsec_canvas)

        mid = QWidget()
        mid_layout = QVBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.addWidget(QLabel("Y Cross-Section (Height direction)"))
        self.ysec_canvas = _Canvas(width=4.0, height=3.5, dpi=100)
        mid_layout.addWidget(self.ysec_canvas)

        top_splitter.addWidget(left)
        top_splitter.addWidget(mid)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)

        # Bottom: plan view
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(QLabel("Plan View (Sources / Probes)"))
        self.plan_canvas = _Canvas(width=8.0, height=3.0, dpi=100)
        bottom_layout.addWidget(self.plan_canvas)

        vsplitter.addWidget(top_splitter)
        vsplitter.addWidget(bottom)
        vsplitter.setStretchFactor(0, 2)
        vsplitter.setStretchFactor(1, 1)
        root.addWidget(vsplitter)

    def _draw_cross_section(self, ax, direction: str) -> None:
        """Draw a cross-section with edge layers and zones.

        direction="x": horizontal axis is panel width, shows left/right edge layers.
        direction="y": horizontal axis is panel height, shows bottom/top edge layers.
        """
        ax.clear()
        project = self.project
        mat_color = self._mat_color

        if direction == "x":
            extent_m = project.width
            near_edge, far_edge = "left", "right"
            title = "X Cross-Section (looking along Y)"
            xlabel = "Width [mm]"
        else:
            extent_m = project.height
            near_edge, far_edge = "bottom", "top"
            title = "Y Cross-Section (looking along X)"
            xlabel = "Height [mm]"

        extent_mm = extent_m * 1000.0
        z_mm = 0.0

        for layer in project.layers:
            t_mm = layer.thickness * 1e3

            # Main layer rectangle spanning full extent
            main_rect = Rectangle(
                (0.0, z_mm), extent_mm, t_mm,
                facecolor=mat_color.get(layer.material, (0.7, 0.7, 0.7, 1.0)),
                edgecolor="black", linewidth=0.6, alpha=0.85,
            )
            ax.add_patch(main_rect)

            # Edge layers on near side (left or bottom): stack inward from 0
            edge_layers_dict = getattr(layer, "edge_layers", {})
            near_list = edge_layers_dict.get(near_edge, [])
            x_cursor = 0.0
            for el in near_list:
                el_w_mm = el.thickness * 1000.0
                rect = Rectangle(
                    (x_cursor, z_mm), el_w_mm, t_mm,
                    facecolor=mat_color.get(el.material, (0.5, 0.5, 0.5, 1.0)),
                    edgecolor="gray", linewidth=0.4, alpha=0.95,
                )
                ax.add_patch(rect)
                # Label if wide enough
                if el_w_mm > extent_mm * 0.02:
                    ax.text(
                        x_cursor + el_w_mm / 2, z_mm + t_mm / 2,
                        el.material, ha="center", va="center",
                        fontsize=5, rotation=90 if el_w_mm < t_mm * 0.8 else 0,
                    )
                x_cursor += el_w_mm

            # Edge layers on far side (right or top): stack inward from extent
            far_list = edge_layers_dict.get(far_edge, [])
            x_cursor = extent_mm
            for el in far_list:
                el_w_mm = el.thickness * 1000.0
                x_cursor -= el_w_mm
                rect = Rectangle(
                    (x_cursor, z_mm), el_w_mm, t_mm,
                    facecolor=mat_color.get(el.material, (0.5, 0.5, 0.5, 1.0)),
                    edgecolor="gray", linewidth=0.4, alpha=0.95,
                )
                ax.add_patch(rect)
                if el_w_mm > extent_mm * 0.02:
                    ax.text(
                        x_cursor + el_w_mm / 2, z_mm + t_mm / 2,
                        el.material, ha="center", va="center",
                        fontsize=5, rotation=90 if el_w_mm < t_mm * 0.8 else 0,
                    )

            # Material zones: project onto this cross-section axis
            for zone in layer.zones:
                if direction == "x":
                    z0_mm = (zone.x - zone.width / 2.0) * 1000.0
                    z1_mm = (zone.x + zone.width / 2.0) * 1000.0
                else:
                    z0_mm = (zone.y - zone.height / 2.0) * 1000.0
                    z1_mm = (zone.y + zone.height / 2.0) * 1000.0
                z0_mm = max(z0_mm, 0.0)
                z1_mm = min(z1_mm, extent_mm)
                if z1_mm > z0_mm:
                    rect = Rectangle(
                        (z0_mm, z_mm), z1_mm - z0_mm, t_mm,
                        facecolor=mat_color.get(zone.material, (0.6, 0.6, 0.6, 1.0)),
                        edgecolor="gray", linewidth=0.4, alpha=0.9,
                    )
                    ax.add_patch(rect)

            # Layer name label at center
            ax.text(
                extent_mm / 2, z_mm + t_mm / 2,
                f"{layer.name}\n{layer.thickness * 1e6:.0f} \u00b5m",
                ha="center", va="center", fontsize=7,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", alpha=0.6, ec="none"),
            )

            z_mm += t_mm

        ax.set_xlim(0.0, extent_mm)
        ax.set_ylim(0.0, max(z_mm, 1e-6))
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Stack height [mm]")
        ax.set_title(title)
        ax.grid(True, alpha=0.2)

        # Legend — show all materials that appear
        used_mats = list(dict.fromkeys(
            name for name in mat_color if any(
                name == layer.material
                or any(z.material == name for z in layer.zones)
                or any(
                    el.material == name
                    for edge_list in getattr(layer, "edge_layers", {}).values()
                    for el in edge_list
                )
                for layer in project.layers
            )
        ))
        if used_mats:
            legend_patches = [
                Patch(facecolor=mat_color[n], edgecolor="black", linewidth=0.4, label=n)
                for n in used_mats
            ]
            ax.legend(
                handles=legend_patches, loc="upper left",
                bbox_to_anchor=(1.01, 1.0), fontsize=6,
                title="Materials", title_fontsize=7, frameon=False,
            )

    def _draw_plan(self) -> None:
        ax = self.plan_canvas.axes
        ax.clear()

        w_mm = self.project.width * 1000.0
        h_mm = self.project.height * 1000.0

        panel = Rectangle((0.0, 0.0), w_mm, h_mm, fill=False, edgecolor="black", linewidth=1.2)
        ax.add_patch(panel)

        layer_names = [layer.name for layer in self.project.layers]
        cmap = colormaps["tab10"]
        layer_colors = {name: cmap(i % 10) for i, name in enumerate(layer_names)}

        show_labels = len(self._expanded_sources) <= 40
        for source in self._expanded_sources:
            color = layer_colors.get(source.layer, "red")
            sx = source.x * 1000.0
            sy = source.y * 1000.0
            if source.shape == "full":
                patch = Rectangle(
                    (0.0, 0.0), w_mm, h_mm,
                    facecolor=color, edgecolor=color, alpha=0.12, linestyle="--",
                )
                ax.add_patch(patch)
                if show_labels:
                    ax.text(w_mm * 0.5, h_mm * 0.5, source.name,
                            color=color, ha="center", va="center")
            elif source.shape == "rectangle":
                if source.width is None or source.height is None:
                    continue
                sw = source.width * 1000.0
                sh = source.height * 1000.0
                patch = Rectangle(
                    (sx - sw / 2.0, sy - sh / 2.0), sw, sh,
                    facecolor=color, edgecolor=color, alpha=0.28,
                )
                ax.add_patch(patch)
                if show_labels:
                    ax.text(sx, sy, source.name, color=color, ha="center", va="center", fontsize=8)
            elif source.shape == "circle":
                if source.radius is None:
                    continue
                sr = source.radius * 1000.0
                patch = Circle((sx, sy), radius=sr, facecolor=color, edgecolor=color, alpha=0.28)
                ax.add_patch(patch)
                if show_labels:
                    ax.text(sx, sy, source.name, color=color, ha="center", va="center", fontsize=8)

        for probe in self.project.probes:
            px = probe.x * 1000.0
            py = probe.y * 1000.0
            ax.plot(px, py, marker="x", markersize=7, color="black")
            ax.text(px, py, f" {probe.name}", color="black", va="bottom", ha="left", fontsize=8)

        ax.set_xlim(0.0, w_mm)
        ax.set_ylim(0.0, h_mm)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x [mm]")
        ax.set_ylabel("y [mm]")
        ax.set_title("Panel Plan View")
        ax.grid(True, alpha=0.25)
        self.plan_canvas.figure.tight_layout()
        self.plan_canvas.draw()
