#include "plugin/PluginAccountSource.h"

#include "plugin/RpcChannel.h"

#include <QJsonArray>
#include <QLocale>

namespace
{

constexpr int kPageLimit = 1000; // the most items.descendants hands out per page
constexpr int kNotFound = -32002;

QString errorText(const RpcChannel::Error& error)
{
    if (error.code == kNotFound)
    {
        return QObject::tr("The folder no longer exists.");
    }
    return error.message;
}

} // namespace

PluginAccountSource::PluginAccountSource(RpcChannel& rpc, QStringList rootHandles, QObject* parent)
    : IAccountSource(parent), mRpc(rpc), mRootHandles(std::move(rootHandles))
{
}

void PluginAccountSource::load()
{
    ++mGeneration;
    mBuilder = TreeBuilder();
    mRootIndex = 0;
    emit progress(tr("Reading the folder list…"), {}, 0, -1);
    mSinceProgress.start();
    readRoots();
}

void PluginAccountSource::readRoots()
{
    QJsonArray handles;
    for (const QString& handle : mRootHandles)
    {
        handles.append(handle);
    }
    const QJsonObject params{{QLatin1String("handles"), handles},
                             {QLatin1String("fields"), QJsonArray{QLatin1String("name")}}};
    const int generation = mGeneration;
    mRpc.request(QStringLiteral("items.get"),
                 params,
                 [this, generation](const QJsonValue& result, const RpcChannel::Error* error) {
                     if (generation != mGeneration)
                     {
                         return;
                     }
                     if (error)
                     {
                         fail(errorText(*error));
                         return;
                     }
                     const QJsonArray items = result[QLatin1String("items")].toArray();
                     for (const QJsonValue& item : items)
                     {
                         mBuilder.addRoot(item[QLatin1String("handle")].toString(),
                                          item[QLatin1String("name")].toString());
                     }
                     readPage({});
                 });
}

void PluginAccountSource::readPage(const QString& cursor)
{
    if (mRootIndex >= mRootHandles.size())
    {
        emit loaded(mBuilder.take());
        return;
    }
    QJsonObject params{
        {QLatin1String("handle"), mRootHandles.at(mRootIndex)},
        {QLatin1String("limit"), kPageLimit},
        {QLatin1String("fields"),
         QJsonArray{QLatin1String("name"),
                    QLatin1String("type"),
                    QLatin1String("parent"),
                    QLatin1String("size"),
                    QLatin1String("mtime")}},
    };
    if (!cursor.isEmpty())
    {
        params.insert(QLatin1String("cursor"), cursor);
    }
    const int generation = mGeneration;
    mRpc.request(QStringLiteral("items.descendants"),
                 params,
                 [this, generation](const QJsonValue& result, const RpcChannel::Error* error) {
                     if (generation != mGeneration)
                     {
                         return;
                     }
                     if (error)
                     {
                         fail(errorText(*error));
                         return;
                     }
                     const QJsonArray items = result[QLatin1String("items")].toArray();
                     for (const QJsonValue& item : items)
                     {
                         mBuilder.addItem(item.toObject());
                     }
                     reportProgress();
                     const QJsonValue next = result[QLatin1String("nextCursor")];
                     if (next.isString())
                     {
                         readPage(next.toString());
                         return;
                     }
                     ++mRootIndex;
                     readPage({});
                 });
}

void PluginAccountSource::reportProgress()
{
    // Pages arrive far faster than anyone can read; a few updates a second is plenty.
    if (mSinceProgress.elapsed() < 100)
    {
        return;
    }
    mSinceProgress.restart();
    emit progress(tr("Reading the folder list…"),
                  tr("%1 items").arg(QLocale().toString(mBuilder.itemCount())),
                  mBuilder.itemCount(),
                  -1);
}

void PluginAccountSource::fail(const QString& error)
{
    ++mGeneration;
    mBuilder = TreeBuilder();
    emit failed(error);
}
