"""Comprehensive visual & DOM graphics parity test cases (MATLAB vs NumKit)."""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class GraphicsCase:
    name: str
    category: str
    code: str
    dpi: int = 120
    expect_error: bool = False
    is_stress: bool = False


CASES: List[GraphicsCase] = [
    # ── 1. Layout & Subplots ─────────────────────────────────────────
    GraphicsCase(
        name="layout_spanning_subplot",
        category="layout",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 900, 580]);
x = linspace(0, 2*pi, 100);
subplot(2, 2, 1); plot(x, sin(x), 'LineWidth', 1.5); grid on; title('Top Left'); ylabel('sin(x)');
subplot(2, 2, 2); plot(x, cos(x), 'r--', 'LineWidth', 1.5); grid on; title('Top Right');
subplot(2, 2, [3, 4]); hold on; grid on;
plot(x, sin(x), 'b-', 'LineWidth', 1.5, 'DisplayName', 'sin');
plot(x, cos(x), 'r-', 'LineWidth', 1.5, 'DisplayName', 'cos');
xlabel('x, rad'); ylabel('val'); title('Spanning Bottom [3, 4]'); legend('Location', 'northeast');
sgtitle('Spanning Subplot Layout');
""",
    ),
    GraphicsCase(
        name="layout_tiledlayout",
        category="layout",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 860, 540]);
t = tiledlayout(2, 2);
x = linspace(0, 4*pi, 120);
nexttile; plot(x, sin(x)); grid on; title('Tile 1');
nexttile; plot(x, cos(x), 'r'); grid on; title('Tile 2');
nexttile([1, 2]); plot(x, sin(x).*exp(-0.15*x), 'LineWidth', 1.6); grid on; title('Wide Tile [1, 2]');
title(t, 'TiledChartLayout Demo');
""",
    ),
    GraphicsCase(
        name="layout_manual_position",
        category="layout",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 800, 500]);
x = linspace(0, 10, 200);
ax1 = axes('Position', [0.10, 0.14, 0.52, 0.76]);
plot(ax1, x, sin(x), 'LineWidth', 1.5); grid(ax1, 'on'); title(ax1, 'Main Axes');
ax2 = axes('Position', [0.68, 0.54, 0.27, 0.36]);
plot(ax2, x, exp(-0.3*x), 'r-', 'LineWidth', 1.5); grid(ax2, 'on'); title(ax2, 'Inset Top');
ax3 = axes('Position', [0.68, 0.14, 0.27, 0.30]);
plot(ax3, x, cos(2*x), 'g-', 'LineWidth', 1.5); grid(ax3, 'on'); title(ax3, 'Inset Bot');
""",
    ),
    GraphicsCase(
        name="layout_axis_modes",
        category="layout",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 860, 560]);
th = linspace(0, 2*pi, 200);
subplot(2, 2, 1); plot(cos(th), sin(th), 'LineWidth', 1.5); axis equal; grid on; title('axis equal');
subplot(2, 2, 2); plot(cos(th), sin(th), 'LineWidth', 1.5); axis square; grid on; title('axis square');
subplot(2, 2, 3); plot(th, sin(th), 'LineWidth', 1.5); axis tight; grid on; title('axis tight');
subplot(2, 2, 4); plot([1, 2, 3, 4], [1, 4, 2, 3], 'o-', 'LineWidth', 1.5); axis ij; grid on; title('axis ij');
""",
    ),
    GraphicsCase(
        name="layout_box_and_axis_off",
        category="layout",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 900, 360]);
