#pragma once

#include "core/IAccountSource.h"

#include <QMainWindow>

class LoadingView;
class QLabel;
class QProgressBar;
class QSplitter;
class QStackedWidget;
class QToolBar;
class QTreeView;
class SizeTreeModel;
class TreemapWidget;

// Tree on top, treemap below, split by a QSplitter. Until the first snapshot
// arrives, LoadingView takes the whole window instead.
class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(IAccountSource& source, QWidget* parent = nullptr);

    // Starts the first load.
    void start();

    // A short note in the status bar, e.g. why "Show in MEGA Explorer" failed.
    void showMessage(const QString& text);

signals:
    // The user asked to see this item in MEGA Explorer.
    void revealRequested(const QString& handle);
    void closed();

protected:
    void changeEvent(QEvent* event) override;
    void closeEvent(QCloseEvent* event) override;

private:
    void showLoadingView();
    void showTreeView();
    void reload();
    void onProgress(const QString& stage, const QString& detail, qint64 done, qint64 total);
    void onLoaded(SnapshotPtr snapshot);
    void onFailed(const QString& error);
    void onCurrentChanged(const QModelIndex& current);
    void onTreemapClicked(const SizeNode* node);
    void showContextMenu(const SizeNode* node, const QPoint& globalPos);
    void reveal(const SizeNode* node);
    // scope: nullptr for everything loaded. select (optional) is selected
    // afterwards, e.g. the folder just left when going up.
    void setScope(const SizeNode* scope, const SizeNode* select = nullptr);
    void scopeUp(int levels);
    void updateScopeBar();
    void updateTitle(const SizeNode& root);

    IAccountSource& mSource;
    bool mHasSnapshot = false;
    // Points into the snapshot the model and treemap hold.
    const SizeNode* mScope = nullptr;

    QStackedWidget* mPages = nullptr;
    LoadingView* mLoadingView = nullptr;
    QSplitter* mSplitter = nullptr;
    SizeTreeModel* mModel = nullptr;
    QTreeView* mTree = nullptr;
    TreemapWidget* mTreemap = nullptr;
    QToolBar* mToolBar = nullptr;
    QLabel* mStatusLabel = nullptr;
    QProgressBar* mProgressBar = nullptr;
    QAction* mReloadAction = nullptr;
    QAction* mUpAction = nullptr;
    QLabel* mBreadcrumb = nullptr;
};
