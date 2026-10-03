#include "core/TreeBuilder.h"

TreeBuilder::TreeBuilder() : mRoot(std::make_unique<SizeNode>())
{
    mRoot->kind = NodeKind::Folder;
}

void TreeBuilder::addRoot(const QString& handle, const QString& name)
{
    SizeNode* node = mRoot->addFolder(name);
    node->handle = handle;
    mFolders.insert(handle, node);
}

bool TreeBuilder::addItem(const QJsonObject& item)
{
    SizeNode* parent = mFolders.value(item.value(QLatin1String("parent")).toString());
    if (!parent)
    {
        return false;
    }
    const QString handle = item.value(QLatin1String("handle")).toString();
    const QString name = item.value(QLatin1String("name")).toString();
    SizeNode* node = nullptr;
    if (item.value(QLatin1String("type")).toString() == QLatin1String("folder"))
    {
        node = parent->addFolder(name);
        mFolders.insert(handle, node);
    }
    else
    {
        node = parent->addFile(name,
                               item.value(QLatin1String("size")).toInteger(),
                               item.value(QLatin1String("mtime")).toInteger());
    }
    node->handle = handle;
    ++mItemCount;
    return true;
}

SnapshotPtr TreeBuilder::take()
{
    auto snapshot = std::make_shared<AccountSnapshot>();
    snapshot->root = std::move(mRoot);
    finalizeTree(*snapshot->root);

    mRoot = std::make_unique<SizeNode>();
    mRoot->kind = NodeKind::Folder;
    mFolders.clear();
    mItemCount = 0;
    return snapshot;
}
