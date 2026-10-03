#pragma once

#include "core/IAccountSource.h"
#include "core/TreeBuilder.h"

#include <QElapsedTimer>
#include <QStringList>

class RpcChannel;

// Reads the folders the user right-clicked, and everything below them, from
// MEGA Explorer's in-memory tree (items.get + items.descendants). Never reaches
// MEGA's servers.
class PluginAccountSource : public IAccountSource
{
    Q_OBJECT

public:
    PluginAccountSource(RpcChannel& rpc, QStringList rootHandles, QObject* parent = nullptr);

    void load() override;

private:
    void readRoots();
    void readPage(const QString& cursor);
    void fail(const QString& error);
    void reportProgress();

    RpcChannel& mRpc;
    const QStringList mRootHandles;
    TreeBuilder mBuilder;
    int mRootIndex = 0;
    // A load superseded by a newer one drops its late responses.
    int mGeneration = 0;
    QElapsedTimer mSinceProgress;
};
