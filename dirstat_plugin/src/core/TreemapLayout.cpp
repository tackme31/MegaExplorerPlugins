#include "core/TreemapLayout.h"

#include <algorithm>
#include <numeric>

namespace
{

// A row is closed before its newest (and so narrowest) member would come out
// narrower than this fraction of the row's thickness.
constexpr double kMinAspect = 0.4;

void layoutNode(const SizeNode& node,
                const QRectF& rect,
                int depth,
                const TreemapOptions& options,
                std::vector<TreemapCell>& out)
{
    const bool subdivide = node.isFolder() && node.size > 0 && !node.children.empty() &&
                           rect.width() >= options.minSide && rect.height() >= options.minSide;
    if (!subdivide)
    {
        out.push_back({&node, rect, depth, true});
        return;
    }

    // Children are sorted descending, so the zero-size ones and then the
    // too-small ones each form a suffix.
    std::size_t count = 0;
    while (count < node.children.size() && node.children[count]->size > 0)
    {
        ++count;
    }
    const double scale = rect.width() * rect.height() / static_cast<double>(node.size);
    std::size_t keep = count;
    if (options.minArea > 0)
    {
        while (keep > 0 &&
               static_cast<double>(node.children[keep - 1]->size) * scale < options.minArea)
        {
            --keep;
        }
        // Merging a single child would only rename it.
        if (count - keep < 2)
        {
            keep = count;
        }
    }
    constexpr std::size_t kAggregate = static_cast<std::size_t>(-1);
    struct Entry
    {
        qint64 size;
        std::size_t child;
    };
    std::vector<Entry> entries;
    std::vector<QRectF> rects;
    qint64 mergedSize = 0;

    // An area above minArea can still come out as a sliver. When a kept child
    // does, merge it and everything smaller too, and lay out again; keep only
    // shrinks, so this ends.
    for (;;)
    {
        if (keep == 0)
        {
            out.push_back({&node, rect, depth, true});
            return;
        }

        entries.clear();
        for (std::size_t i = 0; i < keep; ++i)
        {
            entries.push_back({node.children[i]->size, i});
        }
        mergedSize = 0;
        for (std::size_t i = keep; i < count; ++i)
        {
            mergedSize += node.children[i]->size;
        }
        if (keep < count)
        {
            entries.push_back({mergedSize, kAggregate});
            std::stable_sort(entries.begin(), entries.end(), [](const Entry& a, const Entry& b) {
                return a.size > b.size;
            });
        }

        std::vector<qint64> sizes;
        sizes.reserve(entries.size());
        for (const Entry& e : entries)
        {
            sizes.push_back(e.size);
        }
        rects = layoutRows(sizes, rect);

        if (options.minArea <= 0)
        {
            break;
        }
        std::size_t firstThin = keep;
        for (std::size_t i = 0; i < entries.size(); ++i)
        {
            const bool thin = std::min(rects[i].width(), rects[i].height()) < options.minSide;
            if (thin && entries[i].child != kAggregate)
            {
                firstThin = std::min(firstThin, entries[i].child);
            }
        }
        if (firstThin == keep || count - firstThin < 2)
        {
            break;
        }
        keep = firstThin;
    }

    out.push_back({&node, rect, depth, false});
    for (std::size_t i = 0; i < rects.size(); ++i)
    {
        if (entries[i].child == kAggregate)
        {
            out.push_back({&node, rects[i], depth + 1, true, static_cast<int>(count - keep), mergedSize});
        }
        else
        {
            layoutNode(*node.children[entries[i].child], rects[i], depth + 1, options, out);
        }
    }
}

} // namespace

std::vector<QRectF> layoutRows(const std::vector<qint64>& sizes, const QRectF& bounds)
{
    const std::size_t n = sizes.size();
    std::vector<QRectF> out(n);
    const double total = std::accumulate(sizes.begin(), sizes.end(), 0.0, [](double acc, qint64 v) {
        return acc + static_cast<double>(v);
    });
    if (n == 0 || total <= 0 || bounds.width() <= 0 || bounds.height() <= 0)
    {
        return out;
    }

    // One direction per folder: a wide rectangle gets rows stacked top to
    // bottom, a tall one columns placed left to right.
    const bool horizontalRows = bounds.width() >= bounds.height();
    const double lineLength = horizontalRows ? bounds.width() : bounds.height();
    const double stackDepth = horizontalRows ? bounds.height() : bounds.width();
    const double lineStart = horizontalRows ? bounds.left() : bounds.top();
    const double lineEnd = horizontalRows ? bounds.right() : bounds.bottom();
    const double stackEnd = horizontalRows ? bounds.bottom() : bounds.right();
    double rowPos = horizontalRows ? bounds.top() : bounds.left();

    std::size_t begin = 0;
    while (begin < n)
    {
        double rowSum = static_cast<double>(sizes[begin]);
        std::size_t end = begin + 1;
        while (end < n)
        {
            const double candidateSum = rowSum + static_cast<double>(sizes[end]);
            const double thickness = stackDepth * candidateSum / total;
            const double length = lineLength * static_cast<double>(sizes[end]) / candidateSum;
            if (length < kMinAspect * thickness)
            {
                break;
            }
            rowSum = candidateSum;
            ++end;
        }

        // The last row, and the last cell of each row, take whatever is left,
        // so float drift never opens a gap.
        const double thickness = end == n ? stackEnd - rowPos : stackDepth * rowSum / total;
        double pos = lineStart;
        for (std::size_t i = begin; i < end; ++i)
        {
            const double next =
                i + 1 == end ? lineEnd : pos + lineLength * static_cast<double>(sizes[i]) / rowSum;
            out[i] = horizontalRows ? QRectF(pos, rowPos, next - pos, thickness)
                                    : QRectF(rowPos, pos, thickness, next - pos);
            pos = next;
        }
        rowPos += thickness;
        begin = end;
    }
    return out;
}

std::vector<TreemapCell> layoutTreemap(const SizeNode& root,
                                       const QRectF& bounds,
                                       const TreemapOptions& options)
{
    std::vector<TreemapCell> cells;
    if (root.size <= 0 || bounds.width() <= 0 || bounds.height() <= 0)
    {
        return cells;
    }
    cells.reserve(static_cast<std::size_t>(std::min<qint64>(root.fileCount, 1'000'000)) + 64);
    layoutNode(root, bounds, 0, options, cells);
    return cells;
}
