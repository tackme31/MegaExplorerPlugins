#include "ui/TreemapWidget.h"

#include <QContextMenuEvent>
#include <QHelpEvent>
#include <QLocale>
#include <QMouseEvent>
#include <QPainter>
#include <QToolTip>

#include <algorithm>
#include <array>
#include <climits>
#include <cmath>

namespace
{

// Flat fills, mid-tone enough to read on both light and dark backgrounds.
constexpr std::array<QRgb, 12> kPalette = {
    qRgb(0x3B, 0x82, 0xF6), // blue
    qRgb(0x10, 0xB9, 0x81), // emerald
    qRgb(0xF5, 0x9E, 0x0B), // amber
    qRgb(0xF4, 0x3F, 0x5E), // rose
    qRgb(0x8B, 0x5C, 0xF6), // violet
    qRgb(0x06, 0xB6, 0xD4), // cyan
    qRgb(0xF9, 0x73, 0x16), // orange
    qRgb(0x84, 0xCC, 0x16), // lime
    qRgb(0xEC, 0x48, 0x99), // pink
    qRgb(0x14, 0xB8, 0xA6), // teal
    qRgb(0x63, 0x66, 0xF1), // indigo
    qRgb(0xEA, 0xB3, 0x08), // yellow
};
constexpr QRgb kOtherFiles = qRgb(0x94, 0xA3, 0xB8);
// Folders too small to subdivide and merged groups of small items are painted
// as their folder's main extension blended halfway towards this.
constexpr QRgb kGrouped = qRgb(0x64, 0x74, 0x8B);

// Logical px: anything thinner, or smaller than this squared, is grouped.
constexpr double kMinCellPx = 8.0;

QRgb muted(QRgb c)
{
    return qRgb((qRed(c) + qRed(kGrouped)) / 2,
                (qGreen(c) + qGreen(kGrouped)) / 2,
                (qBlue(c) + qBlue(kGrouped)) / 2);
}

// Returns the bytes per extension in folder's subtree, and records each
// folder's largest extension (by bytes) in mainExtension.
QHash<QString, qint64> collectExtensionBytes(const SizeNode& folder,
                                             QHash<const SizeNode*, QString>& mainExtension)
{
    QHash<QString, qint64> bytes;
    for (const auto& child : folder.children)
    {
        if (child->isFolder())
        {
            const QHash<QString, qint64> sub = collectExtensionBytes(*child, mainExtension);
            for (auto it = sub.cbegin(); it != sub.cend(); ++it)
            {
                bytes[it.key()] += it.value();
            }
        }
        else
        {
            bytes[child->extension()] += child->size;
        }
    }

    auto best = bytes.cend();
    for (auto it = bytes.cbegin(); it != bytes.cend(); ++it)
    {
        if (best == bytes.cend() || it.value() > best.value() ||
            (it.value() == best.value() && it.key() < best.key()))
        {
            best = it;
        }
    }
    if (best != bytes.cend())
    {
        mainExtension.insert(&folder, best.key());
    }
    return bytes;
}

// Rounds both edges independently, so neighbours that share a float edge also
// share the pixel edge and nothing overlaps or leaves a hole.
QRect snapped(const QRectF& r)
{
    const int x0 = static_cast<int>(std::lround(r.left()));
    const int y0 = static_cast<int>(std::lround(r.top()));
    const int x1 = static_cast<int>(std::lround(r.right()));
    const int y1 = static_cast<int>(std::lround(r.bottom()));
    return QRect(x0, y0, x1 - x0, y1 - y0);
}

} // namespace

TreemapWidget::TreemapWidget(QWidget* parent) : QWidget(parent)
{
    setAttribute(Qt::WA_OpaquePaintEvent);
    setMinimumSize(80, 60);
}

void TreemapWidget::setSnapshot(SnapshotPtr snapshot)
{
    mSnapshot = std::move(snapshot);
    mScope = nullptr;
    mSelected = nullptr;
    mSelectedAggregate = false;
    assignColors();
    mDirty = true;
    update();
}

void TreemapWidget::setScope(const SizeNode* scope)
{
    if (scope == mScope)
    {
        return;
    }
    mScope = scope;
    mSelected = nullptr;
    mSelectedAggregate = false;
    mDirty = true;
    update();
}

