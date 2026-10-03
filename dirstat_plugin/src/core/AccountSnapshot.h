#pragma once

#include "core/SizeNode.h"

#include <QMetaType>

#include <memory>

struct AccountUsage
{
    qint64 used = -1;  // bytes, -1 = unknown
    qint64 total = -1; // quota in bytes, -1 = unknown
};

struct AccountSnapshot
{
    // Invisible root; its children are the account's top-level trees
    // (Cloud Drive, Rubbish Bin, ...).
    std::unique_ptr<SizeNode> root;
    AccountUsage usage;
};

using SnapshotPtr = std::shared_ptr<const AccountSnapshot>;

Q_DECLARE_METATYPE(SnapshotPtr)
