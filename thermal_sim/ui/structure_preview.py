"""Structure preview dialog for stack and layout visualization."""

from __future__ import annotations

from matplotlib import colormaps
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from thermal_sim.models.project import DisplayProject


class _Canvas(FigureCanvasQTAgg):
    """Simple matplotlib canvas."""

    def __init__(self, width: float = 5.0, height: float = 4.0, dpi: int = 100) -> None:
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)


class StructurePreviewDialog(QDialog):
    """Preview stack cross-section and plan-view geometry."""

    def __init__(self, project: DisplayProject, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle(f"Structure Preview - {project.name}")
        self.resize(1200, 760)
        self._build_ui()
        self._draw_stack()
        self._draw_plan()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                f"Panel: {self.project.width:.4f} m x {self.project.height:.4f} m, "
                f"Layers: {len(self.project.layers)}, "
                f"Sources: {len(self.project.heat_sources)} + LED arrays: {len(self.project.led_arrays)} "
                f"(expanded: {len(self.project.expanded_heat_sources())}), "
                f"Probes: {len(self.project.probes)}"
            )
        )

        row = QHBoxLayout()
        root.addLayout(row)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Cross-Section Stack (Thickness)"))
        self.stack_canvas = _Canvas(width=5.8, height=5.8, dpi=100)
        left_layout.addWidget(self.stack_canvas)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Plan View (Sources / Probes)"))
        self.plan_canvas = _Canvas(width=5.8, height=5.8, dpi=100)
        right_layout.addWidget(self.plan_canvas)

        row.addWidget(left)
        row.addWidget(right)

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

        legend_lines = [f"{mat}: color" for mat in material_names]
        if legend_lines:
            ax.text(
                1.02,
                0.98,
                "Materials:\n" + "\n".join(legend_lines),
                transform=ax.transAxes,
                va="top",
                fontsize=8,
            )
        self.stack_canvas.figure.tight_layout()
        self.stack_canvas.draw()

    def _draw_plan(self) -> None:
        ax = self.plan_canvas.axes
        ax.clear()

        panel = Rectangle((0.0, 0.0), self.project.width, self.project.height, fill=False, edgecolor="black", linewidth=1.2)
        ax.add_patch(panel)

        layer_names = [layer.name for layer in self.project.layers]
        cmap = colormaps["tab10"]
        layer_colors = {name: cmap(i % 10) for i, name in enumerate(layer_names)}

        expanded_sources = self.project.expanded_heat_sources()
        show_labels = len(expanded_sources) <= 40
        for source in expanded_sources:
            color = layer_colors.get(source.layer, "red")
            if source.shape == "full":
                patch = Rectangle(
                    (0.0, 0.0),
                    self.project.width,
                    self.project.height,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.12,
                    linestyle="--",
                )
                ax.add_patch(patch)
                if show_labels:
                    ax.text(
                        self.project.width * 0.5,
                        self.project.height * 0.5,
                        source.name,
                        color=color,
                        ha="center",
                        va="center",
                    )
            elif source.shape == "rectangle":
                if source.width is None or source.height is None:
                    continue
                patch = Rectangle(
                    (source.x - source.width / 2.0, source.y - source.height / 2.0),
                    source.width,
                    source.height,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.28,
                )
                ax.add_patch(patch)
                if show_labels:
                    ax.text(source.x, source.y, source.name, color=color, ha="center", va="center", fontsize=8)
            elif source.shape == "circle":
                if source.radius is None:
                    continue
                patch = Circle((source.x, source.y), radius=source.radius, facecolor=color, edgecolor=color, alpha=0.28)
                ax.add_patch(patch)
                if show_labels:
                    ax.text(source.x, source.y, source.name, color=color, ha="center", va="center", fontsize=8)

        for probe in self.project.probes:
            ax.plot(probe.x, probe.y, marker="x", markersize=7, color="black")
            ax.text(probe.x, probe.y, f" {probe.name}", color="black", va="bottom", ha="left", fontsize=8)

        ax.set_xlim(0.0, self.project.width)
        ax.set_ylim(0.0, self.project.height)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title("Panel Plan View")
        ax.grid(True, alpha=0.25)
        self.plan_canvas.figure.tight_layout()
        self.plan_canvas.draw()