void TreemapWidget::setSelectedNode(const SizeNode* node)
{
    // The tree echoes a click on a merged group back as its folder; returning
    // here keeps the outline on the group instead of the whole folder.
    if (node == mSelected)
    {
        return;
    }
    mSelected = node;
    mSelectedAggregate = false;
    update();
}

const TreemapCell* TreemapWidget::cellAt(const QPoint& pos) const
{
    const QPointF p = QPointF(pos) * devicePixelRatioF();
    for (const TreemapCell& cell : mCells)
    {
        if (cell.leaf && cell.rect.contains(p))
        {
            return &cell;
        }
    }
    return nullptr;
}

bool TreemapWidget::event(QEvent* event)
{
    if (event->type() == QEvent::ToolTip)
    {
        const auto* help = static_cast<QHelpEvent*>(event);
        if (const TreemapCell* cell = cellAt(help->pos()))
        {
            const QLocale locale;
            const SizeNode& node = *cell->node;
            QString text;
            if (cell->isAggregate())
            {
                text = tr("%n small item(s) in %1", nullptr, cell->aggregatedCount).arg(node.path()) +
                       QLatin1Char('\n') + locale.formattedDataSize(cell->aggregatedSize);
            }
            else if (node.isFolder())
            {
                // A folder cell is one too small to subdivide; say so, or it
                // passes for a single large file.
                const int files = static_cast<int>(std::min<qint64>(node.fileCount, INT_MAX));
                text = node.path() + QLatin1Char('\n') +
                       tr("Folder, %Ln file(s), %1", nullptr, files)
                           .arg(locale.formattedDataSize(node.size));
            }
            else
            {
                text = node.path() + QLatin1Char('\n') + locale.formattedDataSize(node.size);
            }
            QToolTip::showText(help->globalPos(), text, this);
        }
        else
        {
            QToolTip::hideText();
        }
        return true;
    }
    return QWidget::event(event);
}

void TreemapWidget::changeEvent(QEvent* event)
{
    if (event->type() == QEvent::PaletteChange)
    {
        mDirty = true;
        update();
    }
    QWidget::changeEvent(event);
}

void TreemapWidget::paintEvent(QPaintEvent*)
{
    if (mDirty)
    {
        rebuild();
    }

    QPainter painter(this);
    if (mImage.isNull())
    {
        painter.fillRect(rect(), palette().color(QPalette::Window));
        return;
    }
    painter.drawImage(QPointF(0, 0), mImage);

    if (mSelected)
    {
        const qsizetype index = selectedCellIndex();
        if (index >= 0)
        {
            const qreal dpr = devicePixelRatioF();
            const QRectF r = mCells[static_cast<std::size_t>(index)].rect;
            const QRectF logical(r.topLeft() / dpr, r.size() / dpr);
            painter.setRenderHint(QPainter::Antialiasing);
            painter.setBrush(Qt::NoBrush);
            painter.setPen(QPen(palette().color(QPalette::Base), 4));
            painter.drawRect(logical.adjusted(2, 2, -2, -2));
            painter.setPen(QPen(palette().color(QPalette::Highlight), 2));
            painter.drawRect(logical.adjusted(2, 2, -2, -2));
        }
    }
}

qsizetype TreemapWidget::selectedCellIndex() const
{
    // After a resize the folder may no longer have a merged group; then the
    // folder itself is outlined.
    if (mSelectedAggregate)
    {
        const auto it = mAggregateIndex.constFind(mSelected);
        if (it != mAggregateIndex.cend())
        {
            return *it;
        }
    }
    const auto it = mCellIndex.constFind(mSelected);
    return it != mCellIndex.cend() ? *it : -1;
}

void TreemapWidget::resizeEvent(QResizeEvent* event)
{
    mDirty = true;
    QWidget::resizeEvent(event);
}

void TreemapWidget::mousePressEvent(QMouseEvent* event)
{
    // Right-click selects too, like an item view, so the context menu visibly
    // applies to the cell under the cursor.
    if (event->button() == Qt::LeftButton || event->button() == Qt::RightButton)
    {
        if (const TreemapCell* cell = cellAt(event->position().toPoint()))
        {
            // Set before emitting, so the tree's echo finds it already selected.
            mSelected = cell->node;
            mSelectedAggregate = cell->isAggregate();
            update();
            emit nodeClicked(cell->node);
        }
    }
    QWidget::mousePressEvent(event);
}

