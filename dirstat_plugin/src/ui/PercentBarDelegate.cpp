#include "ui/PercentBarDelegate.h"

#include "ui/SizeTreeModel.h"

#include <QApplication>
#include <QPainter>

#include <algorithm>
#include <array>
#include <cmath>

namespace
{

constexpr std::array<QRgb, 6> kDepthColors = {
    qRgb(0x5A, 0x7C, 0xE0),
    qRgb(0xD9, 0x5B, 0x5B),
    qRgb(0x4F, 0xB0, 0x5E),
    qRgb(0xD0, 0xA6, 0x3A),
    qRgb(0x9B, 0x6B, 0xD1),
    qRgb(0x3A, 0xAE, 0xB5),
};

constexpr int kBarWidth = 64;

} // namespace

void PercentBarDelegate::paint(QPainter* painter,
                               const QStyleOptionViewItem& option,
                               const QModelIndex& index) const
{
    QStyleOptionViewItem opt(option);
    initStyleOption(&opt, index);
    const QString text = opt.text;
    opt.text.clear();
    const QStyle* style = opt.widget ? opt.widget->style() : QApplication::style();
    style->drawControl(QStyle::CE_ItemViewItem, &opt, painter, opt.widget);

    const double fraction = std::clamp(index.data(SizeTreeModel::FractionRole).toDouble(), 0.0, 1.0);
    const int depth = index.data(SizeTreeModel::DepthRole).toInt();

    const QRect cell = opt.rect.adjusted(4, 3, -4, -3);
    const QRect bar(cell.left(), cell.top(), std::min(kBarWidth, cell.width() / 2), cell.height());

    painter->save();
    painter->setPen(opt.palette.color(QPalette::Mid));
    painter->setBrush(Qt::NoBrush);
    painter->drawRect(bar.adjusted(0, 0, -1, -1));
    const int filled = static_cast<int>(std::lround((bar.width() - 2) * fraction));
    if (filled > 0)
    {
        painter->fillRect(QRect(bar.left() + 1, bar.top() + 1, filled, bar.height() - 2),
                          QColor(kDepthColors[static_cast<std::size_t>(depth) % kDepthColors.size()]));
    }

    const bool selected = opt.state & QStyle::State_Selected;
    painter->setPen(opt.palette.color(selected ? QPalette::HighlightedText : QPalette::Text));
    const QRect textRect(bar.right() + 4, cell.top(), cell.right() - bar.right() - 4, cell.height());
    painter->drawText(textRect, Qt::AlignRight | Qt::AlignVCenter, text);
    painter->restore();
}

QSize PercentBarDelegate::sizeHint(const QStyleOptionViewItem& option, const QModelIndex& index) const
{
    QSize size = QStyledItemDelegate::sizeHint(option, index);
    size.setWidth(size.width() + kBarWidth + 12);
    return size;
}