x = linspace(0, 2*pi, 100);
subplot(1, 3, 1); plot(x, sin(x), 'LineWidth', 1.5); box on; grid on; title('box on');
subplot(1, 3, 2); plot(x, sin(x), 'LineWidth', 1.5); box off; grid on; title('box off');
subplot(1, 3, 3); plot(cos(x), sin(x), 'LineWidth', 1.5); axis equal off; title('axis equal off');
""",
    ),
    GraphicsCase(
        name="layout_reverse_dirs",
        category="layout",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 760, 480]);
x = 1:10;
plot(x, x.^2, 'o-', 'LineWidth', 1.5); grid on;
set(gca, 'XDir', 'reverse', 'YDir', 'reverse');
xlabel('X (reversed)'); ylabel('Y (reversed)'); title('Reversed XDir & YDir');
""",
    ),

    # ── 2. 2-D Lines, Styles, Markers & Scales ───────────────────────
    GraphicsCase(
        name="line_styles_and_colors",
        category="line2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 820, 480]);
hold on; grid on;
x = linspace(0, 10, 200);
plot(x, sin(x) + 3.0, '-',  'Color', [0.00 0.45 0.74], 'LineWidth', 2.0, 'DisplayName', 'Solid lw=2');
plot(x, sin(x) + 2.0, '--', 'Color', [0.85 0.33 0.10], 'LineWidth', 1.6, 'DisplayName', 'Dashed');
plot(x, sin(x) + 1.0, ':',  'Color', [0.00 0.00 0.00], 'LineWidth', 1.5, 'DisplayName', 'Dotted');
plot(x, sin(x) + 0.0, '-.', 'Color', [0.49 0.18 0.56], 'LineWidth', 1.6, 'DisplayName', 'DashDot');
plot(x, sin(x) - 1.0, 'g-', 'LineWidth', 1.8, 'DisplayName', 'Green g-');
xlim([0 10]); ylim([-2.5 4.5]);
xlabel('x'); ylabel('y'); title('Line Styles & Colors'); legend('Location', 'northeast');
""",
    ),
    GraphicsCase(
        name="line_markers_gallery",
        category="line2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 840, 480]);
hold on; grid on;
x = 1:8;
mks = {'o', 's', 'd', '+', 'x', '*', '^', 'v'};
for k = 1:numel(mks)
    plot(x, ones(size(x)) * k, ['-' mks{k}], 'LineWidth', 1.3, 'MarkerSize', 7, 'DisplayName', ['mk ' mks{k}]);
end
plot(4.5, 4.5, 'ko', 'MarkerFaceColor', [0.00 0.45 0.74], 'MarkerSize', 10, 'DisplayName', 'Filled ko');
xlim([0.5 8.5]); ylim([0 9]);
title('Markers & MarkerFaceColor'); legend('Location', 'eastoutside');
""",
    ),
    GraphicsCase(
        name="line_log_scales",
        category="line2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 900, 360]);
x = logspace(0, 3, 120);
subplot(1, 3, 1); semilogx(x, log10(x), 'LineWidth', 1.5); grid on; title('semilogx');
subplot(1, 3, 2); semilogy(linspace(0, 5, 100), exp(linspace(0, 5, 100)), 'LineWidth', 1.5); grid on; grid minor; title('semilogy + minor');
subplot(1, 3, 3); loglog(x, x.^1.5, 'LineWidth', 1.5); grid on; title('loglog');
""",
    ),
    GraphicsCase(
        name="line_clipping_and_nan",
        category="line2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 800, 460]);
hold on; grid on;
x = linspace(0, 10, 250);
y = 20 * sin(2*x);
y(80:110) = NaN;
y(180) = Inf;
plot(x, y, 'b-', 'LineWidth', 1.6, 'DisplayName', 'Clipped + NaN');
plot([1, 5, 9], [10, 0, -10], 'ro', 'MarkerSize', 8, 'LineWidth', 1.6, 'DisplayName', 'Boundary pts');
xlim([0 10]); ylim([-10 10]);
title('Clipping to YLim & NaN/Inf Gaps'); legend('Location', 'northeast');
""",
    ),
    GraphicsCase(
        name="line_xline_yline",
        category="line2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 760, 460]);
hold on; grid on;
x = linspace(0, 10, 150);
plot(x, sin(x), 'LineWidth', 1.6);
xline(pi, 'r--', 'LineWidth', 1.4, 'Label', 'x = pi');
yline(0.5, 'k:', 'LineWidth', 1.4, 'Label', 'Threshold');
xlim([0 10]); ylim([-1.3 1.3]);
title('xline & yline with Labels');
""",
    ),

    # ── 3. Statistical & Specialized 2-D Charts ──────────────────────
    GraphicsCase(
        name="chart_stairs_stem",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 860, 420]);
x = 0:12;
y = sin(x * 0.5);
subplot(1, 2, 1); stairs(x, y, 'LineWidth', 1.6); grid on; title('stairs');
subplot(1, 2, 2); stem(x, y, 'filled', 'LineWidth', 1.4); grid on; title('stem filled');
""",
    ),
    GraphicsCase(
        name="chart_scatter_varied",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 820, 460]);
