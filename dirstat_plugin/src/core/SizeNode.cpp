#include "core/SizeNode.h"

#include <QStringList>

#include <algorithm>
#include <utility>

SizeNode* SizeNode::addFolder(QString folderName)
{
    auto child = std::make_unique<SizeNode>();
    child->name = std::move(folderName);
    child->kind = NodeKind::Folder;
    child->parent = this;
    children.push_back(std::move(child));
    return children.back().get();
}

SizeNode* SizeNode::addFile(QString fileName, qint64 fileSize, qint64 fileMtime)
{
    auto child = std::make_unique<SizeNode>();
    child->name = std::move(fileName);
    child->kind = NodeKind::File;
    child->size = fileSize;
    child->fileCount = 1;
    child->mtime = fileMtime;
    child->parent = this;
    children.push_back(std::move(child));
    return children.back().get();
}

QString SizeNode::path() const
{
    QStringList parts;
    // The snapshot root is invisible, so it never contributes a segment.
    for (const SizeNode* n = this; n && n->parent; n = n->parent)
    {
        parts.prepend(n->name);
    }
    return parts.join(QLatin1Char('/'));
}

QString SizeNode::extension() const
{
    if (isFolder())
    {
        return {};
    }
    const qsizetype dot = name.lastIndexOf(QLatin1Char('.'));
    if (dot <= 0 || dot == name.size() - 1)
    {
        return {};
    }
    return name.mid(dot + 1).toLower();
}

void finalizeTree(SizeNode& root)
{
    if (!root.isFolder())
    {
        return;
    }

    qint64 size = 0;
    qint64 files = 0;
    qint64 newest = 0;
    for (auto& child : root.children)
    {
        finalizeTree(*child);
        size += child->size;
        files += child->fileCount;
        newest = std::max(newest, child->mtime);
    }
    root.size = size;
    root.fileCount = files;
    root.mtime = newest;

    std::sort(root.children.begin(),
              root.children.end(),
              [](const std::unique_ptr<SizeNode>& a, const std::unique_ptr<SizeNode>& b) {
                  if (a->size != b->size)
                  {
                      return a->size > b->size;
                  }
                  return a->name.compare(b->name, Qt::CaseInsensitive) < 0;
              });
    for (std::size_t i = 0; i < root.children.size(); ++i)
    {
        root.children[i]->row = static_cast<int>(i);
    }
}

const SizeNode* findSamePath(const SizeNode& root, const SizeNode& folder)
{
    // Names can contain '/', so compare segment lists rather than path().
    QStringList names;
    for (const SizeNode* n = &folder; n->parent; n = n->parent)
    {
        names.prepend(n->name);
    }

    const SizeNode* current = &root;
    for (const QString& name : std::as_const(names))
    {
        const auto it = std::find_if(current->children.cbegin(),
                                     current->children.cend(),
                                     [&name](const std::unique_ptr<SizeNode>& child) {
                                         return child->isFolder() && child->name == name;
                                     });
        if (it == current->children.cend())
        {
            break;
        }
        current = it->get();
    }
    return current;
}
