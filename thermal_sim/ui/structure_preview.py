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


class _Canvas(FigureCanvasQTAgg):
    """Simple matplotlib canvas that expands to fill available space."""

    def __init__(self, width: float = 4.0, height: float = 4.0, dpi: int = 100) -> None:
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class StructurePreviewDialog(QDialog):
    """Preview stack cross-section and plan-view geometry."""

    def __init__(self, project: DisplayProject, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self._expanded_sources = project.expanded_heat_sources()
        self.setWindowTitle(f"Structure Preview - {project.name}")
        # Size to 80% of the available screen, capped at 1200x760
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = min(int(avail.width() * 0.8), 1200)
            h = min(int(avail.height() * 0.8), 760)
            self.resize(w, h)
        else:
            self.resize(1200, 760)
        self.setMinimumSize(500, 400)
        self._build_ui()
        self._draw_stack()
        self._draw_plan()

    def closeEvent(self, event) -> None:
        """Close matplotlib figures to prevent memory leaks."""
        self.stack_canvas.figure.clear()
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

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Cross-Section Stack (Thickness)"))
        self.stack_canvas = _Canvas(width=4.0, height=4.0, dpi=100)
        left_layout.addWidget(self.stack_canvas)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Plan View (Sources / Probes)"))
        self.plan_canvas = _Canvas(width=4.0, height=4.0, dpi=100)
        right_layout.addWidget(self.plan_canvas)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    def _draw_stack(self) -> None:
        ax = self.stack_canvas.axes
        ax.clear()

        material_names = list(dict.fromkeys(layer.material for layer in self.project.layers))
        cmap = colormaps["tab20"]
        mat_color = {name: cmap(i % 20) for i, name in enumerate(material_names)}

        z_mm = 0.0
        x0 = 0.0
        width = 1.0
        for layer in self.project.layers:
            thickness_mm = layer.thickness * 1e3
            rect = Rectangle(
                (x0, z_mm),
                width,
                thickness_mm,
                facecolor=mat_color[layer.material],
                edgecolor="black",
                linewidth=0.8,
                alpha=0.85,
            )
            ax.add_patch(rect)
            label = f"{layer.name}\n{layer.material}\n{layer.thickness * 1e6:.0f} um"
            ax.text(0.5, z_mm + thickness_mm / 2.0, label, ha="center", va="center", fontsize=8)
            z_mm += thickness_mm

        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, max(z_mm, 1e-6))
        ax.set_xticks([])
        ax.set_ylabel("Stack depth from bottom [mm]")
        ax.set_title("Layer Stack Build-Up")
        ax.grid(True, axis="y", alpha=0.25)

        if material_names:
            legend_patches = [
                Patch(facecolor=mat_color[name], edgecolor="black", linewidth=0.5, label=name)
                for name in material_names
            ]
            ax.legend(
                handles=legend_patches,
                loc="upper left",
                bbox_to_anchor=(1.02, 1.0),
                fontsize=7,
                title="Materials",
                title_fontsize=8,
                frameon=False,
            )
        self.stack_canvas.figure.tight_layout()
        self.stack_canvas.draw()

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
                    (0.0, 0.0),
                    w_mm,
                    h_mm,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.12,
                    linestyle="--",
                )
                ax.add_patch(patch)
                if show_labels:
                    ax.text(
                        w_mm * 0.5,
                        h_mm * 0.5,
                        source.name,
                        color=color,
                        ha="center",
                        va="center",
                    )
            elif source.shape == "rectangle":
                if source.width is None or source.height is None:
                    continue
                sw = source.width * 1000.0
                sh = source.height * 1000.0
                patch = Rectangle(
                    (sx - sw / 2.0, sy - sh / 2.0),
                    sw,
                    sh,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.28,
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
