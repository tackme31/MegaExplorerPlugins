#include "plugin/PluginHost.h"

#include "plugin/PluginAccountSource.h"
#include "plugin/RpcChannel.h"
#include "ui/MainWindow.h"

#include <QCoreApplication>
#include <QJsonArray>
#include <QTimer>

namespace
{

constexpr int kApiVersion = 1;
constexpr int kMethodNotFound = -32601;
constexpr int kInvalidParams = -32602;
constexpr int kCommandFailed = -32000;

} // namespace

PluginHost::PluginHost(RpcChannel& rpc, QObject* parent) : QObject(parent), mRpc(rpc)
{
    connect(&mRpc, &RpcChannel::requestReceived, this, &PluginHost::onRequest);
    // App gone, or done with this run: nothing more can be answered.
    connect(&mRpc, &RpcChannel::closed, qApp, &QCoreApplication::quit);
}

PluginHost::~PluginHost()
{
    // The window holds a reference to mSource, which goes with this object.
    delete mWindow;
}

void PluginHost::onRequest(const QJsonValue& id, const QString& method, const QJsonObject& params)
{
    if (method == QLatin1String("initialize"))
    {
        mRpc.respond(id, QJsonObject{{QLatin1String("apiVersion"), kApiVersion}});
    }
    else if (method == QLatin1String("command.execute"))
    {
        execute(id, params);
    }
    else if (method == QLatin1String("shutdown"))
    {
        mRpc.respond(id, QJsonObject{});
        // Queued, so the reply above is out before the event loop ends.
        QTimer::singleShot(0, qApp, &QCoreApplication::quit);
    }
    else
    {
        mRpc.respondError(id, kMethodNotFound, QStringLiteral("Unknown method: %1").arg(method));
    }
}

void PluginHost::execute(const QJsonValue& id, const QJsonObject& params)
{
    if (!mExecuteId.isUndefined())
    {
        mRpc.respondError(id, kInvalidParams, QStringLiteral("A command is already running."));
        return;
    }

    QStringList folders;
    const QJsonArray items =
        params.value(QLatin1String("context")).toObject().value(QLatin1String("items")).toArray();
    for (const QJsonValue& item : items)
    {
        if (item[QLatin1String("type")].toString() == QLatin1String("folder"))
        {
            folders.append(item[QLatin1String("handle")].toString());
        }
    }
    if (folders.isEmpty())
    {
        mRpc.respondError(id, kCommandFailed, tr("Select a folder."));
        return;
    }

    mExecuteId = id;
    mSource = new PluginAccountSource(mRpc, folders, this);
    mWindow = new MainWindow(*mSource);
    mWindow->setAttribute(Qt::WA_DeleteOnClose);
    connect(mWindow, &MainWindow::closed, this, &PluginHost::finishExecute);
    connect(mWindow, &MainWindow::revealRequested, this, &PluginHost::reveal);
    mWindow->show();
    mWindow->raise();
    mWindow->activateWindow();
    mWindow->start();
}

void PluginHost::finishExecute()
{
    // Closing the window is the end of the command; the app answers with shutdown.
    mRpc.respond(mExecuteId, QJsonObject{});
}

void PluginHost::reveal(const QString& handle)
{
    mRpc.request(QStringLiteral("ui.reveal"),
                 QJsonObject{{QLatin1String("handle"), handle}},
                 [this](const QJsonValue&, const RpcChannel::Error* error) {
                     if (error && mWindow)
                     {
                         mWindow->showMessage(
                             tr("Couldn't show it in MEGA Explorer: %1").arg(error->message));
                     }
                 });
}