void TreemapWidget::contextMenuEvent(QContextMenuEvent* event)
{
    const TreemapCell* cell = cellAt(event->pos());
    emit contextMenuRequested(cell ? cell->node : nullptr, event->globalPos());
}

void TreemapWidget::rebuild()
{
    mDirty = false;
    mCells.clear();
    mCellIndex.clear();
    mAggregateIndex.clear();
    mImage = QImage();
    if (!mSnapshot || !mSnapshot->root)
    {
        return;
    }

    // Laid out and rendered in device pixels, so HiDPI screens get full detail.
    const qreal dpr = devicePixelRatioF();
    const QSize pixels = (QSizeF(size()) * dpr).toSize();
    if (pixels.isEmpty())
    {
        return;
    }

    TreemapOptions options;
    options.minSide = kMinCellPx * dpr;
    options.minArea = options.minSide * options.minSide;
    const SizeNode& top = mScope ? *mScope : *mSnapshot->root;
    mCells = layoutTreemap(top, QRectF(QPointF(0, 0), QSizeF(pixels)), options);
    mCellIndex.reserve(static_cast<qsizetype>(mCells.size()));
    for (std::size_t i = 0; i < mCells.size(); ++i)
    {
        // An aggregate's node is its parent folder, which has a cell of its own.
        auto& index = mCells[i].isAggregate() ? mAggregateIndex : mCellIndex;
        index.insert(mCells[i].node, static_cast<qsizetype>(i));
    }

    const int gap = std::max(1, static_cast<int>(std::lround(dpr)));

    mImage = QImage(pixels, QImage::Format_RGB32);
    mImage.fill(palette().color(QPalette::Window));
    QPainter painter(&mImage);
    painter.setPen(Qt::NoPen);
    for (const TreemapCell& cell : mCells)
    {
        if (!cell.leaf)
        {
            continue;
        }
        QRect r = snapped(cell.rect);
        // The gap goes on the right and bottom only, so each boundary between
        // two neighbours gets exactly one. Cells too thin to spare it keep it.
        if (r.width() > 2 * gap)
        {
            r.setWidth(r.width() - gap);
        }
        if (r.height() > 2 * gap)
        {
            r.setHeight(r.height() - gap);
        }
        if (r.isEmpty())
        {
            continue;
        }
        painter.fillRect(r, QColor(baseColor(*cell.node)));
    }
    painter.end();
    mImage.setDevicePixelRatio(dpr);
}

void TreemapWidget::assignColors()
{
    mExtensionColors.clear();
    mFolderColors.clear();
    if (!mSnapshot || !mSnapshot->root)
    {
        return;
    }

    // The extensions taking the most bytes get the distinct colours.
    QHash<const SizeNode*, QString> mainExtension;
    const QHash<QString, qint64> bytes = collectExtensionBytes(*mSnapshot->root, mainExtension);

    std::vector<std::pair<qint64, QString>> ranked;
    ranked.reserve(static_cast<std::size_t>(bytes.size()));
    for (auto it = bytes.cbegin(); it != bytes.cend(); ++it)
    {
        if (!it.key().isEmpty())
        {
            ranked.emplace_back(it.value(), it.key());
        }
    }
    std::sort(ranked.begin(), ranked.end(), [](const auto& a, const auto& b) {
        return a.first != b.first ? a.first > b.first : a.second < b.second;
    });
    for (std::size_t i = 0; i < ranked.size() && i < kPalette.size(); ++i)
    {
        mExtensionColors.insert(ranked[i].second, kPalette[i]);
    }

    mFolderColors.reserve(mainExtension.size());
    for (auto it = mainExtension.cbegin(); it != mainExtension.cend(); ++it)
    {
        mFolderColors.insert(it.key(), muted(mExtensionColors.value(it.value(), kOtherFiles)));
    }
}

QRgb TreemapWidget::baseColor(const SizeNode& node) const
{
    // A folder only gets painted as a whole, or as the owner of a merged group.
    if (node.isFolder())
    {
        return mFolderColors.value(&node, kGrouped);
    }
    return mExtensionColors.value(node.extension(), kOtherFiles);
}
