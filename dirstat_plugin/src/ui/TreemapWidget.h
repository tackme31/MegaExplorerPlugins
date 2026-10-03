#pragma once

#include "core/AccountSnapshot.h"
#include "core/TreemapLayout.h"

#include <QHash>
#include <QImage>
#include <QWidget>

#include <vector>

// Flat treemap of a snapshot, or of one folder of it (the scope): one colour
// per file type, a uniform gap between cells, and anything below kMinCellPx
// grouped into one muted cell. The rendered image is cached and only rebuilt on
// resize, a palette change, a new snapshot or scope; selection is drawn on top.
class TreemapWidget : public QWidget
{
    Q_OBJECT

public:
    explicit TreemapWidget(QWidget* parent = nullptr);

    // Also clears the scope.
    void setSnapshot(SnapshotPtr snapshot);
    // A folder of the current snapshot; nullptr shows the whole account.
    // Colours stay those of the whole account, so they keep their meaning.
    void setScope(const SizeNode* scope);
    void setSelectedNode(const SizeNode* node);

signals:
    // For a merged group of small items, node is the folder holding them.
    void nodeClicked(const SizeNode* node);
    // node is as for nodeClicked, or nullptr when no cell is under the cursor.
    void contextMenuRequested(const SizeNode* node, const QPoint& globalPos);

protected:
    bool event(QEvent* event) override;
    void changeEvent(QEvent* event) override;
    void paintEvent(QPaintEvent* event) override;
    void resizeEvent(QResizeEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void contextMenuEvent(QContextMenuEvent* event) override;

private:
    const TreemapCell* cellAt(const QPoint& pos) const;
    qsizetype selectedCellIndex() const;
    void rebuild();
    void assignColors();
    QRgb baseColor(const SizeNode& node) const;

    SnapshotPtr mSnapshot;
    const SizeNode* mScope = nullptr;
    std::vector<TreemapCell> mCells;
    QHash<const SizeNode*, qsizetype> mCellIndex;
    // Keyed by the folder; a folder has at most one merged group.
    QHash<const SizeNode*, qsizetype> mAggregateIndex;
    QHash<QString, QRgb> mExtensionColors;
    QHash<const SizeNode*, QRgb> mFolderColors;
    QImage mImage;
    const SizeNode* mSelected = nullptr;
    // mSelected is a folder picked through its merged group; outline the group.
    bool mSelectedAggregate = false;
    bool mDirty = true;
};
