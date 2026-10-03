#pragma once

#include "core/SizeNode.h"

#include <QRectF>

#include <vector>

struct TreemapCell
{
    // For an aggregate cell, the folder whose small children it stands for.
    const SizeNode* node = nullptr;
    QRectF rect;
    int depth = 0;
    // Painted cells: files, folders too small to subdivide, and aggregates.
    // The other cells are folders whose children are laid out inside them.
    bool leaf = false;
    // > 0: this cell merges that many of node's children, each too small to
    // show on its own.
    int aggregatedCount = 0;
    qint64 aggregatedSize = 0;

    bool isAggregate() const
    {
        return aggregatedCount > 0;
    }
};

struct TreemapOptions
{
    // A folder whose rectangle is thinner than this is painted as one cell.
    double minSide = 1.0;
    // Children that would get less area than this, or come out thinner than
    // minSide, are merged with every smaller sibling into one cell per folder
    // (when that makes at least two). 0 disables merging.
    double minArea = 0.0;
};

// Row layout in the KDirStat/WinDirStat style: rows (columns, for a tall
// rectangle) filled largest-first from the top left, so size reads in one
// direction throughout. sizes must be positive and sorted descending; the
// returned rectangles are in the same order and tile bounds.
std::vector<QRectF> layoutRows(const std::vector<qint64>& sizes, const QRectF& bounds);

// Lays out the whole subtree of root in pre-order (a folder before its
// descendants). Zero-size nodes get no cell. The leaves tile bounds exactly.
std::vector<TreemapCell> layoutTreemap(const SizeNode& root,
                                       const QRectF& bounds,
                                       const TreemapOptions& options = {});
