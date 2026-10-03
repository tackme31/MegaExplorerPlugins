#include "ui/LoadingView.h"

#include <QEvent>
#include <QHBoxLayout>
#include <QLabel>
#include <QProgressBar>
#include <QPushButton>
#include <QStackedWidget>
#include <QVBoxLayout>

#include <algorithm>

namespace
{

constexpr int kColumnWidth = 320;
constexpr int kControlHeight = 32;

QLabel* makeText(const QString& text = {})
{
    auto* label = new QLabel(text);
    label->setAlignment(Qt::AlignHCenter);
    label->setWordWrap(true);
    return label;
}

// QStackedWidget gives each page the tallest page's height; stretch above and
// below keeps the content in its middle.
QVBoxLayout* pageLayout(QWidget* page)
{
    auto* layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(10);
    layout->addStretch();
    return layout;
}

bool isDark(const QPalette& palette)
{
    return palette.color(QPalette::Window).lightness() < 128;
}

} // namespace

LoadingView::LoadingView(QWidget* parent) : QWidget(parent)
{
    mProgressPage = new QWidget;
    {
        auto* layout = pageLayout(mProgressPage);
        mStage = makeText();
        layout->addWidget(mStage);
        mBar = new QProgressBar;
        mBar->setTextVisible(false);
        mBar->setRange(0, 1);
        layout->addWidget(mBar);
        mDetail = makeText();
        layout->addWidget(mDetail);
        layout->addStretch();
    }

    mErrorPage = new QWidget;
    {
        auto* layout = pageLayout(mErrorPage);
        auto* title = makeText(tr("Couldn't load the folder"));
        QFont font = title->font();
        font.setPointSizeF(font.pointSizeF() * 1.5);
        font.setWeight(QFont::DemiBold);
        title->setFont(font);
        layout->addWidget(title);
        mError = makeText();
        layout->addWidget(mError);
        auto* retry = new QPushButton(tr("Try again"));
        retry->setMinimumHeight(kControlHeight);
        layout->addWidget(retry);
        layout->addStretch();
        connect(retry, &QPushButton::clicked, this, &LoadingView::retryRequested);
    }

    mPages = new QStackedWidget;
    mPages->setFixedWidth(kColumnWidth);
    mPages->addWidget(mProgressPage);
    mPages->addWidget(mErrorPage);

    auto* row = new QHBoxLayout;
    row->addStretch();
    row->addWidget(mPages);
    row->addStretch();
    auto* outer = new QVBoxLayout(this);
    outer->addStretch(2);
    outer->addLayout(row);
    outer->addStretch(3); // a little above centre reads as centred

    updateColors();
}

void LoadingView::showProgress(const QString& stage, const QString& detail, qint64 done, qint64 total)
{
    mStage->setText(stage);
    mDetail->setText(detail);
    mDetail->setVisible(!detail.isEmpty());
    if (total > 0)
    {
        // QProgressBar is int-based; scale so large counts cannot overflow it.
        mBar->setRange(0, 1000);
        mBar->setValue(static_cast<int>(std::clamp<qint64>(done * 1000 / total, 0, 1000)));
    }
    else
    {
        mBar->setRange(0, 0);
    }
    mPages->setCurrentWidget(mProgressPage);
}

void LoadingView::showError(const QString& error)
{
    stopProgress();
    mError->setText(error);
    mPages->setCurrentWidget(mErrorPage);
}

void LoadingView::stopProgress()
{
    mBar->setRange(0, 1);
    mBar->setValue(0);
}

void LoadingView::changeEvent(QEvent* event)
{
    QWidget::changeEvent(event);
    if (event->type() == QEvent::PaletteChange)
    {
        updateColors();
    }
}

void LoadingView::updateColors()
{
    const QPalette& base = palette();
    QPalette caption = base;
    caption.setColor(QPalette::WindowText, base.color(QPalette::PlaceholderText));
    mDetail->setPalette(caption);
    // Windows 11's error red, and a lighter one that keeps its contrast on dark.
    QPalette error = base;
    error.setColor(QPalette::WindowText,
                   isDark(base) ? QColor(0xff, 0x99, 0xa4) : QColor(0xc4, 0x2b, 0x1c));
    mError->setPalette(error);
}
