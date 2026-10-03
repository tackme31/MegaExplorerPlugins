#pragma once

#include <QStyledItemDelegate>

// Paints SizeTreeModel's FractionRole as a bar, coloured by tree depth like
// WinDirStat's subtree-percentage column.
class PercentBarDelegate : public QStyledItemDelegate
{
    Q_OBJECT

public:
    using QStyledItemDelegate::QStyledItemDelegate;

    void paint(QPainter* painter,
               const QStyleOptionViewItem& option,
               const QModelIndex& index) const override;
    QSize sizeHint(const QStyleOptionViewItem& option, const QModelIndex& index) const override;
};