x = linspace(0, 3*pi, 60);
y = sin(x) + 0.25 * cos(3*x);
sz = linspace(20, 140, 60);
c = linspace(1, 10, 60);
scatter(x, y, sz, c, 'filled');
grid on; colorbar; title('Scatter with Variable Size & CData');
""",
    ),
    GraphicsCase(
        name="chart_bar_grouped_stacked",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 920, 380]);
Y = [2 3 5; 4 1 6; 3 5 2; 6 2 4];
subplot(1, 3, 1); bar(Y); grid on; title('bar grouped');
subplot(1, 3, 2); bar(Y, 'stacked'); grid on; title('bar stacked');
subplot(1, 3, 3); barh([1 2 3 4], [5 3 8 4]); grid on; title('barh');
""",
    ),
    GraphicsCase(
        name="chart_histogram",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 780, 460]);
rng(42);
data = randn(1000, 1) * 1.5 + 2.0;
histogram(data, 20, 'FaceColor', [0.00 0.45 0.74], 'FaceAlpha', 0.7);
grid on; xlabel('Value'); ylabel('Count'); title('Histogram (N=1000)');
""",
    ),
    GraphicsCase(
        name="chart_area_patch",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 860, 420]);
x = 1:8;
Y = [1 2 3 2 4 3 5 4; 2 1 2 3 2 4 3 2]';
subplot(1, 2, 1); area(x, Y); grid on; title('area stacked');
subplot(1, 2, 2); hold on; grid on;
patch([0 2 1], [0 0 2], [0.2 0.6 0.9]);
patch([2 4 4 2], [0.5 0.5 2 2], [0.9 0.4 0.2]);
xlim([-0.5 4.5]); ylim([-0.5 2.5]); title('patch polygons');
""",
    ),
    GraphicsCase(
        name="chart_errorbar",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 780, 460]);
x = 1:8;
y = [2.0 3.1 2.7 4.2 3.8 5.0 4.5 5.4];
eneg = [0.3 0.4 0.2 0.5 0.3 0.6 0.4 0.3];
epos = [0.5 0.2 0.4 0.3 0.6 0.4 0.2 0.5];
errorbar(x, y, eneg, epos, 'o-', 'LineWidth', 1.4, 'MarkerFaceColor', [0.00 0.45 0.74]);
grid on; xlabel('Index'); ylabel('Measurement'); title('Asymmetric ErrorBar');
""",
    ),
    GraphicsCase(
        name="chart_quiver",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 700, 520]);
[X, Y] = meshgrid(-2:0.5:2, -2:0.5:2);
U = -Y;
V = X;
quiver(X, Y, U, V, 'LineWidth', 1.2);
axis equal; grid on; title('Quiver Vector Field');
""",
    ),
    GraphicsCase(
        name="chart_contour_and_filled",
        category="charts2d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 880, 420]);
Z = peaks(25);
subplot(1, 2, 1); contour(Z, 10); colorbar; title('contour(peaks(25))');
subplot(1, 2, 2); contourf(Z, 10); colorbar; title('contourf(peaks(25))');
""",
    ),

    # ── 4. Raster, 3-D, Polar & Dual-Y ───────────────────────────────
    GraphicsCase(
        name="raster_imagesc_colorbar",
        category="raster_3d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 760, 500]);
Z = peaks(30);
Z(10:14, 10:14) = NaN;
imagesc([-3 3], [-2 2], Z);
colormap('turbo'); clim([-5 6]); colorbar;
xlabel('X'); ylabel('Y'); title('imagesc + turbo + clim + NaN');
""",
    ),
    GraphicsCase(
        name="raster_imshow_rgb",
        category="raster_3d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 640, 480]);
H = 120; W = 160;
img = zeros(H, W, 3, 'uint8');
[cc, rr] = meshgrid(1:W, 1:H);
img(:,:,1) = uint8(255 * (cc - 1) / (W - 1));
img(:,:,2) = uint8(255 * (rr - 1) / (H - 1));
img(:,:,3) = uint8(180);
img(40:80, 55:105, 1) = 255; img(40:80, 55:105, 2) = 255; img(40:80, 55:105, 3) = 0;
imshow(img); title('imshow uint8 RGB');
""",
    ),
    GraphicsCase(
        name="plot3d_surf_mesh",
        category="raster_3d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 900, 440]);
Z = peaks(18);
subplot(1, 2, 1); surf(Z); title('surf(peaks(18))');
subplot(1, 2, 2); mesh(Z); view(45, 35); title('mesh view(45,35)');
""",
    ),
    GraphicsCase(
        name="plot3d_plot3_spiral",
        category="raster_3d",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 720, 520]);
