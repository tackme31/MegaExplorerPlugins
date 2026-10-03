#include "plugin/RpcChannel.h"

#include <QJsonDocument>
#include <QLoggingCategory>

#include <windows.h>

namespace
{

Q_LOGGING_CATEGORY(lcRpc, "dirstat.rpc")

bool isPipe(DWORD stdHandle)
{
    const HANDLE handle = GetStdHandle(stdHandle);
    return handle && handle != INVALID_HANDLE_VALUE && GetFileType(handle) == FILE_TYPE_PIPE;
}

} // namespace

RpcChannel::RpcChannel(QObject* parent) : QObject(parent)
{
    // Queued: emitted on the reader thread, handled on this object's (GUI) thread.
    connect(this, &RpcChannel::lineRead, this, &RpcChannel::handleLine, Qt::QueuedConnection);
}

RpcChannel::~RpcChannel()
{
    if (mReader.joinable())
    {
        // The reader sits in a blocking ReadFile until the app closes stdin.
        CancelSynchronousIo(static_cast<HANDLE>(mReader.native_handle()));
        mReader.join();
    }
}

bool RpcChannel::isConnected()
{
    return isPipe(STD_INPUT_HANDLE) && isPipe(STD_OUTPUT_HANDLE);
}

void RpcChannel::start()
{
    mReader = std::thread([this] { readLoop(); });
}

void RpcChannel::readLoop()
{
    const HANDLE in = GetStdHandle(STD_INPUT_HANDLE);
    QByteArray buffer;
    char chunk[64 * 1024];
    for (;;)
    {
        DWORD read = 0;
        if (!ReadFile(in, chunk, sizeof chunk, &read, nullptr) || read == 0)
        {
            break;
        }
        buffer.append(chunk, read);
        qsizetype newline = 0;
        while ((newline = buffer.indexOf('\n')) >= 0)
        {
            QByteArray line = buffer.left(newline).trimmed();
            buffer.remove(0, newline + 1);
            if (!line.isEmpty())
            {
                emit lineRead(line);
            }
        }
    }
    QMetaObject::invokeMethod(this, &RpcChannel::closed, Qt::QueuedConnection);
}

void RpcChannel::handleLine(const QByteArray& line)
{
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(line, &parseError);
    if (!document.isObject())
    {
        qCWarning(lcRpc) << "not a JSON object:" << parseError.errorString();
        return;
    }
    const QJsonObject message = document.object();
    const QJsonValue id = message.value(QLatin1String("id"));
    const QString method = message.value(QLatin1String("method")).toString();

    if (!method.isEmpty())
    {
        const QJsonObject params = message.value(QLatin1String("params")).toObject();
        if (id.isUndefined())
        {
            emit notificationReceived(method, params);
        }
        else
        {
            emit requestReceived(id, method, params);
        }
        return;
    }

    const ResponseHandler handler = mPending.take(id.toString());
    if (!handler)
    {
        qCWarning(lcRpc) << "response to an unknown request:" << id;
        return;
    }
    if (message.contains(QLatin1String("error")))
    {
        const QJsonObject error = message.value(QLatin1String("error")).toObject();
        const Error e{error.value(QLatin1String("code")).toInt(),
                      error.value(QLatin1String("message")).toString()};
        handler({}, &e);
    }
    else
    {
        handler(message.value(QLatin1String("result")), nullptr);
    }
}

void RpcChannel::request(const QString& method, const QJsonObject& params, ResponseHandler handler)
{
    const QString id = QStringLiteral("d%1").arg(mNextId++);
    mPending.insert(id, std::move(handler));
    write({{QLatin1String("jsonrpc"), QLatin1String("2.0")},
           {QLatin1String("id"), id},
           {QLatin1String("method"), method},
           {QLatin1String("params"), params}});
}

void RpcChannel::respond(const QJsonValue& id, const QJsonValue& result)
{
    write({{QLatin1String("jsonrpc"), QLatin1String("2.0")},
           {QLatin1String("id"), id},
           {QLatin1String("result"), result}});
}

void RpcChannel::respondError(const QJsonValue& id, int code, const QString& message)
{
    write({{QLatin1String("jsonrpc"), QLatin1String("2.0")},
           {QLatin1String("id"), id},
           {QLatin1String("error"),
            QJsonObject{{QLatin1String("code"), code}, {QLatin1String("message"), message}}}});
}

void RpcChannel::write(const QJsonObject& message)
{
    QByteArray line = QJsonDocument(message).toJson(QJsonDocument::Compact);
    line.append('\n');
    const HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
    const char* data = line.constData();
    qsizetype left = line.size();
    while (left > 0)
    {
        DWORD written = 0;
        if (!WriteFile(out, data, static_cast<DWORD>(left), &written, nullptr))
        {
            qCWarning(lcRpc) << "stdout write failed:" << GetLastError();
            return;
        }
        data += written;
        left -= written;
    }
}
