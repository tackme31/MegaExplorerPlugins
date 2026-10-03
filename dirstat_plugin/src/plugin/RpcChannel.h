#pragma once

#include <QHash>
#include <QJsonObject>
#include <QJsonValue>
#include <QObject>
#include <QString>

#include <functional>
#include <thread>

// MEGA Explorer's plugin protocol transport: JSON-RPC 2.0, one message per
// line, over this process's stdin and stdout. Everything but the stdin reader
// runs on the GUI thread.
class RpcChannel : public QObject
{
    Q_OBJECT

public:
    struct Error
    {
        int code = 0;
        QString message;
    };
    // error is null on success.
    using ResponseHandler = std::function<void(const QJsonValue& result, const Error* error)>;

    explicit RpcChannel(QObject* parent = nullptr);
    ~RpcChannel() override;

    // False when stdin/stdout are not pipes, i.e. not started by MEGA Explorer.
    static bool isConnected();

    void start();

    void request(const QString& method, const QJsonObject& params, ResponseHandler handler);
    void respond(const QJsonValue& id, const QJsonValue& result);
    void respondError(const QJsonValue& id, int code, const QString& message);

signals:
    void requestReceived(const QJsonValue& id, const QString& method, const QJsonObject& params);
    void notificationReceived(const QString& method, const QJsonObject& params);
    // stdin reached EOF: MEGA Explorer is done with this process.
    void closed();

    // Internal: hands a line from the reader thread to the GUI thread.
    void lineRead(const QByteArray& line);

private:
    void readLoop();
    void handleLine(const QByteArray& line);
    void write(const QJsonObject& message);

    std::thread mReader;
    QHash<QString, ResponseHandler> mPending;
    int mNextId = 1;
};