t = linspace(0, 8*pi, 300);
plot3(cos(t), sin(t), t, 'b-', 'LineWidth', 1.8);
grid on; xlabel('X'); ylabel('Y'); zlabel('Z'); title('3-D Helix plot3');
""",
    ),
    GraphicsCase(
        name="polar_plot_and_opts",
        category="polar_yy",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 700, 540]);
th = linspace(0, 2*pi, 200);
polarplot(th, abs(sin(2*th)), 'LineWidth', 1.8, 'DisplayName', '|sin(2\theta)|');
hold on;
polarplot(th, 0.5 + 0.3*cos(th), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Cardioid');
pax = gca;
pax.ThetaZeroLocation = 'top';
pax.ThetaDir = 'clockwise';
rlim([0 1.2]);
title('PolarPlot Custom Zero/Dir'); legend('Location', 'northeast');
""",
    ),
    GraphicsCase(
        name="yyaxis_dual",
        category="polar_yy",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 820, 480]);
x = linspace(0, 10, 120);
yyaxis left;
plot(x, sin(x), 'LineWidth', 1.6, 'DisplayName', 'Left sin');
ylabel('Left Amplitude'); ylim([-1.5 1.5]);
yyaxis right;
plot(x, 100 * exp(0.2*x), '--', 'LineWidth', 1.6, 'DisplayName', 'Right exp');
ylabel('Right Scale (100..800)'); ylim([0 800]);
grid on; xlabel('Time, s'); title('Dual Y-Axis (yyaxis)'); legend('Location', 'northwest');
""",
    ),

    # ── 5. Typography, TeX, Ticks & Legends ──────────────────────────
    GraphicsCase(
        name="text_cyrillic_tex_subtitle",
        category="text",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 840, 500]);
x = linspace(0, 360, 180);
plot(x, cosd(x), 'LineWidth', 1.6); grid on;
xlim([0 360]); set(gca, 'XTick', 0:60:360);
xlabel('Азимут \theta, град (\tau = 1.5 мс, \lambda = 0.2 м)');
ylabel('Нормированный отклик, дБ');
title('Спектр сигнала (пик: 65.09^\circ, \Delta\omega = 2\pi)');
subtitle('Подзаголовок: проверка кириллицы и символов \alpha, \beta, \Sigma, \Omega');
""",
    ),
    GraphicsCase(
        name="text_multiline_subsuper",
        category="text",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 800, 480]);
x = linspace(0, 5, 100);
plot(x, x.^2, 'LineWidth', 1.6); grid on;
xlabel('Variable x_1 (input)');
ylabel('Output y = x^2 + c_{max}');
title({'First Line of Title', 'Second Line: f(x) = x^2 + \alpha_0'});
""",
    ),
    GraphicsCase(
        name="ticks_custom_format_angle",
        category="text",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 820, 480]);
x = 1:6;
plot(x, [0.12 0.45 0.89 0.34 0.77 0.61], 'o-', 'LineWidth', 1.6); grid on;
set(gca, 'XTick', 1:6, 'XTickLabel', {'Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta'});
xtickangle(45);
ytickformat('%.2f');
ylabel('Probability'); title('Custom Tick Labels, Angle & Format');
""",
    ),
    GraphicsCase(
        name="legend_locations_and_opts",
        category="text",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 900, 420]);
x = linspace(0, 2*pi, 100);
subplot(1, 2, 1); hold on; grid on;
plot(x, sin(x), 'b-', 'LineWidth', 1.5, 'DisplayName', 'Shown A');
plot(x, cos(x), 'r--', 'LineWidth', 1.5, 'DisplayName', 'Shown B');
plot(x, 0*x, 'k:', 'HandleVisibility', 'off');
legend('Location', 'southwest', 'Box', 'off'); title('Box off + HandleVisibility off');

