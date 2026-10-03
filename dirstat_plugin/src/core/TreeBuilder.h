#pragma once

#include "core/AccountSnapshot.h"

#include <QHash>
#include <QJsonObject>
#include <QString>

#include <memory>

// Assembles a snapshot from plugin-API Items: each selected folder becomes a
// top-level node, and items.descendants pages are fed in as they arrive.
class TreeBuilder
{
public:
    TreeBuilder();

    void addRoot(const QString& handle, const QString& name);

    // An Item with at least handle, name, type and parent (size and mtime for
    // files). items.descendants is pre-order, so a parent always precedes its
    // children; an item whose parent is unknown is dropped and false returned.
    bool addItem(const QJsonObject& item);

    qint64 itemCount() const
    {
        return mItemCount;
    }

    // Finalizes the tree; the builder is empty afterwards.
    SnapshotPtr take();

private:
    std::unique_ptr<SizeNode> mRoot;
    QHash<QString, SizeNode*> mFolders;
    qint64 mItemCount = 0;
};
