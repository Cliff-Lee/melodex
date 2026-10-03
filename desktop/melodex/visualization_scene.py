            mark = self._memory[index]
            positions[index] = QPointF(
                rect.left() + rect.width() * max(0.0, min(1.0, mark.x)),
                rect.top() + rect.height() * max(0.14, min(0.82, mark.y)),
            )

        # Chronological path: the one line in the view whose meaning is always
        # "what I listened to next".
        if len(ordered_indices) > 1:
            path = QPainterPath(positions[ordered_indices[0]])
            for position_index, index in enumerate(ordered_indices[1:], start=1):
                previous = positions[ordered_indices[position_index - 1]]
                current = positions[index]
                mid_x = (previous.x() + current.x()) * 0.5
                path.cubicTo(
                    QPointF(mid_x, previous.y()),
                    QPointF(mid_x, current.y()),
                    current,
                )
            trail = QColor(self._color(0))
            trail.setAlpha(30)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(trail, 1.15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)

        active_index = self._active_memory_index()
        hit: list[tuple[QPointF, int, float]] = []
        max_count = max(mark.count for mark in self._memory)

        # Each group becomes a small luminous island. Horizontal width shows the
        # actual time span of that group; area/brightness reflect play count.
        #
        # Dense history can contain ~100 groups, so only the active island pays
        # for a radial-gradient glow. The rest use two cheap alpha-composited
        # ellipses. This preserves the same semantic hierarchy without making a
        # static history view an unexpectedly expensive paint.
        draw_indices = list(range(len(self._memory)))
        if active_index is not None and 0 <= active_index < len(self._memory):
            draw_indices.remove(active_index)
            draw_indices.insert(0, active_index)
        for index in draw_indices:
            mark = self._memory[index]
            point = positions[index]
            active = index == active_index
            count_scale = math.sqrt(max(1, mark.count) / max(1, max_count))
            radius_y = 7.0 + 11.0 * count_scale
            span_width = rect.width() * mark.span
            radius_x = max(
                radius_y * 1.20,
                min(rect.width() * 0.13, span_width * 0.5 + radius_y * 0.80),
            )

            color = QColor.fromHsv(mark.hue, 145, 242)
            if active:
                self._draw_glow(
                    painter,
                    point,
                    max(radius_x, radius_y) * 2.4,
                    color,
                    46,
                )
                island = QRadialGradient(point, max(radius_x, radius_y))
                core = QColor(color)
                core.setAlpha(190)
                edge = QColor(color)
                edge.setAlpha(48)
                fade = QColor(color)
                fade.setAlpha(0)
                island.setColorAt(0.0, core)
                island.setColorAt(0.62, edge)
                island.setColorAt(1.0, fade)
                painter.setPen(Qt.NoPen)
                painter.setBrush(island)
                painter.drawEllipse(
                    QRectF(
                        point.x() - radius_x,
                        point.y() - radius_y,
                        radius_x * 2,
                        radius_y * 2,
                    )
                )
            else:
                outer = QColor(color)
                outer.setAlpha(16 + int(18 * count_scale))
                painter.setPen(Qt.NoPen)
                painter.setBrush(outer)
                painter.drawEllipse(
                    QRectF(
                        point.x() - radius_x,
                        point.y() - radius_y,
                        radius_x * 2,
                        radius_y * 2,
                    )
                )

                inner = QColor(color)
                inner.setAlpha(44 + int(48 * count_scale))
                painter.setBrush(inner)
                painter.drawEllipse(
                    QRectF(
                        point.x() - radius_x * 0.58,
                        point.y() - radius_y * 0.58,
                        radius_x * 1.16,
                        radius_y * 1.16,
                    )
                )

            outline = QColor("#eef6ff")
            outline.setAlpha(175 if active else 46 + int(38 * count_scale))
            painter.setPen(QPen(outline, 1.15 if active else 0.65))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                QRectF(
                    point.x() - radius_x * 0.62,
                    point.y() - radius_y * 0.62,
                    radius_x * 1.24,
                    radius_y * 1.24,
                )
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(247, 251, 255, 185 if active else 95))
            painter.drawEllipse(point, 1.8 + 1.2 * count_scale, 1.8 + 1.2 * count_scale)

            hit.append((point, index, max(18.0, radius_x)))

        self._memory_hit_points = tuple(hit)

        # Sparse labels only; hover provides the detail card.
        step = max(1, len(self._memory) // 8)
        for ordinal, index in enumerate(ordered_indices):
            if index == active_index or ordinal % step != 0:
                continue
            mark = self._memory[index]