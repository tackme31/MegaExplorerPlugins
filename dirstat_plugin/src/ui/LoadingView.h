#pragma once

#include <QWidget>

class QLabel;
class QProgressBar;
class QStackedWidget;

// What the window shows until the first tree arrives: progress, or the error
// with a retry button.
class LoadingView : public QWidget
{
    Q_OBJECT

public:
    explicit LoadingView(QWidget* parent = nullptr);

    // total -1 = unknown (busy indicator).
    void showProgress(const QString& stage, const QString& detail, qint64 done, qint64 total);
    void showError(const QString& error);
    void stopProgress();

signals:
    void retryRequested();

protected:
    void changeEvent(QEvent* event) override;

private:
    void updateColors();

    QStackedWidget* mPages = nullptr;
    QWidget* mProgressPage = nullptr;
    QWidget* mErrorPage = nullptr;
    QLabel* mStage = nullptr;
    QLabel* mDetail = nullptr;
    QProgressBar* mBar = nullptr;
    QLabel* mError = nullptr;
};