subplot(1, 2, 2); hold on; grid on;
plot(x, sin(x), 'b-', 'LineWidth', 1.5, 'DisplayName', 'Wave 1');
plot(x, 0.5*cos(x), 'g-', 'LineWidth', 1.5, 'DisplayName', 'Wave 2');
plot(pi/2, 1, 'ko', 'MarkerFaceColor', [0 0.45 0.74], 'MarkerSize', 8, 'DisplayName', 'Peak');
legend('Location', 'northoutside'); title('Legend northoutside');
""",
    ),
    GraphicsCase(
        name="annotations_and_data_text",
        category="text",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 800, 480]);
x = linspace(0, 2*pi, 120);
plot(x, sin(x), 'LineWidth', 1.6); grid on; xlim([0 2*pi]); ylim([-1.4 1.4]);
text(pi/2, 1.15, 'Peak (center)', 'HorizontalAlignment', 'center', 'FontSize', 10, 'Color', [0.8 0 0]);
text(0.2, -1.1, 'Left aligned', 'HorizontalAlignment', 'left', 'FontSize', 9);
text(6.0, -1.1, 'Right aligned', 'HorizontalAlignment', 'right', 'FontSize', 9);
annotation('textbox', [0.62, 0.72, 0.25, 0.14], 'String', 'Textbox Note', 'BackgroundColor', [0.95 0.95 0.85]);
title('Data text() & Figure annotation()');
""",
    ),

    # ── 6. Lifecycle & Mutations ─────────────────────────────────────
    GraphicsCase(
        name="mut_live_xdata_ylim",
        category="mutation",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 760, 460]);
x = linspace(0, 2*pi, 80);
h = plot(x, sin(x), 'b-', 'LineWidth', 1.2);
grid on;
h.YData = 2.5 * sin(x) + 1.0;
h.Color = [0.85 0.20 0.15];
h.LineWidth = 2.2;
h.LineStyle = '--';
title('Mutated Line Properties');
""",
    ),
    GraphicsCase(
        name="mut_hold_delete_legend",
        category="mutation",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 780, 460]);
hold on; grid on;
x = linspace(0, 2*pi, 100);
h1 = plot(x, sin(x), 'LineWidth', 1.6, 'DisplayName', 'Keep 1');
h2 = plot(x, cos(x), 'LineWidth', 1.6, 'DisplayName', 'Deleted');
h3 = plot(x, 0.5*sin(2*x), 'LineWidth', 1.6, 'DisplayName', 'Keep 3');
delete(h2);
legend('Location', 'northeast');
title('After delete(h2)');
""",
    ),
    GraphicsCase(
        name="mut_cla_reset_multifig",
        category="mutation",
        code=r"""
f1 = figure('Color', 'w', 'Position', [50, 50, 760, 460]);
plot(1:10, (1:10).^2, 'r-', 'LineWidth', 2); grid on; title('Old Plot');
cla reset;
plot(1:10, sin(1:10), 'b-o', 'LineWidth', 1.5); grid on; title('After cla reset');
f2 = figure('Color', 'w', 'Position', [50, 50, 500, 400]);
plot(1:5, [5 4 3 2 1]);
figure(f1);
""",
    ),

    # ── 7. Edge Cases & Stress ───────────────────────────────────────
    GraphicsCase(
        name="edge_empty_and_constant",
        category="edge",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 900, 360]);
subplot(1, 3, 1); plot([], []); grid on; title('Empty plot');
subplot(1, 3, 2); plot([1 2 3], [NaN NaN NaN]); grid on; title('All NaN');
subplot(1, 3, 3); plot([1 2 3 4], [5 5 5 5], 'LineWidth', 1.6); grid on; title('Constant y=5');
""",
    ),
    GraphicsCase(
        name="edge_log_negative",
        category="edge",
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 760, 460]);
x = linspace(-2, 4, 120);
y = exp(x) - 2.0;
semilogy(x, y, 'LineWidth', 1.6); grid on;
title('semilogy with Negative Values Ignored');
""",
    ),
    GraphicsCase(
        name="stress_100k_points",
        category="stress",
        is_stress=True,
        code=r"""
figure('Color', 'w', 'Position', [50, 50, 860, 460]);
x = linspace(0, 20, 100000);
y = sin(5*x) .* exp(-0.1*x) + 0.15 * cos(47*x);
plot(x, y, 'LineWidth', 1.0); grid on;
xlim([0 20]); ylim([-1.3 1.3]);
xlabel('Time, s'); ylabel('Signal'); title('Stress Test: 100,000 Points');
""",
    ),
]
