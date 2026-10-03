#pragma once

#include <QJsonObject>
#include <QJsonValue>
#include <QObject>
#include <QPointer>

class MainWindow;
class PluginAccountSource;
class RpcChannel;

// One run of the plugin, as MEGA Explorer drives it: initialize, then one
// command.execute that stays unanswered for as long as the window is open,
// then shutdown. Quits the application when the run is over.
class PluginHost : public QObject
{
    Q_OBJECT

public:
    explicit PluginHost(RpcChannel& rpc, QObject* parent = nullptr);
    ~PluginHost() override;

private:
    void onRequest(const QJsonValue& id, const QString& method, const QJsonObject& params);
    void execute(const QJsonValue& id, const QJsonObject& params);
    void finishExecute();
    void reveal(const QString& handle);

    RpcChannel& mRpc;
    QJsonValue mExecuteId = QJsonValue::Undefined;
    PluginAccountSource* mSource = nullptr;
    QPointer<MainWindow> mWindow;
};
